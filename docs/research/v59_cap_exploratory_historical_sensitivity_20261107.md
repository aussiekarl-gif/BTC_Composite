# Exploratory historical cap sensitivity (NOT a V5.9 backtest)

Source: `aussiekarl-gif/btc-audit-data/validated/production_input.csv` fetched 2026-11-07, with dated BTC/USD and USD-per-AUD observations; missing FX carried forward. Weekly Monday observations.

**Critical limitations:** Risk score was NOT reconstructed. For this exploratory sensitivity only, weight = 2 - 1.2 * clamp((current BTC/USD - minimum previous 365 observed daily prices) / (maximum - minimum), 0, 1). This uses the same day's price for both signal and execution and therefore is NOT point-in-time tradable. No fees, slippage, exceptional events, reserve, or true V5.9 indicators. Three overlapping historical windows are NOT independent out-of-sample tests. Results are directional only, not investment recommendations.

A$500,000 initial cash, zero protected reserve. Spend each Monday = min(cash, cash / max(weeks to review,1) * min(raw proxy weight, cap)). Last execution may be before review; no forced terminal spend.

| Window | Mondays | Review | 1x BTC / cash AUD | 1.5x BTC / cash AUD | 2x BTC / cash AUD |
|---|---:|---|---|---|---|
| 2022-01-03–2023-12-25 | 104 | 2024-01-01 | 12.88404 / 1,098 | 13.10691 / 549 | 13.25836 / 394 |
| 2024-01-01–2025-12-29 | 105 | 2026-01-05 | 4.22731 / 0 | 4.27940 / 0 | 4.27908 / 0 |
| 2025-01-06–2026-09-07 | 88 | 2026-12-28 | 3.35881 / 75,325 | 3.66806 / 36,101 | 3.78056 / 23,482 |

This confirms the **mechanical possibility** of larger BTC accumulation in these illustrative scenarios, but does not establish that a higher cap outperforms under real V5.9 signals or that it is preferable after adjusting for remaining cash and risks.

**Release gate:** Need verified point-in-time historical V5.9 risk, next-execution fill prices, transaction costs, equal-date BTC+cash equity and independent windows. No Production or live Research sizing change authorized.
