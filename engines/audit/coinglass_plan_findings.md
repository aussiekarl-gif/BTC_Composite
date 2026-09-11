# CoinGlass plan findings

Verified from the deployed Streamlit environment on 2026-09-12 (Australia/Brisbane): the configured CoinGlass key authenticates, but the following specialist endpoints return HTTP 200 with application-level `code=401`, `msg=Upgrade plan`, and no data. They must not be treated as accessible on the current plan.

- STH SOPR
- LTH SOPR
- STH Realized Price
- LTH Realized Price
- RHODL Ratio
- STH Supply
- LTH Supply
- Reserve Risk

Acquisition implication: do not retry these endpoints during normal research collection on the current plan. Prefer CryptoQuant where the user's entitlement permits, otherwise cached/BGeometrics fallback. This finding is research-only and does not change Production.