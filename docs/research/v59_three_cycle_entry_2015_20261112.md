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

## Verified numerical findings — GitHub Actions 12 November 2026

**Source:** [actual public BTC/AUD historical job and causal tests](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/43221044239). Both real-source calculation and unit tests **passed**. Research DCA regression checks also passed. The complete dated outputs are in the `research-v59-timing-horse-race-report` JSON Actions artifact (key: `three_cycle_price_only_entry`).

### Data-coverage and signal audit

| Cycle | Real prior halving | Common calendar from | Common terminal | First verified prior-Sunday ≤+5% WMA signal | Days since halving at signal | Valid for original V5.9 R2 head-to-head |
|---|---|---|---|---|---:|---|
| 2014_15 | 2012-11-28 | 2015-01-05 | 2016-06-20 | 2015-01-18 | 781 | No — price/FX only |
| 2018 | 2016-07-09 | 2018-03-05 | 2020-02-03 | 2018-12-16 | 890 | Yes — reconstructed R2 |
| 2022 | 2020-05-11 | 2022-01-03 | 2023-12-04 | 2022-06-19 | 769 | Yes — reconstructed R2 |
| 2026 | 2024-04-20 | 2025-12-15 | 2027-11-15 | Unconfirmed | N/A | No, future unavailable |

The actual public BTC archive only furnished a completed **200-Sunday WMA**
from early January **2015**; the first research paper Monday in 2015 was
**5 January 2015**, after the intended first halving+600 Monday in July 2014.
This is a **left-truncated common history** (not the entire bear market).
The 2015 first +5% proximity signal was **18 January 2015**, **four days
after** the hindsight low of 14 January. The 2018 signal (16 Dec)
was one day after its hindsight low (15 Dec). In contrast the
**19 June 2022** signal was **143 days BEFORE** the 9 Nov 2022
retrospective reference low. Both bottom references are hindsight-only;
they never choose live entry dates.

### BTC accumulated, A$500,000 fresh cash

BTC units marked at a *common halving+1300 calendar terminal within
each cycle* after indicative 0.25% annual BTC holding drag. All policies
start from exactly A$500k cash at the earliest supported phase date,
respect the A$25,500 weekly cap, and accrue nominal 5% cash interest.
**Do not compare absolute BTC counts across different decades.**

| Price-only policy or comparable R2 model | 2015 BTC (20 Jun 2016) | 2018 BTC (3 Feb 2020) | 2022 BTC (4 Dec 2023) |
|---|---:|---:|---:|
| Near 200WMA +5%, 20 × A$25k | 1,616.13 | 89.11 | 16.20 |
| Near 200WMA +5%, 25 × A$20k | 1,607.59 | 80.53 | 16.81 |
| Staged; accelerate after an additional 20% fall | 1,612.16 | 79.16 | 16.82 |
| Staged; accelerate after an additional 35% fall | 1,612.16 | 79.16 | 16.82 |
| Halving day ≥800 AND near 200WMA +5% | 1,462.67 | 89.11 | 16.86 |
| Halving day ≥800 ONLY, no WMA condition | 1,605.56 | 78.05 | 16.86 |
| 20 buys only while Sunday ≤WMA+5% | 789.41 | 5.48 | 16.24 |
| Hold 5% AUD cash | 0.00 | 0.00 | 0.00 |
| Research V5.9 aggressive risk-based DCA | N/A | 83.60 | 16.11 |
| Research V5.9 strict risk ≤0.20 | N/A | 84.96 | 16.18 |

### Total portfolio value, including remaining interest-bearing AUD

| Policy | 2015 final value | 2018 final value | 2022 final value |
|---|---:|---:|---:|
| Near 200WMA +5%, 20 × A$25k | A$1,667,005 | A$1,263,971 | A$996,265 |
| Near 200WMA +5%, 25 × A$20k | A$1,659,465 | A$1,145,952 | A$1,034,694 |
| Staged; accelerate after an additional 20% fall | A$1,664,708 | A$1,127,476 | A$1,035,924 |
| Staged; accelerate after an additional 35% fall | A$1,664,708 | A$1,127,476 | A$1,035,924 |
| Halving day ≥800 AND near 200WMA +5% | A$1,519,096 | A$1,263,971 | A$1,038,984 |
| Halving day ≥800 ONLY, no WMA condition | A$1,657,624 | A$1,104,332 | A$1,038,984 |
| 20 buys only while Sunday ≤WMA+5% | A$1,087,679 | A$598,818 | A$999,050 |
| Hold 5% AUD cash | A$536,825 | A$549,009 | A$549,009 |
| Research V5.9 aggressive risk-based DCA | N/A | A$1,162,165 | A$973,850 |
| Research V5.9 strict risk ≤0.20 | N/A | A$1,181,097 | A$978,029 |

### Did the staged model actually respond to falling prices?

**No, not in these three historical entry cohorts.** Both the 20%
and 35% additional-drop variants have **no active threshold-triggered
acceleration** while buying. Their equal historical outcomes arise
from a slower first eight weeks followed by ordinary purchasing,
not from successful extra-drop identification.

| Cycle | First 20% extra-drop acceleration signal | First 35% extra-drop acceleration signal |
|---|---|---|
| 2014_15 | None | None |
| 2018 | None | None |
| 2022 | None | None |

This distinction is central: **the staged historical gains cannot
be claimed as predictive bottom detection.** The extra-drop rules
are still useful to stress-test financial protection if a future
signal turns out early.

### With virtual existing BTC exposure: A$510k, 41% BTC / 59% cash

The model creates the same **virtual** 41% BTC position at each historical
phase start, then spends from the remaining ~A$300,900 cash.
This is **not** a reconstruction of the user's real 10,250 IBIT shares,
and 2015 IBIT never traded.

| Cycle | 20-week near-WMA: total BTC units | Staged after extra-drop: total BTC | V5.9 strict ≤.20: total BTC |
|---|---:|---:|---:|
| 2014_15 | 1,614.93 | 1,612.52 | N/A |
| 2018 | 67.62 | 61.64 | 65.15 |
| 2022 | 12.94 | 13.31 | 12.92 |

### Explicit 20% / 35% / 50% synthetic false-bottom stress (A$500k fresh cash)

At the initial +5%-WMA trigger, BTC drops linearly for 12 weeks and
then remains depressed or returns to the starting price by week 24.
**The WMA is held fixed**, so this is a funding/path-stress simulation,
not a recalibrated forecasting or model-signal exercise.

| Artificial path | Near WMA, 20 equal weeks (BTC) | 25 equal weeks (BTC) | Staged, 20% later fall (BTC) | Staged, 35% later fall (BTC) |
|---|---:|---:|---:|---:|
| flat | 3.47 | 3.47 | 3.47 | 3.47 |
| rally_25pct | 2.99 | 2.95 | 2.90 | 2.90 |
| fall_20pct_then_stay_low | 4.04 | 4.10 | 4.17 | 4.17 |
| fall_35pct_then_stay_low | 4.66 | 4.79 | 4.92 | 4.95 |
| fall_50pct_then_stay_low | 5.58 | 5.86 | 5.96 | 6.15 |
| fall_20pct_then_recover | 3.93 | 3.86 | 3.91 | 3.91 |
| fall_35pct_then_recover | 4.38 | 4.24 | 4.39 | 4.35 |
| fall_50pct_then_recover | 5.00 | 4.76 | 5.06 | 4.98 |

A separate +25% rally and flat control were included because waiting
for another dip creates a **missed-rally opportunity cost**.
For example, in the rally case the 20-week scheme acquired
2.99 BTC,
while the more cautious staged 20%-drop plan acquired
2.90 BTC.

Under a further 50% decline that **stays low**, the 20-week base
would leave total illustrative portfolio value at **A$403,664** versus
**A$445,705** for the
35%-drop staged plan; this does not guarantee a better outcome in
real crashed markets where the moving average and risk would also move.

### Research decision

- **2015 is now numerically included** on valid historical price/FX
  inputs, rather than omitted. V5.9 Research is still **unavailable
  for a like-for-like 2015 comparison**; never invent those scores.
- On same-calendar retrospective cohorts, early 20-week buying
  performed well in 2015/2018, slower buying did better in 2022.
  This mostly reflects **when money was deployed**, not proof that
  the moving average forecast the subsequent bottom.
- Halving day 800 alone is not consistently better than the valuation
  gate. Neither these three selected cycles nor synthetic paths
  justify picking a single promoted threshold.
- Keep **Production V5.8.2, Research V5.9 live recommendation,
  Cycle Trading, single daily ntfy, portfolio and Stake unchanged**.
  The study is now part of the existing **automatic weekly research**
  workflow. Continue actual future-date forward capture to determine
  whether any candidate genuinely improves results.
