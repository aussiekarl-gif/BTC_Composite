# Research audit: continuous BTC capital recycling (2026-10-16)

**Status: exploratory; NOT authorised for Production or portfolio action.**

GitHub Actions run: https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38875463740
Draft research PR: https://github.com/aussiekarl-gif/BTC_Composite/pull/90

## Question being tested

Would it make a material difference to carry sale proceeds from one BTC cycle into
later buying cycles, rather than start a new AUD 500k account for each ~55-week
holdout? YES: these are different questions. Fresh-capital holdouts are useful
for testing chronological generalisation, but cannot quantify the growth of
one continuously recycled account from 2016 to 2026.

## Reproducible experiment

- Data: read-only private central btc_audit_backup.csv, 557 paired weekly
  AUD price/risk observations, 2016-01-04 to 2026-08-31, 7-day maximum gap.
- Capital: AUD 500,000 on the same starting date for every scenario.
- Transactions: prior week's risk signal; current week's closing price,
  0.3% all-in cost on each buy or sell.
- Equal-tranche buying/selling over 1, 12, or 16 weeks per triggered plan.
  Once started, a plan continues even if risk reverses.
- Funds from every sale remain AUD cash available for subsequent buying.
- Buy-and-hold purchases on 2016-01-11, the strategy's first executable week.
- Ending account equity is BTC at the final AUD price plus uninvested AUD cash.
- No tax, market impact, actual execution uncertainty, or cash yield.
- These staged plans are **not yet 200WMA entry/exit signals**.

## Verified full-history results

| Strategy (buy/sell risk; weeks) | Terminal AUD | vs buy and hold |
| --- | ---: | ---: |
| Buy and hold | 84,619,254 | 1.00x |
| 0.25 / 0.75; immediate | 35,397,903 | 0.42x |
| 0.25 / 0.75; 12 / 12 | 100,654,685 | 1.19x |
| 0.25 / 0.75; 16 / 16 | 120,216,283 | 1.42x |
| 0.25 / 0.70; 12 / 12 | 137,734,100 | 1.63x |
| 0.35 / 0.60; 16 / 16 | 200,173,772 | 2.37x |
| 0.25 / 0.75; 12 / 16 | 122,884,877 | 1.45x |
| 0.25 / 0.75; 16 / 12 | 97,676,131 | 1.15x |

**Do not choose the top-performing row using this table.**
All rows are evaluated on the same history; even predeclared comparisons
provide no independent proof of forward excess return.

## Chronological regime diagnostic (each separate fresh-capital start)

This separate diagnostic deliberately resets to AUD 500k for each regime so
relative performance can be compared over identical local price windows.
It must NOT be substituted for the continuous full-cycle headline experiment.

| Strategy | 2016–2021 vs hold | 2022–Aug 2026 vs hold |
| --- | ---: | ---: |
| 0.25 / 0.75; 12 / 12 | 0.57x | 1.74x |
| 0.25 / 0.75; 16 / 16 | 0.70x | 1.68x |
| 0.35 / 0.60; 16 / 16 | 0.68x | 2.87x |

Early-period losses relative to buy-and-hold reveal a major weakness: selling
very early in large bull runs. For example, the 0.25/0.75 model triggered
selling in May 2017 and November 2020, well before later price peaks.
Conversely, 2025's maximum stored weekly risk score is approximately
0.741, so a rigid 0.75 threshold does not initiate a new 2025 high-risk
sell plan; an earlier sell plan began in December 2024.

## Why this is not ready to deploy

1. Historical risk_score values are labelled "Walk-forward Power Law" but
   point-in-time publication/revision audit is incomplete. Some inputs may
   be retrospectively reconstructed; previous-observation execution alone
   cannot cure that.
2. The window/risk table was inspected in-sample, so the 2.37x figure may
   reflect hindsight choice. The era split was inspected after seeing full
   history and is NOT an untouched prospective holdout.
3. Exact weekly closing-price fills, even with 0.3% trading cost, are
   idealised, especially at the resulting very large balances.
4. Tax treatment (personal vs Australian superannuation contexts), FX and
   effective cash yields may substantially alter the best policy.
5. 2015 screenshot hindsight bottoms are not part of this validated paired
   weekly risk data, which begins in January 2016.

## Next work to authorise any candidate change

- Audit point-in-time timestamps and source revisions.
- Design a research-only *risk-arm then confirm exit* policy, with
  momentum/200WMA trend confirmation to address premature bull-market sales;
  compare against the current staged baselines.
- Add selection strictly on preceding history, multiple sequential future
  tests, realistic fills, tax/cash yield scenarios, and missed-cycle costs.
- Preserve Production, the audit master, and any portfolio records until
  independently verified improvement meets explicit promotion criteria.
