# Shared historical Cycle Trading policy — original-BTC and buyback-budget parity

**17 October 2026 · Research only · No promotion to live execution**

## What is now genuinely shared

Both existing HISTORICAL research simulators call deterministic methods
from [`shared_cycle_policy.py`](../../engines/research/shared_cycle_policy.py):

- `staged_exit_decision`: 2024/2020/2016 halving-relative
  day500 5% original-BTC sale; six weighted and trend-adjusted
  original-BTC stages days 525/532/539/546/553/560; optional weekly
  tail after 560. The 20% holdback variant **caps cumulative sales
  at 80% of original BTC through day560**. A later confirmed downside
  breakdown can still sell part of this tail, so 20% is NOT a
  permanently inviolable holding.
- `prior_price_regime`: 90 completed BTC/USD closes through
  yesterday; two-observation bearish breakdown and prior 50DMA
  confirmation. Uses no day's own execution price to decide the action.
- `recovery_buy_budget_fraction`: adaptive recovery buys from
  strictly previous 200 weekly closes and 50DMA recovery. BUY tranches
  are computed against **ORIGINAL AFTER-TAX REBUY BUDGET**, not the
  current cash balance.

The refactor is validated against an INDEPENDENT translation of the
legacy algorithm using dated provider CSVs and across 2017, 2021 and
2025 full 561/600/730-day exit observation windows. This checks
implementation parity, **not strategy profitability**.

The historical self-financing simulator still books FIFO BTC lots,
simplified SMSF CGT escrow, historical date FX and A$3 orders. Its
existing tests continue to run in the same CI workflow.

## What is NOT yet the same, and why

The existing Streamlit and ntfy recommended market allocations have
NOT been silently replaced. Their 2.5% initial BUY rule uses
**remaining AUD cash**, whereas the historical adaptive-recovery
backtest uses a percentage of the **original after-tax buyback budget**
and continues weekly after 200WMA recovery.

The old simple Streamlit SELL table applies percentages to
**remaining ETF units** (37.32% of initial units remain if all seven
tranches fill), whereas this validated historical SELL model is
based on the **original pre-day500 BTC inventory**, with capped
distribution and a conditional later tail.

No identical end-to-end BUY/HOLD/SELL outcome or after-tax BTC multiplier
has yet been demonstrated for the existing Streamlit and daily ntfy
cash-based suggested trades. **Do not apply a historical backtest
outperformance percentage to the simplified dashboard.**

## Exact original-position protection

[`cycle_position_anchor.py`](../../engines/research/cycle_position_anchor.py)
reconstructs inventory owned BEFORE day500 using executed BUY and SELL
transactions in the same existing portfolio ledger, then follows
post-day500 sale amounts separately under FIFO. Direct BTC and whole
ASX:IBIT units are handled as DIFFERENT assets; no imagined equivalent
BTC certificate or historical user holdings are inferred. An
unknown/malformed ledger fails closed.

For the halving **20 April 2024**, day500 was **2 September 2025**.
Purchases first funded in 2026 did **not exist at that sell window**.
The calendar and the Streamlit research page now explicitly note this.
It is not appropriate to size those historical day500 exit stages
against the user's current 2026 position.

## Shared in Streamlit and one daily ntfy

Both use `cycle_exit_stage_status` to display correct future/past
research review dates. This status is *calendar context only*.
The scheduled ntfy runner still cannot read the private Google
Sheets portfolio or broker account; it never invents original BTC,
A$ proceeds, holdings or CGT. The existing one-daily-message schedule,
no-extra-notification guarantee and manually executed
portfolio BUY/SELL records are unchanged.

## Next research milestone before upgrading live trade instructions

Implement and test a STATEFUL, versioned account-level full-cycle
engine with (i) a documented original 2029+ sell inventory anchor,
(ii) original-BTC tranches and 80% cap at day560,
(iii) a verified start to a weekly 200WMA-activated recovery phase,
(iv) preserved after-tax *initial* buyback budget and parcel/tax
escrow, (v) execution date/order idempotency, and (vi) correct direct
BTC vs ASX:IBIT unit sizing. Only once replay output matches this
engine exactly across dated test accounts should Streamlit and
ntfy label its suggested order amounts as model-validated.

Keep Production V5.8.2, Research V5.9, saved user trades and the
authoritative data master unchanged.
