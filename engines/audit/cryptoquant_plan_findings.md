# CryptoQuant entitlement findings

Verified from the deployed Streamlit environment on 2026-09-12 (Australia/Brisbane): the authenticated discovery catalogue is accessible, but targeted BTC on-chain/network indicator requests return HTTP 403 on the current entitlement.

Observed blocked paths include:

- `/v1/btc/flow-indicator/exchange-inflow-cdd`
- `/v1/btc/network-indicator/nvt`
- `/v1/btc/network-indicator/puell-multiple`
- `/v1/btc/network-indicator/nvt-golden-cross`
- `/v1/btc/network-indicator/cdd`
- `/v1/btc/network-indicator/nupl`
- `/v1/btc/network-indicator/dormancy`
- `/v1/btc/network-indicator/utxo-realized-age-distribution`
- `/v1/btc/network-indicator/utxo-realized-supply-distribution`
- `/v1/btc/market-indicator/mvrv`

Acquisition implication: do not keep probing CryptoQuant on-chain endpoints under the current entitlement. Use free/self-calculated sources first, existing local/central cache second, and BGeometrics only for remaining specialist gaps. CryptoQuant remains useful for endpoint discovery and market-data endpoints allowed by the plan. This finding is research-only and does not change Production.