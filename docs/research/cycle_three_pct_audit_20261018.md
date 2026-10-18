# Cycle Trading 3% remaining-cash weekly DCA — next test after prior 3.5% evidence

**18 October 2026, Research only. No change to live Cycle Trading, ntfy, Production V5.8.2, Research V5.9, Streamlit, Google Sheets or broker holdings.**

## Hypothesis

The earlier PR #144 established a **measurable observed aftertax benefit** from raising a hypothetical fresh-cash account's real 7-day-cooldown 200WMA BUY from 2.5% to 3.5% of *remaining cash* in both completed historical cycles with eligible buys (relative total account improvement +1.988% to +5.061%). However, deeper delayed BTC declines in the adversarial paths cost up to −6.924% terminal aftertax AUD, with 5% costs up to −15.130%. The objective of this explicit **exploratory parameter choice made AFTER seeing those results** is to assess whether 3.0% preserves some benefit but reduces downside losses. We make no assertion of independent untouched evidence.

Freeze **2.5%, 3.0%, 3.5%** per eligible executed weekly BUY from the *then-remaining AUD cash*, using exactly the same date-exact `replay_exact_live_market_buy` that calls existing `calculate_allocation_signal` and prohibits transactions closer than 7 days. Strictly yesterday's completed BTC close below prior 200-WEEK moving average, not a lagged 200 DAY average. All accounts initially AUD400k fresh cash with no already-owned BTC, no retrospective peak SELL cash. No buying outside eligible WATCH dates, and no invented prior ledger. No modifications to existing live BUY or SELL percentages.

Same completed historic 2017/2021 cash starts +650/+750/+850/+900, incomplete 2025/26 starts observed through Oct 5 2026, same matched AUD USD FX from preceding dated source, A$3 per fill, illustrative FIFO SMSF accumulation final hypothetical CGT, true net BTC and AUD cash carried forward. The same **8 synthetic** 2017/2021 prefix-preserving further 50/70% crashes and two recovery terminal states reused from PR #144 to assess how 3% changes both return and terminal cash reserves. Real IBIT weekends/bid-ask, ETF expenses and tax phase are NOT modelled. These synthetic paths aren't probability forecasts.

**Decision criteria:** show benefit/loss versus *actual current 2.5% rule*, and 3.5% neighbor, across every eligible historical cash cohort and all matched adverse stress cases. Do not assume best 3% score is out-of-sample proof or prefer a version simply because it has a smaller loss than 3.5%. Warn if the major no-fresh-200WMA-crossing failure is not corrected.

CI evidence/results: completed as below.


## Verified result — 18 October 2026

**[GitHub Actions run 39117073135](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39117073135): SUCCESS — 21 tests passed** (3 fixed-small-percentage tests, 8 original seven-day execution-parity tests and 10 unchanged Cycle Trading allocation tests). [Full historical/8 synthetic path trading orders + USD/AUD FIFO after-tax account values](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39117073135/artifacts/12133046452).

All % gains/losses below are against **current weekly 2.5% of REMAINING AUD cash** with identical dates, tax proxy, FX, BTC prices and A$3 fees.

| In-sample historical window | 3.0% terminal account uplift | 3.5% uplift | Validation |
|---|---:|---:|---|
| 2017 completed +650/+750/+850 | **+0.994%** | +1.988% | each has only ONE fresh below-200WMA BUY |
| 2017 completed +900 | 0.000% | 0.000% | no new below-WMA signal, zero BTC bought by either |
| 2021 completed +650/+750 | **+2.427%** | +4.417% | 39 eligible purchases |
| 2021 completed +850 | **+2.600%** | +4.863% | 30 eligible purchases |
| 2021 completed +900 | **+2.642%** | +5.061% | 22 eligible purchases |
| 2025/26 RIGHT-CENSORED +650/+750 | +0.843%* | +1.667%* | six eligible purchases |
| 2025/26 RIGHT-CENSORED +850 | 0.000%* | 0.000%* | no fresh WMA gate |

*Through archived 2026-10-05; no knowledge of later bottom or trading outcomes.* The repeated +650/+750 cohorts in a cycle have identical chronological purchases; they are NOT independent validation samples.

| Adversarial historic prefix / new forced decline | Simulated terminal BTC vs old pre-shock price | 3.0% vs 2.5% after-tax AUD | 3.5% vs 2.5% |
|---|---:|---:|---:|
| 2017 +750, additional 50% decline | 55% | −0.745% | −1.505% |
| 2017 +750, additional 50% decline | 105% | +2.578% | +4.825% |
| 2017 +750, additional 70% decline | 55% | +0.729% | +1.223% |
| 2017 +750, additional 70% decline | 105% | +3.991% | +7.397% |
| 2021 +650, additional 50% decline | 55% | **−3.689%** | **−6.924%** |
| 2021 +650, additional 50% decline | 105% | +0.326% | +0.258% |
| 2021 +650, additional 70% decline | 55% | **−3.299%** | **−6.513%** |
| 2021 +650, additional 70% decline | 105% | +0.281% | −0.109% |

**Interpretation:** 3.0% provided about half the observed historical total-account benefit of 3.5%, with roughly half the worst adverse aftertax account cost, because it buys less extra BTC in those declines. The policy remains LESS safe than 2.5% in some prolonged bearish markets; it is not a guaranteed win and wasn't verified in untouched cycles. The 3.0% rule does not improve first entry timing and cannot buy when no new WMA crossing occurs.

**Decision:** Document research-only; no live Streamlit or ntfy changes. For possible future live adoption, explicitly choose user risk budget, obtain realistic ASX:IBIT weekday price/fees/spread/FX and the user's actual SMSF tax phase, ensure true market BUY WATCH/ledger parity, and do not claim 20% ex-post bottom-error from this exposure change. Production V5.8.2 research/source parity audit is independently documented in `docs/research/production_v582_causal_budget_audit_20261018.md` and must not be confused with Cycle 3.0% residual-cash buying.
