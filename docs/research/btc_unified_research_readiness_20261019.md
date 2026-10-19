# BTC Unified Research Readiness — 19 October 2026

## Purpose and current evidence

One source-verified report covering Cycle Trading, frozen Production 5.8.2, frozen Research V5.9, prospective BTC microstructure, and matched buy-and-hold / fixed-DCA controls.

Authoritative source records inspected on 19 October around 02:43 UTC:
- Cycle forward observations: **2** dated BTC market HOLD entries, 15 Oct and 17 Oct. The 15 Oct entry was not captured next UTC day, excluded from truly prospective scoring. No verified matured recorded 7/30/90-day return chain; missing 16 Oct not backfilled.
- Genuine ASX:IBIT Sydney-day indicative close observations: **0** in authoritative prospective tape. At review, Monday 19 October ASX had not closed. A free Yahoo AUD candle is not an actual broker bid/ask.
- Kraken: **2** point-in-time resting-book observations; Coinbase: **2** bounded 100-trade samples. Oct18 actual captures 7m27s apart, Oct19 ~33m apart: neither qualifies as a simultaneous five-minute paired observation. A coordinated collector was merged; does not rewrite the existing evidence.
- **6.29% maximum historical BTC provider dispersion**, above 5% manual-review threshold. This is NOT evidence today's spot price is 6.29% wrong. Isolate dated offending provider and source before trusting affected historical risk inputs, without replacing or silently editing the archive.

No tested model win can be inferred from successful CI, 2 historical cycles, two snapshots or a single-model backtest.

## Implementation

New read-only code: engines/research/btc_unified_research_readiness.py

Unit tests: tests/test_btc_unified_research_readiness.py, including stale observations, missing ASX, weekday market close, BTC dispersion, capture skew, fake future, hash tamper and refusal to declare model investment readiness.

Existing research_forward_cycle_tape.yml workflow builds optional report AFTER the independently mandatory hash-verified BTC/ASX forward readiness check. Artifact: artifacts/btc_unified_research_readiness.json. No additional job, schedule, API calls, ntfy, dashboard change, personal portfolio access, broker connection, Production or Research engine change.

The optional report must NOT block valid immutable source tape publication if a diagnostic error occurs. Research source provenance still fails closed.

## Five comparison tracks — all explicitly unranked

1. Cycle Trading control: exact Streamlit 2.5% cash BUY below prior 200WMA, 7-day cooldown, SELL fractions of REMAINING BTC holdings, not previous original-position dynamic-historical Day500 backtest. No historical ASX IBIT trading before 14 Nov 2025, and no independently verified full IBIT bid/ask history.
2. Production V5.8.2: frozen weights, historic reconstructed study NOT independently verified live-funded outcomes from original historical point-in-time indicator vintages.
3. Research V5.9: frozen candidate, NOT a proven out-of-sample improvement.
4. Microstructure: Kraken resting depth and Coinbase bounded trade samples are correlated BTC spot microstructure measures, not independent AI agents or six-hour executed volumes. Score only time-matched future BTC USD quote movements after predefined freeze.
5. Buy-and-hold and equal DCA: need same opening AUD capital and funding, actual future eligible ASX sessions, currency, fees, spreads, cash taxes and real broker execution constraints as challengers.

## Quality and safety gates

Escalate a review flag for: historical BTC source crosscheck >=5%; BTC forward close missing or more than 2 calendar days old; Kraken/Coinbase sample tape not observed for more than 9 hours; same Sydney day ASX:IBIT indicative close absent only on a weekday AFTER 17:00 local. ASX holidays and provider outages are not automatically fraud or failed strategy signals.

Promotion blocked until exact candidate-vs-control executable backtest with no future information, same investment capital and accounting, real ASX timing, realistic AUD FX/fees/spread/lot taxes, and independent prospective follow-up. No investment orders, live BUY/SELL rule changes, portfolio, or ntfy changes result from the control-room report.
