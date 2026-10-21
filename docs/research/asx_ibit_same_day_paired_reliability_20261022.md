# 22 October 2026 — Proven GitHub cron delay and corrected ASX:IBIT prospective collection fallback

## Confirmed incident, not an inferred market failure

At 07:25 Brisbane Thursday 22 October, GitHub `main` had **zero** original mid-session Cycle market WATCH observations, **5** nightly BTC Cycle source rows (last `2026-10-20` verified US$82,936.10 and HOLD, saved 21 October at 17:24 UTC), and **2** ASX:IBIT AUD closes (19 and 20 October only).

The actual [21 October mid-session GitHub Actions run #39554722099](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39554722099) started at **2026-10-21T06:19:40Z = 17:19:40 Sydney**, well past its 15:00 Sydney upper limit. The run passed market-data unit tests then correctly **failed closed** with `ValueError: Not in eligible Sydney weekday 11:00-15:00 mid-session window`. Its separate read-only public probe succeeded at ~06:20Z (21 October completed prior BTC: US$82,936.10, prior 200WMA US$67,072.90, HOLD 0%/0%). The error was **GitHub scheduling delay**, NOT observed BTC-source unavailability. The original 20 October mid-session missing row also remains missing; do not retroactively reconstruct either.

The nightly forward BTC and ASX workflow [#39643491393](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39643491393) started at **2026-10-21T17:24:20Z = Thursday 22 October 04:24 Sydney**, rather than the planned 23:25 Sydney prior evening. The original ASX collector strictly requires an ACTUAL after-17:00 Sydney same-day weekday; it correctly returned `skipped_no_completed_sydney_weekday`. Thus the **21 October ASX close was never saved**, while the previous UTC day Bitcoin close still could be captured. Neither missing bar should be backfilled after the fact.

The already existing paired Kraken/Coinbase source job ran around **2026-10-21T06:00Z = 17:00 Sydney Wednesday** under a delayed scheduled trigger (see GitHub Actions [#39552849176](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39552849176)). This is one real opportunity to capture a completed same-day ASX:IBIT bar WITHOUT inventing or adding a scheduled workflow.

## Narrow future-only research fix

Only extend the existing, independent `.github/workflows/research_btc_paired_microstructure.yml` schedule; retain exact four UTC cron slots `17 1,7,13,19 * * *`. After the original paired book/trade capture and optional Cycle mid-session backup, a new *best-effort* price sidecar:

- Performs a **pure Python standard-library time gate** against actual `Australia/Sydney` weekday, at/after **17:00 local**, for dates starting 20 October 2026. Before that, on weekends or before 17:00, it does not fetch Yahoo or write any CSV.
- Only when eligible, optionally installs the existing research dependencies, fetches **actual Yahoo IBIT.AX daily candles**, then evaluates the Sydney date and UTC timestamp AGAIN **AFTER provider receipt**. If a request crosses into the next Sydney day before 17:00, reject and do not backdate the receipt.
- Reuses exact original `engines.research.ibit_asx_forward_close_tape.capture_once`, whose `read_latest_close` insists on the current Sydney-date IBIT.AX Yahoo bar, Sydney exchange timezone, AUD instrument/currency, sensible OHLC, nonnegative volume and true receipt provenance. Missing late provider bar => no source, not a fabricated price.
- Reuses original immutable `asx_ibit_closes_forward.csv` SHA256 format; never produces real broker/executable fills, never invents missing ASX dates or rewrites the 19/20 Oct rows. Does not relax the original nightly strict same-Sydney-day gate. No 21 October historical backfill.
- **First published source wins:** compare the original local HEAD ASX source with freshly fetched remote `origin/main` before trying to commit. Any change since checkout means another collector already published data; exit without overwrite. Standard GitHub rebase/push conflict also fails closed.
- Keeps optional fallback after original coordinated book/trade source publication; a failed Yahoo request or model dependency cannot prevent existing BTC source saves. Actions artifact retains actual timing, receipt date, skip/publish status and git error logs. No account/portfolio/BTC market signal/ntfy writes.

## Tests and evidence boundaries

Run new `tests/test_asx_ibit_postclose_paired_backup.py` (11 checks) alongside the unchanged original `tests/test_ibit_asx_forward_close_tape.py` source gate. Test after-open timing, exact 17:00 and midnight limits, delayed GitHub after-midnight no fetch, real after-receipt timestamp, stale data, wrong currency, duplicate freeze, pure time guard with no numpy until a valid window, and no-new-cron/first-writer-wins workflow wiring. The paired BTC CI continues to check the independent Kraken/Coinbase captures, and the nightly workflow still verifies prospective ASX source chain.

**No alpha improvement is claimed.** The new opportunity is not a guarantee because GitHub schedules still may all start outside 17:00–midnight Sydney or Yahoo may lag. The existing A$100,000 frozen Cycle-vs-buy/hold-vs-20-week-DCA paper benchmark continues to evaluate ONLY legitimately captured ASX observations. Its market signal must remain timestamped before opening; later recorded closes are not retroactive actual fills.

No user notifications, broker transactions, SMSF/tax changes, Google Sheets writes, Production 5.8.2, Research 5.9, current 2.5% Cycle BUY/SELL modifications, or arbitrary November/2027 forced cash deployment.
