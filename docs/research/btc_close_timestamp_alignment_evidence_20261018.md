# Confirmed timestamp mismatch in Blockchain.com BTC daily data — 18 October 2026

## Status and scope

**Priority: HIGH — date-alignment data correctness.** Do not confuse with additional historical parameter optimisation. This audit is **RESEARCH ONLY**; no production Cycle Trading data feed, Streamlit recommendation, one daily ntfy, buy/sell percentages, user portfolio, SMSF, Production V5.8.2 or past immutable forward records were edited. Implementation needs a separate versioned, reviewed release affecting live data provenance, and original 200WMA 2.5% BUY and halving-gated SELL parameters remain frozen.

GitHub Actions [run 39126914456](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39126914456) **SUCCESS**, 35 tests (13 attribution/shadow tests, 5 existing market-feed, 7 Kraken bridge and 10 unchanged current Cycle market percent tests). The live third-party public HTTP probe returned dated, positive external price readings; exact JSON outputs/artifact attached to that run. The comparisons made here are repeatable deterministic computations on **fetched 18 October public source responses**, which could be updated later by provider, hence the artifact preservation.

## Root cause: Blockchain chart MIDNIGHT DATE represents LAST INTERVAL'S CLOSE, not an end-of-that-labelled-day price

`engines/research/verified_recent_price_bridge.py:parse_blockchain_price()` takes `x` epoch seconds and normalises to UTC date **D**. But the observed source point carrying date **D** is almost exactly the Kraken UTC close for **D−1**, rather than Kraken's same-date close **D**. Comparison uses actual independent Kraken spot XBTUSD 1440min OHLC close and BlockHorizon on exactly matched UTC dates.

Across **31** archive/public overlapping UTC price dates **5 September–5 October 2026**:

| Price comparison | Median absolute deviation | MAX absolute deviation | Unambiguous empirical consequence |
|---|---:|---:|---|
| Archive daily close D vs raw Blockchain label D | **0.60459%** | **6.29465%** | Apparent price-source "conflict" (2 dates above 5%) |
| Kraken spot daily close D vs raw Blockchain label D | **0.61571%** | **6.30253%** | Similarly large false mismatch |
| Kraken spot daily close **D−1** vs Blockchain midnight label **D** | **0.00726%** | **0.05268%** | Near-perfect daily-close alignment |
| Archive daily close **D** vs Blockchain midnight label **D+1** | **0.01047%** | **0.05249%** | Second independent 31-date confirmation |
| Archive daily close D vs Kraken spot daily close D | **0.00532%** | **0.01731%** | Two close-price sources agree |

Worst apparent date **21 September 2026**, archive **US$86,586.52**, Kraken **US$86,593.80**, raw Blockchain **US$81,136.20**; exactly dated Kraken-archive difference **0.00841%**. Two raw-labelled dates above5% were Sep18 and Sep21. No source crossed below versus above archived 200WMA in the 31-date overlap; **this does NOT prove future signals are unaffected**.

### Strong second out-of-archive confirmation

For **10 overlapping raw Blockchain/Kraken labels from 6–15 October 2026**, archive no longer covers this period:

| Alignment | Median absolute difference | MAX |
|---|---:|---:|
| Raw Blockchain D vs Kraken D | **1.34873%** | **2.72938%** |
| Raw Blockchain D vs Kraken **D−1** | **0.01002%** | **0.02260%** |

A short same-date price disagreement is expected if one source averages or marks a UTC boundary while Kraken captures the final exchange trade of the actual preceding interval. But matching **41 separate date-labelled observations to <=0.053% maximum difference** is strong evidence the raw Blockchain **chart timestamp marks the *end* of the previous UTC daily candle**, not the close belonging to its labelled calendar day. Official Blockchain.com describes `market-price` as consolidated average exchange market price, while Kraken OHLC `close` is the last traded price for its interval. We should not claim their different computation methods are identical:
- https://www.blockchain.com/explorer/charts/market-price
- https://support.kraken.com/au/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data

The actual correction needs re-date the public Blockchain chart point **D** as market completed-close date **D−1**, with strict causality and no mislabelled "prospective" capture time; daily labels for original previous snapshots must remain immutable for audit and scored outcomes, marked existing stale/invalid rather than rewritten.

## Exact unchanged market code side-by-side shadow replay — 18 October

On the SAME historic archive, verified halving 2024-04-20, unchanged shared market BUY/SELL code, dated AUD FX, and captured public sources:

| Market measure | Current UNCHANGED live splice using raw Blockchain label | Research SHADOW proposed aligned chart + Kraken verified bridge |
|---|---:|---:|
| Most recent price CLOSE date displayed | **2026-10-15** | **2026-10-17** |
| Most recent BTC/USD closing reference | **US$81,566.64** | **US$81,382.00** |
| Prior completed BTC/USD close for actual recommendation | **US$83,093.75** | **US$81,500.80** |
| Strict prior 200 WEEK WMA | **US$66,908.607** | **US$66,730.181** |
| SHARED market trading recommendation | **HOLD** | **HOLD** |
| BUY as % remaining actual AUD cash | 0.00% | 0.00% |
| SELL as % current BTC holdings | 0.00% | 0.00% |

The research-only aligned Blockchain.com close end-point was dated Oct14, **3 days behind** completed UTC Oct17; append *three* Kraken fully completed 15,16,17 Oct closes, with **7 genuinely recent overlapping aligned Kraken/Blockchain dates**, overlap **max 0.0181%**, **median 0.009%**, no override of earlier archive values. The candidate's corrected archive crosscheck max was **0.05%**, vs current raw feed **6.29%**. Current HOLD same because BTC well above ~66.7k 200WMA and past specified scheduled halving review days. This **does not mean the bug is benign** when BTC nears a threshold and a daily signal changes quickly.

## Next release candidate — NOT IMPLEMENTED

Do **not** simply subtract one day from a price and silently make the 17 Oct close appear without a real source. A safe live and ntfy source correction must:
1. Assign raw Blockchain.com chart end-of-day MIDNIGHT timestamps to **previous completed UTC date** in a *shared, explicit, dated source normaliser* (no arbitrary shift of Kraken exchange OHLC dates). Verify UTC timestamp is genuine midnight or skip; never use future/in-progress bars.
2. Retain existing BlockHorizon historical prices *as-is*, reject conflicting dates, align public overlap exactly, crosscheck corrected latest close against independent **already completed** Kraken XBTUSD spot daily OHLC and verify all missing dates are contiguous.
3. Permit the market model to produce new recommendations **only if data are dated at the most recent completed UTC day** or explicitly report unavailable/stale; do not silently fall back to raw chart prices, include current incomplete UTC close, relabel missing price bars, or claim ASX ETF weekend execution. Make fallback failures visible.
4. Keep the same versioned BUY/SELL settings, 2.5%-remaining cash and existing scheduled SELL percentages; make both Streamlit and ONE daily ntfy resolve the exact same corrected source/as-of date, with optional conservative no-action on a source conflict. Display day-age, quote provenance and last prior completed close.
5. Add tests including a huge one-day BTC move on D, a Sunday ASX gap, chart candle D+1 vs Kraken candle D, later Kraken source missing, underlying 200WMA boundary crossing causing BUY vs HOLD disagreement, as-of no-lookahead, data timestamp-sample revision and shared app/ntfy decision parity.
6. Preserve all earlier immutable `data/research_forward_validation/cycle_market_signals.csv` observations exactly. Their previously published provider labels/date interpretations must be recorded as **superseded-source-date semantics**, not edited retrospectively; do not score old rows as independent prospectively correct outputs.

**Recommendation:** The data-date fix is strongly justified on now-checked public overlap and should be treated as a **correctness release candidate**, *not evidence that a new trading strategy is more profitable*. Because updating the live daily input can change a later BUY/SELL instruction and may require a Kraken provider, require an explicit, reviewed versioned deployment decision and rollback tests. All current source auditing here remains strictly read-only and cannot modify live holdings or send new notifications.
