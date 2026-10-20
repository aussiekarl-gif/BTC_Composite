# First genuine forward ASX:IBIT matched paper session — Tuesday 20 October 2026

Read-only acceptance: `engines/research/forward_ibit_first_session_acceptance.py`; tests: `tests/test_forward_ibit_first_session_acceptance.py`. This was added *after* the original matched-forward three-strategy experiment was frozen on 19 October, without altering any existing trading/cohort/allocation rule. No real broker orders, ntfy, portfolio or original source tape writes.

## What GitHub captured

- First paper enrolment Sydney: **20 October 2026**; all three cash-funded research accounts begin with exactly A$100,000 uninvested and no ETF inventory.
- The actual Yahoo single-provider ASX:IBIT daily AUD candle was observed after ASX hours on **20 October at 2026-10-20T06:57:04 UTC (17:57 Sydney)**: **A$22.299999 indicative closing price**, OHLC range approximately A$22.11–22.47. Source SHA256 row **93af08dc688054d86e28574e9a275276a933e4b1ee8ffcece9664f10f850386a**.
- **Correct pre-ASX-open Cycle market WATCH** came from prospectively recorded BTC observation date **18 October 2026**, captured on **19 October 2026 at 03:14 UTC (14:14 Sydney)**. It reported verified **HOLD** 0% BUY/SELL, code-frozen model SHA `0143723687ff676300734a4bcc9887cdc095c74b70b958852d9448412b7f08a7`, verified recent Kraken/Blockchain discrepancy 0.05%. Thus it was KNOWN before 10:00 Sydney Oct20.
- The more recent BTC completed-close **19 October** was only recorded on **20 October at 06:57 UTC (17:57 Sydney)**, after the ASX had closed. The original pre-open benchmark must NOT let that later observation change the first-session Cycle decision; in particular, it must not invent a same-day early BUY.
- **The completely independent MID-SESSION research signal file remained missing on main as of 20 October 17:51 Brisbane**. Do not backfill that source. It is not required for the frozen *pre-open* three-policy benchmark.

## Equal cash, same observed AUD close, assumptions identical

One-sided **25 basis points BUY spread**, A$3 broker fee for each hypothetical executed paper order, floor to whole IBIT units, no credit interest, SMSF tax, actual executable intraday price or guaranteed ASX closing auction fill.

| Policy | Paper Oct20 entry | Whole ETF units | Original AUD cash left | After-assumption pre-tax value at Oct20 indicative close | Approx ETF share of marked account |
|---|---|---:|---:|---:|---:|
| Frozen Cycle Trading market WATCH | HOLD | 0 | A$100,000.00 | A$100,000.00 | 0% |
| Fixed 20-week DCA (first A$5,000 weekly cash tranche) | BUY | 223 | A$95,011.67 | A$99,984.57 | 4.97% |
| Buy and hold (immediate full-account paper purchase) | BUY | 4,472 | A$22.09 | A$99,747.69 | 99.98% |

**These initial small paper losses reflect assumed brokerage/spread and unequal asset exposure, not historical price performance, market timing skill, or alpha.** Do not claim Cycle Trading outperformed buy-and-hold based on being 100% cash or based on this single session. ETF quotes are *indicative daily closes*, not broker bid/ask fills.

## Test/operational use

Run no-network existing verified tapes:
`python -m engines.research.forward_ibit_first_session_acceptance`.

The acceptance module calls the frozen three-policy `grade`, strictly verifies both earlier SHA256-linked source tapes, reconciles whole-unit order/cash to original first-session frozen policy account marks, checks signal capture strictly before the 10:00 Sydney opening, checks AUD symbol and confirmed-no-broker-fill status, and produces the separate `artifacts/forward_ibit_first_actual_session.json` read-only report with signed source provenance and explicit no-winner flags.

The research PR CI runs this acceptance alongside the old 20 matched-forward source tests, ASX public-candle and trade-allocation regressions. Additional negative tests block after-open source leakage, late BUY, source tampering, wrong instrument/currency and market data as-of future. No new scheduled GitHub job; the original 20-week DCA reference remains a **control**, not a forced November or 2027 investment deadline.

**Next essential evidence:** eligible future ASX AUD sessions, independent actual Sydney mid-session source captures and eventually broker-executable prices/costs. Original live 2.5% of remaining cash when truly eligible remains unchanged.
