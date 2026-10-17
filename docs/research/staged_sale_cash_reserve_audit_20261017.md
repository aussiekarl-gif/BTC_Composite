# BTC Cycle Trading Research — 0/25/40% Net Sale-Proceeds Reserve Audit
17 October 2026 | **Research only, NOT a live trading change**

## Decision

**Neither permanent 25% nor permanent 40% of net BTC sale proceeds is sufficiently robust to replace the current strict-200WMA 2.5%-remaining-cash BUY rule.**

Following the failure in the delayed-bottom stress audit (PR #116), this after-tax AUD experiment tests static minimum reserves tied to cumulative realised *NET BTC sale proceeds*, rather than 2% of the ORIGINAL hypothetical A$500k.

The optional research-only argument min_net_sale_proceeds_reserve_pct defaults to ZERO, with a regression test proving the previous replay output is identical. A nonzero floor counts cumulative net sale cash after simplified 10/15% FIFO SMSF CGT and A$3 per sell fee. No future sale proceeds are known to the account.

None of these alternatives is imported into Streamlit, daily ntfy, or real portfolios.

## Unmodified completed historical cycle windows

Both accounts hypothetically buy A$500k BTC at the historical halving, execute identical fixed day525–560 BTC exits, then recycle net sale proceeds. Results through halving+1150, strictly prior-dated historical USD/AUD FX, daily closes and simplified SMSF tax.

| Historic window | Minimum net sale proceeds reserved | Net sale cash reinvested | Ending AUD wealth after hypothetical CGT vs buy-and-hold |
|---|---:|---:|---:|
| 2017 | 0% | 60.81% | +165.34% |
| 2017 | 25% | 60.81% | +165.34% |
| 2017 | 40% | 60.00% | +163.82% |
| 2021 | 0% | 99.66% | +162.65% |
| 2021 | 25% | 75.00% | +141.44% |
| 2021 | 40% | 60.00% | +131.59% |

## Counterfactual delayed bottoms

For each completed historic pre-shock period, 8 synthetic scenarios: decline begins at halving day780 or 900, a 50% or 70% fall from pre-shock anchor to day1060, then a terminal day1150 close at 55% or 105% of the earlier price. Data before the shock remain historical and future BTC paths are **invented**, not past facts or probabilistic forecasts. Historical USD/AUD FX fixed across scenarios and buyer variants.

| Pre-shock period | Reserve | Worst staged ending aftertax AUD vs conservative 2.5% BUY | Number worse than conservative among 8 artificial stress cases | Maximum sale cash invested before low |
|---|---:|---:|---:|---:|
| 2017 | 0% | −24.13% | 3 | 98.94% |
| 2017 | 25% | −27.76% | 5 | 75.00% |
| 2017 | 40% | −25.98% | 5 | 60.00% |
| 2021 | 0% | −37.58% | 8 | 99.66% |
| 2021 | 25% | −31.35% | 8 | 75.00% |
| 2021 | 40% | −31.84% | 8 | 60.00% |

Scenario counts are **not win rates**, because the stress cases are intentionally adverse, selected and highly correlated.

A quarter of net sale proceeds held in cash reduced the worst 2021 shortfall from −37.58% to −31.35%, but made the worst 2017 outcome worse and sacrificed historical upside. A fixed 40% reserve improved cash preservation but still failed to beat the conservative rule across any of the 2021-based delayed-bottom scenarios. Neither is a reliable stand-alone fix.

## Interpretation

Past success of a rapidly deployed staged DCA-in strategy is not evidence of robustness when the true bottom is later. A permanent cash floor reduces early spending but leaves money stranded during rallies. On ordinary 2021 history, a 25% reserve lowered relative-to-holding performance from +162.65% to +141.44%: a 21.21 percentage-point reduction in that *relative metric*, not a literal portfolio loss.

Further exploratory candidate: a guarded reserve release only after *strictly previously observed* trend confirmation, with independent false-rally and renewed-crash tests. Freeze the rule before measuring; do not tune purely to these synthetic cases. Incorporate real costs, actual 2026 BTC/ETF inventory and annual Australian SMSF tax before any live deployment.

## Reproduction

Code: engines/research/staged_sale_cash_reserve_sensitivity.py.
Underlying after-tax replay: engines/research/staged_tax_aware_roundtrip.py.
Tests: tests/test_staged_sale_cash_reserve_sensitivity.py.
CI: .github/workflows/staged_sale_cash_reserve_validation.yml.
Full scenario audit: GitHub Actions artifact btc-staged-sale-cash-reserve-audit.
Production V5.8.2, Research V5.9, Cycle Trading Streamlit and once-daily ntfy, Google Sheets and user portfolio: **unchanged**.
