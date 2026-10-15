# BTC Composite — Low-risk cleanup implementation report

**Completed 15 October 2026 UTC.** This is a code and workflow maintenance change, not an endorsement of any BTC trading model.

## Completed changes

| Area | Before | After |
|:--|:--|:--|
| Routine Research commits | A full historical workflow with 22 Python modules and 21 artifacts could launch, plus a mislabeled 'quick' historical sensitivity suite | Both full historical and extended sensitivity run **only when their explicit request-marker file is committed**, or via supported manual dispatch. Ordinary source edits no longer launch the costly research suites. |
| Fast safety testing | Extended historical simulations were acting as change checks | New [`research_200wma_fast_safety.yml`](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/.github/workflows/research_200wma_fast_safety.yml) validates workflow YAML, completed-week/paper strategy, append-only provenance, FIFO SMSF tax, dashboard and independent cycle unit tests, without network retrieval. |
| NAS container release | Every push to `main`, including Wednesday paper scheduler documentation, republished a Docker image | [Publisher](https://github.com/aussiekarl-gif/BTC_Composite/blob/main/.github/workflows/publish_nas_image.yml) now triggers only on actual deployment inputs (`app.py`, `engines/**`, `data/**`, runtime dependencies, Docker configuration and publisher changes), or explicit manual dispatch. Research paper-scheduler edits alone do **not** rebuild the image. |
| VanEck VBTC source investigation | One-off worksheet-inspection probe still ran before the verified official importer on issuer checks | Archived the [unchanged probe source](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_archive/experiments/probe_vbtc_official_history.py); removed only its original `engines/research/` location and workflow invocation. The validated issuer importer and price-vs-NAV test remain active. |
| Historical test safety | No automated check against malformed YAML/accidental expensive push trigger | New YAML structure and exact opt-in-request-path assertions run in every fast safety check. |

## Actual verification

- [Fast Research safety workflow, run 38819110981](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38819110981): **passed**, including workflow YAML safety, FIFO tax, paper integrity, dashboard and cycle-backtest tests.
- [VanEck issuer verification, run 38818779989](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38818779989): **passed** after removing the old one-off probe call.
- [NAS publisher, run 38818601852](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38818601852): **passed** after adding deployment-input path filtering. This publisher-workflow edit itself intentionally caused **one** image build; future scheduler-only commits are excluded.
- One intermediate historical sensitivity workflow update produced malformed YAML and [failed registration, run 38818492128](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38818492128). It was corrected; the new automated YAML structure regression **passed** in run 38819110981. Old failed runs remain as audit evidence and are not falsely marked as successful.

## How to run historical research now

The full historical and extended sensitivity workflows exist **on the Research branch**, not the default branch, so GitHub's standard manual Run Workflow UI may not list them. For an explicit run:
1. Switch GitHub's branch selector to `research/cycle-strategy-optimization`.
2. Edit and commit **only** [`research_runs/REQUEST_FULL_HISTORICAL.txt`](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_runs/REQUEST_FULL_HISTORICAL.txt) for the 22-module suite, or [`research_runs/REQUEST_EXTENDED_SENSITIVITY.txt`](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_runs/REQUEST_EXTENDED_SENSITIVITY.txt) for the smaller historical sensitivity suite.
3. Check GitHub Actions and download the corresponding artifacts. A changed `request_utc` line triggers that one workflow. Neither trigger is touched by the Wednesday paper scheduler.

## Safety boundaries and what is *not* cleaned yet

**No Production algorithms, risk scores, sizing controls, Streamlit runtime menus, Google Sheets portfolio data, private audit master, or frozen paper-trading configuration were modified.** The authoritative Production model, UI, portfolio code and app launcher retain their prior Git blob SHAs:

| Immutable live source | Git blob SHA after cleanup |
|:--|:--|
| `engines/production/production_model.py` | `e036eb10b7ef80db51ad06d0a8041c6f380b2060` |
| `engines/production/production_app.py` | `17d57521671f48c8ca7d25b985b34c1595608284` |
| `engines/shared/portfolio_store.py` | `0f4d14eff1934c83bc4eaf12a3f49222f70a7d3d` |
| `main/app.py` | `de9ebf3cee5d7d1b9a5ab59f0b5e06541a5eb18e` |

Other exploratory scripts remain callable by the manual full research suite, and **no historical research data or Git branches were deleted**. In particular, the awkwardly named `engines/research/test_200wma_12week_execution.py` is the **actual staged execution engine imported by the paper portfolio**. It is not safe to delete during simple cleanup.

## Next logical step (separate, higher-risk phase)

1. Add exact risk-score and AUD cash allocation golden outputs for Production + Research before extracting any of the ~745 identical model helper lines.
2. Move duplicate *pure helpers* into `engines/shared` one by one **in Research first**.
3. Validate portfolio and dashboard parity; do not promote shared code to Production without explicit approval.
4. Audit stale `data/` snapshots against the authoritative private `btc-audit-data` repo before deleting or moving dated CSV/PNG files.
5. Review merged/open PRs and non-unique Git branches before retiring historical branch aliases. Branch pruning is organisational housekeeping and has no runtime-performance effect.
