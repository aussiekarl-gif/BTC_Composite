# BTC microstructure forward scorecard — 19 October 2026

**Research-only, preregistered before eligible future source observations; not a BUY/SELL model.**

## What we actually know

The first Kraken book and Coinbase recent-trades records are genuine timestamped observations but were collected 7m27s apart, over the allowed 5-minute skew. The Coinbase API samples only the LAST 100 trades (about 19 seconds on the initial saved snapshot), not the whole six-hour slot. It cannot identify whale wallets, measure a complete six-hour executed-volume imbalance, or establish a near-execution price vs Kraken.

The immutable source tapes and their hash chains must be validated before any score. A scorecard with zero valid pairs is normal, not a failure.

## Frozen exploratory policy v1

Effective ONLY for data observations available at or after **19 October 2026, 02:00 UTC**, before the next eligible 07:xx UTC collection. Earlier Oct 18 observations are **excluded from directional testing** to reduce selection after examining them.

- Match exact six-hour UTC slot, two source capture receipts within **five minutes**.
- Kraken complete 0.25%-midpoint depth band, Coinbase trade sample explicitly partial, last trade within two minutes, sample duration >0 through five minutes, at least 20 reported trades.
- Hypothetical PAPER_BULL if resting buy-side liquidity share and buyer-initiated Coinbase sample USD share are BOTH >=60%.
- PAPER_BEAR if BOTH <=40%. Otherwise retain as PAPER_NEUTRAL (no selective deletion).
- This is a **correlated, two-feature joint hypothesis**, NOT two independent AI votes.
- No synthetic past order books, sample extrapolation, wallet attribution, new market feed, external AI call, AI training, or hindsight-selected entry time.

Frozen policy fingerprint is emitted with each report. These 60/40 thresholds are arbitrary research candidates, not tuned or proven optimal. Do not change them just because a trial outcome is poor; make a distinctly versioned future policy if ever needed.

## What counts as a valid outcome

- For every prospective matched source pair, analysis eligibility begins only when BOTH sources have been captured, max(receipt times).
- BTC returns use Kraken midpoint at source-book receipt for the base and the **first real Kraken snapshot at or after** the target horizon, no more than 90 minutes late.
- Fixed **6h, 24h, 168h** target windows. Do not interpolate between unavailable quotes, use a prior quote for a missed target, or count an unfinished or stale future observation.
- Persisted source tapes remain the authoritative raw observations. Scorecard is computed **read-only** and saved as a GitHub Actions downloadable artifact with its actual computation time and policy hash. It does not modify previous source rows or create independent forecasts after prices become known.
- Per horizon, show valid count, number of distinct UTC calendar days, and gross BTC/USD midpoint movements. A simple hypothetical sign-adjusted move is NOT investable P&L.

Even if the exploratory sample gate reaches 60 active hypotheses spanning >=30 days, **approval to trade stays FALSE** until verified actual ASX:IBIT bid/ask prices, FX, spreads/fees, SMSF taxes, market hours and true causal execution rules are tested. The existing Cycle Trading model remains unchanged.

## Cost and operations

Run 17 no-network standard-library tests in the existing Coinbase validation workflow. After the normal Coinbase sample run, the job also calculates a read-only scorecard and adds a JSON artifact. It creates **no additional GitHub Actions schedule or ntfy sender**. A scorecard failure produces a workflow warning and must not block the source collector or its immutable append.

A reader may run:
python -m engines.research.btc_microstructure_forward_scorecard

Files:
- engines/research/btc_microstructure_forward_scorecard.py
- tests/test_btc_microstructure_forward_scorecard.py
- artifacts/btc_microstructure_forward_scorecard.json (GitHub Actions artifact only, not auto-committed)

## Result interpretation

Early counts and short-horizon results will be dominated by sampling variance, timing delays and overlapping BTC market regimes. No edge, model improvement or profit claim is made. The next legitimate measurement is performance **versus the exact executable Cycle Trading rules and buy-and-hold**, with a sealed unaltered forward test plus fees, FX, tax and drawdown, not cherry-picked rules applied repeatedly to the same two historic cycles.
