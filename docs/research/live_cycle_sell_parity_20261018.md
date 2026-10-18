# Cycle Trading SELL parity against staged original-BTC historical research

## Purpose / status

18 October 2026. **RESEARCH ONLY, UNMERGED UNTIL SUCCESSFUL NUMERICAL REVIEW**. This compares exactly existing `calculate_allocation_signal` used by Streamlit and one daily ntfy, with historically researched stage exits — because SELL percentage denominators and execution triggers differ materially. This is a **model validation** experiment, NOT a claim the current historical 2017/2021/2025 simulations represent the user's actual 2026 account.

Five matched hypothetical accounts start with the **same AUD500,000 direct BTC purchase ON EACH HISTORICAL HALVING DATE**, never claim actual 2026 owner holdings. **ASX:IBIT did not exist before 14 November 2025**; these are BTC/USD next-close A$ converted proxies, not actual ETF quotes, exchange holidays, tracking or spreads. Simplified upfront A$3 brokerage and illustrative FIFO SMSF accumulation-phase short/long realised CGT escrow, strictly PREVIOUS dated AUD/USD FX, same mark-to-market and hypothetical terminal liquidation for all accounts.

1. **Actual live market SELL**: strict prior-close / 200WMA market eligibility from `calculate_allocation_signal`: at halving days 500/525/532/539/546/553/560, only if prior BTC close is at least 1.25x 200WMA and within 5% of prior 90-day high; sells 5/24/20/16/12/8/5% of CURRENT REMAINING BTC. If after day560 and prior price is >=1.4x200WMA, at least 15% below prior 90-day high and below declining 50DMA, can sell an EXPERIMENTAL additional 5% CURRENT REMAINING holdings every 7 executed-trade days. Existing 7-day filled-order cooldown, no fabricated BUY when all starting cash is already deployed.
2. **Live scheduled-only diagnostic**: same shared prior-day market signal and seven-day cooldown, but ignore experimental late >560 SELL. This is NOT a current live toggle; it isolates the unverified tail's consequence.
3. **Research staged 90% ORIGINAL BTC**: unchanged historical pure `staged_day500_dynamic_exit` maturity_90pct, original-denominator distribution and price-regime/tail logic; same USD close/FX execution and SMSF assumptions.
4. **Research staged 90% with original pre560 20% holdback**: historical maturity_90pct_holdback20pct with actual post560 confirmed breakdown exit only.
5. **Buy and hold**: same initial BTC and exact final prices; no sales. Entire account is valued and hypothetical tax on terminal liquidation applies equally.

Score matched accounts on day730 and day1150 after confirmed 2016/2020 halving, and 2024 halving on day730 and latest archived Oct5 2026 before day1150 (RIGHT-CENSORED). Report all true live market SELL WATCHs, dated completed sales, ORIGINAL BTC fraction sold, current remaining units, AUD after actual cash/tax fees, hypothetical liquidation after tax, results vs identical buy and hold and live scheduled-only. Always label 2025/26 incomplete, and do not assume the user held at day500/2025 top.

Stress/evidence: live 7d cooldown, 90d/50DMA conditions, strict previous calendar close, fee/tax and ORIGINAL vs REMAINING BTC denominator invariants and missing prices/FX all tested. We do **NOT** cherry-pick historical staged policy based on terminal account return, or claim the 2025 cycle peak is absolutely known.

No live Cycle Trading BUY/SELL, Streamlit, Production V5.8.2, Research V5.9, Google Sheets portfolio, actual IBIT shares or ntfy changes. Promotion decision remains blocked until closed-market ETF times/actual broker units and genuinely prospective SELL evidence.

CI numerical results: pending.
