# Original BTC Cycle strategy: what was established and what was not

17 October 2026 · **Frozen Research evidence — NOT a live model upgrade**

## Decision

The project’s original historical **below-200WMA-triggered adaptive recovery BUY / day500 original-BTC-denominated staged SELL** is already implemented and extensively tested. No reason to replace that research benchmark with above-200WMA early-accumulation alternatives merely because the simplified live notification initially offers only 2.5% of remaining cash.

However, **the live Cycle Trading Streamlit and ntfy allocation percentages are a different, simplified algorithm**. Until a single stateful account model produces identical dated original-BTC exit and original-after-tax-budget recovery quantities in both the historical backtest and Streamlit/ntfy, DO NOT credit current live suggestions with the historical returns.

This audit reruns the *existing original policy* under its unchanged rules. It adds NO parameter optimisation, no new market signals, no orders and no real portfolio writes.

## Canonical existing historical rules

- **SELL:** Known halving day500 starts selling **5% of ORIGINAL BTC**; original-position staged review dates **525, 532, 539, 546, 553 and 560**, with prices through yesterday determining regime-adjusted quantities. Research variant **maturity_90pct_holdback20pct** sells no more than 80% of original BTC through day560; a later confirmed breakdown may sell more of that original tail. All historical trades are hypothetical and cannot be backdated against actual 2026 purchases.
- **BUY activation:** After original sales finish plus the model's waiting period, strictly previous day's BTC/USD close must be below its strictly prior 200-week moving average. Buys continue over weekly research tranches **after activation**, including recovery phases if the rules permit, even above the 200WMA.
- **BUY sizing:** Research adaptive-recovery percentages apply to the **ORIGINAL after-tax buyback proceeds**, never a freshly recalculated percentage of current remaining cash. The model uses dated close and lagged 50DMA checks. It does not require perfectly finding the exact trough to start.
- **Historical capital:** Hypothetical initial A$500,000 buys BTC at each historical halving date (2016, 2020, 2024). Trades use prior-dated historic USD/AUD, simplified FIFO SMSF CGT effective 10% long-held / 15% short-held, A$3 fees and no invented broker orders.
- **Cycle status:** 2017 and 2021 observation windows through halving+1150 are complete; 2025/26 observation to 5 Oct 2026 is **incomplete/right-censored**. The model was designed after inspection of Bitcoin's history and is NOT independently validated out-of-sample.

## Verified existing-policy results (same start date as buy-and-hold)

The values below are **model outputs from the historical account**, with after-tax AUD wealth reported after **hypothetical liquidation** on the same window-end date as holding. **BTC-equivalent** includes any uninvested AUD cash valued at terminal BTC/AUD and is not necessarily BTC physically owned. All price errors are *buy VWAP relative to the retrospective observed post-sale trough*, not a guarantee of any subsequent peak/trough.

| Historic cycle | BUY sizing after 200WMA activation | Buyback fill count | BUY VWAP error above observed post-sale low | BTC-equivalent vs matched hold | Hypothetical liquidated after-CGT AUD | Matched hold after-CGT AUD | Advantage in after-CGT AUD vs hold |
|---|---|---:|---:|---:|---:|---:|---:|
| 2017 | adaptive_recovery | 15 | **18.584%** | **+218.421%** | **A$25,695,085** | A$8,105,201 | **+217.0%** |
| 2021 | adaptive_recovery | 33 | **27.366%** | **+148.753%** | **A$4,095,969** | A$1,612,205 | **+154.1%** |
| 2025/26* | adaptive_recovery | 15 | **20.330%*** | **+62.851%*** | **A$962,960*** | A$598,418* | **+60.9%*** |
| 2017 | adaptive_value (existing alternative) | 10 | 14.818% | +230.457% | A$26,610,773 | A$8,105,201 | +228.3% |
| 2021 | adaptive_value (existing alternative) | 16 | 36.396% | +135.659% | A$3,904,951 | A$1,612,205 | +142.2% |
| 2025/26* | adaptive_value (existing alternative) | 12 | 11.232%* | +74.205%* | A$1,021,769* | A$598,418* | +70.7%* |

*Right-censored cycle, **not** comparable to the two completed observations and not a completed proof.*

Mean adaptive-recovery entry VWAP error for the two completed cycles: **22.975%**. This is inside the project's 25%-average working research target, but **one completed cycle misses 25% individually**, and the sample is too small to assert expected future error of 23% or promise 20% or 25% bounds.

The historical outperformance is dominated by the day500 SELL model and the matched hypothetical *initial halving-date BTC purchase*, neither of which describes the user's real 2026 Bitcoin holdings. The selling rule's strong retrospective timing cannot be extrapolated as guaranteed.

## The critical current Streamlit/ntfy mismatch

| Rule | Frozen historical original cycle | Simplified currently displayed market recommendations |
|---|---|---|
| SELL unit denominator | **% original pre-day500 BTC inventory** | **% remaining current BTC/IBIT holdings** |
| Core day560 cap | **80% of original BTC sold maximum** | Seven conditional stages applied sequentially leave **37.32%** of original BTC if all fill |
| BUY trigger | Prior close below 200WMA starts *persistent weekly* recovery cycle | New immediate prior-close-below-200WMA gate each check |
| BUY budget denominator | **% original after-tax net sale proceeds / buyback budget** | **2.5% of remaining available AUD cash** in default style |
| Ongoing recovery BUY | After activation, later weekly buys may continue above 200WMA when regime confirms | No verified persistent buyback phase / no matching historical 15% recovery tranche |
| Portfolio / tax | Hypothetical historic matched BTC+cash FIFO SMSF accumulation tax | Real ledger may record ETF buys/sells but ntfy cannot read holdings or calculate personal CGT |

Code explicitly sets **BACKTEST_LIVE_PARITY_VERIFIED=False**. This is a vital warning, not a technicality. Backtested +217%/+154% after-tax advantage belongs to the ORIGINAL HISTORIC replay only, **NOT** to the simplified 2026 ntfy portfolio guidance.

The 2024 halving occurred **20 April 2024** and historical day500 was **2 September 2025**. BTC/IBIT actually acquired in 2026 cannot be sold at a backdated 2025 top. A prospective 2028 halving can create future 2029+ review windows, subject to that halving's confirmation and an actual inventory.

## Remaining engineering work (not a new investment strategy)

1. Keep canonical existing **shared_cycle_policy.py** as the authoritative historical trade rules; no additional above-200WMA candidate tuning or threshold changes.
2. Build a **stateful portfolio-aware Research shadow** with a verified original BTC/IBIT position at the next relevant day500 date, actual executed SELL ledger, after-tax initial buyback budget (tracked separately from unspent cash), 7-day weekly phase, idempotent trade IDs and a fail-closed historical price/FX feed. The existing read-only original BTC SELL shadow is a starting point, not a full BUY+SELL wallet state.
3. Replay that exact **same state machine** in historical AUD after-tax research and in a read-only Streamlit shadow. Compare each scheduled trade/date/quantity/cash/tax reserve against the existing simulator and buy-and-hold; if any mismatch, keep the live status labelled unverified.
4. Use verified user positions, fund phase, actual ASX:IBIT prices and cost bases before considering any manually-executed trading suggestion. No retroactive historical seller for 2026-acquired holdings.
5. Only **after** exactly matched historical and forward shadow ledgers justify it, and the user approves, replace Streamlit/ntfy simplified percentage instructions. Do not silently promote the research signals.

## Reproduction

- Frozen audit driver: engines/research/original_200wma_day500_evidence.py
- Original historical after-tax simulator: engines/research/day500_aftertax_reinvestment.py
- Shared historical model: engines/research/shared_cycle_policy.py
- Parity checks: tests/test_original_200wma_day500_evidence.py and tests/test_shared_cycle_policy.py
- CI: .github/workflows/original_200wma_day500_evidence.yml
- GitHub Actions artifact **original-200wma-day500-frozen-evidence** contains original JSON research metrics.
- **No Production V5.8.2, Research V5.9, original model, Streamlit, ntfy schedule, holdings or broker modifications.**
