# BTC Composite

Primary Streamlit application for the Bitcoin Dynamic DCA project.

## Current sections

- `app.py` — main Streamlit launcher
- `engines/production/production_model.py` — frozen V5.8.2 Production calculations/data logic
- `engines/production/production_app.py` — Production Streamlit UI
- `engines/research/research_model.py` — V5.9 Research calculations/data logic
- `engines/research/research_app.py` — Research Streamlit UI
- `engines/audit/public_model_audit.py` — Public Model Audit and historical data collector
- `engines/shared/central_data.py` — read-only client for the central BTC research-data repository
- `dca_model_compare_notify.py` — temporary daily Production vs Research ntfy comparison; imports the model modules directly

## Data

- Durable audit/research history is stored separately in the private `btc-audit-data` repository.
- `btc_audit_backup.csv` in that repository is the authoritative research master.
- `engines/shared/central_data.py` provides one reusable read-only access path for that shared master, including correct handling of GitHub files larger than the Contents API inline-content limit.
- `engines/audit/cache/public_model_cache.csv` is a local cache/seed, not the authoritative durable master.
- `data/` contains local application support/history files.

### Production data safety

The full research master is **not** automatically a Production input. Production remains on its current data-fetch path until a smaller, explicitly versioned `validated/production_input.csv` is created in `btc-audit-data` and passes parity, coverage and no-look-ahead checks. The central reader added here does not change Production or Research outputs by itself.

## Safety model

Production remains the frozen control. Research and Audit changes do not automatically alter Production. Strategy changes should be tested independently before promotion.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Research development after October 2026 cleanup

- **Daily app and NAS:** `main` remains the deployed Production V5.8.2 control. Research/Paper changes do not automatically promote into Production. The NAS Docker image is published only when deployed runtime inputs change.
- **Fast checks on Research edits:** [Research BTC fast safety checks](https://github.com/aussiekarl-gif/BTC_Composite/actions/workflows/research_200wma_fast_safety.yml) — unit, paper, tax and workflow-syntax tests, not historical optimisation.
- **Historical backtests only on request:** commit a fresh `request_utc` to `research_runs/REQUEST_FULL_HISTORICAL.txt` (all 22 modules) or `research_runs/REQUEST_EXTENDED_SENSITIVITY.txt` (extended sensitivity). Routine code commits do not relaunch those simulations.
- **Scheduled forward paper testing:** approved main-branch Wednesday scheduler checks out Research only and updates the frozen paper portfolio dashboard. Do not rewrite past paper observations.
- **Evidence and archive:** [cleanup implementation](research_outputs/repository_cleanup_implementation_2026-10-15.md), [full inventory](research_outputs/repository_simplification_audit_2026-10-15.md), [research archive](research_archive/README.md).

## Secrets

The Streamlit/GitHub environments currently use secrets such as `BGEOMETRICS_TOKEN`, `NTFY_TOPIC`, and the audit GitHub persistence credentials. Never commit secret values to the repository.

For central-data reads, `engines/shared/central_data.py` uses the existing `AUDIT_GITHUB_REPO` / `AUDIT_GITHUB_TOKEN` environment values when available, with optional `BTC_CENTRAL_DATA_*` overrides. No secret values belong in source control.
