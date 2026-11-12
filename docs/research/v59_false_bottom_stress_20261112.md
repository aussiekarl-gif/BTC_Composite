# Follow-up to PR #259: false-bottom exposure and timing skill — 12 November 2026

**RESEARCH ONLY — do not alter live sizing, Production, Cycle Trading or ntfy.**
This is a pre-results protocol. The machine-readable historical and synthetic
results will be retained in the existing causal horse-race Actions artifact under
`false_bottom_stress`, and the Actions log will print `FALSE_BOTTOM_*` entries.

## Questions

1. When prior-Sunday V5.9 reconstructed WF risk first crosses into <=0.20,
   how often does real BTC/AUD fall a further 20%, 35% or 50% over 12 weeks?
2. Does delayed confirmation or staged buying improve **final BTC + AUD cash**
   versus the PR #259 strict <=0.20 three-times policy on identical paths?
3. Do staged policies actually obtain better average entry prices or merely
   leave more cash untouched? What if BTC rallies without another dip?

## Frozen method before inspecting follow-up outcomes

- Reuse the **exact same public BTC/USD, AUD/USD, WF risk, prior-Sunday signal and
  next-Monday price-proxy input** from `v59_causal_timing_horse_race.py`.
- 104 consecutive weeks; 2017–24 Jan/July cohorts, six 2022–24 historical
  holdouts, explicitly overlapping. No extra independent market cycles.
- Same 41% initial BTC / 59% cash, A$510,000 reference capital, 5% nominal
  annual compounded idle-cash yield, A$3 commission, 0.30% buy spread and
  slippage, 0.25% annual BTC ETF proxy drag, and A$25,500 weekly cap.
- Each policy is fully self-financing, with no sales, borrowing or forced
  deployment. All purchases use Sunday information; a price-drop trigger
  uses **the preceding Monday reference**, never the current Monday fill.
- Keep PR #259 1x, full 3x, and <=0.20 strict 3x unchanged as controls.
  New locked candidates: two- and four-week consecutive risk<=0.20
  confirmation; start 1x, switch to model-based up-to-3x only after a
  **lagged** 10% or 20% decline since the first cheap Monday; start 2x,
  switch to up-to-3x after lagged 10% decline; and risk<=0.20 plus a
  past-year drawdown of at least 25%.
- Price-selection diagnostic: compare the **same total net invested dollars**
  as each policy spread equally across all 104 available execution weeks.
  This uses hindsight total deployment ONLY for price-attribution research,
  **not** a usable buy recommendation; it removes aggregate exposure
  differences for the BTC units comparison but not all funding/fee effects.
- A 12-week *observed subsequent drawdown* episode study begins on first
  <=0.20 week after >0.20, with at least 26 weeks between retained starts;
  these observations are not independent and are **ex post outcomes**.
- Deterministic adverse paths: BTC falls 20%, 35% or 50% across the first
  12 weeks then either stays low or recovers by week 24. Also flat and a
  25% rise. Low risk is **artificially held at 0.05 for 16 weeks** and then
  changed to 0.70; risk is NOT recomputed for shocked prices, so these are
  funding/path stress tests only, not empirical risk-model forecasts.
- Report median / worst holdout portfolio-value differences, drawdown changes,
  cash deployed, timing-vs-uniform price quality, and individual cohorts.
  Avoid choosing a single winner from six correlated cohorts.

## Critical limitations

The WF model's historical parameter choices and publication vintages were not
independently frozen at those past dates; all studies remain retrospective and
subject to selection bias. Monday UTC BTC/AUD prices are **not** actual
ASX:IBIT fills, taxes or guaranteed AAA distribution income. The synthetic
risk path deliberately does not reflect how V5.9 would behave in a crash.
No improvement merits live promotion without time-stamped prospective
validation and practical ETF execution testing.

## Reproduction

```bash
python -m unittest discover -s tests -p 'test_v59_causal_timing_horse_race.py' -v
python -m engines.research.v59_causal_timing_horse_race \
  --out artifacts/v59_buy_timing_horse_race.json
```

The result JSON contains `false_bottom_stress.historical`,
`false_bottom_stress.cheap_signal_episode_study`, and
`false_bottom_stress.synthetic_fixed_risk_stress`.

**No portfolio records, live recommendations, notification logic or trades are written.**

## Completed GitHub Actions research results — 12 Nov 2026

- [Actual-history + unit-test workflow](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/43200888580): **success** (both jobs).
- [Research DCA regression workflow](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/43200888716): **success**.
- Historical inputs: **515** matched weekly executions, **16** completed 104-week cohorts (six later overlapping historical holdouts).
- All tables below are computed from the actual `FALSE_BOTTOM_*` log output in run `43200888580`; not hypothetical or estimated backtest scores.

### Six later historical holdouts, existing 41% BTC, 5% cash yield

Value differences are compared to strict 3x at prior-Sunday R2 risk <=0.20
with identical 104-week valuation dates. Worst means lowest cohort excess
return. Positive extra drawdown (pp) means **less** drawdown than reference.
The price-selection diagnostic compares acquired undragged BTC units against
the **same net executed buying dollars** spread equally over every cohort week;
total dollars were known only after the simulation, so this is NOT investable.

| Policy | Median final value vs strict 3x | Worst | Wins | Median extra drawdown | Median total deployed / original A$510k | Price-selection vs uniform same-net-spend |
|---|---:|---:|---:|---:|---:|---:|
| 1x gate <=0.50 | -10.03% | -12.91% | 1/6 | 1.81 pp | 62.2% | 4.8% |
| Full 3x gate <=0.50 | +0.05% | -1.53% | 3/6 | -0.45 pp | 60.8% | 25.3% |
| Strict 3x gate <=0.20 (reference) | 0.00% | 0.00% | 0/6 | 0.00 pp | 59.4% | 25.8% |
| Strict gate, wait 2 cheap weeks | -0.80% | -2.20% | 1/6 | 0.40 pp | 58.8% | 26.0% |
| Strict gate, wait 4 cheap weeks | -1.61% | -5.31% | 2/6 | 1.27 pp | 57.6% | 26.6% |
| Strict gate, 1x then 3x after 10% fall | -2.75% | -13.51% | 2/6 | 2.19 pp | 52.7% | 20.5% |
| Strict gate, 1x then 3x after 20% fall | -8.64% | -16.16% | 2/6 | 3.07 pp | 47.7% | 17.3% |
| Strict gate, 2x then 3x after 10% fall | -1.13% | -4.62% | 2/6 | 0.59 pp | 58.5% | 25.1% |
| Strict gate plus 25% prior-year drawdown | -6.00% | -29.39% | 0/6 | 2.56 pp | 39.9% | 14.7% |

### Real-market low-risk episodes

There were **7** separated (but not statistically
independent) <=0.20 crossings with a fully observed following 12-week window.
**3/7** subsequently fell at least
20%, **1/7** fell at least 35%,
and **0/7** fell at least 50%.
The worst observed episode was **-37.3%** from the
initial entry proxy; episode selection and reconstructed scores may bias
the apparent frequency. Neither 3/7 nor 1/7 is a forward probability.

### Artificial fixed-risk scenario outcomes

Risk is manually 0.05 for 16 weeks and 0.70 afterwards; BTC prices
decline linearly over 12 weeks and either stay at their low or recover.
These results measure liquidity/funding stress, not V5.9 forecast skill.

| Path | 1x then 3x on -20%: value difference | 1x then 3x on -10%: value difference | 2-week confirmation: value difference | 1x/-20%: BTC units difference |
|---|---:|---:|---:|---:|
| flat | +1.42% | +1.42% | +0.12% | -22.35% |
| rally_25pct | -0.06% | -0.06% | -0.21% | -20.69% |
| fall_20pct_stay_low | +2.75% | +1.80% | +0.43% | -17.90% |
| fall_35pct_stay_low | +3.32% | +2.23% | +0.72% | -8.90% |
| fall_50pct_stay_low | +3.94% | +2.71% | +1.05% | -5.29% |
| fall_50pct_then_recover | +0.79% | +0.74% | +0.37% | -5.55% |

**Interpretation:** The staged 1x/-20% scheme protects more AUD cash in
flat or prolonged falling paths, but commonly accumulates **fewer** BTC units
and missed considerable historical appreciation. Positive total portfolio
values during a crash can be caused by **lower exposure**, not superior
purchase prices. Under a -50% fall that subsequently fully recovers, staged
1x/-20% beat strict 3x by only **+0.79%**
while holding **-5.55%**
fewer simulated BTC units. Values of 5% interest, all costs and implied ETF
holding drag are illustrative.

**Research decision:** There is no convincing basis to replace the
strict <=0.20 3x *research candidate*. Current risk<=0.50 live policy
remains unchanged. Do not optimize to these six overlapping
holdouts; prospectively capture time-stamped risk, actual ASX:IBIT quotes and
broker spreads, and evaluate forward performance before any promotion.
