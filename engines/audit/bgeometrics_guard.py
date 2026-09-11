"""Process-aware BGeometrics quota guard for the Public Model Audit only.

After the first HTTP 429 (or an explicit zero-remaining quota header), skip further
BGeometrics requests until the advertised reset/retry time. If the provider omits a
reset hint, hold requests for one hour as a conservative local guard.

The lockout is mirrored in both Streamlit session_state and this module's process-level
state. That means switching Streamlit sessions/tabs within the same running app process
will not immediately spend another blocked request. A full Streamlit process restart can
still clear the local guard; the next genuine 429 will re-arm it.

Only bitcoin-data.com GET requests are intercepted. All other providers and GitHub
requests pass through unchanged. Production/Research/Parity are not guarded by this module.
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
_PROCESS_UNTIL: dt.datetime | None = None
_PROCESS_REASON: str = ""


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


def _parse_iso(raw):
    if not raw:
        return None
    try:
        x = dt.datetime.fromisoformat(str(raw))
        if x.tzinfo is None:
            x = x.replace(tzinfo=dt.timezone.utc)
        return x.astimezone(dt.timezone.utc)
    except Exception:
        return None


def _set_guard(st, until: dt.datetime, reason: str) -> None:
    global _PROCESS_UNTIL, _PROCESS_REASON
    until = until.astimezone(dt.timezone.utc)
    _PROCESS_UNTIL = until
    _PROCESS_REASON = reason
    st.session_state[_UNTIL_KEY] = until.isoformat()
    st.session_state[_REASON_KEY] = reason


def _clear_guard(st) -> None:
    global _PROCESS_UNTIL, _PROCESS_REASON
    _PROCESS_UNTIL = None
    _PROCESS_REASON = ""
    st.session_state.pop(_UNTIL_KEY, None)
    st.session_state.pop(_REASON_KEY, None)


def _load_until(st):
    """Return the furthest active lockout known to this session or app process."""
    global _PROCESS_UNTIL, _PROCESS_REASON
    now = _now_utc()

    session_until = _parse_iso(st.session_state.get(_UNTIL_KEY))
    process_until = _PROCESS_UNTIL

    candidates = [x for x in (session_until, process_until) if x and x > now]
    if not candidates:
        if session_until or process_until:
            _clear_guard(st)
        return None

    until = max(candidates)
    reason = st.session_state.get(_REASON_KEY) or _PROCESS_REASON or "BGeometrics quota guard active"

    # Synchronise whichever store was missing/staler so new Streamlit sessions inherit
    # the process-level lockout without making a provider call first.
    if session_until != until or st.session_state.get(_REASON_KEY) != reason:
        st.session_state[_UNTIL_KEY] = until.isoformat()
        st.session_state[_REASON_KEY] = reason
    if process_until != until or _PROCESS_REASON != reason:
        _PROCESS_UNTIL = until
        _PROCESS_REASON = reason
    return until


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
        # Ensure a fresh Streamlit session inherits any process-level lockout.
        _load_until(st)
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
            _clear_guard(st)

        response = _ORIGINAL_GET(url, *args, **kwargs)
        if response.status_code == 429:
            _set_guard(st, _parse_until(response.headers), "BGeometrics returned HTTP 429")
        else:
            remaining = response.headers.get("X-RateLimit-Remaining") or response.headers.get("RateLimit-Remaining")
            try:
                if remaining is not None and int(float(remaining)) <= 0:
                    _set_guard(st, _parse_until(response.headers), "BGeometrics reported zero requests remaining")
            except Exception:
                pass
        return response

    setattr(guarded_get, _GUARD_FLAG, True)
    requests.get = guarded_get
    _load_until(st)


def uninstall_bgeometrics_guard() -> None:
    """Restore normal requests.get when another app section is selected.

    Process-level quota state is intentionally retained so returning to Public Model Audit
    in the same app process cannot spend another blocked request.
    """
    if getattr(requests.get, _GUARD_FLAG, False):
        requests.get = _ORIGINAL_GET


def guard_status(st):
    """Return (active, text) for UI display."""
    until = _load_until(st)
    if not until:
        return False, ""
    now = _now_utc()
    if now >= until:
        _clear_guard(st)
        return False, ""
    seconds = max(0, int((until - now).total_seconds()))
    local = until.astimezone(dt.timezone(dt.timedelta(hours=10)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    reason = st.session_state.get(_REASON_KEY) or _PROCESS_REASON or "BGeometrics quota guard active"
    text = (
        f"{reason}. Further BGeometrics requests are being skipped locally until "
        f"{local.strftime('%-I:%M:%S %p')} Brisbane time "
        f"({h}h {m}m {s}s remaining)."
    )
    return True, text
