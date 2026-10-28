# 27 Oct 2026: causal post-signal quote pilot blocked by whole-second source receipts

## Actual prospective source evidence

As of 2026-10-26T23:07 UTC (27 Oct 09:07 Brisbane), both original
`data/research_forward_validation/kraken_spot_depth_forward.csv` and
`data/research_forward_validation/coinbase_trade_samples_forward.csv`
contain **27** hash-chained, genuine, independent market observations.
**22/27** slot-matched rows have *identical stored* `captured_at_utc`
seconds. That is NOT evidence of simultaneous HTTP responses: both
original summarizers used `isoformat(timespec="seconds")` and rounded away
the subsecond receipt order.

The separate prospective causal quote module, merged to `main` on
25 October, intentionally requires **strict** `Kraken receipt < Coinbase
receipt <= new post-signal request start < post-signal receipt`. It correctly
fails closed when the independent original receipt timestamps appear equal.

All **five** source slots since the post-signal collector's 25 Oct release
(25 Oct 12:00/18:00 UTC and 26 Oct 06:00/12:00/18:00 UTC) saved a genuine
new Kraken/Coinbase pair, but all five share identical rounded receipt
seconds. Their GitHub Actions diagnostics therefore report
`SKIP_STALE_ORIGINAL_PAIR` even though the independent source requests
were actually consecutive. The new `kraken_post_signal_quotes_forward.csv`
does **not** exist and the prospective causal quote count is **zero**.
This is a **data-capture evidence defect**, not a provider outage, not
corruption of existing hash chains, and not evidence of trading alpha.

The 26 Oct 23:07 UTC capture:
- Original independent sources: `NEW_SNAPSHOT` / `NEW_SNAPSHOT`,
  no provider failures, zero ntfy/portfolio/broker activity.
- Stored Kraken and Coinbase receipts both
  `2026-10-26T23:07:00+00:00`.
- New quote attempt: `SKIP_STALE_ORIGINAL_PAIR`, appended `false`.
- Forward post-signal quote score: zero rows, zero directional hypotheses.

## Narrow research-only proposed fix (DRAFT PR; no promotion)

Only for *new future* original Kraken and Coinbase research captures,
store actual timezone-aware receipt timestamps at microsecond precision
rather than truncating to whole seconds. Do not alter actual sampling
time, HTTP request sequence, any frozen hypothesis, 60/40 threshold,
after-cost assumptions, or ASX/IBIT prices.

Original source tape readers accept both existing second-only timestamps
and new microsecond timestamps, and continue validating the full
append-only SHA chains. The original legacy rows and their hashes are
**never** modified or inferred to have a strict order. The causal quote
gate remains strict; if clocks really produce equal instants or the
independent request is late, it must still reject the sample. No synthetic
quote is appended, and the first real new quote requires an actual
subsequent HTTP response after both source receipts.

Added offline regressions check (a) microsecond precision on both
original providers, (b) mixed legacy/new timestamp tape integrity,
(c) truly ordered independent receipts within the *same whole second*
now allow a strictly later causal quote, and (d) old rounded equal
receipts still fail closed and never initiate a new provider request.

The existing paired-source CI also validates the immutable original
27-row Kraken/Coinbase files and runs the post-signal quote source
self-check. Public provider probe remains PR-only and read-only.
This change is intentionally **not merged**: observe green CI first,
then seek explicit approval before allowing future source-capture
timestamp changes on `main`.

## Trading implications

Even once the quote collector works, a REST midpoint/bid/ask after
both signals is still **not** a broker fill. Hypothetical two-sided
spot fees do not include ASX:IBIT spreads, brokerage, ETF premium/discount,
market impact, tax, FX, or live slippage. Current Cycle signal remains
HOLD and there are zero matured non-neutral prospective signals.
Do not promote any trading rules, dashboard, portfolio, daily ntfy or
authoritative data master on this evidence.
