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


## Results — verified 18 October 2026

**[GitHub Actions successful run 39115657024](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39115657024), 31/31 tests passed** (8 novel exact weekly execution tests, 10 unchanged current percentage tests, 13 existing Cycle Trading sensecheck tests). Full [JSON with EVERY historical/stress BUY order and CSV summaries, artifact 12131994084](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39115657024/artifacts/12131994084). This was the first properly seven-day-cooled BUY simulation of the actual shared market-level Cycle Trading 2.5%-of-residual-cash policy; the earlier daily-unthrottled benchmark is NOT interchangeable.

### Historical, terminal hypothetical illustrative FIFO accumulation-SMSF CGT included

All numbers below represent **percentage change in entire final after-tax AUD account**, comparing challenger / current 2.5% live-like weekly BUY. Not annualised investment return, not buy-price/low error, not actual holdings. Starts +650/+750/+850/+900 are overlapping retrospective entry scenarios, not statistically independent samples.

| Completed cycle / cohort | Baseline 2.5% eligible trades | Original cash remaining after baseline | 3.5% after-tax AUD vs baseline | 3.5% BTC held relative | 5.0% after-tax AUD vs baseline |
|---|---:|---:|---:|---:|---:|
| 2017 +650/+750/+850 | 1 | 97.50% | **+1.988%** | +40.012% BTC (very small initial baseline) | +4.970% |
| 2017 +900 | 0 | 100% | 0.000% (all cash) | no BTC | 0.000% |
| 2021 +650/+750 | 39 | 37.25% | **+4.417%** | +19.667% BTC | +8.429% |
| 2021 +850 | 30 | 46.79% | **+4.863%** | +23.812% BTC | +10.005% |
| 2021 +900 | 22 | 57.29% | **+5.061%** | +27.985% BTC | +11.151% |
| 2025/26 +650/+750 RIGHT-CENSORED | 6 | 85.91% | +1.667%* | +36.622% BTC | +4.018%* |
| 2025/26 +850 RIGHT-CENSORED | 0 | 100% | 0.000%* | no BTC | 0.000%* |

*2025/26 is NOT a complete cycle and is scored only through archived 5 October 2026. Your actual portfolio may be invested at entirely different real dates and sizes. The 2026 +850 fresh start misses the previous prior-WMA signal, leaving all three policies with 100% cash.*

Significant concrete learning: current live-like **7-day cooldown** makes late 2021 2.5% baseline retain **57.29% of original AUD cash**, unlike the earlier **daily-unthrottled** simplified benchmark that could substantially consume it. The primary historical return uplift comes from taking **more BTC exposure** after a BUY signal, *not* from a better bottom indicator, lower entry-price error or extra sell signal. For 2017 with one BUY trigger, the +40% BTC number applies only to baseline 2.5% of cash, not a 40% overall investment gain.

### Exact synthetic stress — 2017/2021 prefixes, 50/70% renewed drawdown, terminal conditions

All percentages = candidate vs original 2.5% seven-day-limited after-tax AUD. The two terminal ratios (55%, 105%) are in units of pre-shock price; these synthetic paths are intentionally adverse and are **not probability samples**.

| Prefix / further forced decline | Terminal ratio vs pre-shock | 3.5% vs 2.5% | 5.0% vs 2.5% |
|---|---:|---:|---:|
| 2017 +750 / 50% extra drop | 55% | −1.505% | −3.826% |
| 2017 +750 / 50% extra drop | 105% | +4.825% | +9.893% |
| 2017 +750 / 70% extra drop | 55% | +1.223% | +1.579% |
| 2017 +750 / 70% extra drop | 105% | +7.397% | +14.699% |
| 2021 +650 / 50% extra drop | 55% | **−6.924%** | **−14.401%** |
| 2021 +650 / 50% extra drop | 105% | +0.258% | −1.224% |
| 2021 +650 / 70% extra drop | 55% | **−6.513%** | **−15.130%** |
| 2021 +650 / 70% extra drop | 105% | −0.109% | −3.397% |

This proves only the obvious but quantifiable exposure tradeoff: **3.5% beats current 2.5% in every fully observed historical cash-cohort with actual purchases (1.988–5.061% higher total hypothetical aftertax AUD), but loses up to 6.924% of terminal portfolio value in deliberately extended declines**. An aggressive 5% boosts prior observed upside 4.970–11.151%, but can trail by **15.130%** in constructed deeper-bottom paths. No parameter is a strict dominance improvement. 2025/26 small positive observation is censored. Nothing in this experiment proves 3.5% is optimal, that the next BTC low is complete, or that this can be implemented at actual ASX:IBIT prices and tax treatment.

### Practical recommendation and repo decision

- **Keep current 2.5% live BUY until a separate explicit user implementation decision**, with displayed research-only candidate **3.5%** (not yet proven robust), not an automatic 5% switch.
- It is legitimate to say that we found a **historically profitable small change**; it is illegitimate to say we have established a universally superior strategy. The user correctly pointed out that the original wasn't strongly optimised; live weekly backtesting makes this quantifiable.
- Compare 3.5% specifically against a frozen *less aggressive* 3% and against IBIT ASX-day-next-tradable fill timing, AUD spread, fees and exact portfolio tax-phase before any live promotion. That follow-on will be exploratory (selected after inspecting this evidence), not pristine untouched confirmation.
- Keep known selling mismatch on the work list: live SELL % of CURRENT holdings differs from historical original BTC %; cannot credit old backtest exit returns to live engine.
- The standalone research evidence and 31 tests can be merged as **research only** with original live scripts and single daily ntfy untouched; deploy no recommendation without user approval.
