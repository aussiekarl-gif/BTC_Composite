"""Session-level BGeometrics quota guard for the Public Model Audit only.

Purpose: after the first HTTP 429, do not spend another BGeometrics request on later
Streamlit reruns/clicks until the advertised reset/retry time. If the provider omits a
reset hint, hold requests for one hour as a conservative local guard.

The wrapper intercepts only bitcoin-data.com GET requests. All other providers and
GitHub requests pass through unchanged. Production is not guarded by this module.
"""
from __future__ import annotations

import datetime as dt
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests

_ORIGINAL_GET = requests.get
_GUARD_FLAG = "_btc_bgeometrics_guard_wrapper"
_UNTIL_KEY = "bgeometrics_guard_until_utc"
_REASON_KEY = "bgeometrics_guard_reason"


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _is_bgeometrics(url) -> bool:
    try:
        host = (urlparse(str(url)).hostname or "").lower()
    except Exception:
        return False
    return host == "bitcoin-data.com" or host.endswith(".bitcoin-data.com")


def _parse_until(headers) -> dt.datetime:
    now = _now_utc()
    retry = headers.get("Retry-After") if headers else None
    if retry:
        try:
            return now + dt.timedelta(seconds=max(0, int(float(retry))))
        except Exception:
            try:
                parsed = parsedate_to_datetime(str(retry))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                return parsed.astimezone(dt.timezone.utc)
            except Exception:
                pass
    reset = None
    if headers:
        reset = headers.get("X-RateLimit-Reset") or headers.get("RateLimit-Reset")
    if reset:
        try:
            value = float(reset)
            if value > 10_000_000:
                return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
            return now + dt.timedelta(seconds=max(0, value))
        except Exception:
            pass
    return now + dt.timedelta(hours=1)


def _load_until(st):
    raw = st.session_state.get(_UNTIL_KEY)
    if not raw:
        return None
    try:
        x = dt.datetime.fromisoformat(str(raw))
        if x.tzinfo is None:
            x = x.replace(tzinfo=dt.timezone.utc)
        return x.astimezone(dt.timezone.utc)
    except Exception:
        st.session_state.pop(_UNTIL_KEY, None)
        st.session_state.pop(_REASON_KEY, None)
        return None


def _synthetic_429(url: str, seconds_left: int) -> requests.Response:
    r = requests.Response()
    r.status_code = 429
    r.url = str(url)
    r.headers["Retry-After"] = str(max(1, int(seconds_left)))
    r._content = b""
    r.reason = "Too Many Requests (local quota guard)"
    return r


def install_bgeometrics_guard(st) -> None:
    """Install once for the Public Model Audit section."""
    current = requests.get
    if getattr(current, _GUARD_FLAG, False):
        return

    def guarded_get(url, *args, **kwargs):
        if not _is_bgeometrics(url):
            return _ORIGINAL_GET(url, *args, **kwargs)

        until = _load_until(st)
        now = _now_utc()
        if until and now < until:
            seconds_left = max(1, int((until - now).total_seconds()))
            return _synthetic_429(str(url), seconds_left)
        if until and now >= until:
            st.session_state.pop(_UNTIL_KEY, None)
            st.session_state.pop(_REASON_KEY, None)

        response = _ORIGINAL_GET(url, *args, **kwargs)
        if response.status_code == 429:
            until = _parse_until(response.headers)
            st.session_state[_UNTIL_KEY] = until.isoformat()
            st.session_state[_REASON_KEY] = "BGeometrics returned HTTP 429"
        else:
            remaining = response.headers.get("X-RateLimit-Remaining") or response.headers.get("RateLimit-Remaining")
            try:
                if remaining is not None and int(float(remaining)) <= 0:
                    until = _parse_until(response.headers)
                    st.session_state[_UNTIL_KEY] = until.isoformat()
                    st.session_state[_REASON_KEY] = "BGeometrics reported zero requests remaining"
            except Exception:
                pass
        return response

    setattr(guarded_get, _GUARD_FLAG, True)
    requests.get = guarded_get


def uninstall_bgeometrics_guard() -> None:
    """Restore normal requests.get when another app section is selected."""
    if getattr(requests.get, _GUARD_FLAG, False):
        requests.get = _ORIGINAL_GET


def guard_status(st):
    """Return (active, text) for UI display."""
    until = _load_until(st)
    if not until:
        return False, ""
    now = _now_utc()
    if now >= until:
        st.session_state.pop(_UNTIL_KEY, None)
        st.session_state.pop(_REASON_KEY, None)
        return False, ""
    seconds = max(0, int((until - now).total_seconds()))
    local = until.astimezone(dt.timezone(dt.timedelta(hours=10)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    reason = st.session_state.get(_REASON_KEY, "BGeometrics quota guard active")
    text = (
        f"{reason}. Further BGeometrics requests are being skipped locally until "
        f"{local.strftime('%-I:%M:%S %p')} Brisbane time "
        f"({h}h {m}m {s}s remaining)."
    )
    return True, text
