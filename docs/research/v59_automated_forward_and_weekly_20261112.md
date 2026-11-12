# Automatic BTC buying-timing research — 12 November 2026

**Research automation only.** Does not change Production V5.8.2,
Research V5.9 live DCA, Cycle Trading, the single daily ntfy, user holdings,
Google Sheets, AAA cash reserve or Stake orders.

## Two independent automatic activities

| Track | Schedule in Brisbane (UTC+10; no DST) | Retention and purpose |
|---|---|---|
| **DAILY FORWARD VALIDATION** | 11:23 AM daily (after completed UTC close; GitHub Actions scheduling can be delayed) | Independently capture *today's as-of* actual V5.9 risk, price, FX, Sunday 200WMA with a capture timestamp and code SHA into a dedicated append-only `research/v59-forward-tape` branch. Record daily results and only grade later real saved observations; Monday paper entry can be evaluated only after Sunday signal and Monday close both captured. No historical backfill of missing dates. |
| **WEEKLY HISTORICAL BACKTEST** | Mondays 1:17 PM | Re-run PRs #259/#260/#261's fixed 2017–24 BTC/AUD reconstructed-risk horse race, false-bottom and 200WMA strategies against newly fetched public prices and lagged FX. Full result JSON retained as an Actions artifact for 90 days. Doesn't count overlapping history as new independent market cycles. |

Both also accept manual `workflow_dispatch`, but **do not need ChatGPT or manual 'continue'** for ordinary scheduled runs.

Scheduled GitHub Actions are **best effort, not guaranteed punctual**: GitHub can delay, skip or disable schedule events. A daily evidence gap cannot be repaired by recalculating yesterday's score today without destroying prospective proof. On absence, fail closed and flag the issue rather than silently inventing past provider vintages.

## Forward evidence and research scope

- Frozen prospective data branch: `research/v59-forward-tape`
- Market evidence file: `data/research_v59_forward/daily_observations.jsonl`
- Scoreboard: `data/research_v59_forward/scorecard.json`
- First recorded capture wins for each UTC signal date; no overwriting
  earlier published risk, WMA or market close when the provider later revises.
  Missing days are visible and **never backfilled**.
- *Daily* WMA ratio is the latest **completed Sunday** 200-week
  BTC/USD mean; on Sunday it exactly aligns with the historical study's
  prior-Sunday definition. Monday proxy execution is evaluated only with
  the following day's captured market close.
- Paper strategies: R2 risk-gated 1x, up-to-3x below risk 0.50, up-to-3x
  only at risk <=0.20, up-to-3x only at or below 200WMA, and up-to-3x
  no higher than 10% above 200WMA.
- The paper portfolios start at A$510,000 reference value, with
  **41% *virtual* pre-existing BTC** and 59% paper AUD cash, 5% pretax
  annual cash return, A$3 paper order cost, 0.3% friction, 0.25%
  annual ETF-like drag and A$25,500 weekly purchase maximum.
  31 December 2027 is an **illustrative** research review point,
  *not* a real user's forced deployment deadline.
- Once new evidence matures, the scorecard reports 7/28/84-day
  **BTC/AUD spot reference excess over idle 5% cash**, never before
  the actual future close is captured. It also shows paper portfolios
  for actual saved Sunday/Monday pairs. No lookahead or presumed fill.
- **NO ASX:IBIT executed quote, bid/ask spread, private broker cash,
  actual AAA distributions, or genuine account order is verified.**
  Research profit is not proof of execution profitability.

## Notifications: clear separation from the live Cycle Trading ntfy

To preserve the user's request for **one daily live Cycle Trading ntfy**,
research automation **does not post to ntfy**. It uses GitHub Actions
summaries/artifacts every successful run, and **only exceptional GitHub
Issues assigned to `aussiekarl-gif`** (which can generate GitHub mobile /
email alerts if account GitHub notifications are enabled).

Examples of exact issue title prefixes:

- **`[BTC RESEARCH / DAILY FORWARD] Capture FAILED — NOT CYCLE TRADING`**
  = missing prospective point-in-time evidence, invalid feed, failed code
  test or failed push; not a buy or sell recommendation.
- **`[BTC RESEARCH / WEEKLY BACKTEST] FAILED — NOT A TRADING SIGNAL`**
  = historical strategy comparison or its causal unit tests failed;
  previous validated policy remains in place.
- **`[BTC RESEARCH / DAILY FORWARD] Paper strategy gap needs review — NOT A BUY SIGNAL`**
  = at least 12 actually captured Sunday/Monday pairs and at least a
  5% total paper portfolio-value divergence from strict <=0.20 reference.
  **This is not a validated improvement, not statistical proof and cannot
  authorise any trading-policy promotion.** It merely opens one human
  research review issue, not a repeated daily notification.

Failure issues are de-duplicated while open; a later success can close
the matching technical failure issue. Normal successful daily and
weekly runs **do not generate extra notification messages**.
The existing Cycle Trading ntfy format, cadence and credentials
are untouched.

## GitHub audit links

- Daily workflow: `.github/workflows/v59_daily_forward_validation.yml`
- Weekly workflow: `.github/workflows/v59_causal_timing_research.yml`
- Forward tape logic: `engines/research/v59_forward_dca_tape.py`
- Forward snapshot: `engines/research/v59_live_signal_snapshot.py`
- Test suite: `tests/test_v59_forward_dca_tape.py`
- Historical methodology: `docs/research/v59_causal_buy_timing_20261112.md`,
  `docs/research/v59_false_bottom_stress_20261112.md`,
  `docs/research/v59_200wma_proximity_20261112.md`

## Safety conditions

1. PR tests are **read-only**. Write scope is available only for scheduled
   and manual **main** daily captures, and writes **only** into the
   separate research data branch.
2. Provider failures halt publication of that observation; no neutral
   risk or ad-hoc fallback substitution.
3. No data derived from a newly fetched retrospective response is
   inserted as a past as-of observation.
4. All candidate review findings remain research-only; Production,
   Cycle Trading and daily ntfy unchanged until genuinely independent
   evidence and explicit controlled promotion.
5. GitHub Actions, repo permissions, API responses and GitHub alert
   delivery can fail; verify the first live schedule and check Actions
   workflow health independently. Github Issue creation is best effort,
   not proof of mobile notification delivery.
