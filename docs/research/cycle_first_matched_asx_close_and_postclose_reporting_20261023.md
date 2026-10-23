# First real matched Cycle mid-session / ASX:IBIT next-close result — 23 October 2026

## What was genuinely captured (actual receipt evidence)

The hash-chained `data/research_forward_validation/cycle_mid_session_market_watch.csv` has genuine eligible Sydney midday observations on:

- **Thursday 22 Oct**, actual source receipt `2026-10-22T01:28:28.260541Z` (=12:28:28 Sydney); prior fully completed 21 Oct UTC BTC close **US$84,022.50**, prior 200WMA **US$66,954.605750**, live shared model SHA `0143723687ff676300734a4bcc9887cdc095c74b70b958852d9448412b7f08a7`; **HOLD**, BUY **0%**, SELL **0%**.
- **Friday 23 Oct**, actual source receipt `2026-10-23T01:27:40.448933Z` (=12:27:40 Sydney); prior fully completed 22 Oct UTC BTC close **US$81,315.90**, prior 200WMA **US$67,225.626550**, identical frozen model SHA; **HOLD**, BUY **0%**, SELL **0%**.

The independent immutable `asx_ibit_closes_forward.csv` includes **22 Oct ASX:IBIT indicative AUD close 22.389999** captured at 17:06 Sydney, and **23 Oct close 22.120001** captured at 17:01 Sydney. The direct close-to-close change is **−1.205887%** between these two real *prospectively saved* source records.

Both 22 and 23 Oct midi signals are **HOLD**. This decline is **NOT** a profitable Cycle SELL signal, not proof of BUY timing, and not broker-executable intraday alpha. Actual buying or selling at a previously unknown same-day CLOSE is not assured. No taxes or executed transaction data are part of this observation. The original matched three-policy A$100,000 paper study remains independent and frozen.

Earlier missing 20/21 Oct Sydney midi signals and the 21 Oct ASX close are **not backfilled**.

## Small reporting reliability improvement

GitHub's nightly `research_forward_cycle_tape.yml` is not on-time enough to rely on for a fresh mid-session-to-ASX following-close scorecard. The existing, successful, four-slot paired BTC job **already captures and commits the post-17:00 Sydney AUD ASX daily price** through PR #195's optional source sidecar.

Therefore, on an eligible *already-scheduled* paired BTC run, place one **read-only** timing reporter step **after the existing ASX sidecar's source publication** and *before* its existing 30-day diagnostic artifact upload. Its implementation:

1. Proceeds ONLY when the ASX sidecar wrote a genuinely new, receipt-dated, same-Sydney-session single-Yahoo-provider AUD close (`status=captured`, `wrote_close=True`, `not_broker_executable=True` and 0 ntfy/portfolio/broker actions). Earlier/later, duplicate, invalid vendor or unverified cases do not qualify.
2. Fetches the current **remote `origin/main`** via Git; does **not** assume the local checkout or attempted source CSV was successfully committed. Copies only `cycle_mid_session_market_watch.csv` and `asx_ibit_closes_forward.csv` into a temporary directory with `git show origin/main:...`. Checks the latest remotely published ASX source date matches the current captured session.
3. Runs the **unchanged** `engines.research.cycle_mid_session_asx_timing_audit` with this immutable prospective input and writes an artifact at `artifacts/asx_ibit_postclose_paired/published_mid_session_following_asx_timing.json`. Its existing audit enforces SHA chains, prior captured time/date, exactly next real recorded weekday, immutable model SHA, source currency/provider and same versus next price causality. No missing price interpolation or post-hoc market signal.
4. Failures generate only GitHub Actions research diagnostics; do not prevent first-writer ASX capture, modify data tapes or daily ntfy, issue trades, or add a scheduled job. The existing optional ASX artifact upload retains this JSON with the raw provider time-gate and Git logs.

## Tests and limits

New `tests/test_cycle_postclose_published_timing_report.py` regression uses the real prospectively saved 22/23 October two immutable source tapes to verify the first genuine following-session close match and the exact percentage, that HOLD has **no directional trade return**, and that the implementation fetches actual remotely *published* sources after the original ASX publisher without any `git add`, `git commit`, `git push`, ntfy sender or broker trade.

All original Kraken/Coinbase paired-source, Cycle early-mid-session fallback, ASX AUD receipt/ohlc/share code tests continue to run; no changes to Production 5.8.2, Research 5.9, current frozen 2.5% BUY under prior 200WMA, 7-day cooldown, SELL schedule, portfolio, one-daily ntfy, broker, taxes, historical Alpha claims or data tapes.

No automatic trading-strategy improvement can be claimed. This merely makes the observational scorecard available in the post-close workflow rather than waiting for GitHub's frequently delayed independent nightly run.
