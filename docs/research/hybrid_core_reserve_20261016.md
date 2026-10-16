# Hybrid Dynamic BTC DCA: baseline/core + deep-reserve + fallback stress

**16 October 2026 · research only · not promoted to Production**

* [Hybrid execution engine](../../engines/research/hybrid_core_reserve_audit.py)
* [Invariant unit tests](../../tests/test_hybrid_core_reserve_audit.py)
* [Passing historical GitHub Actions #38892609180](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38892609180)
* [Original read-only 25/75, 50/50 run #38891948365](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38891948365)
* Draft [Research PR #90](https://github.com/aussiekarl-gif/BTC_Composite/pull/90)

## Why experiment

The permanent 40% drawdown entry gate met the *user-reported* 25% buy-error
target for the model year 2026 but missed entire uptrends in older years.
User wants flexible DCA and **A$500,000 starting in 2026**, rather than
fictional capital invested in 2016.

This script tests bounded combinations of independent self-financing sleeves:

1. **Baseline/core:** A$125,000 or A$250,000 (25%/50% of A$500k),
   invested in 12 equal AUD weekly orders from the SAME January start.
2. **Deep reserve:** remaining A$375,000 or A$250,000, idle until the
   *previous completed week* closed at least 40% below its preceding
   52-week AUD close high. Then the pre-existing flexible adaptive DCA
   makes risk-scaled buys (and could sell during a later market cycle).
   Its duration is unrestricted; no hindsight future low/peak enters
   the orders.
3. **Optional fallback A:** if no deep gate before the 27th weekly
   opportunity, release reserve as 26 weekly equal AUD tranches.
   If a deep gate appears later, stop the fallback and switch to
   risk-scaled trading with any remaining reserve.
4. **Optional fallback B:** after the same 26-week waiting period, release
   one of 26 equal AUD reserve tranches **only when** the previous
   week's BTC/AUD close exceeds a **rising trailing 20-week SMA**
   (compared with the SMA four observations earlier). Pauses and
   restarts are permitted and the release has no fixed expiry. A later
   deep gate takes over.

The model charges A$3 per **filled order**, with segregated FIFO
accumulation-phase illustrative SMSF CGT accounts: 15% if no long-hold
discount, effective 10% on eligible long-held gains, immediate tax escrow,
and estimated CGT if completely liquidated on the final date.
Cross-sleeve tax-loss offsets are NOT implemented. When core and reserve
buy on the same day, these are separate A$3 orders (conservative).
Fund admin, spreads, ETF expense ratios, slippage, income taxes other
than CGT, real Australian ETF tax nuances and yield on cash are excluded.

Research source is historical master BTC/AUD through **31 Aug 2026**
and independently fetched Blockchain.com BTC/USD and Frankfurter
AUD/USD through **12 Oct 2026**. The archive is read-only.
The independently reconstructed AUD Power Law is strictly prior-data,
**NOT** the archived composite, which has not passed a complete
point-in-time data provenance audit. Older prices warm indicators,
but there is **no user money invested before January 2026**.

## Results: 2026 A$500k January-start account

These are model accounts, **not** actual My Portfolio transactions.

| Strategy | BTC held 12 Oct | BTC VWAP acquisition price vs user-reported $57,717 USD | Model account value A$ | After hypothetical terminal CGT A$ |
|---|---:|---:|---:|---:|
| Immediate buy and hold | 3.644970 | +58.48% | 437,342 | 437,339 |
| Equal DCA 12 weeks | 4.627366 | +29.97% | 555,214 | 546,930 |
| Original January adaptive | 4.141813 | +42.79% | 497,335 | 497,332 |
| **25% core, 75% deep reserve** | **4.991877** | **+21.83%** | **599,331** | **584,426** |
| 50% core, 50% deep reserve | 4.869190 | +24.42% | 584,553 | 571,865 |

The 40% drawdown gate activated **9 February 2026** using a
previous-week observed drawdown of **40.884%**. Therefore neither
calendar nor trend fallback purchased *any* additional Bitcoin.
All the alternative fallback settings yield **identical 2026
results**. Both hybrids meet the requested 25% **average** entry-price
target against a **user-reported, provisional observed low**.
Their cash is approximately 99.9% deployed by this research data
cutoff. The user-reported intraday US$57,717 low on June 30 is not
independently verified as an intraday print with our weekly close data.

No model executed a SELL in the 2026 simulation, so the 25%
**selling** error and full-cycle BTC multiplication are **unknown**.

### 25% core / 75% reserve full 2026 account diagnostics

- A$125,000 core, A$375,000 reserve.
- **12 core buy orders, 27 reserve buy orders** (39 × A$3 = A$117 brokerage).
- **4.99187679 BTC** remaining, A$380.60 cash.
- **A$599,330.84** marked value; **A$584,426.12** hypothetical total liquidation
  after SMSF CGT if every BTC sold at the final observed close.
- Historical model peak-to-trough total account drawdown: **−23.76%**
  (does not measure worst possible future loss).

## Seven fixed Jan-start, ~52-week robustness comparisons

For each 2019–2025 year the strategy and immediate buy-and-hold
received the same starting A$500,000, same endpoint and historical
price data. Results are in-sample, with *some decisions proposed
after seeing the history*, not untouched forward validation.

| Variant | Years exceeding buy and hold | Years exceeding equal 12-week DCA | Median annual relative to hold |
|---|---:|---:|---:|
| 25% core, no fallback | 3/7 | **4/7** | −7.00% |
| 25% core, unconditional 26-week fallback | 2/7 | 3/7 | −7.00% |
| 25% core, rising-20WMA fallback | 3/7 | 3/7 | −7.00% |
| 50% core, no fallback | 3/7 | **4/7** | −9.16% |
| 50% core, unconditional fallback | 3/7 | 3/7 | −9.16% |
| 50% core, rising-20WMA fallback | 3/7 | 3/7 | −9.16% |

### Contrasting stress years (account value A$ at year-end)

| Strategy | 2024 rally | 2025 down-market |
|---|---:|---:|
| Buy and hold immediately | 1,226,238 | 420,379 |
| Equal 12-week DCA | 1,031,039 | 441,186 |
| 25% core, no fallback | 632,704 | 485,273 |
| 25% core, unconditional fallback | 812,756 | 414,412 |
| 25% core, trend fallback | 649,699 | 431,369 |
| 50% core, no fallback | 765,482 | 470,577 |
| 50% core, unconditional fallback | 885,478 | 423,315 |
| 50% core, trend fallback | 776,803 | 434,630 |

**The obvious weakness is not solved.** A lot of reserved cash still
missed the 2024 rally. Blindly spending it later caused 2025 losses.
The historical trend filter, which buys only in visibly strengthening
markets, bought only **8** fallback tranches during 2024 but
**15** during 2025; it also failed to distinguish the two environments
reliably. We cannot claim this is a robust trend-following improvement
just because it has intuitive appeal.

The 2021 test remains poor for all hybrids (roughly 29–33% behind
matched hold) and underscores an unresolved selling-timing problem.

## Promotion decision and research next steps

**Keep all six variants as explicit, read-only Research candidates.
Do NOT make any hybrid the live Production default.**

Meaningful next tests should focus on (1) point-in-time provenance of
archived risk components (not merely prefix-invariance of a replacement
Power Law), (2) forward prospectively logged decisions on untouched
time periods, and (3) a small set of genuinely distinct macro trend
regimes or entry/exit events rather than more 2024/2025-specific
threshold tuning. The outcome measure remains after-tax account value,
BTC accumulated, matched-start opportunity costs, cash deployment,
worst drawdown and **both** buy and sell effective VWAP error.

The customer's true saved My Portfolio receipts and US$57,717 reference
are separate from the six simulated accounts. **No real user
transactions, Portfolio Google Sheets storage, Production rules or
authoritative data master have been written or altered by this work.**
