from pathlib import Path
import re

path = Path('engines/audit/public_model_audit.py')
text = path.read_text()
pattern = re.compile(r'def fetch_bgeometrics_production_sources\(start_date, end_date, token\):.*?(?=\n\ndef )', re.S)
match = pattern.search(text)
if not match:
    raise SystemExit('fetch_bgeometrics_production_sources() not found')
new = '''def fetch_bgeometrics_production_sources(start_date, end_date, token):
    """Capture Production BGeometrics sources without letting one forbidden endpoint abort all others.

    BGeometrics can return HTTP 403 for an individual endpoint that is not included in the
    current account tier. That is not proof that the token itself is invalid. Each endpoint
    is therefore attempted independently, using the same fetch_endpoint() authentication
    path as the existing audit collector. Rate limits still stop the run immediately.
    """
    out = pd.DataFrame()
    statuses = []
    specs = [
        # Migration-critical inputs first so an optional endpoint cannot block them.
        ("mvrv-zscore", {"src__bgeometrics_mvrv_z": ["mvrvZScore", "mvrv_zscore", "zscore", "mvrvZ"]}),
        ("fear-greed", {"src__bgeometrics_fear_greed": ["fearGreed", "fearAndGreed", "fear_greed", "value", "score"]}),
        ("regime-score", {
            "src__bgeometrics_regime_score": ["regimeScore"],
            "src__bgeometrics_regime_delta_30d": ["regimeDelta30d"],
            "src__bgeometrics_regime_active_weight": ["activeWeight"],
            "src__bgeometrics_regime": ["regime"],
        }),
        # Optional parity/archive field. Production does not use this as its main BTC price feed.
        ("btc-price", {"src__bgeometrics_btc_price": ["price", "btcPrice", "btc_price", "value", "close"]}),
    ]

    for endpoint, mapping in specs:
        try:
            frame, rate = fetch_endpoint(endpoint, start_date, end_date, token)
        except RateLimitError:
            raise
        except Exception as exc:
            statuses.append({"Endpoint": endpoint, "Status": f"Unavailable — {exc}"})
            continue

        if frame is None or frame.empty:
            statuses.append({"Endpoint": endpoint, "Status": "No rows returned"})
            continue

        captured = 0
        for dest, aliases in mapping.items():
            col = pick_column(frame, aliases)
            if col is None:
                continue
            series = frame[col].rename(dest)
            if dest != "src__bgeometrics_regime":
                series = pd.to_numeric(series, errors="coerce")
            out = out.join(series, how="outer") if not out.empty else series.to_frame()
            captured += int(series.notna().sum())

        statuses.append({
            "Endpoint": endpoint,
            "Status": f"Captured {captured:,} values" if captured else "Endpoint returned rows but expected fields were not found",
        })

    return (out.sort_index() if not out.empty else pd.DataFrame()), statuses
'''
text = text[:match.start()] + new.rstrip() + text[match.end():]
path.write_text(text)
print('Patched BGeometrics Production-source capture to isolate per-endpoint 403s')
