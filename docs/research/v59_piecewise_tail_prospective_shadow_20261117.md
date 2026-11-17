# Prospective piecewise-tail risk shadow — 17 November 2026

**RESEARCH ONLY.** This candidate does not alter Production V5.8.2, live Research V5.9 risk, DCA Today recommendations, portfolio state, Stake orders, Cycle Trading, or ntfy.

## Objective

Compare the PR #302 piecewise-tail 3x-mid candidate against the existing forward strategies using genuine as-captured daily inputs. The candidate is deliberately not backfilled into older tape rows.

## Candidate mapping

The candidate transforms the raw, point-in-time walk-forward Power Law residual into a research risk score, then applies the existing V5.9 multiplier ladder:

| WF residual | Candidate risk score | Multiplier |
|---:|---:|---:|
| <= -0.32 | 0.000 | 10x |
| -0.31 | 0.010 | 5x |
| -0.30 | 0.020 | 3x |
| -0.25 | 0.030 | 3x |
| -0.10 | 0.049 | 3x |
| -0.04 | 0.200 | 1.5x |
| +0.02 | 0.400 | 0x |
| +0.20 | 1.000 | 0x |

Values between knots are linearly interpolated. Values outside the knot range are clipped to the nearest endpoint. The exact knots are stored in `engines/research/v59_forward_dca_tape.py`.

This is the same candidate tested in PR #302. It is not the active risk formula. It does not reproduce Benjamin Cowen's proprietary risk score.

## Evidence integrity

- The daily snapshot now preserves the raw `power_law_residual` alongside the existing R2 risk and includes it in the model-input fingerprint.
- The forward tape stores the raw residual only when it is present and finite.
- Older tape rows without a raw residual remain valid for existing strategies but are **ineligible** for this new candidate. No residual is reconstructed from today's historical data.
- If the raw residual is missing or invalid, the candidate multiplier is zero for that observation. Existing forward capture remains available for the other strategies.
- Sunday signal / following-Monday paper entry matching remains unchanged. A missing Sunday or Monday capture is not treated as a fill.
- Paper portfolios retain the existing illustrative A$510,000 reference, virtual 41% BTC / 59% cash starting mix, 5% pretax cash yield, cost assumptions and weekly purchase ceiling. These are not the user's actual broker holdings or executable IBIT trades.

## Comparison and decision rules

The scorecard adds `piecewise_tail_3x_mid` alongside the existing strategies and reports the number of observations eligible for the raw-residual candidate.

Interpretation must separate genuinely eligible residual observations, matched prospective Sunday/Monday pairs, purchases and remaining paper cash, BTC reference units and paper portfolio value, and matured 7/28/84-day BTC/AUD outcomes versus idle 5% cash.

Do not claim an advantage until the candidate has enough genuinely captured observations and matched execution pairs. At least 12 matched Monday pairs is only a trigger for human review, not statistical validation. A useful comparison also needs a meaningful number of low-residual episodes; a few weeks within one prolonged event are not independent market cycles.

## Safety

- No automatic purchases, sales, broker actions, or notifications are enabled by this candidate.
- No live or Production policy changes are authorised by this shadow.
- Missing prospective data stays missing; the append-only tape keeps the first captured row for each signal date.
