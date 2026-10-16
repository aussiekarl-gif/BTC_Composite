# After-tax Day-500 Dynamic DCA-out + 200WMA Dynamic DCA-in

**BTC DCA Research · 16 October 2026 · NOT approved for Production**

[Source / replay engine](../../engines/research/day500_aftertax_reinvestment.py) ·
[Regression tests](../../tests/test_day500_aftertax_reinvestment.py) ·
[Successful GitHub Actions complete historical + unit run #38920687461](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38920687461) ·
[Draft PR #90](https://github.com/aussiekarl-gif/BTC_Composite/pull/90)

## Scope / exclusions

At user request, **2013 is EXCLUDED from primary optimisation and the
primary performance table** because BTC was an immature market. Its
documented failures remain in [prior exit audit](day500_dynamic_dca_out_20261016.md).
Only **2017 and 2021** have complete year+ after-top observations
through post-halving day 1150. **2025/26 is right-censored at
5 October 2026**, so comparisons for that cohort are strictly
interim and can reverse.

**IMPORTANT: The user's true A$500,000 deployment began in 2026,
with their actual purchases persisted in the separate My Portfolio.**
To compare earlier full cycles *counterfactually*, every historical
matched account instead starts with hypothetical **A$500,000 fully
spent on BTC at the historic halving date**, including A$3 entry
brokerage and historically observed AUD/USD. These older accounts
are *NOT* the user's holdings, realized profits, investing start dates
or prospective retirement projections. Percent BTC gains below are
relative to an **identical initial cash / BTC entry date buy-and-hold
control** within EACH historical hypothetical cohort.

Research price source: Oct 2026-exported BlockHorizon daily BTC/USD
chart price records. FX: Frankfurter historical AUD per USD, using
the latest observation STRICTLY BEFORE each simulated transaction
date; stale FX over seven days makes the test fail. Prices are
daily *historical close*, not guaranteed trade fills. The original
stored composite risk-score is NOT used by this particular audit.

Each research order carries **A$3 brokerage**. FIFO SMSF
accumulation-phase simplification deducts an effective **10% CGT
on long-held realised gains (eligible >12 months)** or 15% on
short gains, including carry-forward losses, with immediate tax
escrow. The existing account library is reused rather than inventing
a parallel tax calculation. Actual SMSF annual tax, changes of fund
phase, losses elsewhere in the fund, ETF tracking, fund expenses,
slippage, bid-ask spreads, currency conversion charges and cash
interest are **NOT** modelled. Some money is still in AUD cash at
interim dates, which is included in BTC-equivalent marked
evaluation but NEVER counted as BTC actually owned.

## Selling: preserve the user's day-500 Dynamic DCA-out request

- **Dynamic maturity90**: 5% of BTC sold on halving day500, larger
  prior-price-regime-dependent distributions on days 525/532/539/
  546/553/560, weekly sale tail if held BTC remains.
- **Dynamic with 20% holdback**: Same 5% initial sale, maximum 80%
  disposed through day560; last 20% sold only if independently
  confirmed deterioration later.
- **Six fixed weekly control**: 6:5:4:3:2:1 BTC-weighted sales
  on days 525/532/539/546/553/560 without the early day500 sale.
  As earlier tests showed, this simple control historically obtained
  a HIGHER average USD sale price in all three recent cycles.

Real post-2024 halving day500 was **2 September 2025**. The user's
real A$500k portfolio only began deploying in 2026; this research
does NOT recommend selling based on a past trigger.

## Re-entry: strict-prior observed price, NOT future bottom

The model waits until all current simulated sale executions stop
plus a 14-day interval before enabling buyback. This is a simple
**non-overlapping exit/re-entry policy**; it may miss attractive lows
while a sell tail persists.

Three simple controls: trigger when the **PREVIOUS close**
was 40%, 55% or 65% below its past 365-day BTC/USD high.
Then execute 24 or 52 weekly purchases, weighted using prior
drawdown. Unspent cash remains cash until its intended
investment window, no artificial early full investment.

Better alternative: trigger the first close **strictly below
the rolling 200-week BTC/USD average**, computed from **200
once-per-7-days completed prior daily closes**, with **not one
future observation**. The BTC 200WMA is an independently
observable price-only signal (not an unverified on-chain risk score).

Then test two open-ended, *same-rule-across-all-cycles*
dynamic allocation systems, with **no fixed end date** and no
forced investment of all cash:

- `adaptive_value`: percentage of initial NET cash allocated
  each weekly trade = 10% if prior price <=0.85× 200WMA, 3.5%
  between 0.85–1.00×, 12% between 1.00–1.25×, 4% between
  1.25–1.50×, 1% if above 1.50×.
- `adaptive_recovery`: allocate 2.5% while prior price is below
  200WMA, 15% if prior price is 1–1.25× 200WMA AND the
  50-day trailing mean is rising vs 14 days earlier AND the
  prior close is above that mean, 4.5% between 1.00–1.50×
  otherwise, 1% above 1.50×.

These are exploratory in-sample parameters **designed after the
history was inspected**. We must NOT claim they generalize just
because their trades do not use future data. Tests verify
prefix-invariance, lagged exchange rates, BTC/cash conservation,
FIFO tax accounting, strict moving-average warmup, censored
unexecuted buyback cases and null error if no buys executed.

## Primary scorecard: Day-500 Dynamic maturity90 sells; variable DCA-in

Effective VWAP of BTC actually repurchased, including A$ brokerage
converted to USD using historical prior-day FX. "Buy error" =
(USD-acquisition VWAP / lowest BTC/USD *daily closing* price between
final sale and model observation endpoint) − 1. The low is known
only **after** the market period, used solely for scoring, NEVER
as a buy signal.

| Buyback style | 2018 bear buy error | 2022 bear buy error | 2026 interim buy error | 2017 BTC-equivalent lift vs hold | 2021 BTC-equivalent lift vs hold |
|---|---:|---:|---:|---:|---:|
| Drawdown 55% → 52-week DCA | +94.7% | +28.2% | NO trigger | +104.0% | +154.8% |
| Drawdown 65% → 52-week DCA | +61.2% | +33.7% | NO trigger | +143.2% | +142.1% |
| **200WMA → dynamic value (no deadline)** | **+14.82%** | +36.40% | **+11.23%** | **+234.98%** | +143.13% |
| **200WMA → dynamic recovery (no deadline)** | **+18.58%** | **+27.37%** | **+20.33%** | **+222.77%** | **+156.64%** |

At 5 Oct 2026, the 2025/26 interim BTC-equivalent lift vs
matched historical-halving-date hold is +75.12% (value) or
+63.71% (recovery). These are NOT completed-cycle returns,
not actual user portfolio returns and may reverse.

Observed price-only 200WMA activation dates:

| Cycle | First 200WMA entry | Later recorded daily closing low (scoring ONLY) |
|---|---|---|
| 2017–18 | **16 December 2018** | **15 Dec 2018**, US$3,179.54 |
| 2021–22 | **15 June 2022** | **21 Nov 2022**, US$15,766.00 |
| 2025–26 | **6 June 2026** | **30 Jun 2026**, US$58,526.17 through source cutoff |

The user's chosen **US$57,717 on 30 June 2026** is a
*reported intraday low* and NOT the daily chart close
US$58,526.17. Do not silently use the two numbers
interchangeably. The observed 2026 bottom can still be
revised downward in future, even though the prior reported
date is already known.

### Fixed 200WMA DCA sensitivity (not for live parameter cherry picking)

| Post-200WMA planned buy duration | 2018 VWAP error | 2022 VWAP error | 2026 provisional error |
|---|---:|---:|---:|
| 12 weeks | +14.92% | +33.91% | +7.84% |
| 24 weeks | +14.36% | +35.88% | +15.39% |
| 52 weeks | +37.90% | **+24.45%** | +15.40% (cash still idle) |

**DO NOT choose 24 weeks for 2018, 52 for 2022, 12
for 2026 by looking backwards.** That would be timing
hindsight masquerading as a dynamic DCA rule. The
*same-rule* open-ended recovery variant is the more
balanced exploratory model, though 2022 is 2.37
percentage points above the user's requested 25% buying
error. Changing a parameter just to fit 2022 would
almost certainly overfit this tiny sample.

## Important accounting and risk conclusions

- In 2017 and 2021 the day-500 sell/reinvest strategies
  generated more **BTC and after-tax marked AUD wealth**
  than their exact same-date BTC hold benchmarks.
  The model holds no additional contributions outside the
  initial A$500k *in each historical thought experiment*.
- BTC-equivalent lift measures **BTC owned + leftover AUD
  cash converted to BTC at the contemporaneous date**.
  Actual BTC holdings and cash are shown separately in
  the machine-readable GitHub Actions JSON artifact.
- The old **2013 failure is not part of model selection** as
  requested; its existence remains a structural stress risk.
- Only **two** completed comparable modern post-top cycles
  exist here, while 2025/26 is unfinished. There is NO
  statistically sound "win rate" or guarantee of detecting
  any future top/bottom.
- The 200WMA may never be touched in a future bear market,
  potentially leaving cash idle indefinitely. Drawdown
  gates 55/65% in 2025–26 never triggered by the source
  cutoff, demonstrating the missed-entry danger.
- The 2025 seller began distributions in **2025**, before
  the user's actual initial 2026 purchases, so such
  historical gains cannot be transferred to the
  user's real 2026 account. The real 2026 cohort
  still needs a future observed exit and subsequent
  repurchase to test completed net BTC multiplication.

## Promotion decision

**No new selling or buying model is promoted to Production.**
Research draft PR #90 contains numerical engine, the GitHub
test workflow, regression tests and this report. It never
reads or mutates My Portfolio, Google Sheets, the authoritative
audit master or production strategy code.

**Next disciplined validation:**
1. Shadow-track 200WMA and recovery-trigger allocations
   with future observations, without retroactive parameter
   changes, including missed re-entry if price never
   revisits the moving average.
2. Complete forward validation of the SELL signals;
   a valid buyback from perfect historic sale exits is
   not a realistic actual 2026 portfolio experience.
3. Resolve point-in-time vintage provenance for any
   subsequently added on-chain indicators.
4. Account for actual post-2026 BTC/ETF purchase parcels,
   transaction/exchange fees, 10/15/0% appropriate fund
   CGT, and stop comparing against hypothetical BTC
   bought at the 2016/2020/2024 halvings.
