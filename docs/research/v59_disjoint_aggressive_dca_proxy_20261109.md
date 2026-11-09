# Aggressive risk-banded BTC DCA: disjoint-window proxy audit (2026-11-09)

**Disposition: RESEARCH ONLY. NO LIVE ALLOCATION CHANGE.**

This exploratory audit compares the existing-like 1x maximum ordinary
risk multiplier, 2x intermediate and user-preferred 3x risk-banded
multiplier, applying the same eligibility gate at risk > 0.50. The
signal bands are from \`engines/research/v59_dynamic_risk_policy.py\`:
risk <=.10 ->3x; <=.20 ->2x; <=.40 ->1.5x; <=.50 ->1x; >.50 ->0x.

## Input and matching convention

- Source: private \`aussiekarl-gif/btc-audit-data\` master
  \`btc_audit_backup.csv\` fetched on 2026-11-09.
- Available **557** complete weekly rows, 2016-01-04 to 2026-08-31,
  \`btc_price_aud\` and \`risk_score\` with exact \`risk_score_source\`:
  **Walk-forward Power Law**. This is NOT the full V5.8.2 composite or
  the live V5.9 risk signal. Historical source-vintage verification is absent.
- Signal: only the **prior** week's stored risk. Execute the next Monday
  at the next weekly BTC/AUD price. No same-week risk used to size trades.
- Independent 2-year calendar windows, reset at A$500,000 initial cash each.
  Windows are disjoint in dates but **not** independent BTC market cycles.
  They are descriptive, not out-of-sample alpha estimates.
- Deployable base: (cash - protected reserve) / max(weeks to review,1);
  multiply by min(risk band multiplier, ceiling 1/2/3), buy only while risk
  <= 0.50; **maximum weekly buy 5% of initial capital (A$25,000)**.
- Fees and spread/slippage proxy: A$3 *per filled order* plus 0.30% of
  notional net of flat fee on each buy. No leverage, sales, interest,
  ETF tracking costs or taxes. This is BTC/AUD spot proxy, NOT ASX:IBIT
  execution history. Weekly proxy prices need their own source audit.
- Final equity = BTC units × last historical BTC/AUD price plus AUD cash.
  Drawdowns use the matched weekly BTC+cash equity path.
- 2016-2025 windows reviewed at their last Monday; 2026 is **partial**
  through 2026-08-31, and its *review date* is 2027-12-31 (not an
  artificial forced liquidation or allocation by the last observed date).

## Exploratory results — A$0 protected reserve

Numerical results from a direct read-only calculation on the private
master (2026-11-09); reproducible Python CLI and deterministic tests
are provided in this PR. The numeric historical run is **not** a
certified GitHub full-dataset CI run because the source master is private.

| Window | 1x BTC | 3x BTC | BTC change | 1x total equity A$ | 3x total equity A$ | Equity change | Worst drawdown 1x / 3x |
|---|---:|---:|---:|---:|---:|---:|---|
| 2016–17 | 410.768 | 682.672 | +66.19% | 7,370,897 | 12,009,464 | +62.93% | -34.35% / -37.42% |
| 2018–19 | 61.960 | 81.978 | +32.31% | 654,047 | 865,351 | +32.31% | -32.50% / -38.99% |
| 2020–21 | 15.757 | 28.991 | +83.99% | 1,394,266 | 2,165,368 | +55.31% | -36.52% / -42.60% |
| 2022–23 | 13.817 | 15.680 | +13.48% | 873,280 | 991,018 | +13.48% | -10.60% / -17.07% |
| 2024–25 | 4.341 | 4.974 | +14.59% | 569,759 | 652,886 | +14.59% | -23.85% / -26.92% |
| 2026–Aug only* | 1.646 | 3.458 | +110.13% | 512,798 | 522,359 | +1.86% | -5.17% / -12.37% |

*2026 is incomplete and **not** a forecast or the user's actual
2026-start portfolio. The stored historical risk score ends on
2026-08-31. This hypothetical strategy starts January 2026, not
November 2026.

### Protected-cash sensitivity

With A$100,000 protected instead of A$0, the 3x-minus-1x
equity improvement becomes, respectively: 2016–17 **+61.89%**,
2018–19 **+27.16%**, 2020–21 **+50.76%**, 2022–23 **+11.80%**,
2024–25 **+12.02%**, and partial 2026 **+1.50%**.

For the 2026 partial A$0-reserve proxy at 2026-08-31, 1x held
**A$334,262 cash** and 3x **A$147,195 cash**. The more aggressive
policy therefore already tied up substantially more capital. An
*instant hypothetical further 50% BTC price drop*, with **no new
trades**, would hit the 3x portfolio much harder: approximately
**A$334,773** total versus **A$423,530** for 1x. That is a mechanical
valuation stress, NOT a probability forecast.

### Critical timing sensitivity

The choice of review date strongly changes partial-period comparisons.
Artificially forcing the partial January-August 2026 program to
finish by the last available August price produces a different
comparison, including a roughly **-3.8% BTC shortfall** for 3x versus
1x. Extending review to 2027 gives the +110.13% BTC *units* difference
shown above because more cash deliberately remains unspent under 1x.
Neither comparison proves one policy will produce better future
risk-adjusted returns.

## Interpretation

- 3x beats 1x on BTC units in the five completed *selected* two-year
  proxy windows, but has **worse worst drawdowns in every window**
  and uses cash sooner. These descriptive gains are not robust
  walk-forward proof and include a very early, unrepresentative era.
- Accumulated BTC units are **not** a sufficient decision criterion:
  terminal AUD cash, residual optionality, total equity, liquidity,
  reserve, drawdown and downside scenarios are essential.
- The central research master weekly \`risk_score\` is a separate
  retrospective Power Law proxy; archived cross-provider risk
  publication timestamps and historical revisions are unverified.
  Full frozen Production V5.8.2 and live V5.9 risk are NOT reproduced.
- This script is standalone and read-only; it cannot touch Production,
  Streamlit, portfolio writes, ntfy or the authoritative master.
- Independent evidence is required: dated source vintages, true live
  V5.9 curve and exceptional-bottom events, verified IBIT/AUD
  next-tradable fills/spread/fees, 2026-start cash schedule, partial
  holdout testing, and portfolio/UI/notification parity.

## Reproduction

On a trusted machine with both repositories accessible, run
\`python -m engines.research.v59_disjoint_risk_band_proxy --csv <path-to-private-btc_audit_backup.csv> --out <local-private-report.json>\`
from \`BTC_Composite\`. Do not copy the private master into the public
repository. Deterministic unit tests run under the existing
\`V5.9 runway cap research tests\` PR workflow.

**Decision: KEEP PRODUCTION V5.8.2 AND LIVE SIZING FROZEN.
Continue risk-provenance and executable-price acceptance;
do not promote 3x merely because the old chart wins on selected past eras.**
