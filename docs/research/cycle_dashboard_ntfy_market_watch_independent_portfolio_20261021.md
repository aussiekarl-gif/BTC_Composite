# Cycle Trading end-to-end dashboard/ntfy reliability audit — 21 October 2026

## Issue reproduced by code inspection

The read-only Cycle Trading decision adapter, `engines/research/cycle_trade_decision.py`, previously evaluated the **user's saved portfolio** before the `calculate_allocation_signal` shared price-only model. If Google Sheets was unavailable, records were absent or the account ledger was incomplete, the function returned its default `market_signal="UNAVAILABLE"` even with **verified** BTC and FX market data. The Streamlit quick view used this adapter and therefore hid a genuine BUY WATCH / SELL WATCH / HOLD market state behind a private portfolio problem.

The one-daily `cycle_trading_daily_ntfy.py` independently uses `calculate_allocation_signal` from verified public BTC inputs and **does not access user portfolio**. The issue was therefore misleading dashboard presentation and apparent inconsistency with ntfy, **not an error in Cycle Trading's 2.5% BUY algorithm**.

## Narrow correction

Compute the exact unchanged shared `calculate_allocation_signal(market,buy_style=buy_style)` after the existing verified market-date/FX gates, but **before** the saved portfolio check. Copy only the market WATCH and BUY/SELL percentages into the read-only decision result. If portfolio is absent/invalid, or Google Sheets fails, return `action="HOLD"`, `action_aud=0`, `suggested_ibit_units=0`, `data_ok=False`, and show a clear saved-portfolio reason. It must not infer a cash amount, confirmed holdings, broker fill, tax or transaction.

All existing fail-closed rules remain exactly where they were: stale or unverified public BTC inputs => `market_signal="UNAVAILABLE"`; invalid below-200WMA price construction => UNAVAILABLE; portfolio cash and holdings validation, saved execution cooldown, ETF quote and whole-unit rounding and user manual confirmations still block any account-level BUY/SELL suggestion.

## Test evidence and limits

Regression tests in `tests/test_cycle_trade_decision.py` cover three verified market cases (BUY WATCH 2.5%, SELL WATCH 5% day500, and HOLD) with BOTH null and empty personal portfolio. All keep market WATCH visible and action blocked. Failed or stale BTC feed and inconsistent price ratios remain unavailable. `tests/test_cycle_trading_pct_allocation.py` compares the same verified market percentages in the Streamlit decision adapter and the ntfy message even with no portfolio.

Original `research_cycle_trade_decision.yml` PR workflow runs the live adapter, Streamlit model, ntfy percentage parity, dated market reference and cooldown suites. Does **not** send any notification, read personal Google Sheets, update portfolio or modify frozen Production V5.8.2 / Research V5.9 code.

## Wider audit findings and next checks

- The prior 2029 date-reset issue already has a separate durable `model_settings_store` and `test_dca_target_date_persistence.py` suite; no duplicated settings work or trading formula changes in this PR.
- Existing daily ntfy remains one public market signal with its own durable once-per-day sent-date marker; it makes no claims about actual spendable broker cash.
- Real ASX:IBIT Yahoo daily candles remain *indicative/delayed* versus executable broker prices. No order amounts can be called verified without matching broker account state.
- This change fixes a reproducible **missing market recommendation** display path. It does not claim to resolve unrelated Streamlit session/navigation failures, Google Sheets authorization issues or live broker/ntfy delivery.

No model retuning, increased BUY %, SELL timing changes, forced 2026/27 deployment, source-tape backfills, new GitHub schedules or push notifications.
