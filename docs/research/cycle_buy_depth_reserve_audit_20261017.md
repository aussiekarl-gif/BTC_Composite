# 200WMA BUY depth reserve: full AUD tax wallet and downside stress

17 October 2026 | Research only | PR #134

## Decision: REJECT the 50% locked cash reserve as the primary accumulation rule

One frozen BUY-path hypothesis was tested against the original staged day500 SELL → first strict prior close below strict 200 WEEK moving average (on/after day744) → weekly adaptive recovery BUY rule:

**Before** an eligible weekly review has previously observed BTC closing at or below **0.85× its prior 200WMA**, allow **up to only 50%** of the ORIGINAL after-tax sale cash to be invested, spending **half the normal original weekly percentage**. Once the deep discount occurs, use the original FULL weekly fraction of the original after-tax budget on subsequent scheduled buys. No earlier skipped transactions are bought retroactively. The reserve may remain stranded as cash indefinitely if BTC never makes that deeper discount.

This is a **research hypothesis, not an optimised new threshold**. The 50% cash reserve and 15% discount are proposed before scoring and are NOT derived from an independent holdout. We compared against the unchanged original BUY schedule with the SAME initial historical BTC lots, same original staged SELLs/tax, identical first below-200WMA activation, weekly dates, historical BTC USD and lagged AUD/USD FX, A$3 per order and simplified immediate FIFO SMSF CGT escrow. Aftertax terminal value assumes liquidation of remaining BTC at the scored terminal. Synthetic A$500k owned BTC from historical halving; no actual 2026 user holdings could execute 2025 SELLs.

## Observed historical results

| Cohort | Original after-tax terminal AUD | 50% reserve terminal AUD | Reserve minus original terminal AUD | Relative return |
|---|---:|---:|---:|---:|
| 2017 (complete) | 25,695,084.89 | 17,749,506.37 | −7,945,578.52 | **−30.923%** |
| 2021 (complete) | 4,095,969.07 | 4,011,675.75 | −84,293.32 | **−2.058%** |
| 2025/26 (right-censored) | 962,959.67 | 879,691.27 | −83,268.40 | **−8.647%*** |

*Through archived close 5 October 2026 ONLY; 2025/26 full 1150-day future bottom is UNKNOWN.*

Original dates and original early post-sale 200WMA threshold are **unchanged in both**. The counterfactual reserve helps neither completed historic cohort under this scoring. It disproportionately damages 2017, where the first below-WMA entry was just one day after the eventual trough, recovery was rapid, and the new 0.85× WMA unlock threshold was NEVER met on an eligible weekly review. The policy unnecessarily held a large proportion of the cash through an enormous later price rise.

### Was original buying prematurely exhausted in 2021?

No. A hindsight-only diagnostic (not a trading input) shows the AUD cash still held at the **eventual 2021-cycle observed low**:

| Metric | Original | 50% reserve |
|---|---:|---:|
| AUD uninvested cash at actual cycle low | 672,590.80 | 1,352,187.75 |
| Average BTC repurchase USD price *above future cycle low* | +27.37% | **+29.68%** |
| First deep-discount unlock | Not applicable | 7 September 2022 |

The original still had about A$673k of uninvested sale proceeds at the low. The reserve kept A$680k more on that exact date, but yielded a WORSE effective buy price and ended with less after-tax AUD. **The problem cannot simply be summarised as exhausting the entire buyback cash allocation before the trough.** The trajectory of the weekly dynamic buys and return path matters.

For 2017 the cash held at the observed bottom was A$9,804,044.18 in BOTH accounts because the first 200WMA buying trigger arrived ONE DAY AFTER that eventual low. The reserve could only harm the subsequent recovery. For the incomplete 2025/26 observation the cash remaining at the lowest close so far was A$684,968.87 in the original and A$740,722.15 with the reserve; that low is not guaranteed to hold.

## Explicit synthetic further-decline stress (NOT predictions)

We reused the frozen independent delayed-bottom stress framework. Actual history is preserved through **halving day900**; after that, BTC prices are **artificially** forced smoothly down to day1060 by 50% or 70%, then end on day1150 at 55% or 105% of the pre-shock day900 price. Historical AUD/USD FX values are retained; an actual global liquidity crisis could change currency rates, tax and execution costs.

| Pre-shock cycle prefix | New synthetic crash | Final BTC / pre-shock price | Reserve vs original aftertax terminal AUD |
|---|---:|---:|---:|
| 2017-based | 50% | 55% | **+8.398%** |
| 2017-based | 50% | 105% | −2.339% |
| 2017-based | 70% | 55% | **+3.646%** |
| 2017-based | 70% | 105% | −1.523% |
| 2021-based | 50% | 55% | **+17.968%** |
| 2021-based | 50% | 105% | **+15.489%** |
| 2021-based | 70% | 55% | **+35.408%** |
| 2021-based | 70% | 105% | **+30.790%** |

Under these deliberately constructed renewed crashes, holding more cash **can protect aftertax ending wealth materially**. But the 2017-based scenarios with recovery also show losses from late entry. This is NOT a probability of winning or a reason to assume a future 70% crash; it is a diagnostic for failure-mode robustness and the opportunity cost of preserving reserves.

## Interpretation for the main goal

The original BUY VWAP error averaged approximately 22.98% above the eventual lows of the **two previously inspected complete cycles**, compared with the user's preferred roughly 20% target. The original 2021 BUY VWAP was 27.37% above the actual later bottom. This 50% depth-reserve **worsens it to 29.68%**. It does not meet the user's goal or demonstrate a reliable new bottom indicator.

Two consecutive frozen timing challengers have now failed under observed historical BTC prices:

1. PR #133: one additional SELL based on first mature confirmed reversal had no impact in completed 2017/2021 and was slightly worse in censored 2025/26.
2. PR #134: the 50% cash-reserve BUY strategy significantly underperformed in 2017, mildly underperformed in 2021 and did not improve VWAP, although protecting against deliberately severe later bottoms.

This is a strong reason NOT to change the original rules today, and NOT to begin unprincipled threshold optimisation against just these historical examples.

## Research next steps

The next valuable task is an **indicator availability and execution-lag matrix** rather than another arbitrary 0.80/0.90 WMA threshold. For each existing BUY/SELL indicator, verify strict previous-price decision timestamp, how late it fires vs full trade path, how often it is absent, revision risk and real ASX:IBIT quote timing. Keep 2017/2021 explicitly in sample, 2025/26 incomplete, and require independent new data before claiming an out-of-sample improvement. A user-friendly read-only diagnostic of WHY an actual buy occurs is more defensible than pretending to know the future trough.

## Code and tests

- Dated replay `engines/research/cycle_buy_depth_reserve_audit.py`
- Test suite `tests/test_cycle_buy_depth_reserve_audit.py` (8 new tests), plus existing original chronological wallet (5) and shared original policy (8)
- Workflow `.github/workflows/cycle_buy_depth_reserve_audit.yml`; successful Actions run [39025294894](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39025294894).
- Full audit artifact `predeclared-half-cash-deep-200wma-reserve-audit` includes complete executed SELLs/BUYs, BTC positions, cash left, aftertax simulated terminal wealth, ex-post low-date cash, gross BTC repurchase VWAP, and every synthetic scenario.

**Only Research files added. Production V5.8.2, Research V5.9, daily Cycle Trading Streamlit BUY/HOLD/SELL, notifications and existing Google Sheets portfolio entries untouched.**
