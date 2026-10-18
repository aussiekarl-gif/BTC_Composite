# Prospective Australian ASX:IBIT daily AUD close research tape

Started 18 October 2026. **Zero changes to trading signals, live Streamlit, Production V5.8.2, Research V5.9, portfolio, SMSF, ntfy notifications, actual broker shares, or buy/sell recommendations.** This is a single optional read-only observation in the **existing** 22:25 Brisbane daily public BTC Cycle signal workflow, no new schedule or ntfy. All data saved to `data/research_forward_validation/asx_ibit_closes_forward.csv` with separate hash chain; this does not affect the current immutable `cycle_market_signals.csv` or matured 7/30/90d BTC-only prediction outcomes.

## Verified product identity versus unrelated US Bitcoin ETF

- Australian product: iShares Bitcoin ETF **ASX:IBIT**, issuer BlackRock Australia; ticker `IBIT`, Yahoo Finance `IBIT.AX`, Australian-dollar price; **first listed 14 November 2025**, fee **0.39%**. Official https://www.blackrock.com/au/products/346455/ishares-bitcoin-etf
- The US iShares Bitcoin Trust has NASDAQ ticker **IBIT**, **USD**, and a separate trading history/fee. NEVER merge USD US IBIT records into ASX:IBIT AUD data merely because ticker text matches. The existing `engines/research/ibit_quote.py` fetches only `IBIT.AX` and checks symbol/currency.
- Independent secondary places that display historical ASX:IBIT prices include the issuer's official **Historical Prices** chart and InvestSMART `https://www.investsmart.com.au/shares/asx-ibit/ishares-bitcoin-etf/share-price`. **This repo does NOT currently programmatically validate same-day Yahoo closes against issuer data**. No automatic claim of two independently verified providers is permitted.

## Strict prospective capture contract

Use daily candle series from read-only Yahoo Finance public chart for `IBIT.AX`, same source as existing indicative 5-day quote; query1 and query2 hosts are NOT separate providers. Validate `meta.symbol` IBIT.AX/IBIT.AU and `meta.currency` AUD, with `exchangeTimezoneName=Australia/Sydney`. Require complete fields OHLC and volume, finite positive and consistent high/low, provider candle timestamp converts to the SAME Sydney market **calendar day** as actual capture, and capture is at least after **17:00 Sydney** that day (well after 16:00 exchange close).

One daily workflow already runs at **12:25 UTC / 22:25 Brisbane** (23:25 Sydney on daylight savings dates); the new research task skips weekends without any network call and skips holidays, stale/latest previous session and vendor delays by logging `skipped_no_same_day_verified_aud_candle`. Never fabricate weekend bars or mark a previous business day as a same-day prediction. If the Yahoo provider fails or offers an invalid symbol/currency/calendar, no close is written and the rest of verified Bitcoin Cycle daily recording continues independently; the optional step is non-blocking for the BTC watch pipeline.

When the source is available, append **one** dated row with `captured_at_utc`, source daily-candle timestamp (usually exchange bar start; **NOT an actual last broker fill timestamp**), Sydney close date, AUD close/high/low/volume, Yahoo provider, `single_provider_unverified_execution=True`, `is_confirmed_broker_fill=False`. Every row SHA256-chained, prior dates never backfilled or revised, same-session reruns no-op. Old BTC signal tape stays append-only. GitHub Actions archives the full data folder and Git commits changed **research CSV files only**.

The workflow captures prospective BUY/SELL market signals using BTC prior fully completed UTC closes separately from the IBIT Sydney calendar-date close. Those TWO observation clocks are different: a market BTC WATCH can happen on a weekend while IBIT cannot be traded; a same-day IBIT close cannot be used retroactively as an execution price known before its session close. For future valid matched research, derive **next exchange session's close as an observational benchmark only**, and retain an additional conservative bid/ask/premium-to-NAV and market order slippage scenario to avoid pretending the closing price was an achievable intraday fill.

## Status, expected evidence and research promotion limits

On **Sunday 18 Oct 2026** (Brisbane/Sydney) the new recorder must skip and write nothing. Its FIRST fresh row can only appear on a weekday **after** a complete same-Sydney-day quote is actually returned and recorded; even on Monday 19 Oct, a provider error/holiday must skip rather than invent a quote. Before observing a successful real capture, DO NOT claim data collection works merely because unit tests pass.

Local unit tests cover: ASX AUD/symbol/zone, same-session completed candle, no stale/weekend/holiday/source-future rows, price OHLC validity, append-only hash consistency/tamper rejection, duplicates and no network on weekends, and fail closed. Existing BTC forward-tape unit checks remain mandatory. GitHub PR tests cover code quality and remain research-only.

**No historical backfill** of 2017/2021 ASX:IBIT can ever be genuine because fund first traded in 2025. For 2025-Nov to 2026-Oct history, older published prices can be sourced in a separate, labelled retrospectively downloaded dataset, NOT copied into this prospective append-only tape as though they were captured during 2025. The current prospective tape is only a way to accumulate genuine forward **indicative reference prices** from now onward; no evidence of executable limit-order prices, quote depth, spreads, tax parcels, or investment alpha. Retain the weekly conditional readiness watch rather than creating a second recurring user notification.

GitHub first build and first actual post-weekday market capture statuses: pending.
