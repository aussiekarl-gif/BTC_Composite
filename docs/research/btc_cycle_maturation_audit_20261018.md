# BTC cycle maturation: hypothesis diagnostic (18 October 2026)

**Research only, no allocation or trading changes.**

## Question

User hypothesis: as BTC matures and percentage returns diminish, future bear cycles may end sooner, may have higher nominal lows, may have shallower percentage drawdowns, or may never revisit the prior completed 200-week moving average. These are **four different claims** with different investment consequences. In particular a high absolute USD low is entirely compatible with a severe percentage drawdown from a substantially higher peak.

The test fixes existing 2017/2021 complete 1150d cycle horizons; the 2025/26 cycle is censored to 2026-10-05. The 2013 regime remains excluded from PRIMARY as previously requested. The historical archive may be retrospectively revised. BTC USD daily closes are a reference only, not ASX:IBIT order prices.

Frozen measures, all ex-post except lagged WMA gate:

1. Peak daily USD close in halving days 350–800; peak day age.
2. Minimum daily close **after that observed peak and after day744** through cohort terminal; low age and days from peak; percentage drawdown.
3. Nominal new peak/old peak and new low/old low ratios for successive observed periods. No extrapolated cycle return ratios.
4. First **strictly prior-completed** close below the previous **200 WEEKS'** exact sampled closes beginning at day744 (must match existing original first-gate timing). At first gate, prior 90-day drawdown from prior-only high and prior-close/200WMA ratio use only dates earlier than the decision.
5. Retrospective days from first gate to the later observed low, first fill price vs low, low/previous WMA ratio and first 90 days' WMA activity. These are outcomes, not signal features.
6. Independently, first below-WMA gate after fresh cash starting day+650,+750,+850,+900; if no new eligible observation before terminal report **NO BUY**, not perfect pricing performance. Never invent historical day500 sells or previous BTC lots for the real 2026 portfolio.

The 2017/2021 sample has only two completed modern periods and the 2025/26 low is not yet known. This exercise **cannot prove structural regime change**. It can determine which specific relationships changed in the observed periods and guide the next test without fitting a trade rule to the eventual bottom.

## Outputs

- `engines/research/btc_cycle_maturation_audit.py` reproducible date-specific diagnostic.
- `tests/test_btc_cycle_maturation_audit.py`: stricter-than-date close, price-prefix invariance, genuinely missing crossing, ongoing incomplete score, corrupted data failures, independent existing first WMA gate parity.
- `.github/workflows/btc_cycle_maturation_audit.yml` runs all tests and exports JSON, cycle summary CSV and fresh-cash gate wait CSV.
- **No Streamlit, Production V5.8.2, Research V5.9, daily ntfy, broker, Google Sheets or portfolio updates.**
