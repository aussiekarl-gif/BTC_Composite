# Research scenario — 40% peak/bottom execution error, SMSF CGT and diminishing returns

**Date 16 October 2026 · research only, NOT a forecast, live rule, or validated backtest.**

* Code: [diminishing_cycle_smsf_projection.py](../../engines/research/diminishing_cycle_smsf_projection.py)
* Tests: [test_diminishing_cycle_smsf_projection.py](../../tests/test_diminishing_cycle_smsf_projection.py)
* Successful GitHub CI and scenario run: https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38878726336
* Draft PR: https://github.com/aussiekarl-gif/BTC_Composite/pull/90

## Meaning of the error

`sale_price = actual future peak * (1 - 0.40)`; `reentry_price = actual future bottom * (1 + 0.40)`. This is a **price** error at BOTH ends, not a 40% timing-in-weeks error, 40% hit-rate, or a slip from any pre-existing indicator. The actual peak and bottom are future unknowns, so this is an **ex-post opportunity sensitivity**, not a causal trade-execution strategy.

Ignoring brokerage and tax, each round trip increases BTC units only when
`0.6 / (1.4 * (1 - drawdown)) > 1`. Break-even drawdown is **57.14%**.
With 10% tax on almost entirely unrealised-to-date gains at sale, the threshold
can approach **61.43%**. It depends on the AUD cost basis and capital losses.

## Capital, taxes, brokerage

- Start capital: **AUD 500,000**; BTC/AUD reference price normalised to 100 for simplicity (NOT a current BTC price).
- Three consecutive notional four-year cycles to approximately 2038.
- Start with 16 equal-cost purchases. At each future top, sell all BTC spread across 16 fee-bearing synthetic orders **at the same reference execution price**, then repurchase via 16 orders at the bottom-error price. Real weekly staging is not yet simulated.
- **AUD 3 fee per order** = 16 initial buys + (3 × 16 sells + 3 × 16 repurchases) = **112 orders, AUD 336** trading brokerage. Buy-and-hold pays only 16 × 3 = AUD 48.
- Assume each whole position qualifies for **10% effective CGT** in an SMSF in accumulation on net gains after expenses. CGT paid immediately at each sell; net proceeds reinvested. Real-world CGT depends on holding periods, parcel records, fund accumulation/pension status, other gains/losses, and annual tax timing. No tax on final unrealised holdings.
- Record carryforward capital losses, but exclude all ETF management fees, spreads, FX changes, slippage, SMSF administration, inflation, additional capital flows or money held in cash.

## Assumptions (bull price multiples measured from previous bottom)

| Hypothetical environment | Sequential bull rises, x | Peak-to-bottom BTC corrections |
|---|---|---|
| Conservative | 3.0×, 2.5×, 2.0× | 60%, 45%, 30% |
| Middle | 4.0×, 3.0×, 2.5× | 70%, 60%, 45% |
| Strong | 5.0×, 4.0×, 3.0× | 75%, 65%, 55% |

## Calculated outcomes: end of third hypothetical bear market (in AUD)

| Case | Buy-and-hold | Trade (after CGT and $3 orders) | Relative to hold | Realised CGT paid | Trading brokerage |
|---|---:|---:|---:|---:|---:|
| Conservative | $1,154,889 | $560,147 | -51.50% | $46,119 | $336 |
| Middle | $989,905 | $1,079,611 | +9.06% | $112,389 | $336 |
| Strong | $1,181,137 | $2,064,841 | +74.82% | $265,647 | $336 |

In the middle scenario, the first completed sale-reentry improves BTC holdings
by 34.5%, the second by 4.8%, and the third **loses 22.6% BTC**.
Thus diminishing bear-market amplitude can erase the first cycle's advantage.

## Interpretation and required follow-up

1. This is **not** a revision of the historical A$393.65m in-sample result.
   Applying 40% peak/bottom errors requires a separately specified transaction
   policy and historical source dates; the SMSF tax must be computed lot-by-lot
   from actual AUD trades, not by multiplying terminal equity by 90%.
2. A$3 flat fees are negligible at A$500k position size but spreads, custody,
   ETF annual fees and income taxes may not be.
3. Later BTC drawdowns below approximately 60% eliminate a reliable repurchase
   advantage for 40%-off peak/trough trades with realised CGT.
4. Test a causal decision-based trade policy (risk arm + trend confirmation,
   USD 200WMA reference) with FIFO parcel age (10% vs 15%), CGT loss offsets,
   accum/pension treatment, withdrawal and terminal after-tax balances, plus
   realistic future/forward paper trading. Keep Production unchanged.
