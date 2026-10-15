# BTC Composite Repository Simplification Audit
**Inspection date:** 15 October 2026 UTC  
**Branches examined:** `main` (Production/deployment) and `research/cycle-strategy-optimization` (experimental and paper testing).  
**Status:** **Inventory and recommendations only**. No files deleted, no Production code changed, no existing data/portfolio records touched.

## Executive decision

**Simplify aggressively around execution and maintenance, but conservatively around financial calculations and data provenance.** The most valuable improvement is to separate the *two actively maintained models*, the *forward paper experiment*, and the *reproducibility archive*. Removing branches/files alone does not make the BTC strategy more profitable.

### Verified inventory

| Measure | Current |
|:--|--:|
| Tracked files on `main` | 52 |
| Tracked files on Research | 110 |
| Git branch names | 99 |
| GitHub workflow YAMLs on `main` | 6 |
| Workflow YAMLs on Research | 10 |
| Python source files under `engines/research` on Research | 44 |
| Research `test_*.py` modules | 25 |
| Python jobs in full `research_causal_history.yml` workflow | **22** |
| Artifact uploads in that workflow | **21** |
| Shared top-level model function names, Production vs Research | 26 |
| Exact matching top-level function bodies | **20**, roughly **745 repeated lines** |
| Exact matching top-level helper bodies across Streamlit Production/Research UI | **4**, roughly **84 repeated lines** |
| Same-commit feature branches for bottom-signal-timeline | **11** |

Research code has ~110 tracked files / ~2.3 MB. The `data/` folder on `main` is ~1.5 MB. **Repository disk size is not a pressing problem**. Primary costs are cognitive load, duplicated code, expensive CI re-runs and unsafe version-promotion potential.

## 1. KEEP — essential working components

| Files | Reason |
|:--|:--|
| `app.py` | Entrypoint for all four current Streamlit pages; simplify carefully. Research branch has a **different menu and maintenance toggle** from `main`; merging branches blindly may change UI. |
| `engines/production/production_model.py` and `production_app.py` | **Frozen V5.8.2**. Do not delete, automatically refactor, or change live sizing during cleanup. |
| `engines/research/research_model.py` and `research_app.py` | Research V5.9 risk model and user interface, distinct from new 200WMA tier paper experiment. |
| `engines/shared/portfolio_store.py` | Actual portfolio persistence via Google Sheets / SQLite fallback. Back up real data separately. Never treat a data-file deletion as code cleanup. |
| `engines/shared/central_data.py`, `engines/audit/public_model_audit.py` | Validated source/provenance research, with authoritative durable audit master **outside this repo**, in private `btc-audit-data`. Keep collector and read-only access until a replacement is verified. |
| `engines/audit/bottom_signal_timeline_app.py`, `engines/research/wma_tier_app.py` | Both exposed as current main-menu pages; remove or merge only after deciding whether those views are wanted. The current 200WMA page uses a **fixed October 2026 CSV** and explicitly is *not live*; it must not be presented as a current signal. |
| `engines/research/forward_paper_200wma.py`, `paper_dashboard.py`, `vbtc_official_history.py`, `smsf_cgt_ledger.py` | Forward paper execution, performance dashboard, official VBTC issuer source and tax-lot accounting. These support the prospective, append-only experiment and must remain. |
| `engines/research/test_200wma_12week_execution.py` | Despite its `test_` name, it is the **core staged-execution engine** also imported by paper trading. Do not archive/delete until safely renamed and all imports updated. |
| `engines/research/test_200wma_cash_deployment.py`, `test_200wma_exact_10x10.py`, `btc_200wma_history.py` | Used by simulations/benchmarks for DCA and tier constants. Centralise the logic before changing callers. |
| `research_forward/200wma_v1/config_frozen.json`, `DASHBOARD.md` and future `weekly_observations.jsonl`/`scoreboard.json` | **Frozen forward protocol and timestamped evidence.** Never retrospectively alter records or strategy settings to improve results. |
| `main/.github/workflows/research_vbtc_wednesday_scheduler.yml` | Approved Wednesday 9:17 AM Brisbane schedule. **Writes must remain restricted to Research.** |
| `Dockerfile`, `compose.nas.yaml`, `requirements.txt`, `.streamlit/config.toml` | Current NAS/Streamlit deployment. Keep all runtime dependencies unless measured import/runtime tests prove they're unused. |

## 2. Candidate REMOVE/ARCHIVE — conditional, not yet safe to delete

| Candidate | Current finding | Safe precondition |
|:--|:--|:--|
| `data/risk_history.csv` | Seven short rows contain duplicate 30 August 2026 dates and inconsistent trailing columns. Benchmark workflow **explicitly rejects this file** as a valid historical BTC/AUD dataset. | Verify no external download/manual process depends on it; archive and remove from app checkout, **not** central audit master. |
| `data/manual_metrics.json` | Small static manual metric snapshot dated 30 August 2026. Not referenced directly by current main model/UI source files inspected. | Confirm no operational import/glob or external script uses it; archive snapshot. |
| `data/miner_revenue_total_daily__2026-10-09T22-10-04.png` | ~240 KB static chart with no literal Python reference in the active app/model files inspected. | Confirm it is not embedded by a GitHub README, historical report or external user link; archive instead of permanent deletion. |
| Old provider CSV exports (miner, MVRV, NUPL, PlanB realised price, SOPR, supply in profit) | Large, dated reference snapshots, mostly not directly loaded by Production/Research Streamlit model source. Some are provenance inputs to historical studies. | **Do not delete** until data lineage is verified against private authoritative master and historical backtests. Move stable copies to archival research storage and update paths if possible. |
| `engines/research/probe_vbtc_official_history.py` | Early proof-of-source script now superseded for normal use by validated `vbtc_official_history.py`. | Update `research_vbtc_source_probe.yml` to use authoritative importer/checks only; archive probe and preserve historical run. |
| One-off historical experiment modules, including `test_200wma_entry.py`, `_weighted.py`, `_core_satellite.py`, `_roundtrip.py`, `_percentage_bands.py`, `_tier_ladders.py`, `_start_sensitivity.py`, `_lower_tier_sensitivity.py`, `_sell_cross_direction.py`, `_failure_attribution.py`, `_cash_exposure_ceiling.py` | Historical parameter explorations; useful for reproducibility but do not all need to execute on each research commit. | Move to `research_archive/experiments` or preserve a clearly tagged Git commit and retained artifacts, then replace 22-step workflow with representative regression tests. **Do not archive imported engine modules by filename alone.** |
| `engines/audit/coinglass_plan_findings.md`, `cryptoquant_plan_findings.md`, `provider_access_summary.md` | Older provider investigation notes; not runtime calculation modules. | Keep in `docs/archive/providers/` if provenance useful; otherwise delete only with review. |
| `dca_model_compare_notify.py` and `main/.github/workflows/dca_model_compare_notify.yml` | Labelled **temporary** in source, but still configured for daily ntfy Production-vs-Research alerts. | Keep until owner confirms no longer using those daily notifications. |
| Obsolete Git branches | 99 branch names; at least **11** bottom-signal branch aliases have the exact same commit. Existing `cleanup/*` and `research/repository-cleanup-audit` branches also exist. | Review open PRs, remote references, retained evidence and unique commits. Delete only merged/discarded branches on explicit approval. **Branch deletion does not improve Streamlit runtime.** |

## 3. Biggest complexity and CI wins

### A. Separate three workflows rather than rerun historical parameter searches
1. **Fast change validation:** syntax/import checks, frozen model/paper-config fingerprint, FIFO tax lot invariants, data date safety, paper replay/no-lookahead and representative golden regression outputs. Target a few minutes.
2. **Full historical research (manual or occasional):** all exploratory parameter sweeps + dated artifacts, only when a research decision needs them. Currently `research_causal_history.yml` executes **22 Python modules**, uploads **21 artifacts** and can approach its 20-minute timeout.
3. **Wednesday forward paper and alerts:** preserve independent weekly schedule; never mix one-off historical optimisation with unalterable prospective results.

The current `research_200wma_quick.yml` itself runs five research scripts, including simulations, rather than just true unit smoke checks. Move expensive sensitivity experiments out of a gate called *quick*.

### B. Avoid unnecessary NAS-image republishing
`main/.github/workflows/publish_nas_image.yml` currently runs on **every push to `main`**, including scheduler-only or documentation commits. Introduce a carefully reviewed `paths:` filter for `app.py`, executed `engines/` modules, requirements, Dockerfile and required runtime data, plus workflow self-changes. Do not disable builds on real model changes. A scheduler tweak should not push a new Production container image.

### C. Refactor duplicate model and UI helpers only after frozen parity
The `production_model.py` and `research_model.py` contain **20 exactly matching top-level function bodies** (~745 duplicate lines by static text partition). Examples: historical BTC and FX retrieval, risk occurrence summaries, interpolation and equal-capital allocator. Extract **stable, side-effect-free** data/math utilities into `engines/shared/` one function at a time, with:
- Golden end-to-end Production outputs before/after the refactor (risk score, allocation, cash balance, trade history, dates and price sources).
- Research parity/golden tests and no-lookahead checks.
- Strict version pinning or a frozen adapter so later Research work cannot silently alter Production semantics.
- Explicit approval before merging to `main`.

The Streamlit apps also share four identical top-level helpers (~84 lines). Retain separate Production/Research UI pages, share only proven-safe display/portfolio plumbing.

### D. Simplify `app.py` presentation without changing model behaviour
- Root launcher CSS has repeated contradictory header/toolbar styling (hide then restore), a maintenance burden introduced while protecting the sidebar reopen control. Replace with minimal carefully tested CSS, verify desktop/mobile sidebar visibility.
- Its comment says **three** choices while it displays **four**. Remove unused audit guard imports on `main` *after* verifying the actual launcher branch.
- The Research branch `app.py` has a different menu including audit/probe/parity diagnostics. Decide on one navigation contract; do not merge it blindly over the Production launcher.
- Prefer a single labelled 200WMA Research page and link it to the forward-paper dashboard, rather than keeping two unrelated displays of **static** historical WMA signals and **live** paper results.

### E. Untangle Research execution code from ad-hoc experiment filenames
Keep one validated code path for:
- **completed-week BTC/USD 200WMA signals**,
- **AUD/ETF quote ingestion + provenance**,
- **cash-first DCA benchmark**,
- **staged tier execution + portfolio/cash ledger**,
- **SMSF CGT accounting**,
- **paper state/events + dashboard**,
- **independent validations**.

Proposed eventual mapping (names subject to import migration):
```
app.py
engines/
  production/production_app.py, production_model.py   # frozen
  research/research_app.py, research_model.py         # active
  research/strategy/200wma_signal.py
  research/strategy/cash_dca.py
  research/strategy/tier_execution.py
  research/strategy/aud_etf_data.py
  research/strategy/smsf_tax.py
  research/paper/runner.py, dashboard.py
  shared/portfolio_store.py, central_data.py
research_forward/200wma_v1/                          # append-only
tests/                                               # fast golden + unit
research_archive/experiments/                        # one-offs, optional/manual
.github/workflows/                                   # small CI, full manual, paper scheduler, deploy
```
Do **not** make this rename all at once: first draw the exact import graph; move one dependency at a time; old paths can act as compatibility shims until workflow/tests are migrated.

## 4. Prioritised safe execution plan

| Phase | Task | Risk | Preconditions |
|:--|:--|:--|:--|
| 0 | Tag/pin Production `main` and Research source SHAs; snapshot Google Sheets portfolio + audit data master externally | Low | Confirm backup and golden metrics first |
| 1 | Move one-off experiments from push-triggered full workflow to **manual/archived** suite; introduce fast checks | Low-medium | Full comparison outputs archived; full suite can still run on demand |
| 2 | Add NAS publish path filter; separate scheduler updates from app-image deployment | Low-medium | Test changes to `app.py`, Dockerfile, critical modules still publish |
| 3 | Trim root CSS and clarify 4-page navigation **in Research first** | Medium | Verify Streamlit sidebar, mobile, state persistence |
| 4 | Refactor stable Research-only execution/data helpers into shared modules | Medium | Frozen paper config and precise historical results must be unchanged |
| 5 | Gradually deduplicate Production model utility functions | High | Signed-off golden comparison; explicit Production promotion |
| 6 | Archive dated research snapshots, remove unused experiment/probe scripts and clean stale Git branches | Medium | Audit provenance, no external consumers; retain reproducibility and PR links |

## 5. What we'll need going forward

**Definitely retain:** frozen Production V5.8.2 + separate Research model; a single authoritative validated data-history reader; durable Google Sheets portfolio storage; actual BTC/AUD and ETF NAV/traded-price evidence; complete-week no-lookahead timing; append-only paper journal; tax/fee ledger; baseline benchmarks; reproducible backtests; automated failure alerts; short deterministic CI regression tests; and versioned Research-to-Production approval gates.

**Less important to retain in the active development path:** every abandoned formula variation, dated provider screenshot, repeated multi-hour backtest on every small script change, old utility probes superseded by a validated data source, duplicate UI/CSS, duplicate Git branches, and historical experiments that are no longer called by current research decisions.

## 6. Non-negotiable change controls
- **No change to Production calculations, portfolio records, Google Sheets, live order interfaces or `btc-audit-data` in this audit.**
- Do not merge all of Research into `main`; the root launcher and research pathways differ.
- No deletion of `weekly_observations.jsonl`, `scoreboard.json`, frozen config, audit master, or portfolio state.
- Before removing a module or moving a CSV, search static imports, path literals, runtime/dynamic imports, workflows, Docker/NAS startup and external documentation.
- Changes must pass a byte-for-byte/golden behavioural diff for affected computations and a clean CI run; archive prior evidence first.
- No Promotion from Research to Production without user approval and documented validation.

**Recommended first implementation:** create a **small, independent fast-CI suite** and mark the 22-module full historical workflow **manual-only** once the current set of artifacts and exact SHA are archived. Then adjust NAS publish triggers. This has the highest maintenance payoff at relatively low strategy risk.
