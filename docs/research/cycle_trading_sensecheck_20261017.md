# Cycle Trading — Operational sense check and simplification (17 Oct 2026)

**Status: safer and usable for MANUAL shadow decisions, NOT cleared as a prospectively validated primary trading strategy.**
Research feature only; no broker orders, no Production model changes, no modifications to master data or saved transaction rows.

## Real public-data availability (independent GitHub Actions runner)

The nonblocking [public-feed smoke test](../../engines/research/cycle_live_feed_check.py)
ran 16 October 2026 at 21:22 UTC (17 October 07:22 Brisbane) with:

- Archived BTC/USD + Blockchain.com historical full price series: **31 exact overlapping dates** passed provider-crosscheck.
- Latest **completed** BTC closing-price observation: **2026-10-15** (1 day old on the runner).
- Historical USD/AUD conversion dated **2026-10-14**; market validation successful.
- ASX **IBIT.AX**, AUD indicative quote dated **2026-10-16 04:59:37 UTC**, about **16.4 hours old**, provider Yahoo Finance.
- Runner outcome `market_ok=true`, `ibit_quote_ok=true`. No portfolio read, broker order or ntfy publication.
- **Snapshot, not an uptime guarantee**. Streamlit/ntfy must refuse to propose trades on unavailable/stale or inconsistent BTC or FX inputs.

ASX:IBIT spot quotes come from *one public provider* with two HTTP host fallback endpoints. This is **not** an executable broker bid/ask or an independent corroborated market price. Manual broker override remains available and necessary to place an actual order. Historical BTC/AUD references use trade-date market price and trade-date-or-earlier AUD/USD, not 2026 exchange rates for older fills.

## Corrections made

1. **No more accidental daily DCA stacking:** A trading signal can stay active for days. The current Research BUY/SELL amount is now suppressed to HOLD if there is *any* recorded executed BUY/SELL less than **seven calendar days ago**, while the market signal and its desired allocation % remain visible. Next eligible trade date is explained. Trades NOT recorded in My Portfolio cannot be detected; user must still reconcile with actual broker.
2. **No ASX:IBIT quote ⇒ no actionable BUY:** Market remains BUY WATCH, but the actual current transaction field stays HOLD and A$0 until an ASX:IBIT AUD quote can be supplied. Never use Nasdaq IBIT/USD or a BTC spot price as an ASX ETF unit price.
3. **Use saved cash automatically:** Current A$ cash = original contributions − recorded buy consideration − fees + sale proceeds; manual *downward* override if broker cash or SMSF tax escrow differs. Missing portfolio now defaults to zero rather than a made-up A$50,000.
4. **Date-aware historical transaction reference:** When recording an actual executed BUY, the historical BTC/AUD value is automatically proposed from completed dated BTC/USD and dated non-future AUD FX (when available). For an old ETF trade, actual executed AUD unit price remains mandatory manual input; it is not replaced by the current IBIT delayed quote. Actual trade execution must be confirmed.
5. **One shared provider merge policy** used by Streamlit and the one daily ntfy runner: prior complete UTC day only, at least 3 archive/public dated overlaps, deviation checks, archive not rewritten. Stale feed triggers data-unavailable guidance.
6. **Simple front page:** Trading decision first, main cash and IBIT inputs automatic/optional; prior cycle top and post-top bottom in **A$ with percentages remain visible**; the more detailed price/200WMA chart moves under an optional expander.
7. **Preserve simple notification:** exactly one scheduled market-only Cycle Trading ntfy (8 AM Brisbane), with BUY/Sell percentages but **no fabricated private portfolio amount**, and no new ntfy sender.

## Material model risk found: historical results do NOT yet match the Streamlit trading rules

**SELL percentage denominator mismatch — important!**

The current Streamlit/ntfy `SELL_REVIEW_DAY_WEIGHTS` are:
day500 **5%**, day525 **24%**, day532 **20%**, day539 **16%**, day546 **12%**, day553 **8%**, day560 **5%**.
Each is a percentage of the BTC/IBIT holdings **remaining at that signal**, NOT of the original acquired position.

Even if EVERY stage executed, the fraction remaining is:

`0.95 × 0.76 × 0.80 × 0.84 × 0.88 × 0.92 × 0.95 = 0.37316471808`

That means **62.68% of the original BTC sold and 37.32% retained**, before any trend-gated skipped tranche. **It is not the 20% holdback used in the separate historical day500 exit replay.**

The backtest's `staged_day500_dynamic_exit()` instead sizes its six anchor tranches as fractions of **ORIGINAL BTC**, with a previous-day regime factor of 0.75/1.20/1.30, and the holdback variant caps day500–560 total sales at **80% of original**. The current Streamlit sell rule is only a separate research simplification. No exact historical SMSF/BTC multiplier may be attributed to it.

**BUY stage mismatch — equally important:**

The historical `adaptive_recovery` buyback continues over later weekly dates after the initial below-200WMA crossing, increasing allocation on specified price/50DMA recovery signals and retaining unspent after-tax cash. The current Streamlit `adaptive_recovery` output simply uses an initial 2.5% of remaining cash on a prior close **below** 200WMA, with a seven-day recorded-order cooldown. It does not persist a verified active buyback state or implement the 15% above-200WMA recovery tranche.

Therefore the previously reported 2017/2021 historical gain-vs-hold and bottom-error numbers **are not validated outcomes of the current simplified UI BUY/SELL engine**. Both the UI and daily ntfy now explicitly mark lack of end-to-end backtest parity.

Only **two completed modern cycles** were present in the earlier historic comparison (2017, 2021); 2025/26 remained right-censored; 2013 excluded as user requested. No out-of-sample cycle-top/low proof exists. The default late-cycle SELL rollover is particularly exploratory.

## Trading workflow

Go to the Streamlit default model **Cycle Trading — Research**.

**Trading decision:** Confirm latest verified price and ETF quote timestamp. Saved Google Sheets portfolio loads the actual recorded capital, net unsold IBIT units, direct BTC, executed BUY/SELL and net cash. The market watch percentage is shown, but actual A$ / whole ETF unit trading instruction is gated by data safety, cash, seven-day cooldown, and broker holdings confirmation where relevant.

**My Portfolio — Buy & Sell:** Enter only filled purchases/sales, including **actual executed per-unit price**, fees, date and reference, then save to the existing Google Sheets portfolio; never add planned trades as if executed. Net quantities update from recorded executions. Importing actual broker statements automatically is **not** yet available.

**Historical comparison:** Explore hindsight outcomes with complete-cycle vs incomplete labeling. These aren't your actual 2026 portfolio performance or a live strategy validation.

The data service cannot prove broker holdings or fund SMSF tax phase. An A$ balance after a sale is **before actual CGT reserve**; tax liabilities, ETF spreads, cash interest and execution slippage are not modelled in the current trading suggestion.

## Required before promoting Cycle Trading to the live investment model

1. Design one **identical** causal buy/sell state machine for **historical replay, Streamlit and ntfy** (incl. staged proceeds, past executed signal dates, recovery phase, max allocation, last-trade and tax escrow); then rerun date-exact FIFO after-tax comparisons, modern holdouts and fee/slippage stress tests.
2. Resolve original-vs-remaining position denominators and choose the intended 20% holdback behavior **before** altering sale instructions.
3. Use actual verified broker fills, historical ETF NAV/spread and tax lots to test a complete forward 2026 cohort. For 2026 the 2024-halving day500 was already in Sep 2025 and cannot be harvested retroactively.
4. Document a fallback for potential future cycles that never fall below the 200WMA, to avoid missing an entire BTC rally while in cash.

**Promotion decision:** Keep V5.8.2 Production and V5.9 unchanged, make Cycle Trading the primary **interface** but not a validated live execution authority. Trading remains manual.

## Automation and cost discipline

Cache historical research exports 12h, public prices 6h, historical FX 24h, ETF delayed price 15m and My Portfolio 10m; one explicit **Refresh** button clears data and saved-portfolio caches. The once-daily GitHub ntfy workflow is unchanged; no repeated message or new push sender is added. Existing provider files remain preserved; no need for a NAS or additional subscriptions.
