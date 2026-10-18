# BTC Cycle top timing: frozen FIRST-alert sell screen (18 October 2026)

## Status

**Research-only. DO NOT PROMOTE any extra top indicator sale to the live Cycle Trading, Production 5.8.2 or Research 5.9 defaults.**

GitHub Actions run: [39096568577](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39096568577) — **8 unit tests pass, full historical audit passes, original chronological wallet parity checks pass for every cycle.** Downloadable reproducible JSON and CSV artifact [top-first-alert-sell-evidence](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39096568577/artifacts/12125415068).

This report was generated from those actual CI log results, NOT hypothetical figures invented in the document.

## Frozen experiment before reading results

- Original baseline: begin with hypothetical A$500,000 at the dated 2016-07-09, 2020-05-11 or 2024-04-20 halvings; execute the **existing** original day500..730 staged selling fractions of ORIGINAL BTC; after day730+14, trigger weekly recovery BUY only on first strictly previous BTC daily close **below its strictly previous 200WMA**, then buy weekly using fixed ORIGINAL after-tax sale cash percentages.
- Experimental candidate: **one 20% of ORIGINAL BTC extra sale**, at the FIRST qualifying, strictly prior-observation indicator warning that arrives halving+350..730. The extra sale reduces BTC remaining and reduces later staged sales where the original inventory ceiling would be reached. No double counting or selling non-existent holdings; baseline staged review schedule and subsequent BUY timing rule unchanged.
- Seven already-declared top signals: `classic_euphoria` (lagged MVRV Z / NUPL), `pi_top_cross`, `relative_euphoria`, `trend_reversal`, `cycle_maturity_warning`, `maturity_confirmed_reversal`, `late_trend_break`. We did not fit a different sell fraction, first-alert eligibility window or threshold for each signal.
- Every test uses the SAME BTC price history, strictly previous-day signal observations, historical USD/AUD FX strictly before the order date, A$3 per hypothetical BTC execution, simplified immediate FIFO 10%/15% SMSF CGT withholding, exact historical BTC close as an optimistic fill proxy, and final hypothetical liquidation after CGT.
- Completed day1150 score cycles: 2017, 2021. Incomplete: 2025/26 marked **right-censored** at 2026-10-05.
- Every `original_no_extra_sell` result must reproduce the already existing independent chronological wallet's aftertax terminal AUD, BTC, cash, initial BTC, BUY and SELL counts. It did.
- **Not** a new buy-side optimization; the original 200WMA buy strategy is held fixed.

## Historical results: hypothetical terminal after-tax AUD percentage gain/loss vs ORIGINAL

| First-warning indicator family | 2017 | 2021 | 2025/26 incomplete | First 2017 alert | First 2021 alert | First 2025 alert |
|---|---:|---:|---:|---|---|---|
| Original staged, no extra SELL | 0.000% | 0.000% | 0.000% | — | — | — |
| Classic euphoria | **−5.414%** | 0.000% | 0.000% | 2017-12-02 | None | None |
| Pi Cycle Top cross | **+5.596%** | 0.000% | 0.000% | 2017-12-17 | None | None |
| Relative euphoria | **−17.251%** | 0.000% | 0.000% | 2017-06-24 | None | None |
| Trend reversal | **+1.574%** | **−6.176%** | −4.154% | 2018-01-31 | 2021-05-13 | 2025-04-10 |
| Cycle maturity warning | **−17.251%** | **−5.431%** | −3.708% | 2017-06-24 | 2021-04-26 | 2025-04-05 |
| Maturity confirmed reversal | 0.000% | 0.000% | −0.132% | None | None | 2025-11-21 |
| Late trend break | **+0.540%** | **−8.204%** | −0.132% | 2018-02-02 | 2021-05-18 | 2025-11-21 |

2017 baseline terminal illustrative aftertax A$25,695,084.89; Pi extra SELL A$27,133,047.74; relative euphoria A$21,262,371.95. 2021 baseline A$4,095,969.07; maturity warning extra SELL A$3,873,534.03; late trend break A$3,759,953.17. The incomplete 2025/26 baseline A$962,959.67 and should not be treated as a full-cycle terminal value.

2017 extra Pi Cycle Top first-warning result **+5.596%** is attractive *for one completed historical cycle only*. No additional Pi event qualified in 2021 or 2025/26. An indicator that does not fire is not proof it predicted those peaks or a robust positive out-of-sample winner. In contrast, selling a full fixed 20% on the first broad maturity warning was **harmful in BOTH completed cycles** (−17.251%, −5.431%) — evidence against immediate large first-warning sells under this policy.

The strategy's primary goal is **portfolio value after tax and BTC accumulated**. CSV evidence also contains terminal BTC-equivalent including cash, ending BTC units, cash AUD, realised tax escrow, BUY/SELL counts, and dates of first alert. A return relative to hypothetical 2016/2020 cycle BTC purchases must NOT be presented as user returns on actual 2026 IBIT purchases.

## Why this is NOT approval to trade with the winning indicator

1. **Only two complete cycles**, non-independent structural conditions, and very large price scaling since early BTC. A 1-of-2 signal is not a validated 50% hit rate or a reliable estimate of future profit.
2. **Data vintage / historical availability:** all named on-chain CSVs were exported in October 2026. Their historical numbers might be revised. Strict prior-day computations prevent future computational data leakage but NOT publication-time lookahead in revised history.
3. **Known thresholds and historical multiple comparison:** seven indicators were compared after historical cycle peaks were known to researchers. Picking the one best result now would be data snooping; none is verified genuinely out-of-sample.
4. **Hypothetical SMSF tax:** immediate FIFO escrow approximates an accumulation-phase account; actual FY-based SMSF tax, carried losses, pension exemptions and tax treatments differ. IBIT trading units, ASX sessions, tracking, spread and order slippage not modelled.
5. **Right censoring:** 2025/26 ends 2026-10-05, ahead of day1150. Comparisons there can reverse as prices move; do not extrapolate.
6. **First warning versus retrospective nearest peak:** the first eligible signal is traded. Ex-post peak-relative plot matching is explicitly NOT used to select the event.
7. **Weekly BUY unchanged:** no fresh 2026 BTC/IBIT positions are fabricated in past cycles; the result is historical counterfactual evidence only.

## Decision and next research

**Keep the original live and research rules unchanged.** These fixed-20%-sale overlays did not yield a consistent improvement. Prioritize: (1) ascertain point-in-time availability and completeness of MVRV/NUPL/SOPR and compare **price-only** signals to eliminate a key hindsight-vintage risk; (2) assess whether indicators are most useful as **caution / confirmation weighting** around existing staged day500 SELL dates, *without introducing extra early sells*; (3) test a truly chronological validation design in which policy parameters are frozen before held-out cycles — a very limited resource given BTC history; (4) after that, assess 200WMA entry latency, time spent in cash and alternative BUY allocation schedules on matching capital and aftertax basis.

Run code:
```bash
python -m unittest discover -s tests -p "test_sell_top_first_alert_horse_race.py" -v
python -m engines.research.sell_top_first_alert_horse_race --out artifacts/sell_top_first_alert
```

The audit writes complete per-cycle CSV, summary CSV and JSON alongside the GitHub Actions artifact. No Google Sheets read/write or broker account access, no live ntfy changes.
