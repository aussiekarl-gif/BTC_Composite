# VBTC / BTC 200WMA Forward-Only Paper Experiment V1

**Research-only. Never place orders, access wallets/brokers, or modify Production V5.8.2.** The authoritative master remains unchanged.

## Frozen experiment — committed 15 October 2026 UTC
- Three model portfolios each begin with **A$500,000** hypothetical capital, initially 20% VBTC-equivalent ETF units and 80% cash.
- **DCA-only control:** 12-week risk-weighted initial purchases, then holds ETF units.
- **Trading candidate:** identical DCA entry plus sell triggers at 200WMA/USD +100% … +280%, rebuys at +25% … −30%, 12-week bell purchases, 16-week bell sells; same-tier job overlap blocked.
- **Cash-recycling candidate:** same trading algorithm plus partial investment of 25% of available cash after 26 idle weeks when unreserved cash is over half of marked portfolio value.
- **Costs:** A$20 per executed fill, 0.1% dealing fee, 0.5% extra slippage, and modelled FIFO 15% SMSF accumulation CGT with conservatively early July settlement. **Issuer VBTC traded prices and NAV already reflect fund management fees; no extra 0.45% MER is deducted.**
- **Frozen config:** [config_frozen.json](./config_frozen.json), identified by SHA256 stored in every observation and scoreboard.
- Earliest prospective completed BTC USD weekly bar is **Monday 19 October 2026 UTC**; initial simulated VBTC entry is valued from that week's issuer-traded reference price. No simulated paper actions are retroactively created for earlier periods.

## Data and causal separation
1. [Blockchain.com BTC/USD market-price](https://api.blockchain.info/charts/market-price) provides daily USD prices and a completed W-MON close. Previous 200 completed weekly closes determine the 200WMA; the latest complete week determines the deviation.
2. [VanEck VBTC NAV and premium/discount history](https://www.vaneck.com.au/etf/alternatives/vbtc/downloads/fundhistoprices/) provides real daily NAV, *last traded ASX reference price*, volume, and premium or discount. The issuer workbook is checked for headings, row dates, positive values and calculated premium reconciliation.
3. Week N's confirmed deviation produces a signal executed against the **next** complete week's issuer-reported trade reference. This is a paper fill, **not a guaranteed real bid/ask or intraday fill**.
4. If an ETF quote or BTC weekly close is missing, stale or fails validation, the run **fails closed** and places no paper fill. Earlier observations and scores cannot be repriced or edited by an incoming data-source revision.
5. Independent trades are evaluated from append-only prospective observations; previous weeks' results are recomputed and must match the previously committed scoreboard bit-for-bit.

## Running it
The [research-only workflow](https://github.com/aussiekarl-gif/BTC_Composite/actions/workflows/research_forward_paper_200wma.yml) executes self-tests, checks for a timely completed week, then appends `weekly_observations.jsonl` and `scoreboard.json` **only on the Research branch**, if an eligible week exists.

The workflow currently runs on Research code/config pushes and supports manual dispatch. A successful pre-inception run prints `awaiting_first_complete_week` and writes **no simulated trades**.

**Weekly unattended GitHub scheduling is NOT enabled.** GitHub's `schedule` trigger executes workflows on the repository's default branch, while this experiment intentionally lives only in `research/cycle-strategy-optimization`. Installing a default-branch scheduler would modify the protected master and requires separate explicit approval; we have not done that.

For a manual week: choose GitHub Actions → `Research forward 200WMA VBTC paper journal` → `Run workflow` (if the GitHub interface exposes this branch workflow) and select the **research/cycle-strategy-optimization** ref. A run shortly after the VanEck release following a completed Monday BTC bar is appropriate. Missing an observation by more than seven days blocks silent backfills and requires an explicit integrity decision; it must not be fixed by pretending old prices were known prospectively.

## Files
- `config_frozen.json`: fixed strategy parameters. Do not edit after first observation.
- `weekly_observations.jsonl`: created only once real prospective inputs exist. Each record captures the official issuer workbook SHA256, observed timestamp, issuer traded quote vs NAV, volume, completed BTC close and contemporaneously calculated 200WMA.
- `scoreboard.json`: created after the first eligible weekly quote; historical weekly returns, simulated VBTC ETF units, free cash, modelled tax and actual paper fills per model.
- `engines/research/forward_paper_200wma.py`: fully deterministic replay and integrity checks.
- `engines/research/vbtc_official_history.py`: official issuer spreadsheet importer.
- `engines/research/test_vbtc_official_market_vs_nav.py`: historical sanity check since actual VBTC inception June 2024 (limited history).

**Risk**: Bitcoin ETFs involve significant price volatility, spreads, liquidity risk, taxes and tracking differences. Results are not investment advice or live executed results.
