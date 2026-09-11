from pathlib import Path

p = Path('engines/audit/public_model_audit.py')
s = p.read_text()
old = '''source_token = get_token()
if st.button(
    "CAPTURE BGEOMETRICS PRODUCTION SOURCES (USES UP TO 4 REQUESTS)",
    disabled=not bool(source_token),
    key="capture_production_sources",
):
    try:
        with st.spinner("Capturing exact Production-source BGeometrics history..."):
            source_frame, source_rows = fetch_bgeometrics_production_sources(MASTER_START_DATE, dt.date.today(), source_token)
        if source_rows:
            st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)
        if source_frame is not None and not source_frame.empty:
            cache = combine_caches(cache, source_frame)
            save_runtime_master_cache(cache)
            save_runtime_cache(cache)
            memory = save_audit_memory(memory, cache, base)
            st.success("Exact Production-source BGeometrics history saved to the durable central master in src__ columns.")
        else:
            st.warning("No source-preserving BGeometrics rows were returned.")
    except RateLimitError as exc:
        st.warning("BGeometrics quota reached before source capture completed. " + rate_text(exc.rate))
    except Exception as exc:
        st.error(f"Production-source capture failed: {exc}")
'''
new = '''source_token = get_token()

# Keep the last capture result visible across Streamlit reruns so the user can
# confirm exactly what was durably saved without having to catch a transient table.
if st.session_state.get("production_source_capture_rows"):
    st.dataframe(
        pd.DataFrame(st.session_state["production_source_capture_rows"]),
        use_container_width=True,
        hide_index=True,
    )
    if st.session_state.get("production_source_capture_status"):
        st.caption(st.session_state["production_source_capture_status"])

if st.button(
    "CAPTURE BGEOMETRICS PRODUCTION SOURCES (USES UP TO 4 REQUESTS)",
    disabled=not bool(source_token),
    key="capture_production_sources",
):
    source_rows = []
    persisted_any = False
    specs = [
        ("mvrv-zscore", {"src__bgeometrics_mvrv_z": ["mvrvZScore", "mvrv_zscore", "zscore", "mvrvZ"]}),
        ("fear-greed", {"src__bgeometrics_fear_greed": ["fearGreed", "fearAndGreed", "fear_greed", "value", "score"]}),
        ("regime-score", {
            "src__bgeometrics_regime_score": ["regimeScore"],
            "src__bgeometrics_regime_delta_30d": ["regimeDelta30d"],
            "src__bgeometrics_regime_active_weight": ["activeWeight"],
            "src__bgeometrics_regime": ["regime"],
        }),
        ("btc-price", {"src__bgeometrics_btc_price": ["price", "btcPrice", "btc_price", "value", "close"]}),
    ]

    with st.spinner("Capturing and saving exact Production-source BGeometrics history..."):
        for endpoint, mapping in specs:
            try:
                frame, _rate = fetch_endpoint(endpoint, MASTER_START_DATE, dt.date.today(), source_token)
            except RateLimitError as exc:
                source_rows.append({"Endpoint": endpoint, "Status": "HTTP 429 — stopped immediately"})
                st.session_state["production_source_capture_rows"] = source_rows
                st.session_state["production_source_capture_status"] = "Quota reached. Every successful endpoint before the 429 was already saved and verified."
                st.warning("BGeometrics quota reached during source capture. " + rate_text(exc.rate))
                break
            except Exception as exc:
                source_rows.append({"Endpoint": endpoint, "Status": f"Unavailable — {exc}"})
                continue

            if frame is None or frame.empty:
                source_rows.append({"Endpoint": endpoint, "Status": "No rows returned"})
                continue

            endpoint_frame = pd.DataFrame(index=frame.index)
            captured = 0
            for dest, aliases in mapping.items():
                col = _pick(frame, aliases)
                if col is None:
                    continue
                series = frame[col]
                if dest != "src__bgeometrics_regime":
                    series = pd.to_numeric(series, errors="coerce")
                endpoint_frame[dest] = series
                captured += int(series.notna().sum())

            endpoint_frame = endpoint_frame.dropna(how="all")
            if endpoint_frame.empty:
                source_rows.append({"Endpoint": endpoint, "Status": "Endpoint returned rows but expected fields were not found"})
                continue

            # Transactional durability boundary: save THIS endpoint immediately.
            # A later endpoint failure or Streamlit rerun cannot lose earlier captures.
            cache = combine_caches(cache, endpoint_frame)
            save_runtime_master_cache(cache)
            save_runtime_cache(cache)
            memory = save_audit_memory(memory, endpoint_frame, base)
            cache = combine_caches(memory, cache)
            durable = st.session_state.get("audit_remote_save_status", "save status unavailable")
            persisted_any = True
            source_rows.append({"Endpoint": endpoint, "Status": f"Captured {captured:,} values | {durable}"})
            st.session_state["production_source_capture_rows"] = source_rows
            st.session_state["production_source_capture_status"] = "Latest durable master: " + master_schema_text(memory)

    if source_rows:
        st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)
    if persisted_any:
        st.success("Successful Production-source endpoints were saved and verified individually in the durable central master.")
    elif source_rows:
        st.warning("No new Production-source BGeometrics data was durably saved in this run.")
'''
if old not in s:
    raise SystemExit('target block not found')
s = s.replace(old, new, 1)
p.write_text(s)
