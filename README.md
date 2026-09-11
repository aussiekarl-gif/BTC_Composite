# BTC Composite

Primary Streamlit application for the Bitcoin Dynamic DCA project.

## Current sections

- `app.py` — main Streamlit launcher
- `engines/production/production_model.py` — frozen V5.8.2 Production calculations/data logic
- `engines/production/production_app.py` — Production Streamlit UI
- `engines/research/research_model.py` — V5.9 Research calculations/data logic
- `engines/research/research_app.py` — Research Streamlit UI
- `engines/audit/public_model_audit.py` — Public Model Audit and historical data collector
- `dca_model_compare_notify.py` — temporary daily Production vs Research ntfy comparison; imports the model modules directly

## Data

- Durable audit/research history is stored separately in the private `btc-audit-data` repository.
- `engines/audit/cache/public_model_cache.csv` is a local cache/seed, not the authoritative durable master.
- `data/` contains local application support/history files.

## Safety model

Production remains the frozen control. Research and Audit changes do not automatically alter Production. Strategy changes should be tested independently before promotion.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Secrets

The Streamlit/GitHub environments currently use secrets such as `BGEOMETRICS_TOKEN`, `NTFY_TOPIC`, and the audit GitHub persistence credentials. Never commit secret values to the repository.
