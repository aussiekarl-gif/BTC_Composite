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
