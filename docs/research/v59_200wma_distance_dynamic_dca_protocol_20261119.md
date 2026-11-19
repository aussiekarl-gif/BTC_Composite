# V5.9 200WMA-distance dynamic DCA — research protocol

**19 November 2026 · Research only · Not a live recommendation**

## Decision

Simplify V5.9 accumulation sizing by removing Power Law residual risk from the new candidate's decision path. Use the prior completed BTC/USD close relative to a strictly prior-data 200-week moving average (200WMA). As the discount deepens, increase the percentage of currently available AUD cash allocated to a buy.

The model's primary output is always a **percentage**, not a fixed AUD amount. A separate execution adapter may calculate an illustrative AUD amount and whole IBIT units only after the percentage decision and only when a verified ASX:IBIT price is available.

Production V5.8.2, the existing live V5.9 implementation, Cycle Trading, notifications, saved portfolio data, brokerage and orders are out of scope and must remain unchanged.

## Signal definition

- Calculate 200WMA from 200 completed, consistently spaced weekly BTC/USD closes.
- Signal uses the latest completed weekly close and a moving average that excludes that close if that is the established causal convention in the existing data pipeline; document the exact timestamp convention in code and tests.
- ratio = prior_completed_BTC_close / prior_200WMA.
- discount_pct = max(0, (1 - ratio) * 100).
- Thresholds: 20% below = ratio <= 0.80; 25% below = ratio <= 0.75; 30% below = ratio <= 0.70.
- A deeper discount must never produce a smaller allocation.
- No Power Law risk score, valuation-risk score, future close, or retrospective low may influence the signal or sizing.
- Do not require a strict below-200WMA gate for every buy: retain a clearly labelled base DCA rule, and let the deep-discount tiers increase its percentage. Evaluate a separate earlier-entry variant only as a separate candidate.

## Candidate percentage ladders (all percentages of available AUD cash)

These are **test candidates**, not approved settings:

| Candidate | Base allocation | At 20% below | At 25% below | At 30% below |
|---|---:|---:|---:|---:|
| A — measured | 2.5% | 3.5% | 5.0% | 7.5% |
| B — stepped | 2.5% | 5.0% | 7.5% | 10.0% |
| C — aggressive | 2.5% | 7.5% | 10.0% | 15.0% |

Interpret the table as the target percentage of *remaining available cash* at that observation, not additive percentages and not a percentage of original capital. If the price is 27% below the 200WMA, use the 25%-below tier. No interpolation in the first test; a separate continuous interpolation sensitivity may be reported.

The base rule and review cadence must be tested consistently against:
1. Current 2.5% remaining-cash BUY policy with its seven-calendar-day executed-trade cooldown.
2. A fixed weekly DCA control.
3. Candidate A, B and C.
4. A distinct early-entry variant if it adds buys above the 200WMA; do not blend this into the primary results.

## Capital and execution guardrails

- Preserve the existing ordinary maximum weekly allocation of 5% of original contributed capital as a hard cap. Enforce it internally in percentage terms; do not display a fixed-dollar recommendation.
- Also cap each buy at the available cash balance. Never allow a negative balance or leverage.
- Retain the existing minimum-ticket rule and at least seven calendar days between executed buys. Test weekly cadence separately from any daily signal cadence.
- Use the next eligible ASX trading session for IBIT execution, not the BTC weekend close. Use historical ASX:IBIT prices and spread/fees when data are available; otherwise label BTC/AUD proxy fills clearly and do not present them as actual ETF execution.
- Keep cash yield, fees, FX, ETF drag and all cohort assumptions identical across matched candidates.
- The user's ordinary weekly cap is a safety limit, not a target to spend every week.

## Required evaluation

For identical matched start dates and cash:
- BTC / IBIT exposure acquired and weighted average entry price.
- Percentage of available cash allocated, percentage of original capital deployed, and remaining cash percentage.
- Final total portfolio value and BTC-equivalent exposure.
- Maximum drawdown and worst cohort.
- Number of buys and eligible weeks.
- False-entry / renewed-low stress, including deeper falls after first reaching each threshold.
- Missed-rally / prolonged-above-WMA stress, including cash left uninvested.
- Same-net-spend deployment-neutral entry comparison, clearly labelled hindsight diagnostic rather than a deployable strategy.
- Train and holdout results separately. Historical overlapping cohorts are not independent cycles.
- Current prospective cohort separately, with no invented future values.

Do not select a ladder solely because it has the best BTC entry price, uses the most cash, or produces the prettiest distribution. It must improve total portfolio outcomes without unacceptable downside or cash-deployment failure.

## Prospective paper record

Add an append-only, point-in-time record only after the model implementation is tested. Store signal timestamp, prior BTC close, prior 200WMA, discount percentage, selected allocation percentage, eligible next ASX session, actual/reference IBIT price and source, and whether the hypothetical buy could execute. Never backfill or rewrite prior records. A paper record is not a broker order.

## Acceptance tests

- Boundary tests at exactly 20%, 25%, and 30% below, plus just above/below each boundary.
- Monotonicity: deeper discount never lowers allocation.
- Percent-of-remaining-cash denominator and weekly-cap enforcement.
- Seven-day cooldown and no duplicate daily buys.
- No look-ahead in WMA or execution date.
- Missing/invalid BTC, FX or ASX quote fails closed; no synthetic quote.
- No Power Law field is read by the new allocation function.
- No changes to Production V5.8.2, current live V5.9, ntfy, portfolio writes or broker actions.

## Prior evidence and limitations

Earlier 200WMA-only tests showed that strict below-WMA gating can leave substantial cash uninvested and miss rallies. The new proposal is specifically a **dynamic percentage increase at deeper discounts**, not an exclusive wait-for-the-bottom strategy. The 20/25/30% tiers are user-proposed hypotheses and require matched historical and prospective validation. BTC/AUD spot proxies are not equivalent to executable ASX:IBIT fills.