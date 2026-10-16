# Isolating the actual benefit from BTC Dynamic DCA weighting

**16 October 2026 · RESEARCH ONLY · No Production changes.**

* [Validated GitHub historical run #38883104463](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38883104463)
* [Execution-weighting engine](../../engines/research/adaptive_weighting_attribution.py)
* [Deterministic VWAP unit tests](../../tests/test_adaptive_weighting_attribution.py)
* [Underlying risk/price-triggered variable-length DCA](../../engines/research/adaptive_dca_execution.py)
* PR #90 is draft: https://github.com/aussiekarl-gif/BTC_Composite/pull/90

## Question and controlled comparison

The previous A$100,000 plus A$100,000 example did **not** reflect
Dynamic DCA. This experiment explicitly attributes observed improvements
to **how much BTC is bought or sold on each actual fill date**.

For **each** existing 2016–2026 trade leg, all orders are fixed on the
**same dates** and the number of A$3 fees is exactly the same:

- BUY comparison: Keep the total AUD spent in that leg unchanged;
  redistribute it equally across all observed buying dates. Calculate
  `total AUD spent / total BTC acquired` for actual dynamically
  weighted and equal-cash date distribution. No arithmetic mean of
  per-trade BTC prices is used.
- SELL comparison: Keep the total BTC quantity disposed unchanged;
  distribute equal BTC quantities across each observed selling date.
  Compare `total net AUD received / total BTC disposed`.
- Actual dynamically weighted trades use risk, AUD prices and 20/50-week
  trends observed the **previous** week. No future trough/peak enters
  these trades. The *equal weighting* inside an already completed leg
  is retrospective normalization and is **NOT a separate self-financing
  portfolio backtest**: the future number of fills would not have been
  known in real time.
- Each actual order incurs A$3. No effective-fee double counting.
- Underlying historical master risk-score point-in-time availability
  **has not been established**. Past signal rules are heavily in-sample.
- Scoring against ex-post time-ordered local reference high/low occurs
  **after** simulation. A pair is eligible only if all future 26-week
  reference prices were observable by the dataset endpoint. Same
  reference intervals used for both sets of weights.

## Results: 557 weekly paired BTC/AUD source rows, Jan 2016–Aug 2026

This is the 10% drawdown + trailing 20WMA confirmation **research
candidate**, NOT a vetted recommendation.

| Metric | Result |
|---|---:|
| Actual purchase legs with a dynamic advantage over equal AUD per date | 5 / 7 |
| Actual sale legs with a dynamic advantage over equal BTC per date | 1 / 6 |
| Median buying BTC-per-AUD advantage from dynamic weighting | +3.955% |
| Median selling AUD-per-BTC advantage from dynamic weighting | 0.000% |
| Mean buying BTC-per-AUD advantage across 7 legs (unweighted) | +4.529% |
| Mean selling AUD-per-BTC advantage across 6 legs (unweighted) | +0.417% |
| Filled original adaptive orders | 322 |
| Original before-CGT dynamic strategy end equity A$ | 305,789,901 |

The original A$305.79m account is the full-history continuous account
started from A$500k in **2016**, **NOT** the equal-weight benchmark and
**NOT** a plausible return expectation for A$500k invested in 2026.

### One-page threshold comparison (same five eligible historical pairs)

| Execution error target on BOTH sides of each cycle | Actual dynamic weighting | Equalized weights |
|---|---:|---:|
| 15% | 2 / 5 | 2 / 5 |
| 20% | 2 / 5 | 2 / 5 |
| 25% | **3 / 5** | **2 / 5** |
| 35% | 4 / 5 | 3 / 5 |

For the five completed eligible historical pairs:

- Dynamic SELL average error from local reference highs: **15.6%**,
  unweighted mean of 21.941%, 4.722%, 46.382%, 0%, 5.082%.
- Equal-weight SELL mean error: **16.2%**.
- Dynamic BUY mean error from local reference lows: **19.2%**,
  unweighted mean of 12.614%, 28.942%, 41.296%, 9.251%, 3.857%.
- Equal-weight BUY mean error: **25.7%**.

**Caveat:** the average per-cycle error can look good while an important
cycle is much worse. User's 25% target for each cycle's average fill
price should be reported together with tail/missed-cycle risk.

### Representative actual weighted-price versus equal-weight price

All BTC prices expressed in historic AUD and based on exactly the
same execution dates and notional units within the leg:

| Leg (start) | Side | Dynamic effective AUD/BTC | Equalized effective AUD/BTC | Dynamic improvement |
|---|---|---:|---:|---:|
| 2016-01-11 | BUY | 582.02 | 717.50 | +23.28% BTC/AUD |
| 2018-02-12 | SELL | 11,605.10 | 10,189.83 | +13.89% AUD/BTC |
| 2018-12-10 | BUY | 5,094.15 | 5,734.71 | +12.57% BTC/AUD |
| 2019-10-14 | BUY | 11,248.73 | 13,009.07 | +15.65% BTC/AUD |
| 2021-05-24 | SELL | 47,659.23 | 53,751.77 | **−11.33% AUD/BTC** |
| 2022-05-30 | BUY | 34,453.37 | 32,840.06 | **−4.68% BTC/AUD** |
| 2024-07-08 | BUY | 90,071.63 | 93,633.79 | +3.95% BTC/AUD |
| 2025-11-24 | BUY | 130,650.34 | 104,898.50 | **−19.71% BTC/AUD** |

The 2025–2026 associated roundtrip is **not fully scorable** because
the dataset ends before the 26-week following oracle window. The leg's
equal-date weighting is nonetheless computable and warns that dynamic
allocations bought more heavily at relatively high prices; it must not
be called a finished cycle success or failure.

### Main failure: 2021 high followed by 2022 low

Against the same feasible local reference extrema:

| Execution | Actual dynamic error | Equalized error |
|---|---:|---:|
| Sold BTC, started 2021-05-24 | **46.38% below high** | 39.53% below high |
| Bought BTC, started 2022-05-30 | **41.30% above low** | 34.68% above low |

Thus simply replacing equal DCA with **the current** dynamic sizing
does not solve the user's 25% objective. When prices were poor,
it misallocated too much capital, on both sides of this major cycle.

## Status / next steps

1. Keep 25% as a **desirable cycle-level effective average execution
   price error**, not a required bound on every single buy or sell.
   Also inspect 15%, 20%, and 35% plus maximum error, cash waiting and
   missed opportunities.
2. Pre-register at most two simple **causal allocation challengers**:
   sell more when elevated risk is confirmed but BTC trades relatively
   close to recent highs, and retain a larger buy reserve for deeper
   drawdowns or confirmed recovery, without presuming a 12/16-week end.
3. Check archived `risk_score` source publication-vintage integrity.
   A prior prefix-invariance check covers a newly reconstructed pure
   Power Law series, **not the whole stored composite**.
4. Compare new allocation policies as **full self-financing AUD accounts**
   including A$3 orders, per-lot SMSF capital gains (10% after >=12mo,
   potentially 15% for shorter holdings), and cash equity.
   The equal-weight dates diagnostic alone cannot establish total profits.
5. Split research calibration and future evaluations. The 2016–2026
   sample is already studied, not untouched out-of-sample data. Leave
   Production, portfolio, and master exactly as they were.
