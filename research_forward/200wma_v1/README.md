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

## Live Research dashboard and failure alerts
- **[Open the Research paper portfolio dashboard](./DASHBOARD.md).** It shows the frozen A$500,000 DCA control, 12-week buy/16-week sell candidate, and the version with a 26-week idle-cash rule. All figures are *paper-only* and show latest portfolio value net of modelled tax, excess return versus DCA, free cash, ETF units, hypothetical fills and twelve-week historical trends.
- Each successful Wednesday run appends the same summary to its GitHub Actions **Run summary**. Until 19 October's first eligible completed weekly close is available, the dashboard correctly says *awaiting first paper observation* and reports **no actual or simulated results**.
- **Failure alert:** If Wednesday's scheduled workflow fails, its GitHub Actions failure step creates or comments on a single GitHub Issue titled `BTC 200WMA Research paper scheduler needs attention`, assigned to the repository owner `aussiekarl-gif`. A subsequent successful run closes it. GitHub notifications depend on account preferences; check **GitHub → Notifications** and enable email/mobile notifications for assigned issues if desired.
- Alert notifications cannot be tested without deliberately making the job fail. An unsuccessful GitHub Actions run remains the primary definitive source of failure, even if Issues API permissions or GitHub notification settings prevent a user-visible alert. GitHub does not guarantee execution precisely on schedule.

## Running it
The [research-only workflow](https://github.com/aussiekarl-gif/BTC_Composite/actions/workflows/research_forward_paper_200wma.yml) executes self-tests, checks for a timely completed week, then appends `weekly_observations.jsonl` and `scoreboard.json` **only on the Research branch**, if an eligible week exists.

The workflow currently runs on Research code/config pushes and supports manual dispatch. A successful pre-inception run prints `awaiting_first_complete_week` and writes **no simulated trades**.

**Weekly unattended GitHub scheduling is now enabled with explicit approval (15 October 2026 UTC).** A minimal launcher at [`main/.github/workflows/research_vbtc_wednesday_scheduler.yml`](https://github.com/aussiekarl-gif/BTC_Composite/blob/main/.github/workflows/research_vbtc_wednesday_scheduler.yml) runs every Wednesday at **09:17 Brisbane time** (`23:17 UTC Tuesday`). It checks out `research/cycle-strategy-optimization`, runs the frozen model/integrity and dashboard tests and pushes **only** new `weekly_observations.jsonl`, `scoreboard.json`, and `DASHBOARD.md` files to that Research branch. It shares the same concurrency lock as manual paper runs. No Production scripts, deployed Streamlit model, exchange or broker integrations are changed. GitHub scheduled runs are subject to platform delays; check the Actions history if a weekly snapshot is missing. The scheduler fails closed on missing prices and will not retrospectively invent past paper trades.

For a manual week: choose GitHub Actions → `Research forward 200WMA VBTC paper journal` → `Run workflow` (if the GitHub interface exposes this branch workflow) and select the **research/cycle-strategy-optimization** ref. A run shortly after the VanEck release following a completed Monday BTC bar is appropriate. Missing an observation by more than seven days blocks silent backfills and requires an explicit integrity decision; it must not be fixed by pretending old prices were known prospectively.

## Files
- `config_frozen.json`: fixed strategy parameters. Do not edit after first observation.
- `weekly_observations.jsonl`: created only once real prospective inputs exist. Each record captures the official issuer workbook SHA256, observed timestamp, issuer traded quote vs NAV, volume, completed BTC close and contemporaneously calculated 200WMA.
- `scoreboard.json`: created after the first eligible weekly quote; historical weekly returns, simulated VBTC ETF units, free cash, modelled tax and actual paper fills per model.
- `engines/research/forward_paper_200wma.py`: fully deterministic replay and integrity checks.
- `engines/research/vbtc_official_history.py`: official issuer spreadsheet importer.
- `engines/research/test_vbtc_official_market_vs_nav.py`: historical sanity check since actual VBTC inception June 2024 (limited history).

**Risk**: Bitcoin ETFs involve significant price volatility, spreads, liquidity risk, taxes and tracking differences. Results are not investment advice or live executed results.
