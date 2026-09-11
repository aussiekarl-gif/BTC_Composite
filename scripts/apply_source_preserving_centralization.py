from pathlib import Path

p = Path('engines/audit/public_model_audit.py')
t = p.read_text()

anchor = 'def puell_threshold_research(merged, total_capital=500000.0):\n'
insert = r'''
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_blockchain_source_history(start_date, end_date):
    """Capture the exact Blockchain.com BTC/USD source used by Production."""
    start_ts = pd.Timestamp(start_date, tz="UTC") if pd.Timestamp(start_date).tzinfo is None else pd.Timestamp(start_date).tz_convert("UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC") if pd.Timestamp(end_date).tzinfo is None else pd.Timestamp(end_date).tz_convert("UTC")
    r = requests.get(
        "https://api.blockchain.info/charts/market-price",
        params={"timespan": "all", "format": "json", "sampled": "false"},
        headers={"User-Agent": "BTC-DCA-Simulator/3.4"},
        timeout=30,
    )
    r.raise_for_status()
    rows = []
    for point in r.json().get("values", []):
        try:
            ts = pd.to_datetime(float(point["x"]), unit="s", utc=True).normalize()
            value = float(point["y"])
            if value > 0 and start_ts.normalize() <= ts <= end_ts.normalize():
                rows.append((ts, value))
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows, columns=["date", "src__blockchain_btc_usd"]).drop_duplicates("date", keep="last").set_index("date").sort_index()
    return out


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_frankfurter_source_history(start_date, end_date):
    """Capture the exact Frankfurter USD/AUD source used by Production."""
    url = f"https://api.frankfurter.app/{pd.Timestamp(start_date).strftime('%Y-%m-%d')}..{pd.Timestamp(end_date).strftime('%Y-%m-%d')}?from=USD&to=AUD"
    r = requests.get(url, headers={"User-Agent": "BTC-DCA-Simulator/3.4"}, timeout=30)
    r.raise_for_status()
    rows = []
    for day, vals in r.json().get("rates", {}).items():
        aud_per_usd = float(vals.get("AUD", 0) or 0)
        if aud_per_usd > 0:
            rows.append((pd.to_datetime(day, utc=True), 1.0 / aud_per_usd))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=["date", "src__frankfurter_usd_per_aud"]).drop_duplicates("date", keep="last").set_index("date").sort_index()


def fetch_bgeometrics_production_sources(start_date, end_date, token):
    """Capture the same BGeometrics endpoints/fields used by Production for parity."""
    out = pd.DataFrame()
    statuses = []
    specs = [
        ("btc-price", {"src__bgeometrics_btc_price": ["price", "btcPrice", "btc_price", "value", "close"]}),
        ("mvrv-zscore", {"src__bgeometrics_mvrv_z": ["mvrvZScore", "mvrv_zscore", "zscore", "mvrvZ"]}),
        ("fear-greed", {"src__bgeometrics_fear_greed": ["fearGreed", "fearAndGreed", "fear_greed", "value", "score"]}),
        ("regime-score", {
            "src__bgeometrics_regime_score": ["regimeScore"],
            "src__bgeometrics_regime_delta_30d": ["regimeDelta30d"],
            "src__bgeometrics_regime_active_weight": ["activeWeight"],
            "src__bgeometrics_regime": ["regime"],
        }),
    ]
    for endpoint, mapping in specs:
        frame, rate = fetch_endpoint(endpoint, start_date, end_date, token)
        if frame is None or frame.empty:
            statuses.append({"Source": endpoint, "Status": "No usable rows returned"})
            continue
        piece = pd.DataFrame(index=frame.index)
        for dest, aliases in mapping.items():
            col = _pick(frame, aliases)
            if col is None:
                continue
            if dest.endswith("__regime"):
                piece[dest] = frame[col].astype(str)
            else:
                piece[dest] = pd.to_numeric(frame[col], errors="coerce")
        if not piece.empty:
            out = combine_caches(out, piece)
            statuses.append({"Source": endpoint, "Status": f"Captured {len(piece):,} source rows"})
        else:
            statuses.append({"Source": endpoint, "Status": "Endpoint returned rows but expected fields were not found"})
    return out, statuses


'''
if insert.strip() not in t:
    if anchor not in t:
        raise SystemExit('function insertion anchor missing')
    t = t.replace(anchor, insert + anchor, 1)

old = '''    if free_frame is not None and not free_frame.empty:\n        cache = combine_caches(cache, free_frame)\n        save_runtime_master_cache(cache)\n        save_runtime_cache(cache)\n        memory = save_audit_memory(memory, cache, base)\n        st.success(f"Free indicator cache updated: {len(free_frame):,} daily rows. No BGeometrics quota used. Audit memory saved automatically.")\n    else:\n        st.warning("No Coin Metrics Community rows were available. Price-only indicators still work and BGeometrics was not contacted.")\n'''
new = '''    source_status = []\n    try:\n        blockchain_source = fetch_blockchain_source_history(free_start, free_end)\n        if not blockchain_source.empty:\n            free_frame = combine_caches(free_frame, blockchain_source)\n            source_status.append({"Production source": "Blockchain.com BTC/USD", "Status": f"Captured {len(blockchain_source):,} rows"})\n    except Exception as exc:\n        source_status.append({"Production source": "Blockchain.com BTC/USD", "Status": f"Unavailable: {str(exc)[:120]}"})\n    try:\n        fx_source = fetch_frankfurter_source_history(free_start, free_end)\n        if not fx_source.empty:\n            free_frame = combine_caches(free_frame, fx_source)\n            source_status.append({"Production source": "Frankfurter USD/AUD", "Status": f"Captured {len(fx_source):,} rows"})\n    except Exception as exc:\n        source_status.append({"Production source": "Frankfurter USD/AUD", "Status": f"Unavailable: {str(exc)[:120]}"})\n    if source_status:\n        st.dataframe(pd.DataFrame(source_status), use_container_width=True, hide_index=True)\n    if free_frame is not None and not free_frame.empty:\n        cache = combine_caches(cache, free_frame)\n        save_runtime_master_cache(cache)\n        save_runtime_cache(cache)\n        memory = save_audit_memory(memory, cache, base)\n        st.success(f"Free/source-preserving cache updated: {len(free_frame):,} daily rows. No BGeometrics quota used. Audit memory saved automatically.")\n    else:\n        st.warning("No free/source-preserving rows were available. Price-only indicators still work and BGeometrics was not contacted.")\n'''
if old not in t:
    raise SystemExit('free-step block anchor missing')
t = t.replace(old, new, 1)

anchor2 = '# -----------------------------------------------------------------------------\n# STEP 4 — Acquire only specialist history still missing\n# -----------------------------------------------------------------------------\n'
insert2 = '''st.subheader("④A Preserve exact Production-source inputs")\nst.caption(\n    "Source-preserving archive for parity only. Blockchain.com and Frankfurter are captured in the free step above. "\n    "This button captures the exact BGeometrics endpoints used by Production (btc-price, MVRV-Z, Fear & Greed, Regime Score) into dedicated src__ columns. "\n    "It does not change Production and uses up to four BGeometrics requests."\n)\nsource_token = get_token()\nif st.button(\n    "CAPTURE BGEOMETRICS PRODUCTION SOURCES (USES UP TO 4 REQUESTS)",\n    disabled=not bool(source_token),\n    key="capture_production_sources",\n):\n    try:\n        with st.spinner("Capturing exact Production-source BGeometrics history..."):\n            source_frame, source_rows = fetch_bgeometrics_production_sources(MASTER_START_DATE, dt.date.today(), source_token)\n        if source_rows:\n            st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)\n        if source_frame is not None and not source_frame.empty:\n            cache = combine_caches(cache, source_frame)\n            save_runtime_master_cache(cache)\n            save_runtime_cache(cache)\n            memory = save_audit_memory(memory, cache, base)\n            st.success("Exact Production-source BGeometrics history saved to the durable central master in src__ columns.")\n        else:\n            st.warning("No source-preserving BGeometrics rows were returned.")\n    except RateLimitError as exc:\n        st.warning("BGeometrics quota reached before source capture completed. " + rate_text(exc.rate))\n    except Exception as exc:\n        st.error(f"Production-source capture failed: {exc}")\n\n'''
if insert2.strip() not in t:
    if anchor2 not in t:
        raise SystemExit('step4 anchor missing')
    t = t.replace(anchor2, insert2 + anchor2, 1)

p.write_text(t)
print('patched audit source-preserving capture')
