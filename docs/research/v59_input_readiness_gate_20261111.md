# V5.9 aggressive accumulation — archived-input readiness gate (11 Nov 2026)

**Research only. No Production V5.8.2, Streamlit, DCA sizing, Cycle Trading, portfolio, data master or ntfy changes.**

## The actionable discovery

A direct read-only inspection of the PRIVATE aussiekarl-gif/btc-audit-data main-branch btc_audit_backup.csv on 2026-11-11 found **6,358 data rows**.

| Field | Last filled observation UTC | Context |
|---|---|---|
| risk_score / btc_price_aud | **2026-08-31** | 557 weekly proxy rows, Walk-forward Power Law |
| src__blockchain_btc_usd | **2026-11-10** | Public BTC/USD reference |
| src__frankfurter_usd_per_aud | **2026-11-10** | Public FX reference |
| Puell Multiple | **2026-11-09** | Separately investigated; date alignment unresolved |

As of 2026-11-11, the last archived weekly *proxy* risk was **72 days old** while public price/FX references were current. This **does not mean live Streamlit V5.9 risk is stale**; the archive's risk_score is a different, limited-duration research series. Replacing missing late-2026 V5.9 scores with this proxy is not a valid way to claim live-strategy performance.

## New reproducible safety check

The script at engines/research/v59_input_readiness.py streams the private local CSV without modifying or uploading it. It identifies last observation dates/sources for historical risk and public price/FX, validates dates and finite values, and reports ready_to_promote_3x=false, ready_for_v59_trading_claim=false.

Example, with the PRIVATE archive already available locally:

    python -m engines.research.v59_input_readiness --csv /trusted/private/btc_audit_backup.csv --asof 2026-11-11

Expected risk status for the 2026-11-11 snapshot:
- risk_latest_date: 2026-08-31
- risk_latest_source: Walk-forward Power Law
- risk_age_days: 72
- risk_weekly_fresh: false
- market_reference_fresh: true
- ready_to_promote_3x: false

Do not commit the private CSV into this public repository. Unit tests use only synthetic inputs. The existing V5.9 research CI runs these tests; it does not claim to have verified real live fills.

## What is still needed to achieve the BTC accumulation goal

1. Capture real, completed **V5.9 risk snapshots** prospectively, with full source provenance, as-of and ingestion timestamps. Verify the same exact signal used by Streamlit and the weekly decision.
2. Match the user's **late-2026 actual starting cash, recorded holdings, reserves and flexible review into 2027**. Avoid retroactively claiming 2026 January trades. Stop buying when risk > 0.50 as agreed. Do not silently use a retrospective Power Law risk label in lieu of V5.9.
3. Run identical 1x/2x/3x, equal-cash plain weekly DCA, and hold comparator histories with **lagged signals**, next executable AUD instrument prices, realistic spread, fixed brokerage, ETF-specific fees and cash constraints.
4. Report BTC units, available/unspent AUD, after-cost equity, maximum drawdown, worst delayed-bottom stress, and cash exhaustion. Historical provider publication timestamps and revised-vintage checks remain necessary before any historical trading-alpha claims.
5. Only then consider a change to live model allocations; require Streamlit/ntfy exact parity, rollback, and a user-reviewed release.

**Decision:** This data gap is a BLOCKER to claims of validated aggressive 3x outperformance, not a reason to stop running the frozen live system. Do not replace unknown live V5.9 signals with old proxy rows or invent future returns.
