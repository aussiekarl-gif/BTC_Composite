# Frozen mid-session Cycle Trading vs next ASX closing-price timing study

Initiated 20 October 2026, BEFORE the first new mid-session BTC market WATCH observation. Research-only; no new investment advice or automatic orders.

## Why this is separate from the original ASX benchmark

The official BTC nightly research tape runs 12:25 UTC / 22:25 Brisbane, AFTER the Australian stock market closes. It cannot establish same-day execution timing from the single ntfy message, which is usually attempted at 10:00–10:35 Brisbane during ASX hours. The original 20 October A$100,000 Cycle vs fixed DCA vs buy-and-hold paper benchmark only accepts Cycle signals that were known BEFORE 10:00 Sydney. That benchmark is frozen and unmodified.

New independent mid-session market evidence is prospective, collected only at the actual receipt time within 11:00–15:00 Sydney on eligible weekdays, from the same verified completed UTC Bitcoin close, Kraken/Blockchain crosscheck, AUD FX, confirmed halving and unchanged shared Cycle Trading signal model. This is NOT proof a push notification was delivered at the exact capture instant.

## Pure observational follow-up

Module: `engines/research/cycle_mid_session_asx_timing_audit.py`. Test: `tests/test_cycle_mid_session_asx_timing_audit.py`.

The audit verifies the SHA256-linked mid-session BTC model tape and the independently recorded hash-linked Yahoo ASX:IBIT indicative AUD close tape. A model signal is eligible only if:
- actually recorded inside the mid-session window, AFTER the completed previous UTC BTC close, and its source verified as Kraken/Blockchain crosscheck <=1%;
- matches the original frozen Cycle model code SHA from 17–18 October 2026; any later model changes form a new cohort;
- the ASX same-date indicative closing candle was captured later that day after 17:00 Sydney, with verified AUD currency, IBIT.AX identity, source OHLC range and non-executable provider status;
- the *following* ASX indicative closing candle is actually captured on the immediately expected NEXT calendar weekday. Friday→Monday allowed; missing intervening weekdays, public holidays, weekend rows, or gaps >4 days are NOT silently interpolated or misrepresented as adjacent sessions.

For each eligible BUY WATCH and SELL WATCH, separately record the AUD **same-day indicative close** and **next recorded session indicative close** (no actual trades). The exploratory directional *cost of waiting* is positive for a BUY if the following close is higher, or for a SELL if following close is lower. HOLD events are retained as neutral and cannot be sign-adjusted. The report includes every missing/pending status and source hash reference.

This measures a **hypothetical price difference between two future daily closes**, not whether a trade could actually have been executed at either close, and not whether the proposed ntfy order was known or filled at a specific intraday time. A broker bid/ask or order timestamp would be necessary to test true same-day vs next-day executable advantage. The next-close comparator is exploratory; zero evidence can establish improved Cycle strategy alpha from it.

## Strict release and automation

- No new scheduled GitHub Actions job for the scorer: the existing nightly `research_forward_cycle_tape.yml` runs it read-only and keeps its JSON as an OPTIONAL artefact `artifacts/cycle_mid_session_asx_timing_audit.json`, after its usual immutable source integrity checks.
- Initially the new mid-session tape may be empty and/or today's ASX close not recorded. The report must show **0 paired close outcomes**, no winner and no investment signal, instead of fabricating history.
- The timing hypothesis needs at least 30 completed **non-HOLD** observations for an exploratory review; even then live alpha, broker execution and tax-aware outperformance remain unproven.
- Never backfill earlier Oct19 source observations or revise the separately frozen A$100,000 benchmark, historic provider records, one-daily ntfy, Streamlit trading rules, SMSF holdings, brokers, Production 5.8.2 or Research 5.9.
