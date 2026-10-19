# ASX:IBIT forward-capture public-provider health check — 19 October 2026

## Why this check exists

The equal-capital prospective ASX:IBIT Cycle-vs-DCA-vs-BuyHold benchmark starts on 20 October 2026, Sydney time. As of 19 October **16:58 Brisbane / 17:58 Sydney**, the hash-chained forward AUD close tape `data/research_forward_validation/asx_ibit_closes_forward.csv` had not yet been created. This is expected, because the EXISTING research tape cron runs once at **22:25 Brisbane / 23:25 Sydney**, several hours later. Do not invent an early close or backfill previous days.

The existing prospective ASX capture module was previously tested only on constructed Yahoo Finance schema fixtures. A successful parser test does not prove the current public Yahoo `IBIT.AX` API returns a valid current-day AUD candle.

## Improvement

Read-only public `engines/research/ibit_asx_public_probe.py`:
- Reuses the EXACT existing `fetch_yahoo_asx_daily_candle` and `read_latest_close` functions; checks actual provider response on PR CI with no file writes.
- Validates Australian `IBIT.AX` / `IBIT.AU` symbol, `AUD` currency, `Australia/Sydney` provider zone, actual same-Sydney-date candle and completed session after 17:00 Sydney.
- Reports three distinct statuses: `NO_ELIGIBLE_COMPLETED_LOCAL_SESSION`, `PROVIDER_NOT_READY_OR_REJECTED`, or `READY_REAL_COMPLETED_SYDNEY_AUD_CANDLE`. A previous Friday Yahoo candle on a Monday **does not** become a fresh Monday entry, even if the delayed live quote looks usable.
- Before 21:00 Sydney, source delay may be temporary and produces a warning, not fabricated data. Optional `--fail-after-sydney-21` can strictly reject a missing completed candle after 21:00 local, but is not enabled on this PR.
- Separately, the EXISTING scheduled ASX capture prints a visible GitHub Actions **warning** if the provider is rejected/late, while preserving successful independent BTC Cycle research capture. Warning does not send an ntfy or change any BUY/SELL result.

The companion offline suite covers timezone, weekend, pre-close time, stale prior-session daily bars, non-AUD US IBIT, upstream error, valid response, and no-write/no-ntfy safety.

**No additional scheduled GitHub job. No ASX data backfill, provider subscription, broker API, portfolio or daily ntfy. Production 5.8.2, Research 5.9, live Cycle and forward benchmark policy remain unchanged.** The first real hash-linked ASX row can only be appended when the existing scheduled recorder finds a genuine newly completed local trading-day candle.

## Do not misinterpret readiness

Passing the real Yahoo probe validates technical availability/shape **at its exact time only**; does not establish an independently confirmed broker-executable price or a positive BTC timing edge. The forward ASX benchmark will remain NO WINNER until sufficient genuine future sessions and matched decisions exist.
