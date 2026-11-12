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
