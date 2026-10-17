# Chronological original Cycle Trading wallet — parity audit
17 October 2026 | Research only

## Verified outcome

The original day500/original-position SELL and prior-completed-200WMA adaptive recovery BUY strategy was replayed in a strictly chronological wallet with real historical AUD FX, FIFO simplified SMSF CGT and A$3 fees.

An earlier simulator calculates the *last actual SELL date* using the completed historical observation window before starting buyback monitoring 14 days afterward. This creates a potential knowledge-of-future-sale risk: before the review window closes, real investors cannot know a later optional tail SELL won't fire. The new wallet instead **keeps all possible SELL review dates open through halving day730**, then begins checking for the first below-200WMA prior close **at day744 or later**. That is a more conservative *research execution sequencing assumption*, not a new price signal or an optimised model.

## Results of real archived history

| Historical BTC peak cycle | Buy style | Legacy buyback trigger | Chronological earliest eligible crossing | Legacy aftertax AUD wealth advantage vs matched hold | Chronological advantage vs hold | Chronological BTC held at terminal |
|---|---|---|---|---:|---:|---:|
| 2017 | adaptive_recovery | 2018-12-16 | 2018-12-16 | +217.02% | **+217.02%** | 1,846.97584308 |
| 2017 | adaptive_value | 2018-12-16 | 2018-12-16 | +228.32% | **+228.32%** | 1,916.79173716 |
| 2021 | adaptive_recovery | 2022-06-15 | 2022-06-15 | +154.06% | **+154.06%** | 94.70398498 |
| 2021 | adaptive_value | 2022-06-15 | 2022-06-15 | +142.21% | **+142.21%** | 89.71874422 |
| 2025/26* | adaptive_recovery | 2026-06-06 | 2026-06-06 | +60.92%* | **+60.92%*** | 8.02975953* |
| 2025/26* | adaptive_value | 2026-06-06 | 2026-06-06 | +70.74%* | **+70.74%*** | 8.58960367* |

*2025/26 right-censored at 5 October 2026. This remains hypothetical A$500k purchased at the 2024 halving; it is NOT the user's 2026 starting capital.*

**For all tested historical paths, the review-closure requirement did not change the observed first 200WMA buyback date.** After-tax terminal wealth was unchanged to the printed precision. This resolves the timing concern for these inspected cycles, **not as a general mathematical guarantee**. A future below-200WMA crossing before day744 could be missed by the conservative chronology when the earlier algorithm would buy.

SELL quantities are explicitly checked against the old original-BTC algorithm, not % of remaining holdings. BUY tranches are fractions of the **fixed initial after-tax sale proceeds**, not 2.5% of the remaining uninvested cash. Both use prior-date price observations, and account replay prevents retrospective orders.

## Why this still doesn't establish live Streamlit/ntfy parity

The current live-market notice sizes BUY as **2.5% of current available AUD cash**, and SELL as a percentage of **remaining current BTC/IBIT units**. The original historical policy sizes BUY using a *fixed after-tax net-sale budget* and SELL using *original pre-day500 BTC inventory*. The 2024 halving day500 occurred 2 September 2025, before the user's actual 2026 allocation. No historical 2025 original-BTC sale or 2026 after-tax proceeds can be inferred from this user's existing actual purchase ledger.

The new chronological audit does not infer a verified brokerage cost basis, tax parcel register, order fills, exact current BTC-equivalent ETF units, SMSF accumulation/pension phase or tax escrow. Those remain essential to issue dollar/quantity recommendations for a new investment cycle.

## Reproduction

Engine: engines/research/cycle_chronological_wallet.py.
Tests: tests/test_cycle_chronological_wallet.py plus tests/test_shared_cycle_policy.py.
Workflow: .github/workflows/original_cycle_chronological_wallet.yml.
Full date-by-date simulated account with every execution: GitHub Actions artifact original-cycle-chronological-wallet-audit.
No Production V5.8.2 / Research V5.9 / active Streamlit DCA or ntfy trading rules modified.
