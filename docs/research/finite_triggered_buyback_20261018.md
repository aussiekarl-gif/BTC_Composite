# BTC Cycle: 24 / 52 weekly buyback schedule AFTER first strict 200WMA gate

18 October 2026. **RESEARCH ONLY, opt-in candidate, not current Cycle Trading rules.** Do not change Streamlit BUY/SELL, Production V5.8.2, Research V5.9, personal BTC/ASX:IBIT portfolio, Google Sheets or one ntfy daily message.

## Reason

Merged PR #151 demonstrated a major *cash-rich, BTC-poor* failure of the current post-sale buyback in the 2017 historical proxy: with BTC initial purchases made hypothetically at the 2016 halving and the historical 90%-original BTC staged SELL rule, actual BTC after buyback at day1150 was **62.2096 BTC + A$9.606m uninvested cash**, vs buy-and-hold **580.0424 BTC**. Despite attractive hypothetical +29.116% aftertax AUD account returns, most SALE proceeds were not reinvested: current 2.5%-of-remaining cash requires prior close below 200 WEEK MA ON EVERY new weekly purchase, and 2018 just one Sunday eligible date.

Goal for new in-sample experiment: keep EXACT same prior-data, date-accurate, illustrative FIFO/AUD tax seller and prior-WMA FIRST buy gate; once a BUY is actually executed, precommit to up to **24 or 52 weekly at-least-7-calendar-day-spaced BUYs** from then-available aftertax AUD cash, **even if BTC has recovered above the 200WMA**. No purchase before original WMA gate. No future bottom knowledge. A dynamic `remaining cash / remaining scheduled purchase tranches` fraction deploys the cash in a predetermined number of purchases; in the 24-tranche policy a last remaining balance may be large if few planned tranches are left, and a sharp price recovery can make chasing price very expensive.

## Exact three matched buyback policies

1. **Original live 2.5%** remaining aftertax available AUD cash only WHEN the prior BTC/USD completed close is strictly below prior 200 spaced WEEKLY closes, 7-day executed BUY/SELL ledger cooldown. NO change.
2. **24 executed-weekly-order candidate**, first actual fill must satisfy original live BUY WATCH; from then on up to 24 real purchases, at least seven calendar days apart, spending remaining available cash in equal *remaining-tranche denominator* increments, possibly after BTC has recovered and original shared market recommendation is HOLD. If original live SELL WATCH appears on a planned buy date, suppress BUY; use one ledger transaction max per 7 days.
3. **52 order candidate** identical, with 52 scheduled purchases. Smaller average order, slower market re-entry, leaves more cash at short as-of horizons.

Each entire SELL strategy is simulated independently with all 3 buyback policies: (a) unchanged live scheduled-and-experimental recurring rollover; (b) live scheduled-only, experimental rollover suppressed; (c/d) unchanged historical original BTC-denominator staged 90% / pre560 20%-holdback exits; (e) buy & hold. **Same hypothetical A$500k entire BTC position purchased at HISTORICAL halving, NOT user's actual 2026 account.** No invented cash, initial SALE at 2025 peak or new outside capital. Same strict prior completed BTC data, USD/AUD date prior, A$3 per fill, illustrative FIFO SMSF accumulation gain taxes charged from each SELL, 7 day ledger gap for BUY and SELL, and hypothetical end liquidation taxes. All instruments are BTC/USD AUD-price closing proxies, NOT actual pre-Nov2025 ASX:IBIT exchange prices.

Two execution contexts: every calendar day BTC close (2017 included Sunday gate) and weekday-only BTC close proxy. In weekday-only **a Sunday-only gate does not activate any planned buyback** because no actual ETF order can fill without a separately tested carry-forward policy; do not silently use a weekend quote as executable IBIT fill. No ASX public holidays, quoted bid/ask, tracking errors, intraday broker orders or exact SMSF pension phase modelled.

Evaluate 2017 / 2021 completed through day1150 and 2025/26 right-censored through archived Oct5 2026. Artificial prefix-preserving stresses for 2017 and 2021: rising BTC 2x/4x between halving+600 and day1150; after day900 another 50%/70% drawdown reaching low at day1060 and ending at 55% of pre-stress BTC price. **All histories reused and candidates selected after looking at original outcomes; NEVER claim out-of-sample improvement or causal effectiveness for unobserved market.**

Metrics required: actually held BTC, BTC-equivalent of unspent cash at terminal (clearly different), unspent cash AUD, terminal hypothetical liquidated aftertax AUD, absolute and relative to unchanged 2.5%-only-below-WMA policy within same historical SELL strategy, actual BUY/SELL count and first market trigger, additional exposure downside and real weekday execution gap.

No live rule promotion without strong independent validation. CI evidence: pending.
