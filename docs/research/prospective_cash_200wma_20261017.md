# Prospective BTC accumulation from 2026 AUD cash — original 200WMA percentage engine
17 October 2026 | Research only · **NOT historical-live parity verified**

## Why this was necessary

The historically strong day500 staged SELL → 200WMA recovery BUY backtest (2017/2021 completed observations) assumes an investor already owned Bitcoin at the prior halving and sold original BTC around day500. An investor who instead began buying BTC/ASX:IBIT in **2026** did **not** have holdings at the 2 September 2025 day500 SELL window, and cannot fund a real 2026 buyback with fictitious earlier sale proceeds.

To make the originally chosen technical indicator usable going forward **without pretending that 2025 sales occurred**, this experiment reuses precisely the original `shared_cycle_policy.recovery_buy_budget_fraction()` signal but with a **newly confirmed fixed AUD starting budget** derived from cash actually available now. This is a **funding adaptation**, not a continuation of the historically proven self-financing after-tax round trip. Its forward results are unknown and its target average 20/25% buy-error has **not** been established.

## Prospective entry and DCA-in rules (unchanged technical indicators)

- On a **user-confirmed calendar day** (today in Brisbane, never backdated), initialise a fixed starting AUD cash budget less than or equal to BOTH the saved portfolio's recorded available cash AND separately broker-confirmed free cash **after** unpaid tax and other reserves. No assumed A$500k, no new cash injected.
- Start monitoring **the following day**. BUY activation occurs only after the immediately previous *completed* BTC/USD daily close is strictly **below** the **200 exact, prior seven-day-spaced closes** (200WMA). There is no predicted calendar trigger and no purchases invented for periods before enrolment.
- After activation, eligible model reviews occur every **7 calendar days**. The original adaptive-recovery percentages remain:
  - **2.5% of FIXED starting cash budget** when previous BTC close is at/below the prior 200WMA;
  - **15%** during confirmed recovery within 1.25×200WMA when prior BTC closes and 50-day average trend support it;
  - **4.5%** above that recovery band up to 1.5×200WMA; otherwise **1%**.
- The number is a **percentage of the anchored starting cash**. This is *not* the current simplified daily 2.5% of `remaining` cash, which compounds downward every eligible trade. Future percentages are unknown until the previous close for each future review.
- The research preview exists ONLY on the dated weekly review itself, with a fresh user-confirmed broker free AUD cash number. Historical/missed review dates show **no retroactive AUD order**. Actual ASX:IBIT shares would still need separately verified executable broker quotes and whole-unit/fee rounding.
- Conservatively subtract all post-enrolment executed buys and fees of unknown or cycle-funded source from the original budget; user-labelled Independent cash buys may be excluded from this ONE programme's budget, but still reduce the recorded account and broker cash. No "reinvestment" without an executed buy, and no unrecorded outside transfers.
- Recorded buys during the current seven-day calendar window block a new duplicate research suggestion. Unspent cash is capped by both the fixed budget and the recorded account balance, plus manually verified free broker cash after liabilities.
- The saved portfolio ledger **before and on the starting date is hashed** for consistency. Editing historical trade cost, holdings or amounts after enrolment blocks the budget until reconciled. Separate Streamlit sessions cannot overwrite changed portfolio snapshots during enrolment; only a deliberate user form submit stores this *metadata*.

## Streamlit UI

**Cycle Trading — Research → Trading decision → 2026 onward — forward cash-funded 200WMA DCA (Research)** (expand).

Before enrolment, manually confirm broker available AUD after unpaid taxes and reserves, enter the portion you want to earmark, tick the confirmation and press **Save prospective research budget**. No action is taken automatically. This stores one additional research-only configuration object in the **existing single** portfolio JSON; it does not create trades, notifications, brokerage orders or new spreadsheets. The enrolment start is today's date; 2025 backtesting top/bottom dates are irrelevant for your recorded 2026 holdings.

After enrolment, the panel shows anchored budget, later recorded spending and actual unspent amount, whether the 200WMA trigger has appeared *since* enrolment, historical review dates, next review and last observed percentage. It requires a fresh manual verified broker cash input before showing a same-day AUD **research preview**. The existing main daily BUY/HOLD/SELL section and ntfy remain unchanged, with the currently unverified historical-to-live parity disclaimer.

## Status / limitations

- **No automated orders, no ntfy changes, no automatic enrolment.** Real portfolio records and existing trades remain untouched until the user explicitly submits their optional research budget configuration.
- The last Bitcoin halving's confirmed sale window ended in 2026 and cannot be retroactively executed on newer 2026 positions. A future halving date and its +500 SELL review must be confirmed later. This PR does **not** introduce a new sell policy or claim prospective buy-and-sell superiority.
- The 2017/2021 after-tax historical backtest measured capital recycled from actual (simulated) BTC sales. The **new cash-funded prospective case was not included in those results**, so their +217%/+154% relative advantage should NOT be attached to this new programme or current daily live notification.
- An early 200WMA trigger can fail to materialise. The strategy could leave new money in cash while price rallies. A later local trough can still arrive after much of the budget is spent, particularly with 15% original-budget recovery buys. The model has **not** established the 20% average target for a 2026 funding start.
- User-supplied broker cash is not independently verified by an API. The model does not know actual annual SMSF tax or pension phase, all ETF bid/ask conditions, slips, holidays, transferred funds, withdrawals or future prices. Recorded source labels are user attestations.
- With date-only purchase records, the model treats trades made on the enrolment day as part of the starting cash snapshot. It will not try to infer intra-day transaction order.
- State is stored as `cycle_forward_cash_dca_research` metadata. Do not silently reset or replace it; changing the planned budget requires a separately audited future feature.

## Audited files

- `engines/research/cycle_forward_cash_dca.py`: prospective fixed-budget engine; old technical signal imported verbatim
- `tests/test_cycle_forward_cash_dca.py`: dated trigger, original-budget sizing, no future leakage, no duplicate review, immutable past ledger, explicit user confirmation, broker-cash caps, stale sessions
- `engines/research/cycle_trading_app.py`: optional research-only Streamlit enrolment and review, separated from live decision
- `.github/workflows/research_cycle_trading_dashboard.yml`: unit tests and Streamlit regressions
- Production V5.8.2, Research V5.9, original historical research benchmarks, current live 2.5% daily DCA, existing daily ntfy, broker and Google Sheets transactions **unchanged unless user separately opts in**.

Next recommended research validation: replay this **exact** forward-cash-budget policy from multiple realistically declared historical entry dates WITHOUT optimising against later lows, compare to the current remaining-cash rule and fixed DCA on exactly the same capital, apply AUD/IBIT spreads, SMSF taxes, and measure actual BTC accumulated, cash remaining and VWAP timing errors. Only after that should it be considered for replacing live allocation alerts.
