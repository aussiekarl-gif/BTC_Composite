# BTC Dynamic DCA V3.2 FULL

This is the full-size upgrade path, based on the original Streamlit simulator lineage rather than the compact rewrite.

## Major changes
- Preserves Historical Backtest and Forward Deployment Plan modes
- Preserves Power Law and SMA legacy risk modes
- Adds Composite V3.2 as the default risk model
- MVRV Z-Score, Fear & Greed and optional BGeometrics Regime Score
- Local Power Law, Mayer Multiple and RSI components
- Smooth risk multiplier and risk-derived BTC target allocation
- Valuation multiplier with configurable floor/cap
- Time target + deployment pressure + hard per-period buy cap
- Portfolio-target profit taking with cost basis and minimum sale spacing
- AUD accounting, fees, realised/unrealised P&L
- Equal DCA and Lump Sum benchmarks
- Sharpe, Sortino, CAGR and max drawdown
- Data-quality coverage panel
- 70/30 train/validation walk-forward optimiser with normalized multi-objective ranking
- CSV export

## Run
`pip install -r requirements.txt`

`streamlit run btc_dynamic_dca_v3_2_full.py`

## Secrets
Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` locally, or add this in Streamlit Community Cloud Secrets:

`BGEOMETRICS_TOKEN = "YOUR_NEW_TOKEN"`

Never commit the real token. Rotate any token previously exposed in chat.
