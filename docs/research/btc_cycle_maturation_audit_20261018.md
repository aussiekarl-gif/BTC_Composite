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


## Verified numerical findings (CI completed 18 October 2026)

[Successful run 39104984522](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39104984522): **7 new + 10 existing causal-timing + 8 shared-policy unit tests passed**, 3-cycle diagnostic successfully replayed, independent exact original 200WMA gate dates agreed. [Full dated JSON and cohort CSV artifact](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39104984522/artifacts/12128510517).

| Metric | 2017 full | 2021 full | 2025/26 as of 2026-10-05, **INCOMPLETE** |
|---|---:|---:|---:|
| Peak-close date | 2017-12-16 | 2021-11-08 | 2025-10-06 |
| Peak USD close | 19,187.78 | 67,559.00 | 124,728.00 |
| Peak age after halving | 525 days | 546 days | 534 days |
| Lowest post-peak USD close recorded | 3,179.54 | 15,766.00 | 58,526.17 *observed only* |
| Date of score-window low | 2018-12-15 | 2022-11-21 | 2026-06-30 *not confirmed final* |
| Peak → low elapsed | 364d | 378d | 267d *censored* |
| Peak-to-low decline | -83.43% | -76.66% | -53.08% *may deepen* |
| Low price / preceding 200WMA minus 1 | **+0.42%** | **-34.33%** | **-6.60%** *subject to change* |
| First genuine prior-close-below-prior-200WMA original BUY date | 2018-12-16 | 2022-06-15 | 2026-06-06 |
| Signal vs ex-post low | 1 day AFTER | 159 days BEFORE | 24 days BEFORE *observed low* |
| First-gate execution BTC price above observed low | +0.45% | **+43.06%** | +3.99% *censored* |
| Nominal low multiple vs previous period | n/a | 4.959× | 3.712× *censored* |
| Peak multiple vs previous peak | n/a | 3.521× | 1.846× |

### Interpretation / decision

**Observations consistent with gradual maturation:** peak-to-peak USD growth multiples have compressed (3.521× → 1.846×); nominal USD lows in successive sampled periods are higher; the two completed drawdowns decreased by 6.77 percentage points from 2017 to 2021. The observed 2025/26 peak-to-low drawdown so far is shallower, but ongoing observation can reverse that.

**Observations against a simple clock or WMA-floor prediction:** the complete 2017→2021 peak-to-low span **increased** from 364 to 378 days. The historical lows were approximately at 200WMA (+0.42%) in 2018 and deeply below (-34.33%) in 2022, while the incomplete 2026 observed low is only -6.60% below it. The 200WMA crossing was about **43% above eventual low** in 2021 even though the eventual percentage drawdown was less severe than 2018. Thus nominal higher lows or lower peak-to-peak gains cannot justify buying a fixed large fraction at first WMA crossing.

**Research action:** retain original strict completed-prior-close 200WMA as a *value-zone/first-gate timing benchmark*, not a guaranteed low; preserve remaining cash and ability to buy on a deeper or faster recoverable path. Do not assume a shorter future cycle or invent a numerical probability from two completed modern cycles. The fully exposed 10%-of-original-cash first-gate frontload (prior PR #137) underperformed original in all 8 deliberate delayed-bottom synthetic stresses: *do not promote*. A potential future predeclared rule must work even if no new WMA crossing occurs after actual fresh-cash start, and be validated in matched AUD FIFO aftertax accounts.

### Why this is NOT a green light to update trading sizes

These are retrospectively available historical close observations. All *peak dates, drawdown percentages, eventual lows and distances to lows* are **evaluation labels**, not safe trade-timing inputs. There are just **two completed** 1150d modern cohorts; 2025/26 low, terminal return, and market regime remain unconfirmed. No annual return, future drawdown depth or 20%-within-bottom buying-error target is proven. Public BTC close/WMA, real A$ ETF price, tax phase, fees, spreads and verified personal cash are different. Live Streamlit/ntfy still do not have exact end-to-end parity with original historical model.

**Verdict: RETAIN AS RESEARCH DIAGNOSTIC, NO BUY/SELL POLICY CHANGE.**
