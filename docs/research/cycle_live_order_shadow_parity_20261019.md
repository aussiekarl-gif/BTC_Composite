# Cycle Trading exact-live-rule execution parity — isolated research shadow, 19 October 2026

**No change to the Streamlit dashboard, production, Research V5.9, ntfy, model weights, holdings, broker or Google Sheets.**

## Confirmed problem

The present Cycle Trading market/Streamlit SELL stages apply each percentage to **remaining units**. Historical standalone dynamic day500 simulation tranches were sized against **original units**, with different regime decisions and an approximately 20% historical holdback. Seven live sell-stage percentages, even if every event occurs, leave about 37.32% of original BTC exposure unsold, not the historical 20% holdback. BTC accumulation differs too: live `adaptive_recovery` is an initial 2.5% of remaining available AUD cash whenever prior BTC USD close is below prior 200WMA and there has not been a filled trade in the previous seven calendar days. Standalone historical research buyback is stateful and may continue **above** the 200WMA.

**Never claim historical standalone Day500 buy/sell multipliers are backtest results for the actual current Streamlit engine.** This research addition does NOT reconcile their economic performance yet, because there are no valid 2017/2021 ASX:IBIT fills, no complete broker bid/ask archive, and the actual live user's stored portfolio is intentionally not accessed.

## What changed

New module `engines/research/cycle_live_order_shadow_replay.py` calls **the existing unchanged** `calculate_allocation_signal` and `make_current_decision` for each explicitly supplied verified ASX session and actual prior dated BTC market snapshot. It models a paper execution at ASK for buy, BID for sale, whole ETF units, the already-saved FIFO purchase/sales ledger and same seven-day cooldown. BUY money never exceeds spendable AUD cash. SELL quantities are fractions of remaining ETF units, not originally owned units.

A caller MUST supply the opening ledger, corresponding source-dated actual ETF bid/ask at every session, quote receipt before simulated time and no older than fifteen minutes, and verified trading dates; weekend, unknown ASX holiday, pre-inception, crossed spread, future BTC closing price, FX newer than the market snapshot, future-market-pricing, negative cash and duplicated session are refused. No auto-invention of 2017/2021 IBIT prices.

An optional explicit tax CASH ESCROW fraction of gross sale proceeds is withheld from future buy cash. This is **not** CGT calculation, tax rates, lot-level realised gains or an after-tax result. Without verified tax lots, do not infer after-tax wealth or ROI.

A synthetic fixture demonstrates:
- BUY: initial AUD150,000 capital with preowned 1,000 IBIT units; 2.5% of remaining AUD available cash, priced using 20.01 AUD ASK rather than a BTC proxy.
- SELL: a 5% sell on day500 from 1,000 units gives 50 sold, then a 24% day525 sale of 950 REMAINING units gives 228 sold (rather than 240 of original).
- Seven-calendar-day cooldown and exact paper ledger, quote-date, FX provenance, no historical IBIT data before November 2025, weekend and no-lookahead gates.
- Prefix invariance: an earlier recommendation/execution record does not change when adding a future simulated ASX session.

These are **synthetic regression fixtures only**. No claim of a better strategy or actual 2026 IBIT fill and no automatic promotion. The next requirement is a real forward ASX broker bid/ask and exact session calendar plus actual cash lots, then side-by-side comparison against buy-and-hold/equal DCA and the original Cycle Trading historical experiment. Do not change the user's live investment decisions based on the fixture.

Run:
`python -m unittest discover -s tests -p 'test_cycle_live_order_shadow_replay.py' -v`

The dedicated PR/push manual-only GitHub Actions runs those tests and existing `test_cycle_trading_pct_allocation.py` with no new schedule, no extra paid source, no ntfy and no production code modifications.
