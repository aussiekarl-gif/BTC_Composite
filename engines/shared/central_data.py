#!/usr/bin/env python3
"""Read-only client for the shared BTC research-data repository.

This module establishes the central-data access layer without changing any
Production or Research calculation path yet. The full research master is NOT a
Production-authoritative input. Production must migrate only after a separate
validated export passes parity and stability checks.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import requests

DEFAULT_REPO = "aussiekarl-gif/btc-audit-data"
DEFAULT_MASTER_PATH = "btc_audit_backup.csv"
DEFAULT_REF = "main"
GITHUB_API = "https://api.github.com"
RAW_GITHUB = "https://raw.githubusercontent.com"


class CentralDataError(RuntimeError):
    """Raised when the shared BTC data repository cannot be read safely."""


@dataclass(frozen=True)
class CentralDataConfig:
    repository: str = DEFAULT_REPO
    token: str = ""
    ref: str = DEFAULT_REF
    master_path: str = DEFAULT_MASTER_PATH
    timeout_seconds: int = 45

    @classmethod
    def from_environment(cls) -> "CentralDataConfig":
        return cls(
            repository=(
                os.getenv("AUDIT_GITHUB_REPO")
                or os.getenv("BTC_CENTRAL_DATA_REPO")
                or DEFAULT_REPO
            ).strip(),
            token=(
                os.getenv("AUDIT_GITHUB_TOKEN")
                or os.getenv("BTC_CENTRAL_DATA_TOKEN")
                or ""
            ).strip(),
            ref=(os.getenv("BTC_CENTRAL_DATA_REF") or DEFAULT_REF).strip(),
            master_path=(
                os.getenv("BTC_CENTRAL_DATA_MASTER") or DEFAULT_MASTER_PATH
            ).strip(),
        )


def _headers(token: str) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "BTC-Composite-Central-Data/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _raw_headers(token: str) -> dict[str, str]:
    headers = {"User-Agent": "BTC-Composite-Central-Data/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_repository_file(
    path: str,
    *,
    config: CentralDataConfig | None = None,
) -> bytes:
    """Fetch one file from the central repository.

    GitHub's Contents API can omit inline file content for large files. We use it
    only to verify that the path/ref resolves, then download through the raw URL.
    This mirrors the large-file behaviour already learned from the audit backup.
    """
    cfg = config or CentralDataConfig.from_environment()
    if not cfg.repository or "/" not in cfg.repository:
        raise CentralDataError("Central data repository must be in owner/name form.")

    api_url = f"{GITHUB_API}/repos/{cfg.repository}/contents/{path}"
    try:
        meta = requests.get(
            api_url,
            params={"ref": cfg.ref},
            headers=_headers(cfg.token),
            timeout=cfg.timeout_seconds,
        )
        meta.raise_for_status()
    except requests.RequestException as exc:
        raise CentralDataError(
            f"Could not resolve central data file {cfg.repository}:{path}@{cfg.ref}: {exc}"
        ) from exc

    raw_url = f"{RAW_GITHUB}/{cfg.repository}/{cfg.ref}/{path}"
    try:
        response = requests.get(
            raw_url,
            headers=_raw_headers(cfg.token),
            timeout=cfg.timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CentralDataError(
            f"Could not download central data file {cfg.repository}:{path}@{cfg.ref}: {exc}"
        ) from exc

    if not response.content:
        raise CentralDataError(f"Central data file is empty: {path}")
    return response.content


def load_master(
    *,
    config: CentralDataConfig | None = None,
    columns: Iterable[str] | None = None,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Load the authoritative research master as a normalized date-indexed frame.

    This is intentionally a read-only research-data helper. It does not write to
    GitHub and it does not imply that the master is approved for Production use.
    """
    cfg = config or CentralDataConfig.from_environment()
    raw = fetch_repository_file(cfg.master_path, config=cfg)

    requested = list(columns) if columns is not None else None
    usecols = None
    if requested is not None:
        usecols = list(dict.fromkeys(["date", *requested]))

    try:
        frame = pd.read_csv(io.BytesIO(raw), usecols=usecols)
    except Exception as exc:
        raise CentralDataError(f"Could not parse central master CSV: {exc}") from exc

    if "date" not in frame.columns:
        raise CentralDataError("Central master is missing required 'date' column.")

    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["date"])
    frame = frame.drop_duplicates(subset=["date"], keep="last")
    frame = frame.sort_values("date").set_index("date")

    if start is not None:
        start_ts = pd.Timestamp(start)
        if start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize("UTC")
        else:
            start_ts = start_ts.tz_convert("UTC")
        frame = frame.loc[frame.index >= start_ts]

    if end is not None:
        end_ts = pd.Timestamp(end)
        if end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize("UTC")
        else:
            end_ts = end_ts.tz_convert("UTC")
        frame = frame.loc[frame.index <= end_ts]

    return frame


def master_summary(
    *,
    config: CentralDataConfig | None = None,
) -> dict[str, object]:
    """Return a small health/coverage summary for the shared master."""
    frame = load_master(config=config)
    return {
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "start": frame.index.min() if len(frame) else None,
        "end": frame.index.max() if len(frame) else None,
        "repository": (config or CentralDataConfig.from_environment()).repository,
        "master_path": (config or CentralDataConfig.from_environment()).master_path,
    }
