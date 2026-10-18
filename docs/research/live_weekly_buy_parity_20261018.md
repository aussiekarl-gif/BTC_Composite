# Live Cycle Trading 7-day BUY parity — frozen small-percentage alternatives

18 October 2026. RESEARCH ONLY; this report assesses whether the CURRENT Streamlit/ntfy BUY recommendation is reliably improved by small percentage adjustments. No changes to current trading, Streamlit, ntfy, V5.8.2 Production, V5.9 Research or personal portfolio.

## Important mismatch discovered

Historical `fresh_cash_200wma_matched_backtest.py` used **every daily eligible** close below 200WMA to spend 2.5% of residual cash, whereas the CURRENT Streamlit `make_current_decision` suppresses a new transaction if any previously recorded BUY or SELL was executed within **7 calendar days**. Hence the repeatedly cited 2017 **+149.04%** comparison of original weekly buying versus daily-2.5% proxy was *not* a validated comparison of the original versus actual live BUY execution. Also the historical 2.5/15/4.5/1% of ORIGINAL cash model is not the live 2.5% of REMAINING cash model, and staged SELL percentages use different original-versus-remaining BTC unit denominators. Live SELL rule, tax lots and available real portfolio remain independent limitations.

## Frozen small sizing comparison

Three identical hypothetical **A$400,000 originally uninvested cash-only** accounts; all see the exact same price, FX and market signals, no backdated 2025 top sale proceeds. Frozen percentage of **REMAINING AUD cash** on each eligible day with **>=7 calendar days since last executed BUY**:

- **2.5%:** unchanged current Cycle Trading market-level BUY WATCH and one weekly recorded trade.
- **3.5%:** small +1 percentage point candidate, not deployed.
- **5%:** 2x allocation candidate, not deployed.

Every buying date T must satisfy prior date T-1 BTC/USD close STRICTLY below the exact 200 **WEEK** average of the prior 200 spaced completed 7-day closes (identical helper as original), AND existing `calculate_allocation_signal` returns BUY WATCH 2.5% of residual cash for the **current base strategy**. No other BUY dates, pre-gate starters, sell proceeds, recovery BUY above WMA, or leverage. A real seven-day cool-down is applied to *executed transactions*, rather than the fixed calendar 7-day cadence in the original full-cycle model. No account continues buying without eligible signal even if previously active.

Score the hypothetical AUD 400k cash-only start at Bitcoin halving day+650,+750,+850,+900, complete 2017/2021 through halving+1150, censored 2025/26 through 2026-10-05; same actual historical BTC/USD day-close proxies, strictly previous USD/AUD FX, A$3 brokerage and simplified FIFO accumulation SMSF CGT at hypothetical terminal liquidation. Same starting cash means after-tax terminal AUD is directly comparable. Also report remaining AUD cash, purchased BTC and number of trades. These histories are already researched; results are NOT genuinely out-of-sample.

Stress under frozen independent delayed further BTC lows:
- 2017-completed historical prefix until halving+960 with cash start+750.
- 2021-completed historical prefix until halving+900 with cash start+650.
- 50% and 70% artificial post-prefix declines through day1060, then day1150 terminal at 55% or 105% of the original pre-shock level. These are adversarial counterfactuals, not frequency estimates.

Tests: exact same current market BUY percentage, individual 7-day executed-trade cadence, no entry after WMA recovery, delayed cash trajectories, prefix invariance, no-price-cross and bad FX/no-history fail closed.

## Live implementation decision BEFORE results

Do NOT deploy either candidate just because it accumulates more BTC in one rising in-sample period. Compare observed after-tax AUD gains versus additional exposure in deeper and later selloffs, remaining unspent cash, sensitivity across different fresh-cash enrolment dates, practical ASX:IBIT weekday execution/spread and real SMSF tax timing. As of this candidate, SELL rules are still not part of this cash-only comparison; the historical cycle SELL gains must never be attributed to the tested live model.
