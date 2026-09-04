import json
from datetime import datetime, timezone

import requests
import streamlit as st

st.set_page_config(page_title="Kote MVRV Diagnostic", page_icon="₿", layout="centered")

st.title("Kote MVRV Diagnostic")
st.caption("Standalone test only — no BTC, FX, BGeometrics, Alternative.me, or backtest data is loaded.")

api_key = st.text_input("Kote API key", type="password", placeholder="kote_…")

st.info("This diagnostic never displays or writes your API key. It makes one small request with a 12-second timeout.")


def summarize_json(payload):
    out = {
        "top_level_type": type(payload).__name__,
        "top_level_keys": list(payload.keys()) if isinstance(payload, dict) else None,
        "list_length": len(payload) if isinstance(payload, list) else None,
    }

    rows = None
    container_key = None
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        # Probe common response container names without assuming one exact schema.
        for k in ("data", "results", "items", "rows", "values", "chart", "series"):
            v = payload.get(k)
            if isinstance(v, list):
                rows = v
                container_key = k
                break
            if isinstance(v, dict):
                # Sometimes data contains another list.
                for kk in ("data", "results", "items", "rows", "values"):
                    vv = v.get(kk)
                    if isinstance(vv, list):
                        rows = vv
                        container_key = f"{k}.{kk}"
                        break
                if rows is not None:
                    break

    out["row_container"] = container_key
    out["detected_row_count"] = len(rows) if isinstance(rows, list) else 0
    if rows:
        first = rows[0]
        out["first_row_type"] = type(first).__name__
        out["first_row_fields"] = list(first.keys()) if isinstance(first, dict) else None
        # Sanitized sample: values only from API response, truncated, no headers/key.
        if isinstance(first, dict):
            sample = {}
            for k, v in first.items():
                s = str(v)
                sample[str(k)] = s[:160] + ("…" if len(s) > 160 else "")
            out["first_row_sample"] = sample
        else:
            out["first_row_sample"] = str(first)[:500]
    return out


if st.button("Test Kote MVRV connection", type="primary", use_container_width=True):
    if not api_key.strip():
        st.error("Paste your Kote API key first.")
    else:
        url = "https://kotecharts.com/api/v1/public/charts/mvrv-z-score"
        params = {
            "limit": 5,
            "offset": 0,
        }
        headers = {
            "X-API-Key": api_key.strip(),
            "Accept": "application/json",
            "User-Agent": "BTC-DCA-Audit-Kote-Diagnostic/1.0",
        }

        with st.spinner("Testing Kote only…"):
            try:
                r = requests.get(url, headers=headers, params=params, timeout=12)
            except requests.Timeout:
                st.error("Kote request timed out after 12 seconds.")
                st.code("Result: TIMEOUT\nEndpoint: /api/v1/public/charts/mvrv-z-score")
            except requests.RequestException as exc:
                st.error("Kote connection failed before an HTTP response was received.")
                st.code(f"Result: CONNECTION ERROR\nType: {type(exc).__name__}\nMessage: {str(exc)[:500]}")
            else:
                st.subheader("Diagnostic result")
                st.write(f"**HTTP status:** {r.status_code}")
                st.write(f"**Content-Type:** {r.headers.get('content-type', '(not supplied)')}")
                st.write(f"**Response bytes:** {len(r.content)}")
                st.write(f"**Final URL path:** {r.url.split('?',1)[0]}")

                try:
                    payload = r.json()
                except ValueError:
                    st.warning("The response was not valid JSON.")
                    body = r.text[:1500]
                    # Defensive redaction in the unlikely case an upstream echoes the key.
                    body = body.replace(api_key.strip(), "[REDACTED]")
                    st.code(body or "(empty response body)")
                else:
                    summary = summarize_json(payload)
                    st.json(summary)

                    if 200 <= r.status_code < 300:
                        if summary.get("detected_row_count", 0) > 0:
                            st.success("Kote responded successfully and returned detectable MVRV rows.")
                        else:
                            st.warning("Kote responded successfully, but this diagnostic did not detect a row list. Send me the JSON summary above.")
                    elif r.status_code in (401, 403):
                        st.error("Kote rejected the request as unauthorized/forbidden. This points to key permissions or plan access rather than the parser.")
                    elif r.status_code == 404:
                        st.error("Kote returned 404 for this route. The endpoint path is not accepted by the server handling your request.")
                    elif r.status_code == 429:
                        st.error("Kote rate-limited the request (HTTP 429).")
                    else:
                        st.error(f"Kote returned HTTP {r.status_code}.")

st.divider()
st.caption("Send me a screenshot of the Diagnostic result. Do not send the API key again.")
