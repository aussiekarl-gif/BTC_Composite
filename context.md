# BTC_Composite — context

Main repo (dynamic DCA BTC research; Python). History is in git — `git log`; use `git show <sha>` / `git log --grep=<topic> -i` to find past work rather than relying on memory.

## Where we are (Nov 20, 2026)

- Branch `main`, in sync with origin/main.
- Recent history (`git log --oneline -7`):
  - `9043ebd Dashboard: add downside metrics and sensitivity cohort counts to the V6.0 research screen`
  - `c487f40 Research: V6.0 matched accumulation ranking by BTC units and AUD equity` — new study engine + tests + CI workflow update (`engines/research/v60_accumulation_backtest.py`, `tests/test_v60_accumulation_backtest.py`, `.github/workflows/v60_allocation_scale.yml`).
  - `297655b Research: V6.0 sell/re-entry studies on the weekly execution tape` — new: `engines/research/v60_200wma_sell_reentry_study.py` (4 studies vs matched fixed-weekly baselines; guardrails: 5% weekly cap, min ticket, protected cash floor) + `tests/test_v60_200wma_sell_reentry_study.py` (34 tests, all pass).
  - `5e5b382 V6.0: compare 200WMA DCA threshold ladders`
  - `de7def7 Research synchronized BTC book/trade samples [skip ci]`
- `engines/research/v60_research_app.py` — "similar dashboard" upgrade (downside metrics + sensitivity cohort counts) — committed `9043ebd` (reviewed 2026-11-20: diff verified against frozen snapshots; 22 dashboard tests pass).
- Research 7 top-candidate paper tape (built 2026-11-20): `C:\Users\rittm\Research7\papers\v60_measured_200wma_discount_ladder_tape.csv` + `..._summary.json` — per-week decision log of the V6.0 measured ladder on the historical tape.",
- Research 7 project context: `C:\Users\rittm\Research7\context.md` (authoritative handoff — updated 2026-11-21). Research 7 additions this session (all research-only, no changes to this repo): strict-prior fix + re-run of the 2026 tape-gap backtests (+8 regression tests); forward paper-tape engine/runbook (`engines/paper_tape/forward_paper_tape.py`, first eligible Sunday 2026-11-22, fresh-capital seed by default, hash-chained append); sell-side accumulation study + friction/TP-basis sensitivity grids (`backtests/sell_side_*`) — buy-only control ranks #1 under all tested settings; dashboard wired into `Research7/app.py` (headless AppTest verified, 0 exceptions). Deployment protocol draft in `Research7/docs/deployment_protocol_draft.md` remains a human-review template, not an approval.

## Where we are (Nov 23, 2026) — Cowen Risk Matrix: risk-line timeline fix (v13+)

- **Risk-gauge timeline fixed on the 'Load BTC_Composite data' path** (`engines/cowen_risk_matrix_app.py`). Before: `_load_btc_composite_data()` merged `risk_history.csv` + `data/mvrv_z_score_*.csv` via `reset_index()` → risk line had a RangeIndex (0..5817); with the v12 live-Puell replacement, `_risk_history_line()` concatenated the RangeIndex frame + live Puell DatetimeIndex → crash in `main()` (`TypeError: '<=' not supported between instances of 'int' and 'Timestamp'`). Now `_load_btc_composite_data()`/`_load_research7_series()` return DataFrames indexed by the merged dates (DatetimeIndex named "date"). Verified by mimicking `main()` (2026-11-23): df `2010-11-01 → 2026-10-05` (n=5818); MVRZ risk 0.4326; live Puell n=1455 span `2022-11-23 → 2026-11-16` cur 0.9786 (v12 summary); risk line `2010-11-01 → 2026-11-16`, n=5860; chart years 2010…2026.
- Standalone repo `../cowen_risk` synced (app.py = engines/cowen_risk_matrix_app.py); committed in both repos.

## Going forward (per user)

- After every major task, update `context.md`: what changed, why, and what's next.
- Write detailed commit messages; use `git log` for history instead of memory.
