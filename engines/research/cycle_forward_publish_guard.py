"""Fail-closed publication of already-captured paper-only Cycle forward records.

Called ONLY after the existing research workflow has committed new prospective
rows and uploaded its original evidence artifact. Does not fetch market data,
create a signal, backfill a missed observation or alter live trading.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable

ALLOWED_PATHS = frozenset({
    "data/research_forward_validation/cycle_market_signals.csv",
    "data/research_forward_validation/cycle_signal_outcomes.csv",
    "data/research_forward_validation/asx_ibit_closes_forward.csv",
})


class PublicationBlocked(RuntimeError):
    """No safe publication was possible; preserve the existing run artifact."""


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if check and result.returncode:
        raise PublicationBlocked(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def publish(*, repo: Path = Path("."), verify: Callable[[], None] | None = None,
            max_attempts: int = 3, retry_delay: float = 2.0) -> str:
    """Rebase only disjoint paper-data commits, reverify and push without force.

    On a same-tape conflict, rebase is aborted and the captured artifact is
    retained outside git. A failed validation blocks all pushes. A second
    remote advance can trigger a bounded retry, never an unbounded loop.
    """
    repo = Path(repo).resolve()
    if max_attempts < 1 or max_attempts > 5:
        raise ValueError("Bounded attempts must be 1..5")
    if _git(repo, "diff", "--quiet", check=False).returncode:
        raise PublicationBlocked("Uncommitted tracked changes; refusing publication")
    if verify is None:
        def verify() -> None:
            subprocess.run([sys.executable, "-m", "engines.research.forward_market_readiness"],
                           cwd=repo, check=True)
    for attempt in range(max_attempts):
        _git(repo, "fetch", "--no-tags", "origin", "main")
        if _git(repo, "merge-base", "--is-ancestor", "HEAD", "origin/main",
                check=False).returncode == 0:
            return "ALREADY_PUBLISHED"
        rebased = _git(repo, "rebase", "origin/main", check=False)
        if rebased.returncode:
            _git(repo, "rebase", "--abort", check=False)
            raise PublicationBlocked("Concurrent source conflict; no forced rewrite or backfill")
        changed = set(_git(repo, "diff", "--name-only", "origin/main...HEAD").stdout.splitlines())
        if not changed:
            return "ALREADY_PUBLISHED"
        if not changed <= ALLOWED_PATHS:
            raise PublicationBlocked(f"Unexpected publication paths: {sorted(changed - ALLOWED_PATHS)}")
        try:
            verify()  # existing hash-chain/date/provenance readiness after EVERY rebase
        except Exception as exc:
            raise PublicationBlocked("Post-rebase prospective tape validation failed") from exc
        pushed = _git(repo, "push", "origin", "HEAD:main", check=False)
        if pushed.returncode == 0:
            return "PUBLISHED_VERIFIED_PAPER_DATA"
        if attempt + 1 < max_attempts:
            time.sleep(retry_delay)
    raise PublicationBlocked("Remote kept advancing or push failed; artifact preserved, no force push")


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe paper-only Cycle forward publication")
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    print(publish(max_attempts=args.max_attempts))


if __name__ == "__main__":
    main()
