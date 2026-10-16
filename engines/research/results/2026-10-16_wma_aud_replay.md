# Historical 200WMA AUD research replay — 2026-10-16

**Status: RESEARCH ONLY / NOT CERTIFIED / NO PRODUCTION PROMOTION.**

## Data and methodology

- Input: read-only `aussiekarl-gif/btc-audit-data:btc_audit_backup.csv`, blob SHA `ed5b0ca3c5611ed8ce645f4652d28fdd0d4b3e48`, `btc_price_aud`.
- 557 consecutive valid weekly AUD observations dated 2016-01-04 to 2026-08-31.
- First valid weekly bar after 200 **prior** weekly observations: 2019-11-04. Last: 2026-08-31. The backtest uses 357 weekly bars.
- Independently replayed Research `simulate_wma_windows` campaign logic in JavaScript to review model behavior; **these figures are NOT verified Python CI outputs**, do not claim parity yet.
- Initial AUD 500,000; 0.10% buy and sell transaction fees; signal crossing at weekly close, fill at the **next weekly close** at that closing price; no taxes, execution slippage or spread beyond explicit fee. No leverage or shorting.
- Campaign weights triangular, 12 or 16 weeks, for a crossing below buy threshold / above sell threshold, with all available starting cash / BTC eligible in that campaign.
- Buy-and-hold benchmark enters at first valid week's price with 0.10% fee, then simply marks BTC holdings to the last price.
- A completed cycle backtest **does not** imply this strategy beats buy-and-hold, or that it is fit for execution.

## Full-window outcomes (2019-11-04 to 2026-08-31)

| Window | Buy threshold (% vs 200WMA) | Sell threshold | Final AUD equity | Max portfolio drawdown | Buy fills | Sell fills |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 12 | -10 | +75 | 1,945,485 | -15.06% | 12 | 12 |
| 12 | 0 | +100 | 1,873,628 | -27.11% | 24 | 12 |
| 12 | +10 | +125 | 1,709,941 | -27.11% | 24 | 12 |
| 16 | -10 | +75 | 1,790,157 | -15.06% | 16 | 16 |
| 16 | 0 | +100 | 1,828,618 | -24.54% | 28 | 16 |
| 16 | +10 | +125 | 1,694,521 | -24.54% | 32 | 16 |
| Buy and hold | n/a | n/a | **4,064,456** | **-72.57%** | 1 | 0 |

Comparisons are sensitive to the starting date and exposure, and the buy-and-hold drawdown is materially larger. Do not treat final equity alone as risk-adjusted superiority. Numbers are rounded.

## Chronological 70/30 holdout (not nested walk-forward)

- 249 weeks training (2019-11-04 to 2024-08-05); 108 weeks holdout (2024-08-12 to 2026-08-31).
- Selection used only training-period final equity. Chosen rule: 12-week buy -10% / sell +75%.
- Held-out scenario uses **fresh cash**, not a carried position. No signals led to fills during holdout.
- Held-out rule: **AUD 500,000**, 0 trades; same-start buy-and-hold: **AUD 608,799**; shortfall: **AUD 108,799**.
- This is a critical structural issue: when the model stays entirely in cash it may miss sustained appreciation.
- The model's initial crossing under -10% generated buys from 2022-11-21 to 2023-02-06, with sells from 2024-02-26 to 2024-05-13. It held BTC in roughly 21.6% of the whole tested weeks.

## Diagnostic core + satellite mix (illustration, not a newly approved model)

A hypothetical permanent core bought at the initial full-window price plus a proportional satellite using the 12-week -10/+75 strategy (and independent fresh-capital holdout for the corresponding test):

| Core BTC share | Full-window equity AUD | Full-window maximum drawdown | Fresh-capital holdout AUD |
| ---: | ---: | ---: | ---: |
| 0% | 1,945,485 | -15.06% | 500,000 |
| 25% | 2,475,228 | -50.41% | 527,200 |
| 50% | 3,004,971 | -63.23% | 554,399 |
| 75% | 3,534,713 | -69.14% | 581,599 |
| 100% | 4,064,456 | -72.57% | 608,799 |

Greater passive BTC exposure increased ending equity in this sample **and** worsened peak-to-trough drawdown. This is not evidence that 100% BTC is suitable for an individual investor.

## No-promotion decision

**DO NOT PROMOTE the standalone 200WMA trading rule to Production.** It has not shown out-of-sample outperformance; the selected rule executed no holdout trades. Existing Production V5.8.2 and authoritative master are unchanged.

Next:
1. Verify exact Python implementation with CI and archived results.
2. Add a validated, reproducible point-in-time AUD pricing audit, including earliest historical dates and revisions.
3. Compare across several independent rolling/anchored windows and multiple entry dates; avoid selecting a winner based on one holdout.
4. Include slippage/spread, tax treatment as relevant, and explicit maximum uninvested time / exposure statistics.
5. Test a simple core-plus-satellite approach *only as a separate research hypothesis*, alongside passive and fixed DCA baselines.
