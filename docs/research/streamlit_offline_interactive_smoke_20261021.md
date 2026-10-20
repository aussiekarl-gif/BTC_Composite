# BTC Streamlit interactive smoke test — 21 October 2026

This CI addition tests the **real** `app.py` Streamlit launcher in Streamlit's `streamlit.testing.v1.AppTest` runner, without opening a real browser or contacting a broker/portfolio/ntfy source. It also tests an isolated interactive date-widget component that calls the **exact same real stored-settings functions** used by the larger existing Production 5.8.2 and Research 5.9 pages. Those full two model pages have their own unchanged calculation/data regression tests; the isolated date control is not misrepresented as a full browser test of their entire UI.

## Actual interactive behaviors

1. With entirely synthetic completed BTC/USD 1900-day history, prior AUD FX and verified historical 2024 halving metadata patched at source, and public quote explicitly marked `SYNTHETIC UNITTEST ONLY`, launch the original `app.py` Cycle Trading page under real Streamlit AppTest execution. No network, Google credentials or account writes. Stub portfolio load to a simulated offline failure. Assert the visible quick view shows a **verified HOLD** market signal even when personal holdings are unavailable, while spendable trade remains Not verified. Assert no BUY/SELL execution preview or actual order appears.
2. Click the real **Refresh market feed and My Portfolio** button through AppTest; verify the public and portfolio stub providers are called again after cache invalidation and the verified public market state remains visible. No data or trading file is written.
3. Use real Streamlit `st.selectbox` + `st.date_input` widgets and the real `choose_target_date`, `load_dca_target_date` and `save_dca_target_date` functions. Use a unique temporary SQLite database (not user's Google Sheets). Save a Production target, construct a **fresh** Streamlit AppTest session and confirm the previously chosen date survives rather than falling back to +3 years. Save a different Research target and prove the two independent preferences persist without a `shared` executed-trades portfolio row.
4. Assert that the real Production/Research Streamlit source pages still render distinct date-widget keys and call the same persistent settings functions; the original numerical and broker/account regression suites remain unchanged.

## CI and release caveats

The new workflow `.github/workflows/streamlit_offline_dashboard_smoke.yml` runs only on PR modifications to affected UI/test files or on explicit manual request. It is NOT a new scheduled workflow, DOES NOT send ntfy, copy real Google credentials, fetch market quotations, touch the user's actual portfolio, alter any buy/sell rules, backfill historical BTC data or place orders. CI uses a scoped SQLite backend only.

The test does **not** prove an actual remote Streamlit Cloud browser session, mobile rendering, cross-device Google Sheets authorisation or delivered push notification; those require separate real-environment acceptance after code checks pass. AppTest simulates Streamlit widgets in Python, not a browser engine.

Do not merge unless the new actual-app and interactive-date UI tests plus existing durable dates / Cycle decision / ntfy parity tests pass. No Production 5.8.2, Research 5.9 or Cycle market algorithm changes.
