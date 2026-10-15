# Streamlit-first BTC DCA refactoring — safe phase 1
**Date:** 16 October 2026 (Brisbane). **Branch:** `research/cycle-strategy-optimization`. **Status:** golden fixture + one Research-only helper extraction.

## Deployment scope
The user uses **Streamlit only**, not the NAS. The previously unused `Dockerfile`, `compose.nas.yaml`, `.dockerignore` and NAS publish workflow were removed from active `main`, after archive copies were retained under [`research_archive/unused_nas/`](../research_archive/unused_nas/README.md). Streamlit continues to start from `app.py` with `requirements.txt`; this operation did not modify that launcher.

## Phase 1 changes
- Added [a synthetic golden input generator](../tests/streamlit_model_golden_input.py) and **checked-in, review-only** [golden values](../tests/fixtures/streamlit_model_golden_v1.json) from the original separate Production V5.8.2 and Research V5.9 model implementations.
- Golden outputs lock completed BTC risk scores, underlying valuation metrics and zones, **A$500,000** contribution budget, actual purchased synthetic BTC units, AUD fees, execution-date schedules, and model primitive calculations.
- A separate Research **Research WF Power Law** golden snapshot was added after verifying that this is the risk mode actually selected inside `engines/research/research_app.py`. It is **not interchangeable** with the older Composite V3.6 test case.
- Extracted unchanged implementations of `clamp`, `interpolate`, `risk_occurrence_table`, `align_fx_to_dates`, and `apply_equal_capital_allocator` from Research V5.9 into [`engines/shared/streamlit_pure_math.py`](../engines/shared/streamlit_pure_math.py). Research still imports the same helper names; **Production continues using its frozen local copies**.
- Research model file reduced from **2,272 to 2,139 lines** (133 fewer lines in that file). The new shared helper module adds ~158 lines, so this is a **separation-of-concerns step, not a claim that total repository lines have fallen yet**. Once Production can safely use the shared module, true deduplication is possible.
- Regression coverage compares saved inputs/outputs without a network connection, plus FX lookup parity, risk bucket boundaries, empty allocator behaviour, budget conservation, and frozen Research Power Law.

## Verified CI gates
- [Streamlit model parity workflow](https://github.com/aussiekarl-gif/BTC_Composite/actions/workflows/research_streamlit_model_parity.yml): model imports, independent historical-free synthetic snapshots, checked-in golden output comparison.
- [Research BTC fast safety checks](https://github.com/aussiekarl-gif/BTC_Composite/actions/workflows/research_200wma_fast_safety.yml): validated paper-portfolio protocol, tax, data immutability, workflow and cycle invariants.
- On refactoring, both Research fast checks and Streamlit golden tests passed at commit `05974c31`; the **final expanded active Power Law test** must also pass before further code changes. Check the newest CI run, not only intermediate green runs.

## Guardrails for the next steps
1. Do **not** auto-rebase or merge this Research branch wholesale into Streamlit Production. `app.py` differs between branches; importing experimental UI or paper strategies into the default Streamlit deployment is a separate operation.
2. Do **not** alter real portfolio data (Google Sheets or local fallback), `btc-audit-data`, or any live price/source settings during pure-helper refactors.
3. Prefer deterministic golden parity and smoke tests before touching `engines/research/research_app.py` or the large `app.py` CSS block. Its sidebar reopen control relies on Streamlit header/toolbar behaviour, so visual testing matters.
4. After more Research-only simplification, obtain specific user approval to migrate shared helpers into frozen Production V5.8.2. Measure before/after risk scores, DCA amounts, AUD cash, BTC holdings, taxes and timestamps with the golden fixtures plus realistic historical samples.
5. Consolidate only clearly safe helpers; preserve the fixed independent V5.9 and V5.8.2 strategy calculations until explicit promotion requirements are met.

**No Production model, Streamlit app launcher, real broker order, portfolio record or Wednesday research scheduler was changed by this phase.**
