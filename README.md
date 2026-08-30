# btc-composite-dca

A weekly check that combines five independent Bitcoin valuation signals
into one composite score, and converts it directly into a suggested
weekly DCA allocation percentage - no price ceiling, no on/off gate.
Pushed via [ntfy](https://ntfy.sh).

## What feeds the composite (weights)

| Signal | Weight | Source |
|---|---|---|
| Power-law residual (price vs long-term trend) | 25% | Computed from blockchain.com price history |
| MVRV Z-Score | 25% | bitcoin-data.com API |
| AHR999 | 20% | Computed in-script (published formula) from price history |
| Price / Realized Price | 20% | Realized Price from bitcoin-data.com API |
| Puell Multiple | 10% | bitcoin-data.com API |

Each signal is converted to a 0–1 "value score" (1 = cheap, 0 = expensive)
using published thresholds for that indicator, then combined by weight
into one `composite_value` (`composite_risk = 1 - composite_value`).

## How the suggested allocation works

No hard price ceiling and no binary START_DCA/WAIT gate - every run
produces a number:

```
invest_pct_full  = composite_value * 100   (the "if you went all-in today" %)
weekly_slice_pct = invest_pct_full / 12    (spread over 12 weeks)
```

`weekly_slice_pct` is recalculated fresh every run from the live
composite - if conditions improve, next week's slice rises
automatically; there's no dollar cutoff that blocks buying above some
fixed price. Even in unfavourable conditions you'll see a small
non-zero number rather than a flat "wait."

## One-time setup

### 1. Get a free bitcoin-data.com API token
Register at [portal.bitcoin-data.com/pricing](https://portal.bitcoin-data.com/pricing)
for the free tier (10 requests/hour, 15/day - this script uses 3 requests/week).
Grab your token from the dashboard.

### 2. Pick or reuse an ntfy topic
Pick a hard-to-guess topic name, or reuse one from another project
(remember: GitHub secrets are per-repo).

### 3. Add repo secrets
**Settings → Secrets and variables → Actions → New repository secret**
- `BITCOIN_DATA_API_TOKEN` — your token from step 1
- `NTFY_TOPIC` — your topic name
- `NTFY_SERVER` — only if self-hosting ntfy; otherwise leave unset
- `NTFY_TOKEN` — only if your ntfy topic requires auth; otherwise leave unset

### 4. Create your config.json
Copy `config.example.json` to `config.json`:

```json
{
  "max_metric_age_hours": 60,
  "cheap_residual": -0.10,
  "neutral_residual": 0.00,
  "expensive_residual": 0.20,
  "ntfy_server": "https://ntfy.sh"
}
```

- `max_metric_age_hours` — how old the on-chain metrics from
  bitcoin-data.com are allowed to be before the run fails loudly
  instead of using stale data. Their metrics update roughly daily, so
  60 hours gives comfortable buffer without masking a genuinely broken
  feed.
- `cheap_residual` / `neutral_residual` / `expensive_residual` — the
  power-law-component boundaries, in log10 units of deviation from
  trend. `-0.10` ≈ 21% below trend, `0.20` ≈ 58% above trend. Worth
  revisiting once you've seen a few weeks of real `powerlaw_residual`
  values in `data/risk_history.csv`.

`config.json` is **not** a secret - it's your strategy parameters, not
credentials - and is safe to commit to the repo.

### 5. Push this repo to GitHub
```bash
cd btc-composite-dca
git init
git add .
git commit -m "Initial commit: composite DCA monitor"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

### 6. Test it
**Actions** tab → "BTC Composite DCA Monitor" → **Run workflow**. Check
the run log for the full breakdown, and confirm `data/risk_history.csv`
gets committed back.

The scheduled run fires every **Monday at 11:10am Brisbane time**
(01:10 UTC) - fixed year-round since Queensland has no daylight saving.

## Local testing
```bash
pip install -r requirements.txt
export BITCOIN_DATA_API_TOKEN=your-token
export NTFY_TOPIC=your-topic-name
python btc_composite_dca.py
```

## Data files
- `data/risk_history.csv` — one row per run: every input, every
  component score, the composite, `invest_pct_full`, and
  `weekly_slice_pct`. Your full audit trail.

## Honesty check
- The power-law fit, AHR999, and MVRV/Puell thresholds are all public,
  well-documented methods - not reverse-engineered guesses at a
  proprietary formula.
- The **weights** (25/25/20/20/10) and the **boundary values** for each
  indicator's cheap/neutral/expensive score are still a specific choice,
  not a universal standard - worth revisiting after watching real output
  for a few weeks.
- `max_metric_age_hours` guards against acting on stale on-chain data if
  bitcoin-data.com's feed lags - the run fails loudly (no notification,
  no bad number) rather than silently using an old value.
- There's no price ceiling by design - the composite score already
  accounts for "how expensive is this," so a separate hard dollar cutoff
  would double-count that judgment in a cruder, binary way.
