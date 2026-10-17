# Integrated Cycle Trading — AUD after-tax SELL + BUY research audit
17 October 2026 | **Research only — not deployed**

## What was actually tested

This audit combines two independent research parts in a **self-financing account**: (1) the existing historical fixed day525–560 or historical dynamic 90%-core/20%-holdback exit schedule, and (2) either the current live **2.5% of remaining cash below 200WMA** BUY rule or the new research **3–20% staged value/recovery** BUY challenger.

Both accounts start with an identical **hypothetical A$500,000 used to buy BTC at the relevant historical halving**, not the user's actual SMSF or BTC/IBIT purchases in 2026. All original-BTC SELL instructions and dates match between buyer variants. They buy back on weekly dates at or after **halving+574 days** using **only prior BTC closes and strictly preceding dated USD/AUD exchange rates**.

Model assumptions: historical BTC/USD archive through 5 Oct 2026; Frankfurter historical daily FX; A$3 per executed trade; simple FIFO effective **10% SMSF CGT on long-held gains** and **15% on short-held gains**, escrowed immediately upon each sale; realised losses carried within this simplified ledger. No capital is injected beyond the original A$500k. Hold comparator buys the same starting-date BTC and liquidates hypothetically on the same ending date with the same simplified tax rules. *Actual yearly SMSF taxation and ETF transaction execution will differ.* Initial asset exposure, elapsed horizons, dividends/distributions, fees, GST, timing of tax recognition, pension status, fiscal-year offsets, spreads and execution assumptions are incomplete.

**Important:** the 2017 and 2021 windows are completed but in-sample/historically inspected; 2025/26 is **right-censored**. The model's 2025 history is evaluated only through **5 Oct 2026**; its subsequent bottom and market outcome are unknown. This test does not establish a future predictive win rate.

## Fixed day525–560 SELL schedule, same in both BUY comparisons

Percentages in columns marked *versus holding* are **additional hypothetical end-of-window after-liquidation AUD wealth relative to buy-and-hold**. These are not absolute ROI from initial A$500k.

| Historical cycle | BUY method | After-tax AUD wealth versus holding | AUD net sale proceeds redeployed | BUY VWAP error above ex-post bottom | SELL VWAP error below ex-post top |
|:--|:--|--:|--:|--:|--:|
| 2017 | Current strict 200WMA 2.5% | +31.59% | 0.00% | N/A | 17.75% |
| 2017 | Staged value/recovery | **+165.34%** | 60.81% | **16.72%** | 17.75% |
| 2021 | Current strict 200WMA 2.5% | +134.66% | 61.79% | 26.59% | 7.13% |
| 2021 | Staged value/recovery | **+162.65%** | 99.66% | **31.39% — misses 25%** | 7.13% |
| 2025/26* | Current strict 200WMA 2.5% | +41.66%* | 11.89% | 5.73%* | 9.58%* |
| 2025/26* | Staged value/recovery | **+64.92%*** | 88.71% | **16.24%*** | 9.58%* |

*Still incomplete. Recent low/high are censored **observation-window values**, not true final cycle extremes or completed achievements.*

BUY VWAP error is (full gross USD costs, including commission / BTC purchased) relative to the **observed low after day574**; SELL VWAP error is (1 - average sale proceeds USD per BTC / observed high day500–730). These are **different historical scoring windows**. Recommending large weekly BUY fractions entails high exposure to a falling market.

All terminal BTC-equivalent values include residual AUD cash valued in BTC using the same terminal day's FX/BTC close, not actual BTC coins fully reinvested.

## Alternative dynamic-90% exit, same BUY policies

| Historical cycle | BUY method | After-tax AUD wealth versus holding | Net sale proceeds redeployed | BUY VWAP error | SELL VWAP error |
|:--|:--|--:|--:|--:|--:|
| 2017 | Existing 2.5% rule | +20.96% | 0.00% | N/A | 24.45% |
| 2017 | Staged | **+143.90%** | 60.81% | 16.72% | 24.45% |
| 2021 | Existing 2.5% rule | +123.53% | 61.79% | 26.59% | 12.14% |
| 2021 | Staged | **+150.18%** | 99.64% | 31.39% | 12.14% |
| 2025/26* | Existing 2.5% rule | +38.49%* | 11.89% | 5.73%* | 11.73%* |
| 2025/26* | Staged | **+61.24%*** | 88.71% | 16.24%* | 11.73%* |

This reveals an important compromise: **more capital deployed yields larger ending BTC and AUD in these observed windows even though the average BUY price is worse than the existing rule in 2021**. It does not prove that rapid spending will outperform in cycles with a significantly later trough.

## Adverse trade execution stress (fixed SELL schedule)

Stress assumes every initial BTC purchase and staged repurchase fills at **1% or 2% higher** than observed AUD close and every BTC sale at **1% or 2% lower**. The buy-and-hold comparator receives the **same initial purchase penalty**.

| Completed cycle | Execution friction per side | Existing 2.5% rule: after-tax AUD vs hold | Staged rule: after-tax AUD vs hold | Staged BUY error |
|:--|--:|--:|--:|--:|
| 2017 | 0% | +31.59% | +165.34% | 16.72% |
| 2017 | 1% | +30.28% | +160.71% | 17.89% |
| 2017 | 2% | +28.97% | +156.17% | 19.06% |
| 2021 | 0% | +134.66% | +162.65% | 31.39% |
| 2021 | 1% | +130.87% | +157.69% | 32.70% |
| 2021 | 2% | +127.13% | +152.83% | **34.01%** |

This test is favorable to staged DCA in historical periods chosen after studying Bitcoin cycles, **not out-of-sample evidence**. 2% symmetric execution friction is a sensitivity, not a calibrated estimate of actual ASX:IBIT trading spreads.

## Price-error target and methodological conclusions

The 25% central BUY error (20% stretch) has only one of two completed windows passing under the staged buying strategy. A superficial mean of buy and sell errors can appear to hit ~20% for the fixed exit, but that hides the failure in 2021 and the two-cycle sample; it should **not** be marketed as a validated "20% timing error" trading system.

The starting BTC purchase is assumed at a historical halving with a known valuation, and day500–560 exit assumptions were already inspired by past cycles. A real investor starting in 2026 **cannot execute sales in 2025**, and a selected 2024 halving-date purchase never occurred in the user's real portfolio. Historical hold comparisons do not substitute for an actual-position-aware portfolio model.

Future work before considering a live change: freeze candidate allocation thresholds; stress delayed bear-market bottoms and bull markets that never breach the 200WMA; test additional non-crypto fixed allocation / alternative signals out of sample; reconcile SMSF phase/tax and real IBIT holdings; verify independent BTC and historical FX provider vintages; assess failure scenarios and prospective performance. Staged SELL timings need the same scrutiny as staged BUY sizes.

## Reproducibility

- Code: engines/research/staged_tax_aware_roundtrip.py
- Tests: tests/test_staged_tax_aware_roundtrip.py
- CI: .github/workflows/staged_tax_aware_roundtrip_validation.yml
- Full historical dated trade ledgers: GitHub Actions artifact **staged-dca-aud-aftertax-roundtrip**
- Previous cash-only challenger: docs/research/staged_value_dca_initial_audit_20261017.md
- Live Production V5.8.2, Research V5.9, Cycle Trading Streamlit, ntfy, Google Sheets and private holdings **unchanged**
