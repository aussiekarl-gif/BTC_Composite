# Forward BTC / ASX:IBIT research recorder — safety gate and readiness report

18 October 2026. **No live Cycle Trading or Production BUY/SELL percentage, market signal, broker order, Streamlit portfolio or ntfy changes.** A narrow correctness fix to the existing daily *research-only* forward source recorder.

## Verified defect

The existing workflow from #154 applied GitHub Actions `always()` to the final commit/push of every research CSV. A preceding CI test failure could therefore still allow the workflow to publish local changes under `data/research_forward_validation/`, contrary to fail-closed research-data handling.

**Fix:** give the single test step stable `id: capture_validation`. Later research ASX market fetch, readiness audit and archive require `!cancelled() && steps.capture_validation.outcome == 'success'`. Final Git save additionally demands `steps.readiness.outcome == 'success'`. These are **actual GitHub Actions state conditions**, not an ordinary shell command after a failed step. They retain the intended original decoupling: if the BTC SOURCE fetch alone fails after tests pass, the **independent ASX indicative close** step can still attempt a same-Sydney-day observation, and the valid research CSV can be saved only after the WHOLE tape passes hash/date/instrument checks.

**Important:** the research script's `main` for IBIT catches provider/schema errors and skips the row; this is not a reason to downgrade immutable chain validation. No fabricated provider value, fallback to USD NASDAQ ticker IBIT or non-market daily candle is published. The ordinary BTC recorder still fails closed when latest completed UTC source isn't fresh.

## New read-only health report

`python -m engines.research.forward_market_readiness` emits JSON to the **GitHub Actions artifact** at `artifacts/forward_readiness.json` only. It is not a new ntfy notification or new daily job; the same 12:25 UTC / 22:25 Brisbane scheduled workflow produces it after price-capture attempts.

The audit reads the actual committed append-only BTC and ASX CSVs, verifies both SHA256 previous-row chains and chronological date order, refuses fake broker executions and non-Sydney-day or before-17:00 ASX entries, checks that any matured 7/30/90day BTC grading references truly recorded signal row hashes and is not duplicated. It reports:
- All BTC observations versus **strictly prospective next-UTC-day-captured** BTC observations, including the original stale row dated Oct15 captured on Oct18, and missing intervening dates (never backfilled).
- ASX AUD reference closes from IBIT.AX after their actual Sydney session, which are **indicative historical observation marks, not an executable bid/ask**. A Sunday has zero recorded session closes.
- BTC historical provider source crosscheck maximum; the current existing tape carries **6.29%**. This may reflect different historical providers/series, not necessarily a 6.29% difference in the most recent BTC spot price, but it deserves explicit separate inspection before claiming tight cross-source parity.
- Pipeline smoke-test sample targets: **30 genuinely prospective daily BTC close observations** and **20 distinct new ASX session close records**. These are data quality gates, **NOT proofs of superior timing, guaranteed execution or the user's approximate 20% historical peak/trough error target**.

Regardless of counts, `eligible_for_automatic_live_rule_promotion` remains **False**, and user approval and independent trade outcomes still govern any change. Hash tamper, missing dated prior data or fake ASX quotes fail the research workflow rather than being silently published.

## GitHub acceptance

[GitHub Actions PR run 39125658207](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39125658207) **SUCCESS: 52 tests passed** (11 forward BTC ledger, 7 Kraken source bridge, 10 forward ASX quotes, 9 new readiness validations, 10 current live Cycle percent regressions, 5 price feed checks). No change to actual live trading/portfolio/notifications. A pull-request test cannot establish live Yahoo availability; first market session observation and the on-main archive/report will be checked separately. No backfilled 2017/2021 ETF quotes can exist.
