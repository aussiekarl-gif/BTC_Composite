# BTC DCA Project Handover

Last updated: 2026-11-27 (Brisbane; session update 08:22 UTC)

This file is the durable starting point for future ChatGPT sessions and human contributors. Update it when material decisions, validation results, or project status change. The repository and committed evidence are authoritative; chat summaries are secondary.

## Mission

Improve BTC accumulation timing and total portfolio outcomes through reproducible research, historical backtests, walk-forward validation, and reliable daily research data. Compare BTC accumulated and final AUD portfolio value against buy-and-hold and fixed-DCA baselines.

## Non-negotiable operating rules

- **Production is frozen.** Do not change Production signals, sizing, execution, or dashboard behaviour unless the user explicitly authorizes a separately validated production change.
- Research changes must remain clearly labelled research-only until validated.
- Do not merge code that has not passed relevant automated tests and review.
- Do not invent data, fill missing observations with zero, or silently publish stale/corrupt snapshots.
- Preserve source provenance, units, date conventions, and missingness.
- Notifications are currently **disabled**. Do not re-enable ntfy or add new notification routes.
- Streamlit is the intended UI. No NAS deployment.
- User prefers autonomous, sensible low-risk project improvements without approval requests for every routine change.

## Portfolio and policy context

User-provided portfolio context (12 Nov 2026; reconfirm before any live execution calculation):
- Original capital: A$510,000.
- Holdings: 10,250 ASX shares and 5,829 AAA shares.
- Approximate AAA reserve market value: A$292,383.
- Approximate IBIT market value: A$209,305.
- AAA variable distributions were estimated at about 5% annualised at that time.
- Ordinary weekly buy allocation cap: 5% of original capital (A$25,500).
- No leverage.
- Stop buying when risk exceeds 0.50 under the aggressive research policy.

These are historical user-supplied figures, not live account data. Never imply current holdings, cash, or prices have been refreshed unless verified.

## Research preferences and constraints

- Prioritise timing research over unnecessary cash-accounting complexity.
- Test buying near/below the 200-week moving average, including recovery confirmation and the historically observed period below the 200WMA.
- Include relevant pre-2018 cycles; ignore 2013 and pre-2017 test periods as previously requested.
- Include BTC realised price where relevant.
- Target average cycle timing error is approximately 25%, not 40%.
- Compare BTC accumulated and final AUD value, not only signal accuracy.
- Keep the actual BTC USD price visible as a single clear value where relevant.
- Where IBIT execution is modelled, show IBIT quantity and price per IBIT as well as BTC reference price.
- User-supplied cycle bottom reference: USD 57,717 on 30 Jun 2026. Treat as a user input, not independently verified market data.

## Daily research data reliability

The user needs daily data early enough to make decisions. External cron-job.org dispatch is configured for 9:00am Brisbane time. GitHub scheduled backup windows are UTC 23:17, 00:17, and 01:17 (approximately 9:17am, 10:17am, and 11:17am Brisbane time).

External dispatch endpoint is the GitHub Actions workflow-dispatch API for:
`aussiekarl-gif/BTC_Composite/actions/workflows/cowen_onchain_daily_refresh.yml`

A GitHub API response of HTTP 204 / "No content" means the dispatch request was accepted; it does not prove the workflow completed successfully. Verify the resulting Actions run and each source outcome.

A fine-grained token renewal reminder is scheduled for 11 Feb 2027 at 9:00am Brisbane time. Token expiry was 25 Feb 2027. Never put token values in this repository or ask the user to share them.

## Data-source handling decisions

- Aethereal is the preferred transaction-fee source when valid and fresh.
- Coin Metrics Community FeeTotNtv is a fallback/cross-check for missing Aethereal fee observations. Keep source series and provenance distinct; do not splice them invisibly.
- The six-day comparison (18–23 Nov 2026) showed about 2.04% mean absolute percentage difference between Aethereal and Coin Metrics fees. This is a short sample, not evidence of long-run equivalence.
- Open Bitcoin Metrics CDD was last observed current through 22 Nov 2026 as of 27 Nov.
- Aethereal local snapshot was last observed through 23 Nov 2026 as of 27 Nov.
- Do not integrate restricted CDD APIs without confirming licence and permitted use. In particular, avoid providers whose terms prohibit trading/investment-decision use or whose API terms do not permit the intended GitHub Actions + Streamlit deployment.

## Current open work (27 Nov 2026)

### PR #407 — Aethereal Google DoH fallback

URL: https://github.com/aussiekarl-gif/BTC_Composite/pull/407

- State: open, not merged.
- Branch: `research/aethereal-google-doh-fallback`
- Head at last review: `ab96ce29ad23c769c25e161ddfebe487e0e0bd09`
- Adds a separately testable Python DoH helper used by the scheduled refresh after normal DNS retries.
- Tries Cloudflare then Google DoH, validates IPv4 A records, and uses curl `--resolve` for the original Aethereal hostname, preserving HTTPS hostname/TLS verification.
- Adds unit coverage for resolver failover, empty answers, IPv4 validation, pinned HTTPS hostname, and parsing the downloaded CSV.
- Regression run 45964857234: `test` job passed, including the new DoH fallback tests, matched 200WMA research, and V6.0 path/cost sensitivity report. V5.9 validation run 45964857301 passed all steps.
- Live smoke run 45964857234: Explore21 and Coin Metrics retrieved through 26 Nov. Direct Aethereal fetch failed with a normal DNS resolution error; the explicit DoH fallback then received DNS status 3 (NXDOMAIN) from both Cloudflare and Google for `dataset.aethereal.top`. No HTTPS download was attempted.
- Public web-indexed Aethereal dataset pages still describe the Bitcoin Network Daily dataset through 24 Nov 2026, but this does not prove the download hostname currently resolves.
- Current branch head `ab96ce29ad23c769c25e161ddfebe487e0e0bd09` adds `continue-on-error: true` to the direct Aethereal smoke fetch so independent source checks still run. Fresh CI for this head is pending.
- **Do not merge PR #407 until current-head CI passes and the source hostname is restored or a verified alternative endpoint is available.** Keep Production untouched.

## Session continuation protocol

At the end of each substantial work session, update this file or add a dated checkpoint recording:
1. PRs/branches and exact head SHAs.
2. Files changed and purpose.
3. Tests/workflow run IDs and actual outcomes.
4. What was not tested or remains uncertain.
5. The next concrete task.
6. Any user decision that changes project constraints.

In a new ChatGPT conversation, begin with: "Continue BTC DCA project. Read docs/BTC_DCA_PROJECT_HANDOVER.md and inspect the current GitHub state before making changes."