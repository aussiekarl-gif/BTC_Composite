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

Both workflow checks passed on the **corrected cohort/episode code**:
[causal timing unit and actual-history run](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/43201427368)
and [Research DCA regression](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/43201427388).
Results below were extracted directly from the successful job logs. The
complete numerical JSON (including individual holdout records and stress
paths) is stored in the `research-v59-timing-horse-race-report` Actions artifact.
PR #259 base numerical controls have parity regression tests.

### Historical holdout outcomes (41% BTC already held; 5% idle AUD return)

515 matched prior-Sunday -> Monday historical observations; 16 complete
104-week cohorts, including six **overlapping** 2022–24 historical holdouts.
All final value percentages are relative to 3x only for risk <=0.20.

| Policy | Median total-value gap | Worst cohort gap | Positive / 6 | Median drawdown change | Median deployed / original capital | Timing-only diagnostic vs equal-week same-net-spend |
|---|---:|---:|---:|---:|---:|---:|
| 1x gate <=0.50 | -10.03% | -12.91% | 1/6 | 1.81 pp | 62.2% | 4.8% |
| 3x gate <=0.50 | +0.05% | -1.53% | 3/6 | -0.45 pp | 60.8% | 25.3% |
| 3x <=0.20 reference | 0.00% | 0.00% | 0/6 | 0.00 pp | 59.4% | 25.8% |
| Wait 2 cheap weeks | -0.80% | -2.20% | 1/6 | 0.40 pp | 58.8% | 26.0% |
| Wait 4 cheap weeks | -1.61% | -5.31% | 2/6 | 1.27 pp | 57.6% | 26.6% |
| 1x then 3x after prior 10% fall | -2.75% | -13.51% | 2/6 | 2.19 pp | 52.7% | 20.5% |
| 1x then 3x after prior 20% fall | -8.64% | -16.16% | 2/6 | 3.07 pp | 47.7% | 17.3% |
| 2x then 3x after prior 10% fall | -1.13% | -4.62% | 2/6 | 0.59 pp | 58.5% | 25.1% |
| Strict plus past-year drawdown <=-25% | -6.00% | -29.39% | 0/6 | 2.56 pp | 39.9% | 14.7% |

A positive drawdown change means **less** negative drawdown. The same-total
net-spend BTC comparison is **hindsight matched**: the net dollars ultimately
invested are evenly spread over the entire evaluation cohort, which removes
total net expenditure differences for entry-price diagnosis. It is not a
usable causal trading strategy, does not include the idle-cash earning-time
effect, and remains sensitive to vintage/selection bias. Deployment can
exceed 59% of original A$510k because accrued cash interest may also be bought.

### Follow-through after observed low-risk threshold crossings

**7** risk transitions from an actually observed >0.20
Sunday to <=0.20 on the following *contiguous* weekly signal were eligible,
with a 26-week episode separation and a full **12 consecutive** subsequent
execution weeks. **2/7** fell at least 20%
after initial Monday proxy entry, **1/7**
at least 35%, and **0/7** at least 50%.
The most severe subsequent excursion was
**-37.28%**.
This corrects the earlier left-censored first-week counting error.
Observations are few and not independent; these are not forecast probabilities.

### Synthetic false-bottom path results

BTC price moves linearly down 20%, 35% or 50% over 12 weeks, then either
stays depressed or recovers within 12 weeks; plus flat and rising paths.
R2 risk is **artificially** set to 0.05 for 16 weeks and 0.70 thereafter,
not recomputed for the manipulated prices. Every strategy respects the
A$25,500 weekly cap, 5% cash yield, 41% existing BTC, trading friction
and no leverage.

| Path | Stage 1x then 3x on -20%: total value gap | Stage 1x then 3x on -10%: total value gap | Confirm 2w: total value gap | Stage 1x/-20%: BTC unit gap |
|---|---:|---:|---:|---:|
| flat | +1.42% | +1.42% | +0.12% | -22.35% |
| rally_25pct | -0.06% | -0.06% | -0.21% | -20.69% |
| fall_20pct_stay_low | +2.75% | +1.80% | +0.43% | -17.90% |
| fall_35pct_stay_low | +3.32% | +2.23% | +0.72% | -8.90% |
| fall_50pct_stay_low | +3.94% | +2.71% | +1.05% | -5.29% |
| fall_50pct_then_recover | +0.79% | +0.74% | +0.37% | -5.55% |

**Finding:** Staged 1x/-20% schemes may protect value by retaining more
cash in prolonged declines, but consistently bought less BTC in these fixed-risk
stress cases. In the 50% crash/recovery simulation the 1x/-20% scheme
changed final portfolio value by **+0.79%**
versus strict 3x while ending with **-5.55%**
BTC units. That is **cash exposure protection**, not proof of more effective
bottom-price timing.

**Decision:** None of these new delays or staged gates robustly beats the
strict <=0.20 3x *research candidate* on historical total portfolio value.
Keep all live Production V5.8.2, Research V5.9, Cycle Trading and ntfy logic
unchanged. The most useful next test is genuinely forward-dated risk
snapshots paired with timestamp-matched ASX:IBIT quotes, spreads and observed
later drawdowns, rather than refining thresholds on the same cycles.
