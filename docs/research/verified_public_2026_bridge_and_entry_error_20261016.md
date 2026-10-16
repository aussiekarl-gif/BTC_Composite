# Independent public price bridge and 25%-average-entry audit (16 October 2026)

**Research only · DO NOT promote to Production or mutate the audit master.**

Successful [historical + test run #38888724291](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38888724291).
Implementation: [verified_recent_price_bridge.py](../../engines/research/verified_recent_price_bridge.py).
Safety tests: [test_verified_recent_price_bridge.py](../../tests/test_verified_recent_price_bridge.py).

## Reason

Historical research master had 557 paired BTC/AUD price/risk rows through
**31 August 2026**. The actual user's A$500,000 portfolio started in 2026,
but its actual transactions reside in My Portfolio/Google Sheets, not the
research master. Prior A$100m simulated accounts beginning in 2016 must
not be conflated with the user's 2026 wealth.

The bridge reads the **existing master strictly read-only**, obtains
Blockchain.com BTC/USD historical chart data and Frankfurter historical
AUD-per-USD rates, and matches each UTC Monday only to timestamps on or
before that Monday (rejects stale or future observations). It does **not**
write the new data to the authoritative master, portfolio or Production.

## Verified new data

| Evidence | Result |
|---|---|
| Master last paired date | 31 August 2026 |
| Added PUBLIC provider Mondays in in-memory research only | **6** |
| Fresh interval | 7 September – 12 October 2026 |
| Overlap between public BTC/AUD and archived BTC/AUD | **11 Mondays** |
| Median absolute overlap difference | **0.000%** |
| Maximum absolute overlap difference | **0.000%** |
| New master risk-score rows written | **0** |

The provider market snapshot and FX align perfectly across these sampled
overlap dates, but this does not verify underlying data release timing
at each historical weekly close and does not certify the original risk.

## Independent causal risk audit

For ALL weekly AUD-price observations, built an expanding strict-prior
quarterly-refitted Power Law regression on BTC/AUD and calendar days
since Bitcoin genesis. This is a deliberately independent **price-only
candidate**, **not** the existing Research WF Power Law based on USD
nor the stored multi-component composite risk. It produces a 0–1 score,
and each coefficient fit excludes the current/future price.

Compared 453 risk-scored historical weeks where archived risk was available:

- Mean absolute score difference: **0.2005** on a 0–1 risk scale.
- Maximum difference: **1.000**.
- Weeks differing by more than 0.20: **127**.

**Interpretation:** the price-only candidate and archived risk are
substantially non-equivalent. This does not prove the archive contains
lookahead; it does mean we cannot substitute one for the other, nor
label the causal candidate validated Production risk. A future audit
must verify the archived composite's component publication timestamps
and source vintage before promotion.

## Research 2026-start matched-capital valuations at 12 October 2026

Each model starts with a separate **A$500,000** fresh AUD account.
The January cohort executes from Monday 5 January; June cohort from
Monday 22 June. Prestart prices warm the indicators without prestart
trades. The June date is an example, not evidence that the actual user's
full capital was available that date.

| Model (A$ account marked to market before terminal CGT) | Jan cohort | June cohort |
|---|---:|---:|
| Immediate buy | $437,342 | **$664,883** |
| Equal AUD DCA 12 observations | **$555,214** | $633,418 |
| Historical adaptive sizing at 10% downturn confirmation | $497,335 | $652,162 |
| Proposed trend/reserve sizing | $549,025 | $625,987 |
| Cash only | $500,000 | $500,000 |

All strategies have **zero sells**. The 10%, 15% and 25% sell-confirmation
branches produce identical 2026 results; don't credit any sales logic for
them. All account values are before a hypothetical terminal forced-sale
CGT but inclusive of $3 brokerage per fill; the repository also reports
the conservative tax-on-full-liquidation sensitivity.

## Dollar-fee-inclusive BTC-quantity-weighted buying errors

Use the user-reported benchmark **US$57,717 on 30 June 2026**.
For each model purchase on date d:
`USD spent_d = AUD gross cash spent_d / (AUD-per-USD as of d)`.
Effective average price:
`sum(USD spent_d) / sum(BTC actually acquired)`.
Error:
`100 × (effective average USD/BTC / 57,717 − 1)`.
The benchmark is a **user-provided observed intraday low**, *not*
independently confirmed by the daily-average source or a predicted
final bottom. Report unused A$ cash separately; the score applies
only to BTC actually acquired.

| Model | Jan avg entry USD/BTC | Jan error vs low | June avg entry USD/BTC | June error vs low |
|---|---:|---:|---:|---:|
| Immediate buy | $91,469 | **+58.48%** | $63,235 | **+9.56%** |
| Equal 12wk DCA | $75,013 | **+29.97%** | $66,713 | **+15.59%** |
| Existing adaptive DCA | $82,414 | **+42.79%** | $63,775 | **+10.50%** |
| Trend/reserve challenger | $75,657 | **+31.08%** | $65,716 | **+13.86%** |

All January-start variants **MISS** 25%; all June-start variants
**MEET** 25% using the given benchmark. June adaptive invested
**97.0%** of A$500k; June trend/reserve invested **90.18%**.
A model that never buys does not qualify as a success; its score is null.

### Why this is not future-timing proof

- June 2026 was chosen for an *illustrative cohort after the fact*.
  A live investor in January cannot know with certainty there will
  be an observed low on June 30. The two cohorts have fundamentally
  different available entry opportunities.
- Without a full observed sell/rebuy cycle, the 25%-sell-error
  objective cannot be scored.
- Scores vary sharply across the starting regimes. Selection of
  the best date after viewing the bottom is hindsight and must not
  be presented as a causal entry-signal improvement.
- Archived composite `risk_score` has no verified per-component
  point-in-time source chronology.
- No ETF management, spreads, market impact, cash interest, actual SMSF
  annual-return rules or user-real transaction/portfolio values are
  included in the simulated portfolios.

## Next disciplined research

1. Test *predeclared, causal* starting/deployment gates against an
   always-on DCA benchmark. All comparisons must start **the same day**
   with the same cash, and held-out or prospective data must decide.
   **Do not** compare a January rule to a conveniently selected June
   post-bottom start as if both were implementable in January.
2. Reconstruct the real-time USD 200-week MA / momentum using strictly
   prior completed observations; explicitly distinguish *signal
   detection* from *position-size optimisation*.
3. Audit the actual stored risk components' publication dates and
   potential backfilled revisions before risking Production promotion.
4. Track actual user's portfolio 2026 fee-inclusive BTC-equivalent
   buy error on My Portfolio against editable US$57,717. The GitHub
   research workflow does **not** read private user purchases.
5. Keep [PR #90](https://github.com/aussiekarl-gif/BTC_Composite/pull/90)
   **draft**. Production, portfolio and audited master untouched.


## NEW: Causal January-funded drawdown activation stress test

Successful historical+unit test run:
[Research Verified Sep-Oct 2026 BTC Price Bridge #38889155427](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38889155427).

The user wants fewer than 25% *average acquisition-price errors* with Dynamic DCA, but starting a hypothetical June cohort because the market is already known to have bottomed in June is retrospective and cannot establish a tradeable entry signal.

Here the starting capital **really is available in cash on 1 Jan 2026** for every model. The model **waits** until the prior completed Monday shows Bitcoin already **30%, 40% or 50% below the preceding 52-week BTC/AUD high**, then switches on the exact same variable-duration adaptive sizing thereafter. Prices/risk are warmed with the prior archive. Each gate observation is t−1 relative to the earliest trading date t, and cannot peek ahead to June 30 or October close. All trade orders remain sequential and the account is self-financing with A$3 fees and the same approximate SMSF CGT accounting.

| Entry gate; same Jan 2026 cash | First executable gate Monday | Price decline known at trigger | BTC accumulated | Avg entry USD/BTC, after A$3 fees | Error relative to *user reported* $57,717 | Oct 12 marked A$ |
|---|---|---:|---:|---:|---:|---:|
| January adaptive with **no gate** | January | n/a | 4.141813 | $82,414 | +42.79% | $497,335 |
| ≥30% decline from preceding 52wk high | **2 Feb 2026** | 33.058% | 4.970803 | $70,636 | **+22.38%** | $596,807 |
| ≥40% decline | **9 Feb 2026** | 40.884% | **5.115268** | **$68,889** | **+19.36%** | **$614,147** |
| ≥50% decline | **9 Mar 2026** | 50.209% | 5.044130 | $69,527 | **+20.46%** | $606,000 |

The 30/40/50% triggers are **previous-week-causal**, but their *testing and selection* occurred after seeing the 2026 price history. This is NOT untouched out-of-sample proof. Critically: only buying legs occurred to Oct 12, so nothing establishes the quality of top timing or selling CGT.

All three gates invested more than **99.8%** of initial capital by Oct 12. Selling has not occurred, so **realised CGT so far is zero**, and terminal A$ marked account valuations above **exclude hypothetical final liquidation CGT**. The 40%-gate hypothetical after-liquidation figure was A$597,023.

### Transfer-risk warning

A gate requiring Bitcoin to fall 30–50% can miss an entire bull market if no such correction occurs. The next research step is to run fixed 52-week **same-start-date** negative-control periods from 2018/2020/2022/2024, not to tune the 2026 gate retrospectively and immediately promote it. A 40% gate is a *candidate*, not a recommendation to leave all remaining personal capital in cash indefinitely. The customer's actual purchase dates and amount are NOT incorporated; the A$500k fresh cash model is hypothetical.
