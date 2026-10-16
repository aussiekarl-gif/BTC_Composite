# Can one indicator always call the Bitcoin top? Historical horse race

**16 October 2026 • research only • NOT validated for Production.**

- [Unit-tested daily top-detector source](../../engines/research/top_signal_horse_race.py)
- [Unit tests](../../tests/test_top_signal_horse_race.py)
- [Successful GitHub Actions #38893989529](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38893989529)
- [Staged halving-clock follow-up](halving_clock_selling_windows_20261016.md)
- Research draft [PR #90](https://github.com/aussiekarl-gif/BTC_Composite/pull/90)

## User goal

Find market-top warnings effective enough to sell BTC with a **BTC-quantity
weighted average disposal price** no more than approximately 25% below
the later identified major cycle peak, not requiring every partial sale
at that price. Future precision can NEVER be guaranteed. Any rule
whose thresholds are chosen from completed cycles may look perfect
without having prospective predictive value.

## Source & causality

- Read-only exported **BlockHorizon** data
  `data/mvrv_z_score_2026-10-06T21-46-14.csv`,
  `data/nupl_net_unrealized_profit_loss__2026-10-06T08-54-39.csv`, and
  `data/sopr_spent_output_profit_ratio__2026-10-07T21-21-13.csv`.
- Timestamp align three provider datasets on exact UTC days and
  require their reported BTC/USD prices to agree within 1%.
- The matched set starts 1 Nov 2010, ends 5 Oct 2026.
- All computed tradeable warnings execute on the NEXT day's price,
  using on-chain metrics and completed price observations
  **at most through the previous day**.
- Prefix-invariance unit tests: changing dates in the future cannot
  change earlier warnings.
- **CRUCIAL:** these historical provider CSVs were downloaded in
  October 2026, so component values may be retrospectively revised.
  Passing a no-lookahead code test is NOT a demonstration the original
  scores were actually published and observable years earlier.

## Seven predeclared qualitative top-warning families

| Family | Concept | Macro top windows with ANY nearby alert | Total distinct alerts since 2013 |
|---|---|---:|---:|
| Classic overheating | MVRV Z >=7 or NUPL >=.75 | 2 of 4 | 4 |
| Pi Cycle Top | 111-day SMA cross > twice 350-day SMA | 2 of 4 | 4 |
| Relative overheating | >=95th historical MVRV and >=90th NUPL percentile of strictly prior 3-year window | 2 of 4 | 9 |
| Price trend break | Past uptrend, 10% drawdown, closing below falling 50DMA | 2 of 4 | 14 |
| Mature halving + highs warning | 350–800 days from halving and within 3% of observed 365-day high | 4 of 4 | **16** |
| Mature warning then price confirmation | Recent maturity warning, price down >12% from 365-day high and below 50DMA | 1 of 4 | 9 |
| Late trend break | 20% off 90-day high and below falling 50DMA | 2 of 4 | 15 |

Macro windows: December 2013, December 2017, November 2021
(the larger *full-cycle* high, not April 2021), October 2025.
For the ANY-alert statistic an alert is called "near" if it occurred
140 days BEFORE or 56 days AFTER the ex-post peak close.
This is intentionally generous. Select the historical nearest
alert to illustrate the maximum opportunity, NOT a live rule.

**A high number of ANY-near alerts is not a good strategy if many
false/early alerts also occurred.** Among four Pi crosses from 2013
onward, the major 2017 and December 2013 crosses were close, but
the 2021 cross was in **April**, roughly seven months prior to the
November top, and there was no 2025 cross.

## No hindsight cherry-picking: FIRST tradeable maturity warning

The next audit always acts on the FIRST matured-halving warning
(day 350–800 after each halving) rather than picking a later warning
which happened to be near the peak.

| Cycle | First alert | First alert sell close USD | Later macro peak close USD | Price shortfall |
|---|---|---:|---:|---:|
| 2013 | 13 Nov 2013 | $393.50 | $1,132.01 | **65.24%** |
| 2017 | 24 Jun 2017 | $2,557.66 | $19,187.78 | **86.67%** |
| 2021 | 26 Apr 2021 | $54,073.41 | $67,559.00 | **19.96%** |
| 2025 | 5 Apr 2025 | $83,507.00 | $124,728.00 | **33.05%** |

**Only 1 of 4** first alerts would achieve the desired <=25%
one-shot sale-price error. The 4/4 nearest-alert result is **not**
a valid reason to sell entire holdings after a warning. Early alert
should mean monitor / modest risk reduction, not exit everything.

## Implications for actual BTC strategy

1. **Pi Cycle is not a universal top rule.** Near 2017 top but silent
   for October 2025; April 2021 signal does not locate November's high.
2. **Fixed on-chain euphoria thresholds decay.** Latest BTC bull top
   in 2025 did not reach the previous classic warning levels.
   Institutional adoption and diminishing cycle amplitude provide
   plausible explanations but do not prove a specific next regime.
3. Pure trend rules often confirm *too late* to meet 25% disposal VWAP.
4. Cycle-clock + price highs is the best **early contextual flag**,
   but naive one-shot selling on the first warning can fail severely.
5. Investigate partial, pre-specified staged sales around the modern
   halving-clock peak clustering. Explicitly test earlier regime
   transfer failures, wider timing, missing rallies, after-tax
   cash/BTC and capital recycling; do not cherry-pick optimum dates.

## Relevant independent research

Galaxy's June 12, 2026 research "Bitcoin May Not Have Bottomed Yet"
reports that in the Oct 2025 top only 2 of 11 traditional warning
metrics cleared their weakest prior peak thresholds, and the Pi
Cycle never crossed. Their MVRV peak was 2.29, below prior peaks.
Source:
https://www.galaxy.com/insights/research/bitcoin-four-year-cycle-where-is-the-bottom

A July 2026 research paper
"Bitcoin Runs on a Clock: Why Every Price Indicator Dies and the Halving
Clock Doesn't" suggests halving-relative mature cycle peak clustering,
but turns are defined ex post and sample is tiny; do not treat
any hypothesis as a guaranteed forecast.
https://arxiv.org/abs/2607.26188

No files in Production, audit master or actual Google Sheets My
Portfolio were altered.
