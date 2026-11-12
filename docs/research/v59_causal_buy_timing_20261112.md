# V5.9 causal BTC buying-timing horse race — 12 November 2026

**Status: RESEARCH ONLY. Do not activate a new trading policy or alter the current
V5.9/Production/Cycle Trading recommendation from these results.**

## Executive finding

The **V5.9 Research WF Power Law risk**, reconstructed from publicly fetched
historical BTC/USD observations, produces promising results when earlier low-risk
purchases are larger. But the apparent benefit has two separable causes:
**(1) deploying capital sooner** and **(2) choosing entry weeks conditional on
risk or discount**. Shorter review windows can greatly improve outcomes in
rising historical cohorts, even with unchanged 1x risk gates.

A prospective-predeclared, 12-policy retrospective comparison supports further
study of **3x at R2 risk ≤0.20 (zero above 0.20)** as a *research candidate*.
It had a slightly lower later-period median than unrestricted 3x when starting
from 100% AUD, but more consistent results and less relative drawdown. The
difference remains small and is not statistically established. No guarantee of
an optimal future BTC bottom.

## Input and causal rule

- Market references: Blockchain.com BTC/USD daily series and Frankfurter AUD/USD
  historical FX, fetched by read-only GitHub Actions on 12 November 2026.
- BTC observed input series 2011-03-07 to 2026-11-12 (latter may be partial,
  but **no partial current-day signal is used in historical buys**); historical
  FX 2011-12-30 to 2026-11-11.
- **515** matched, weekly Monday BTC/AUD proxy executions with the prior
  **Sunday's** Research WF Power Law risk and technical context.
- AUD FX uses the latest existing historical fixing **on or before Sunday**,
  not Monday's potentially unpublished official fixing.
- No historical stored `btc_audit_backup.csv` risk score is used: V5.9 is
  **recalculated** with `engines/research/research_model.py` from BTC prices,
  with specialist API fields explicitly unavailable exactly as in DCA Today.
- 16 completed 104-week Jan/July-anchored cohorts from 2017–2024. Seven
  2017–early 2020 cohorts are a research TRAIN split, three 2020–21 bridge
  cohorts excluded from selection, six 2022–24 cohorts a *historical* holdout.
  These cohorts overlap and are not independent BTC cycles; designs were
  proposed after observing BTC's history.
- Starting AUD A$510,000; fixed fee A$3 each BTC proxy buy, illustrative 0.30%
  spread/slippage, illustrative 0.25% annual ETF drag, <=5% of original
  capital purchase per week, no leverage or sales.
- Simulated uninvested cash earns 0% or **5% annual compounded pretax**; reserve
  0% or 10% of starting capital. Real AAA distributions and taxes may differ.
- Total value includes BTC *and* unspent interest-bearing cash; all policies
  share the same initial valuation, execution dates, and cost assumptions.
- Policies include risk-gated 1x/2x/3x, restrictive 3x ≤0.20, 200WMA discounts,
  25/40% one-year drawdowns, 50DMA and rising 50DMA confirmation, combinations,
  and plain weekly buys. No hindsight lowest prices used to choose buys.

## Results: 100% new cash, 5% interest, 0% protected reserve

Percentages are differences from the **same 104-week risk-gated 1x**
benchmark on the six *historical holdout* cohorts. Drawdown change is in
percentage points, where a negative number means a **larger** drawdown.

| Policy | Median final total value uplift | Worst cohort | Win rate | Median extra drawdown |
|---|---:|---:|---:|---:|
| Plain 1x weekly | −1.58% | −10.59% | 0/6 | −2.85 pp |
| Risk-gated 2x | +14.42% | −1.92% | 5/6 | −2.39 pp |
| **Risk-gated 3x** | **+20.63%** | **−3.25%** | **5/6** | **−3.92 pp** |
| **3x only at risk ≤0.20** | **+19.66%** | **+3.16%** | **6/6** | **−1.84 pp** |
| 3x only below 200WMA | +11.37% | −10.04% | 4/6 | +4.05 pp |
| 3x after ≥25% drawdown | −0.42% | −42.33% | 3/6 | +8.58 pp |

Note that below-200WMA used only ~41% of original capital at the median
end date in these holdout cohorts. Its relatively smaller drawdown is therefore
partly a consequence of cash **not being invested**. A better entry-price
claim cannot be made merely from lower market exposure.

## More realistic starting holdings: 41% existing BTC / 59% uninvested AUD

Each cohort is marked to the same starting total value. The 41% BTC
position is pre-existing at that date and **never re-bought**, while only
the remaining cash earns 5% and is timed into additional BTC. This approximates
the user's current investment split but does not invent historical Stake fills.

| Policy | Median total portfolio uplift vs 1x | Worst cohort | Win rate | Extra drawdown |
|---|---:|---:|---:|---:|
| Risk-gated 2x | +7.54% | −1.08% | 5/6 | −2.08 pp |
| Risk-gated 3x | +11.05% | −1.82% | 5/6 | −3.26 pp |
| **3x only at risk ≤0.20** | **+11.22%** | **−0.29%** | **5/6** | **−1.81 pp** |
| 3x only below 200WMA | +6.83% | −4.61% | 4/6 | +1.46 pp |
| 3x only at ≥25% drawdown | −1.36% | −18.93% | 2/6 | +2.47 pp |

**Interpretation:** Existing exposure dilutes the absolute differences between
new-cash entry rules. The more restrictive ≤0.20 gate remains an interesting
robustness candidate, not a reason to stop the currently agreed 1x or 3x live
workflow. Six overlapping historical cohorts cannot validate a new rule.

## Review-horizon sensitivity: is it signal timing or simply faster buying?

All policies below are scored at the **same final 104-week date** regardless
of whether buying was paused after week 39, 52, 60, 78, 104 or would continue
at week 130. At the chosen review date buying **pauses**, with no mandatory
investment or liquidation. Results again use 100% initial cash and 5% pretax
return on any remaining cash, and are measured relative to 104-week 1x.

| Review after | 1x risk-gated | 3x risk-gated | 3x only risk ≤0.20 |
|---|---:|---:|---:|
| 39 weeks | +33.51% | +37.39% | +32.67% |
| 52 weeks | +25.33% | +36.62% | +33.53% |
| 60 weeks | +20.86% | +34.52% | +32.47% |
| 78 weeks | +11.69% | +28.80% | +26.13% |
| 104 weeks | Baseline | +20.63% | +19.66% |
| 130 weeks (unfinished at scoring) | −9.34% | +15.93% | +14.60% |

The **39-week 1x** strategy itself beats the **39-week restrictive 3x**
strategy in median equity for these historical cohorts. That is strong
evidence **against** treating a high historical score solely as proof of
better bottom detection. Much of it can be explained by earlier cash
deployment into appreciating BTC. Investing faster also increases risk in
drawdowns: e.g. 39-week 1x had median drawdown change **−6.29 pp** versus
104-week 1x.

These horizons are **sensitivity axes**, not fixed new trading deadlines.
The user's actual late-2026 programme has a flexible review period in 2027,
and no simulated future BTC prices are known.

## Interpretation and decision

**Research front-runner:** staged, relatively aggressive purchases when
R2 sizing risk is extremely low, with a stricter >0.20 pause candidate
for prospective examination. The 3x band from the current manual planner
can remain unchanged while new, timestamped R2 signals accumulate.

Before any promotion:
1. Test true historical **as-published** provider risk vintages or accumulate
   sufficiently long genuine forward observations; retrospective refits and
   risk thresholds chosen in 2026 remain vulnerable to hindsight.
2. Check BTC/AUD spot timing against actually tradable ASX:IBIT prices,
   bid-ask spreads and broker execution. Historical IBIT did not exist in
   early cohorts; FX fixing lags and Monday UTC BTC reference are proxies.
3. Include realistic distribution/tax, total return, tracking differences,
   missed fills and cash settlement impacts; 5% is a parameter, not a
   historical AAA yield guarantee.
4. Evaluate path risk and cash needed if BTC drops another 30–50% after
   the first risk=0.000 observation. Aggressive front-loading may lose the
   ability to buy cheaper later.
5. Reconcile the current Google Sheet and Stake positions before producing
   any actionable buy quantity. Respect stop-buy at >0.50 and A$25,500 max
   ordinary weekly allocation on A$510,000 starting capital.

**No Production V5.8.2, live V5.9 sizing, Cycle Trading, ntfy, stored portfolio
or brokerage order was changed by this research.**

## Reproduce

```bash
python -m engines.research.v59_causal_timing_horse_race \
  --out artifacts/v59_buy_timing_horse_race.json
python -m unittest discover -s tests -p 'test_v59_causal_timing_horse_race.py' -v
```

The research-only GitHub Actions workflow:
`.github/workflows/v59_causal_timing_research.yml`. Full per-cohort
trade, total return and sensitivity reports are retained as a 90-day
Actions artifact, not copied into a user portfolio or NTfy.
