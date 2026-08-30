# btc-risk-dca — Composite DCA Monitor

A weekly check that combines four independent Bitcoin valuation signals
into one transparent composite score, gates a DCA "start" signal on both
price and that score holding for several consecutive weeks, and pushes
the result via [ntfy](https://ntfy.sh). This is your own composite proxy —
explicitly not Benjamin Cowen's proprietary Risk Metric.

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
into one `composite_value` (and `composite_risk = 1 - composite_value`).

## The DCA signal

`START_DCA` fires only when **both**:
1. BTC price is at or below your `entry_price_usd`, **and**
2. `composite_risk` is at or below your `risk_start_threshold`

...and both hold for `confirmation_days` consecutive runs in a row (to
avoid firing on a single noisy day). Until then you'll see intermediate
statuses: `PENDING_CONFIRMATION`, `PRICE_OK_RISK_TOO_HIGH`,
`RISK_OK_PRICE_TOO_HIGH`, or `WAIT`.

## One-time setup

### 1. Get a free bitcoin-data.com API token
Register at [portal.bitcoin-data.com/pricing](https://portal.bitcoin-data.com/pricing)
for the free tier (10 requests/hour, 15/day — this script uses 3 requests/week).
Grab your token from the dashboard.

### 2. Pick or reuse an ntfy topic
Same as before — pick a hard-to-guess topic name, or reuse one from
another project (remember: GitHub secrets are per-repo).

### 3. Add repo secrets
**Settings → Secrets and variables → Actions → New repository secret**
- `BITCOIN_DATA_API_TOKEN` — your token from step 1
- `NTFY_TOPIC` — your topic name
- `NTFY_SERVER` — only if self-hosting ntfy; otherwise leave unset
- `NTFY_TOKEN` — only if your ntfy topic requires auth; otherwise leave unset

### 4. Create your config.json
Copy `config.example.json` to `config.json` and edit the strategy values
to your own targets:

```json
{
  "entry_price_usd": 100000,
  "risk_start_threshold": 0.30,
  "confirmation_days": 3,
  "max_metric_age_hours": 48,
  "cheap_residual": -0.10,
  "neutral_residual": 0.00,
  "expensive_residual": 0.20,
  "ntfy_server": "https://ntfy.sh"
}
```

**These are placeholder values — edit them to match your actual strategy:**
- `entry_price_usd` — the price ceiling you're willing to buy under. The
  placeholder (100000) is almost certainly not your real number.
- `risk_start_threshold` — how low the composite risk score must be
  (0.30 in earlier discussion, but this composite score isn't on the
  same scale as Cowen's metric — worth watching a few weeks of real
  output before trusting a specific cutoff).
- `confirmation_days` — how many consecutive weekly runs must qualify
  before it actually fires `START_DCA` (this script runs weekly, so
  `confirmation_days: 3` means 3 consecutive weeks).
- `cheap_residual` / `neutral_residual` / `expensive_residual` — the
  power-law-component boundaries, in log10 units of deviation from
  trend. `-0.10` ≈ 21% below trend, `0.20` ≈ 58% above trend. Adjust
  once you've seen a few weeks of real `powerlaw_residual` values in
  `data/risk_history.csv`.

`config.json` is **not** a secret — it holds your strategy parameters,
not credentials, and is safe to commit to the repo (unlike the four
secrets above).

### 5. Push this repo to GitHub
```bash
cd btc-risk-dca
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
and `data/state.json` get committed back.

The scheduled run fires **daily at 08:15 UTC** (18:15 Brisbane time,
fixed year-round since Queensland has no daylight saving). Daily is
required, not optional - `confirmation_days` counts consecutive *runs*,
so a weekly schedule would silently turn "3 confirmation days" into
3 confirmation weeks.

## Local testing
```bash
pip install -r requirements.txt
export BITCOIN_DATA_API_TOKEN=your-token
export NTFY_TOPIC=your-topic-name
python btc_composite_dca.py
```

## Data files
- `data/risk_history.csv` — one row per run: every input, every
  component score, the composite, and the signal. Your full audit trail.
- `data/state.json` — tracks `consecutive_qualified_days` between runs
  so confirmation logic persists across weeks.

## Honesty check
- The power-law fit, AHR999, and MVRV/Puell thresholds are all public,
  well-documented methods — not reverse-engineered guesses at a
  proprietary formula.
- The **weights** (25/25/20/20/10) and the **boundary values** for each
  indicator's cheap/neutral/expensive score are still a specific choice,
  not a universal standard — worth revisiting after watching real output
  for a few weeks.
- `max_metric_age_hours` guards against acting on stale on-chain data if
  bitcoin-data.com's feed lags — the run fails loudly (no notification,
  no false signal) rather than silently using an old number.
