# Three BTC bear cycles (2014–15, 2018, 2022): valuation and halving timing
**Research-only protocol — 12 November 2026. This protocol precedes the new GitHub Actions numerical run.**

## Main problem

Can a **causal** BTC/USD 200-week moving-average valuation entry combined with
a known halving age outperform fixed accelerated DCA, including the
2014–15 bear market? Can it withstand another 20–50% post-signal decline?

This deliberately corrects the limitation of PR #264: the 2015 bottom
was identified but excluded from numeric comparisons due to unavailable
reconstructed V5.9 R2 historical signals. We will include 2015 using
**real historical BTC/USD and AUD/USD price/FX observations only**, with
V5.9 risk baselines marked **unavailable**, NOT faked.

## Three historically completed cycle groups

- Prior halving **28 Nov 2012** → January **2015** bear bottom
- Prior halving **9 Jul 2016** → December **2018** bear bottom
- Prior halving **11 May 2020** → November **2022** bear bottom
- 20 Apr 2024 → 2026/27 episode is **unconfirmed and right-censored**;
  no artificial future prices or scores. 2020 COVID is an additional
  **separate crash**, NOT a distinct four-year cycle for counting results.

True bottom dates are **ex post context only**, NEVER used to choose
purchase weeks.

## Frozen pre-results method

- **Actual** Blockchain.com historical BTC/USD daily prices from the
  existing research runner, including 2011 warmup if available; public
  Frankfurter AUD/USD fixing dated **no later than prior Sunday**.
- For a Monday paper fill, the gate uses ONLY the **preceding Sunday**
  BTC price and **200 prior/completed Sunday closes**. A missed Sunday
  creates an empty MA window, NEVER a fabricated Saturday substitute.
- Start comparing all strategies on the **same first Monday after
  halving day 600**, end on the same first Monday after halving day 1300.
  **2015 may need an explicitly flagged left-truncated common start** if
  the full 200-week MA did not yet exist at day 600. Every policy in that
  cycle then shares this smaller observable calendar.
- WMA valuation gate: first Sunday BTC/USD at or below **1.05 × completed
  200WMA** after halving day **600** (the previously existing 600–1200
  phase context). The +5% threshold was already examined historically,
  so **not a novel independent holdout**.
- A separate gate waits until **halving day 800** AND the same <=+5%
  WMA valuation: explicit sensitivity, chosen after past cycles and NOT
  a prevalidated predictor.
- **Daily-price-only comparators across all three cycles:** 20 equal
  calendar buys of A$25,000 on qualifying trigger; 25 calendar buys
  of A$20,000; phase age-800 only 20×A$25k; 20 purchases only while
  <=+5% 200WMA (may leave cash unspent); and two staged strategies:
  cautious A$12,500/week for the first eight eligible weeks then
  A$25,000/week, *accelerating to the A$25,500 cap* if the **prior
  Sunday close** is 20% / 35% below the first entry's Sunday price.
  No reading Monday's trade price into the decision.
- **V5.9 R2 risk3 and strict <=0.20 only in 2018 and 2022**, where
  correctly reconstructed validated WF risk exists on ALL corresponding
  Monday rows. Historical 2015 R2 model scores are **not available**
  under this matched framework. Do not compare against a made-up 2015
  V5.9 policy.
- Starting **A$500,000 fresh cash**, also sensitivity A$510,000 portfolio
  with 41% *virtual* prior BTC / 59% new cash. No false real holdings.
  The original **A$25,500 maximum weekly** applies to all candidates.
  Idle AUD cash returns 5% annually compounded **pretax**; A$3/fill,
  illustrative 0.30% execution friction and 0.25% annual BTC wrapper drag.
  No leverage, sales, forced deployment, actual ASX:IBIT fills or taxes.
- Report final BTC held, cash left, terminal AUD equity, terminal
  BTC-equivalent if cash converted, total spend, first/last signal,
  drawdown. For each market cycle, all strategies share the same
  phase-1300 terminal, removing shifting-valuation-date distortions.

## Further-fall stress

Deterministic synthetic -20%, -35%, -50% BTC declines over 12 weeks
after a hypothetical initial value signal, with a stay-low or
full-recovery variant. Compare fixed 20/25-week, staged on deeper
discount, and proximity-only buying with **fixed WMA reference
held constant**. This is **funding/drawdown stress only**, not a
forecast of how V5.9 risk or true WMA would change in a crash.

## Important validity limits

Three different early BTC markets are not a statistically reliable
modern forecast. Historical BTC prices, early-2015 Sunday closure,
2015 market liquidity and variable FX matter significantly. IBIT
did not exist; no historical fills from Stake exist. 2015 inclusion
does not provide a new independent *held-out* cycle because 2015 is
known when these rules are being designed. **A historical increase
in BTC units may be entirely explained by deploying cash earlier**,
not superior bottom-picking. Observe actual forward outcomes before
any promotion. Production V5.8.2, live V5.9, Cycle Trading, weekly
schedule, daily ntfy, and portfolio remain unchanged.

## Reproducibility

```bash
python -m unittest discover -s tests -p 'test_v59_three_cycle_entry.py' -v
python -m engines.research.v59_causal_timing_horse_race --out artifacts/v59_buy_timing_horse_race.json
```

The existing weekly scheduled read-only GitHub workflow embeds the
full `three_cycle_price_only_entry` JSON record and logs
`THREE_CYCLE_CONTEXT`, `THREE_CYCLE_OUTCOME`, `THREE_CYCLE_SHOCKS`.
No added ntfy messages.
