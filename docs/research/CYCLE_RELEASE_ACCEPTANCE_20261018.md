# BTC Composite — Release-readiness and validation freeze
**Frozen 18 October 2026 — Brisbane (AEST). Owner sign-off required for any live strategy change.**

## Why this exists

The research has generated dozens of experiments and hundreds of deterministic assertions, but essentially **two completed recent BTC boom–bust cycles** underpin the strongest historical SELL / BUYBACK conclusions. Testing many parameter settings against the *same* 2017 and 2021 events does **not** create additional independent samples. Therefore, **stop new parameter sweeps** based solely on those cycles. New work is limited to correcting proven execution/data bugs, enforcing cash- and tax-feasible trading, obtaining prospective point-in-time observations and evaluating frozen candidates without parameter selection.

A passing CI test means **the implementation matches its declared logic and accounting constraints**. It does not prove the strategy will profit or beat BTC buy-and-hold out of sample.

## Frozen policies — independent status

| Policy / evidence | Current status | What has and hasn't been proved |
|---|---|---|
| **Live Cycle Trading (control)** | **ACTIVE; UNCHANGED** | BUY WATCH: prior completed BTC USD close strictly below prior exact 200-week SMA, 2.5% of **remaining available AUD cash**, subject to existing 7-day executed-ledger cooldown. SELL WATCH: gated fixed halving review dates, selling fractions of **remaining actual BTC holdings**, plus **experimental repeated** 5% late-rollover SELL eligibility. Neither rule is guaranteed profitable. |
| **Production V5.8.2 DCA Today** | **ACTIVE; risk/weights unchanged** | Current production DCA amount uses remaining cash, remaining weeks and risk multiplier. Historical chart was corrected for available warmup and prior dated FX by merged PR #149; it still uses a retrospectively normalised future-total-weights allocator and MUST NOT be advertised as historical live DCA Today fills. |
| **Cycle weekend WATCH to first ASX session** | FROZEN RESEARCH only — PR #148 | Simulated recovery of the only 2018 Sunday entry under a Monday BTC-close proxy; no verified 2018 ASX:IBIT quote could exist. Risk of extra cash exposure in synthetic deeper bears. Requires actual session calendar, stored dated signal and executable pricing. |
| **Cycle 3.0% of remaining cash per eligible weekly BUY** | FROZEN RESEARCH only — PR #146 | Improved some in-sample historical AUD results, worsened synthetic prolonged declines; merely increases exposure, NOT bottom timing accuracy. |
| **Finite 24-/52-order post-trigger full cash BUYBACK** | FROZEN RESEARCH only — PR #152 | 24 weeks accumulated more ACTUALLY HELD BTC with attractive 2017/2021 retrospective returns, but a 2021 deep-bear synthetic path showed approximately **−36.96% hypothetical aftertax AUD** vs current strict BUYBACK. A 52-week plan is a different exposure compromise, not uniformly superior. |
| **Valuation-aware 52-order 50/50 core and protected reserve** | FROZEN RESEARCH only — PR #153 | First successful original strict BUY gate required; 50% paced core after actual net proceeds, reserve only if previous BTC/USD <=85% of previous 200WMA. In-sample attractive 2021 aftertax and actual BTC, but some future bear stress and censored 2025/26 outcomes worse. |
| **Original-BTC-denominator staged SELL study** | Historical CHALLENGER, NOT live SELL — PRs #150–151 | Historical original-BTC stage exits don't share current live SELL market conditions or remaining-holdings percentages. The buyback study also shows a cash-rich yet BTC-poor outcome, so don't transfer SELL-only profits into live model claims. |

**Freeze:** no changes to `engines/research/cycle_trade_allocation.py`, the existing Cycle Trading Streamlit BUY/SELL action, Production DCA Today risk constants or the single daily ntfy message without a separate reviewed proposal and explicit user implementation choice. All challengers remain **shadow-only**.

## Empirical facts as of 18 October 2026

1. **Genuine forward Bitcoin observations:** `data/research_forward_validation/cycle_market_signals.csv` contains actual captured source-stamped snapshots for **2026-10-15** and **2026-10-17**. Both say **HOLD**. Missing 16 Oct is **NOT backfilled**, and hash-chain provenance means a later operator must not rewrite earlier states. The 7/30/90-day subsequent outcomes cannot yet establish an investable strategy gain. The observation tape contains no verified original point-in-time historical onchain vintage.
2. **ASX:IBIT:** Australian iShares Bitcoin ETF listed 14 Nov 2025. The `IBIT.AX` AUD close recorder (PR #154) has 43 passing validation tests, shares the existing 12:25 UTC / 22:25 Brisbane once-daily RESEARCH schedule and creates **no new user ntfy**. As at this protocol date, **zero actual same-day IBIT observations recorded**. Yahoo query1/query2 are the **same vendor**, not two independently corroborating quotes; daily candle close is NOT a broker-executable bid/ask. No 2017 or 2021 ASX:IBIT history ever existed.
3. **Production historical reporting:** draft PR #149 was numerically checked and merged as a *historical-only accuracy correction*: legacy selected-start pre-indicator trimming discarded required calibration. Partial-input MVRV + BTC diagnostic changed **167 of 167 paired valid risk-score days** and filled 14 missing initial score days in each of three 181-day windows (Jan 2017, Jan 2021, Jan 2025). This is NOT a new live risk rule or verified full historical composite, since historical Fear & Greed and genuine point-in-time provider vintages are unavailable.

## Go / no-go: explicit requirements

### A. Correctness and consistency — must pass before any real change

- Same exact **dated PRIOR market-close** signal between Streamlit, one daily ntfy, research replay and each saved observation. Never use current incomplete UTC BTC day or same-day ASX close to choose an earlier intraday order.
- Personal BUY/SELL portfolio quantities and remaining AUD cash must come from verified user-entered executed transactions; track deposits, actual filled **whole ASX:IBIT units**, realised costs, remaining holdings, days since last executed trade and no negative cash. Do not assume historic 2016/2020/2024 starting BTC was actually user-owned.
- A single ledger applies the actual **7 calendar day cooldown** to executed BUY and SELL, with fees, split/accumulated tax lots, AUD FX provenance, cash after estimated realised tax, and explicit SMSF tax-phase assumptions. No historical sale-cash magically appears in a fresh funded account.
- Australian IBIT timing needs an **actual market-session/holiday calendar**, eligible order date, indicative vendor reference, quoted bid/ask or explicit conservative hypothetical costs, NAV fee treatment without double charging, and actual ETF share price and quantity. A Saturday/Sunday signal is not a filled ETF BUY.
- Test no-lookahead, prefix invariance, no missing prices/FX, no double fills, no implicit weekend fill. Every required deterministic test suite green; also inspect real Streamlit error handling before promoting.

### B. Independent evidence — don't overinterpret counts

- Freeze candidate parameter values **now**. Track the original live policy and each frozen *shadow* policy separately on truly new source-stamped closes; never revise old shadow signals in light of subsequent prices. Report missing observation days and non-trading dates explicitly.
- As a **data pipeline smoke test**, check after at least **20 recorded distinct IBIT weekday session dates** and **30 independent UTC BTC daily snapshots** that provider dates, FX, instrument symbol/currency, model version and hash-chain all remain consistent. **These counts do not establish an investment performance advantage.**
- A BUY-only or SELL-only proposed change cannot be certified by mere elapsed days: it needs **prospectively captured relevant actual WATCH events and enough subsequent market outcomes** to score the decision, or it must be transparently designated a *limited user-approved experiment* with an exposure cap. With only two completed previously studied cycles, future outperformance is still uncertain and may take a full cycle to assess.
- Report **ACTUALLY HELD BTC**, unspent AUD, marked BTC-equivalent **including** residual cash, realised taxes/fees, and *hypothetical* after-tax terminal AUD as five distinct metrics; include buy-and-hold and unchanged live-policy comparators. Stress a 2x/4x continued BTC bull and an additional 50%/70% delayed bear, but never assign those constructed futures probabilities.
- The user's aspirational roughly **20% bottom/top execution error** must be defined as an ex-post, BTC-quantity-weighted execution-price statistic after genuine cycle extremes are observed; it is NOT the same as return uplift, not a tolerance guaranteed for each trade, and cannot be confirmed for the unfinished 2025/26 cycle.

### C. Release authorization — never automatic

- New market signal logic or changed percentage is not promoted merely because a GitHub PR has 26/34/43 successful tests or a fitted history shows a large gain.
- Require an explicit **candidate-vs-control review** documenting gain, downside, risk of never getting another <200WMA BUY, personal portfolio implications and real ASX order practicality.
- First consider a **read-only shadow panel** (show comparative candidate action with warning), not an automated purchase or a second notification. Even shadow strategy display must never be mistaken for the single authoritative live recommendation.
- Only after the user chooses to implement a named, versioned proposal may Streamlit and single daily ntfy messages change in concert, with a rollback commit path and one definitive before/after example for AUD and ETF units.
- If data validation fails, use **HOLD / UNAVAILABLE** (no fabricated price or recommended quantity), keep the previous user-verified holdings untouched, and surface a diagnostic without multiplying ntfy traffic.

## Next work allowed under this freeze

1. Confirm the existing single daily BTC signal workflow persists valid rows and genuinely captures the FIRST completed Sydney ASX:IBIT market-session close (with no weekend row), then observe a series of independent new sessions. Investigate failure only if real source data are missing.
2. Review Production historic corrected backtest outputs and keep the retrospective method clearly labelled; a *true forward cash-funded Production backtest* is a separate task only if its parity gap affects an upcoming actual investment decision.
3. Implement **execution/readiness reporting** and, when enough new evidence exists, compare the predeclared frozen candidates **without tuning historical parameters again**.
4. Maintain exactly one existing daily ntfy and the previously established weekly readiness check. Do **not** create more alerts or recurring search jobs.

**Current release verdict:** **NO LIVE STRATEGY CHANGE YET.** Historical numerical correctness improved; independent prospective data and actual Australian ETF execution evidence remain insufficient. Continue observational validation, not open-ended historical parameter sweeps.
