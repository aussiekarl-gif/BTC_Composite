# Research: flexible-length BTC DCA and 25% *average execution-price* goal

**16 October 2026 — exploratory, research only. DO NOT PROMOTE to Production.**

GitHub CI: https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38882027400

Implementation: `engines/research/adaptive_dca_execution.py`
Tests: `tests/test_adaptive_dca_execution.py`
Draft PR: https://github.com/aussiekarl-gif/BTC_Composite/pull/90

## User constraints now clarified

- Buying and selling duration may be **any length**; 12 and 16 weeks were only comparison baselines. A buy/sell leg can accelerate, pause, resume or end based on observations.
- 25% is a target for the **BTC-quantity-weighted average execution price of the trading leg** relative to the ex-post major/local cycle turning price. Individual orders may be better or worse.
- Prefer measuring **both buying and selling within 25%** in each completed cycle and reporting overall mean, median and tail errors separately. Do not allow a very lucky cycle to obscure missed or poor cycles.
- Buy effective price: total AUD cash spent (including the A$3/order fee) / total BTC acquired. Sell effective price: net AUD receipts / total BTC disposed. Fees cannot be double-counted.
- Illustrative equal-AUD buys at 110 and 140 against low 100 have effective BTC acquisition price 123.2: **23.2% buy error**, although one fill is 40% above bottom.
- Fixed A$3/order is applied to each simulated execution; the example has **NO SMSF CGT**, ETF management fee, spreads, or FX cost.

## Adaptive research engine (purely causal rules relative to supplied risk)

- Starts each week using **previous** weekly BTC/AUD price, risk score and trailing 20/50-week averages. Trades at current close (idealised).
- Low risk <=0.35 permits buying; tranche percentage of **remaining available AUD** depends on risk, previous-week trend and drawdowns. Cash carries forward without a fixed expiry.
- High risk >=0.60 arms exit monitoring; requires previous-week drawdown from observed high of 10%, 15% or 25% plus price under trailing 20WMA; trade rate depends on drawdown and trend. Selling can pause if price recovers. No commitment to a 12- or 16-week plan.
- Plans/legs are groups of same-direction executions, **including pauses without actual orders**. Calendar duration may therefore exceed the number of trades.
- Trades are in AUD with **A$3 brokerage per filled order**.
- Historical `risk_score` master point-in-time integrity remains unverified and 2016–2026 sample heavily researched, so these are NOT out-of-sample results.

## Results against 557 valid weekly paired observations 2016–August 2026

| Exit-confirmation drawdown | Last available A$ account value (pre-CGT) | Actual orders | Buying orders | Selling orders | Completed feasible matched pairs | Both sides average within 25% |
|---|---:|---:|---:|---:|---:|---:|
| 10% | 305,789,901 | 322 | 249 | 73 | 5 | **3 of 5** |
| 15% | 293,387,383 | 303 | 233 | 70 | 3 | 1 of 3 |
| 25% | 296,181,224 | 252 | 187 | 65 | 3 | 1 of 3 |

These huge nominal AUD terminal values reflect allocating A$500k to BTC in 2016; they **do not represent forward 2026 investment projections**. The scenarios have different numbers of completed eligible round trips and their results cannot select future production settings. The model's apparent simplicity hides an important drawback: many trades and potentially large SMSF realised-gain liabilities are not yet reflected in wealth.

### Example per-pair 10%-confirmed adaptive errors

| Start sale | Start rebuy | Sell execution error | Buy execution error | Both <=25%? |
|---|---|---:|---:|---|
| 2018-02-12 | 2018-12-10 | 21.94% | 12.61% | Yes |
| 2019-10-07 | 2019-10-14 | 4.72% | 28.94% | No |
| 2021-05-24 | 2022-05-30 | 46.38% | 41.30% | **No** |
| 2024-07-01 | 2024-07-08 | 0.00% | 9.25% | Yes |
| 2025-03-17 | 2025-03-24 | 5.08% | 3.86% | Yes |
| 2025-10-27 | 2025-11-24 | 8.65% | 51.52% | Censored |

The 2025–2026 incomplete 26-week future buy comparison is **excluded** from the eligible count. It must not be treated as a success.

### What must be improved, not hidden

- Even with no fixed duration, the 2021 sell and 2022 rebuy pair was **~46% below the available high and ~41% above the available low**, respectively. The biggest cycle is not solved.
- This is NOT a truly tradeable point-in-time model yet because the audit master risk scores need source-timestamp integrity checks.
- Choosing the 10% rule from in-sample performance risks overfitting.
- No annual SMSF CGT, 12-month parcel-age checks, transaction spreads or fund overheads are in the account outcome.
- Comparisons to older fixed-window models must first harmonise 0.3% proportional trading friction versus A$3 flat brokerage.
- AUD execution errors use hindsight reference highs and lows only for **post-simulation scoring**. Different oracle windows give different error rates.

## Proposed next experiments

1. Add **adaptive sell urgency** to avoid 2021's 53-week liquidation, including partial early profit-taking plus confirmed bear-market exit; do not cap all trades to a fixed number of weeks.
2. Add **adaptive buy cash reserve** and capitulation/recovery evidence to avoid buying too aggressively before the full 2022 bear-market bottom.
3. Backtest full SMSF cost-basis ledger: 10% effective CGT after holding >=12 months, 15% for short-term assets, correct gains/loss carry-forward, A$3 per trade, fund/pension status and after-tax closing value.
4. Pre-register a small small parameter set based only on earlier data, then hold out later data; genuine prospective paper trading is the clearest validation given repeated inspection of 2016–2026.
5. Show entry/exit average price error, both-within-25% pair frequency, number of missed cycles, terminal after-tax BTC/AUD, and worst cash/equity drawdowns. Keep Production, portfolio and master unchanged.
