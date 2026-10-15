# BTC Composite — Research archive and active-code boundaries

**Cleanup date:** 2026-10-15 UTC  
**Production model:** V5.8.2, unchanged.  
**Research branch:** `research/cycle-strategy-optimization`.

This directory holds **superseded diagnostic code**. Its original contents and Git history are retained to reproduce provider investigations. Files archived here are *not* part of the active paper-trading engine.

## Archived now

| Original active path | Archived path | Reason |
|:--|:--|:--|
| `engines/research/probe_vbtc_official_history.py` | [`research_archive/experiments/probe_vbtc_official_history.py`](./experiments/probe_vbtc_official_history.py) | An initial workbook-header and source probe. Replaced by validated `engines/research/vbtc_official_history.py` and its issuer-market-vs-NAV audit. The corresponding GitHub workflow no longer calls the obsolete probe. |

The original workbook probe was copied **without modifying its content**, then deleted from the active `engines/research/` folder after removing its only active workflow invocation.

## Historical tests retained but no longer run on every push

The 22-module `.github/workflows/research_causal_history.yml` suite and the 5-module extended sensitivity workflow **remain reproducible and on demand**. They do not run when ordinary Research code changes.

To request an on-demand run without a default-branch workflow dispatcher:
- **Full historical:** Edit only `research_runs/REQUEST_FULL_HISTORICAL.txt` to include a new `request_utc` value, and commit to `research/cycle-strategy-optimization`.
- **Extended sensitivity:** Edit only `research_runs/REQUEST_EXTENDED_SENSITIVITY.txt` and commit to that same branch.

The workflows are restricted to those precise path triggers. This avoids the GitHub requirement that a workflow be present on the default branch to show its ordinary manual Run Workflow button. No request marker is automatically changed by the scheduler.

## Never archive/delete without a replacement and verified parity

- `engines/research/test_200wma_12week_execution.py`: **a production-like paper simulation dependency**, despite its `test_` name. Rename only with simultaneous compatibility and golden-output tests.
- `engines/research/test_200wma_cash_deployment.py`, `test_200wma_exact_10x10.py`, `btc_200wma_history.py`: shared simulator and benchmark inputs used by current experiments.
- `engines/research/forward_paper_200wma.py`, `paper_dashboard.py`, `vbtc_official_history.py`, `smsf_cgt_ledger.py`: the actual frozen forward-only simulated portfolios, issuer price history and FIFO tax-lot accounting.
- `research_forward/200wma_v1/config_frozen.json`, future `weekly_observations.jsonl`, `scoreboard.json`: immutable strategy settings and append-only prospective observations; **do not reprice or backfill**.
- `engines/shared/portfolio_store.py` and private `btc-audit-data`: user portfolio and authoritative research data; never subject to code-archive cleanup.
- `engines/production/*` and deployed Streamlit/NAS runtime, including `main`'s `app.py`.

## Workflow structure after cleanup

| Purpose | Workflow | Runs |
|:--|:--|:--|
| Low-cost deterministic safety tests | `.github/workflows/research_200wma_fast_safety.yml` | On relevant Research source/test changes, plus optional dispatch |
| Full historical experiments and source artifacts | `.github/workflows/research_causal_history.yml` | Only explicit full-history request marker change or dispatch where available |
| Extended historical USD sensitivity | `.github/workflows/research_200wma_quick.yml` | Only explicit sensitivity request marker change or dispatch where available |
| Official VBTC NAV/execution sanity check | `.github/workflows/research_vbtc_source_probe.yml` | On issuer-data/importer changes; original one-off probe archived |
| Prospective VBTC paper study | `main/.github/workflows/research_vbtc_wednesday_scheduler.yml` | Wednesday 09:17 Brisbane; Research branch only |
| NAS image publish | `main/.github/workflows/publish_nas_image.yml` | Only when live runtime inputs or build definition change; scheduler/doc edits excluded |

## Remaining cleanup deferred deliberately

Historical one-off strategy experiments are still **called by the opt-in historical suite**. Rather than deleting them, the suite is now dormant during normal development. Full physical migration needs import-path dependency inspection, a versioned evidence snapshot, and validated numerical reproduction. Old data snapshots, branch aliases, provider documentation and Production/Research duplicated functions are likewise **not yet deleted**.

This archive has no authority to modify Production, cash or portfolio balances. Refer to [the full simplification audit](../research_outputs/repository_simplification_audit_2026-10-15.md) for further phased work.
