# FIRST contemporaneous mature-top reversal: aftertax AUD roundtrip verdict

17 October 2026 | Research only | PR #133

## Verdict: REJECT this candidate as a change to SELL timing

One predeclared candidate was tested: after the original staged day500 SELL has begun, immediately sell **up to an additional 20% of ORIGINAL BTC** on the FIRST genuinely new (False→True) `maturity_confirmed_reversal` warning between halving days 500 and 730. The indicator is identical to the already-defined `top_signal_horse_race.build_daily_signals` family and uses prices/indicators from strictly prior completed observations. The same original day500/core/tail staged exits continue otherwise. Total original position sold never exceeds 100%. No repeated alert sells, no choice of the eventual nearest top, no new indicator tuning. The buyback begins only on/after day744 at the first prior-close below strict 200WMA and uses the same weekly original after-tax budget adaptive-recovery fractions in both accounts.

This candidate **did not improve 2017 or 2021 at all**. On the currently censored 2025/26 price archive the observed differences are very small and mostly negative. Do NOT deploy this rule, modify the historical original strategy or change the live BUY/HOLD/SELL decision.

## Matched AUD self-financing comparison

Both hypothetical accounts own the SAME BTC originally bought at the historic halving for AUD500,000; they use the same daily BTC USD closes, last prior dated AUD/USD FX, A$3 per trade, FIFO SMSF simplified 10/15% immediate CGT escrow on gains and identical 200WMA buyback timing. Terminal values are **hypothetical portfolio liquidation after CGT**, and cannot be inferred to be your own actual 2026 SMSF holdings.

| Cohort | Window complete? | First new confirmed reversal in SELL window | Original after-tax AUD (0d lag) | Candidate after-tax AUD (0d lag) | Candidate relative improvement |
|---|---|---|---:|---:|---:|
| 2017 | Yes, day1150 | 13 Jun 2018 | 25,695,084.89 | 25,695,084.89 | **0.000%** |
| 2021 | Yes, day1150 | 8 Jan 2022 | 4,095,969.07 | 4,095,969.07 | **0.000%** |
| 2025/26 | No, cutoff 5 Oct 2026 | 21 Nov 2025 | 962,959.67 | 961,687.74 | **−0.132%** |

**Mechanism:** in 2017 and 2021 the first eligible confirmed reversal was so late that it did not change the original completed SELL distribution. Selling more based on that warning would not have rescued the late 2017 exit. In 2025/26 the first warning slightly changed WHICH planned original-position units were sold and when, even though **both policies ultimately sold the same total fraction of the original position**. That marginal timing difference was slightly adverse in the current truncated observation.

## Delay sensitivity: same decisions, later execution

Change ONLY the execution date of each predetermined tranche, not the signal or its size at decision time. This makes no claim that a specific daily BTC close was executable by ASX:IBIT. Real bid/ask, trading hours, commissions, ETF tracking, settlement and SMSF taxes could differ.

| Cohort | +1d: candidate vs original | +3d | +7d |
|---|---:|---:|---:|
| 2017 | 0.000% | 0.000% | 0.000% |
| 2021 | 0.000% | 0.000% | 0.000% |
| 2025/26* | −0.285% | −0.078% | +0.008% |

The marginal +0.008% at +7 days is **not convincing predictive evidence**. It is tiny and applies to a still-incomplete cycle. Nothing in the data supports selecting a seven-day delay to improve performance; doing so would be hindsight parameter fitting.

The fixed base/confirmed account with 2017 7-day SELL execution delay ended with A$23,150,770.82, versus A$25,695,084.89 for 0-day execution — a large price sensitivity unrelated to the new indicator. This highlights execution risk even for unchanged model events.

## What the test proved and did not prove

- **Proved internally**: The no-accelerator run matches the independent pre-existing `cycle_chronological_wallet.replay_chronological_wallet` on synthetic tests, including dates of WMA buys, order counts and tax-adjusted value; the first alert—not hindsight best/nearest—is used; edge triggered no earlier than day500 and no later than day730; late/carry-over warnings are not fresh; BTC cannot be oversold; simulated 1/3/7-day delays do not move decision dates; equal prices/FX and initial capital are used.
- **Not proved**: that historical October 2026 MVRV/NUPL export values are unchanged from what traders actually saw in 2017/2021; that past threshold design is out-of-sample; that future Bitcoin tops occur at a similar halving-relative age; that the delayed AUD close is executable by an IBIT order; or that an SMSF has the illustrated CGT rates or tax timing.
- This was **one frozen experiment**, not a sweep or optimisation. No true external test set exists: 2017 and 2021 are already researched, while 2025/26 remains right-censored.
- For the real user, BTC/IBIT first acquired in 2026 **could not** have participated in September 2025 SELL tranches. This is a *matched hypothetical historical position* only.
- There were **no changes** to Production V5.8.2, Research V5.9, live Streamlit calculations, My Portfolio entries, broker imports, daily ntfy or the one notification schedule.

## Decision and next priority

**REJECT the additional 20%-original FIRST confirmed reversal SELL.** Its warnings arrive too late relative to the original sale schedule, and it did not improve the two completed cycles. Do not endlessly refine a threshold against two past cycles.

The stronger next analysis is on the **BUY path**: in the 2021 cycle the original 200WMA activation occurred **159 days before** the eventual low. Inspect whether the weekly 2.5/15/4.5/1% of original after-tax cash schedule depleted reserves too early, what cash remained at the low and after, and its BTC holdings and mark-to-market drawdown. Compare one frozen reserve-preserving candidate against the same current original baseline including late or failed new lows. Evaluate gains and failures in a matched aftertax AUD/FX wallet without hindsight activation.

## Reproducibility

- Main code: `engines/research/first_confirmed_top_sell_roundtrip.py`
- Tests: `tests/test_first_confirmed_top_sell_roundtrip.py` (9), plus existing causal first-signal (10), chronological wallet (5), shared cycle policy (8).
- CI workflow: `.github/workflows/first_confirmed_top_sell_roundtrip.yml`
- Successful run: https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39024830536
- Detailed artifact: `first-confirmed-mature-top-sell-aftertax-audit` stores every dated SELL decision, delayed execution, BUY and AUD outcome for 2017, 2021, and censored 2025/26.
