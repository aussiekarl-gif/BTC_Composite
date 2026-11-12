# Bitcoin four-year *bear-cycle bottoms* versus 200WMA touches — 12 Nov 2026

**CORRECTION / RESEARCH ONLY.** The previous PR #263 compared 200-week moving
average **crossings**, not uniquely the larger ~four-year Bitcoin bear
cycle bottoms. Distinct moving-average events within the same 2022–23 bear
market and the 2020 COVID shock were incorrectly easy to read as
independent bottom episodes. This study removes that ambiguity.

## Independent historical reference anchors

The following approximate historical low dates and peak dates are established
from external cycle references (Fidelity Bitcoin four-year cycle explainer,
March 2026; exchange price vendors may differ by one/two days), not selected
to maximize this new 17/20-week strategy's outcome:

| Broad bear cycle | Prior bull peak | Observed cycle low (EX POST) | How treated |
|---|---|---|---|
| 2014/15 | 4 Dec 2013 | 14 Jan 2015 | Listed, but the V5.9 reconstructed risk-matched market cohort is unavailable prior to 2017. Do not invent a risk baseline. |
| 2018 | 17 Dec 2017 | 15 Dec 2018 | Independent COMPLETE historical major bear-cycle episode |
| 2022 | 8 Nov 2021 | 9 Nov 2022 | Independent COMPLETE historical major bear-cycle episode |
| 2026 | 6 Oct 2025 (candidate) | *Unconfirmed* | Right-censored and never called a confirmed bottom |

**March 2020 is an exceptional COVID-driven shock**, not a new independent
four-year bear cycle bottom. The PR #263 2020 run remains an isolated stress
scenario, not one of the independently counted four-year market bottoms.
2023 WMA recrossings belong to the **2022 broad cycle**, not extra
independent four-year cycles.

## Two very different clocks

**Causal rule (tradable in principle):** prior-Sunday BTC/USD closed crossing
down into <=105% of completed 200-week Sunday moving average, **after the
previous Sunday was above**; buy BTC/AUD reference at the next Monday close.
For each broad cycle the earliest eligible such crossing between the
preceding peak and retrospective trough is used for the historical report.
This near-WMA threshold was introduced after other historical research and
has selection bias. The retrospective boundary helps *label* episodes,
not signal a live bottom.

**Oracle rule (never tradable as defined):** start 17/20-week buying on the
Monday after the actual future-proven low. Such dates cannot be known at
the time; this is only a hindsight ideal to measure how early the moving
average might fire relative to the true bottom.

Each entry cohort has 104 consecutive following Monday price-proxy
observations, actual dated BTC/AUD public proxy quotes, illustrative 5%
pretax cash return, A$3 brokerage, .30% friction, .25% annual BTC ETF-style
drag, **no leverage**, and the original capped A$25,500/week allocation.
Reported 17-week full A$500,000 is *illustrative and cap-noncompliant*;
the 20-week A$25,000/week version is permissible under the cap. Both
fresh A$500k and virtual 41%-existing-BTC / A$510k account cases are
replayed. No historical fake Stake or ASX:IBIT executions.

**Limits:** only TWO mature major cycles in the same-model comparable
sample, and those have very different market conditions. A median of two
events offers no statistically reliable forecasting edge. 2015 can be
independently examined for price-only accumulation with an older source,
but must not be scored against missing R2 risk. 2026/27 results can only
mature later using timestamped forward observations, without relabeling
June 2026 as an established irreversible bottom.

## Execution

```bash
python -m unittest discover -s tests -p 'test_v59_four_year_bottoms.py' -v
python -m engines.research.v59_causal_timing_horse_race --out artifacts/v59_buy_timing_horse_race.json
```

Detailed `major_bear_cycle_bottom_audit.cycles` retained in the
research-only scheduled weekly horse-race GitHub Actions artifact.
No changes to Production V5.8.2, live V5.9, Cycle Trading, ntfy,
portfolio, positions or cash/selling calculations.

## Completed real-history results (12 November 2026)

GitHub Actions: [causal history and unit tests](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/43217517898),
[research regression tests](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/43217517979).
Both completed successfully following field-name test correction.
Numerical values below come from actual `CYCLE_MAJOR_BOTTOM` GitHub Actions
records, not manually selected price anecdotes.

**Only TWO completed mature matched V5.9 comparison cycles (2018 and 2022).**
2015 has no verified reconstructed V5.9 risk cohort under this runner;
2026 has no 104-week future and its ultimate cycle trough is unconfirmed.
2020 COVID is **excluded** from the major-cycle sample.

### Fresh A$500,000, 5% idle cash, A$25,500 cap

| Broad cycle | Ex-ante near +5% WMA signal Sunday | Ex-post observed trough date | Causal signal vs eventual trough | 20-week capped DCA BTC at week 104 | V5.9 strict <=0.20 BTC at week 104 | 20-week capped total AUD portfolio at week 104 | V5.9 strict AUD portfolio at week 104 |
|---|---|---|---|---:|---:|---:|---:|
| 2018 | 2018-12-16 | 2018-12-15 | +1 day | **88.9173** | **67.2197** | **A$2,326,962** | A$1,757,901 |
| 2022 | 2022-06-19 | 2022-11-09 | **−143 days** | **16.1762** | **15.7310** | **A$1,694,530** | A$1,645,354 |

Same starting dates, costs, 104-week marks and cash yield within each
cycle. 20 equal calendar buys of A$25,000 fully deploy A$500,000 regardless
of whether BTC subsequently leaves the 200WMA neighborhood; the original
risk-gated V5.9 policy may stagger capital over the entire 104 weeks.

### Explicit EX-POST bottom-date oracle (NOT A TRADING STRATEGY)

If the first 20-week DCA begins on the first Monday *after the known
historical bottom* (not possible in advance):

| Cycle | Hindsight first Monday | 20-week fixed DCA BTC at 104 weeks | V5.9 strict BTC at 104 weeks from that same hindsight start |
|---|---|---:|---:|
| 2018 | 2018-12-17 | 88.9173 | 67.2197 |
| 2022 | 2022-11-14 | 16.9466 | 14.0104 |

Comparing 16.9466 versus 16.1762 BTC across two **different start dates**
is a retrospective timing illustration, not a fair same-start trading
strategy comparison; terminal dates also differ. This is the limited
meaning of a 'perfect bottom' benchmark.

### With virtual 41% already invested in BTC (A$510k reference portfolio)

These are NOT historic user holdings. The 2018 or 2022 virtual BTC balance
was marked at the starting historical reference price, then remaining
A$300,900 was deployed. The 17-week calendar schedule A$17,700/week is
within the A$25,500 limit for this particular split.

| Cycle near-WMA signal | 17-week accelerated model BTC at week 104 (includes virtual existing) | V5.9 strict <=0.20 BTC at week 104 (includes virtual existing) | 17-week accelerated AUD portfolio value | V5.9 strict AUD portfolio value |
|---|---:|---:|---:|---:|
| 2018 | **101.7005** | 86.3560 | A$2,658,402 | A$2,256,678 |
| 2022 | **16.8381** | 16.5271 | A$1,761,274 | A$1,727,645 |

**Summary:** Early WMA proximity almost coincided with the 2018 low, but
in 2022 it preceded the eventual trough by **143 days**. Fast DCA was
retrospectively successful in both of these rising 104-week follow-through
windows, but with only two distinct mature market cycles and much earlier
deployment there is **no credible proof** that it will outperform
in a new bear market, particularly if BTC keeps declining. The 2020
event is a valid *separate shock sensitivity*, not a third independent
four-year bottom.

Research next step: hard-code a 2026+ forward-only first near-WMA
signal, add independent 20/35/50% further-fall stress with the same
capital-at-risk, and record actual later ASX:IBIT quotes before
considering changed Production behaviour.
