# External metric CSV review — 2026-10-09

## Scope and safety

This is a structural/data-quality review of the CSVs recently added to `BTC_Composite/data/`. It is **not** a declaration that all indicators have been independently replicated or approved for the authoritative audit master. No Production logic, `btc_audit_backup.csv`, or Production manifest was changed.

The new files were added in the GitHub commit [a0c63a6](https://github.com/aussiekarl-gif/BTC_Composite/commit/a0c63a680b345dc5dd0f904c3a0bc68ca7f033bb). That commit records an upload, but does not identify the original chart/provider page for each CSV. Preserve source provenance per file rather than assuming it from the commit.

## Structural results

| File / metric | Coverage | Structural check | Review status |
|---|---|---|---|
| `nupl_net_unrealized_profit_loss__2026-10-06T08-54-39.csv` | 2010-11-01–2026-10-05; 5,818 daily rows | No missing dates, duplicate dates, or missing metric/price values | Validated in the prior BlockHorizon cross-check |
| `mvrv_z_score_2026-10-06T21-46-14.csv` | 2010-11-01–2026-10-05; 5,818 daily rows | No missing dates, duplicate dates, or missing metric/price values | Validated in the prior BlockHorizon cross-check |
| `sopr_spent_output_profit_ratio__2026-10-07T21-21-13.csv` | 2010-11-01–2026-10-06; 5,819 daily rows | No missing dates, duplicate dates, or missing values | Structurally clean; metric semantics and independent parity still pending |
| `supply_in_profit_2026-10-07T21-21-51.csv` | 2010-11-01–2026-10-06; 5,819 daily rows | No missing dates, duplicate dates, or missing values | Structurally clean; units/definition and independent parity still pending |
| `price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv` | 2013-01-01–2026-10-06; 5,027 daily rows | Dates are continuous and unique. 489 leading 200WMA blanks; price column present | Leading blanks are consistent with a rolling-window warm-up and must not be backfilled. Verify exact calculation against the benchmark daily close before promotion |
| `miner_revenue_total_daily__2026-10-07T21-26-46.csv` | 2009-01-09–2026-10-06; 6,480 daily rows | Dates are continuous and unique. Metric series is populated; 555 leading blanks in the accompanying price column | Structural pass; metric units and definition must be confirmed before calculating Puell Multiple |
| `planb_realized_prices_2026-10-07T21-19-48.csv` | 2011-12-31–2026-10-06; 5,394 daily rows | Dates are continuous and unique; no missing values in the exported columns | Structural pass; provider/source provenance and formula parity unresolved |

## Cross-file price consistency

Across the five files with overlapping populated price columns in the review, 5,026 shared timestamps had exactly matching prices. This is a useful internal consistency check, but it is not independent validation: the exports may share a common underlying price source.

The NUPL and MVRV Z exports are each dated through 2026-10-05, while several other exports run through 2026-10-06. Do not forward-fill or splice these series and label the result as a same-day snapshot without recording the as-of date per metric.

## Puell Multiple caution

The miner-revenue file is an underlying series, not a Puell Multiple series. Do not substitute its latest value for Puell. A reproducible Puell calculation requires confirming the revenue denomination (USD versus BTC), whether the data includes block subsidy and fees, the daily aggregation convention, and the exact long-term-average window. Until those are confirmed, retain Puell as a separately sourced/calculated metric.

## Stale manual snapshot

`data/manual_metrics.json` is dated 2026-08-30 and contains manually entered MVRV Z = 0.85, Puell Multiple = 0.78, and realised price = 58,200. These should be treated as a historical manual snapshot, not current values. Repository code search did not establish whether the file is consumed at runtime; therefore this review does not delete it or change application behaviour. If it remains in use, add an explicit as-of/stale label or migrate its values to a provenance-tracked input.

## Promotion gates

Before any of these new indicators enter `btc_audit_backup.csv` or a Production input:

1. Record provider name, exact source URL/page, export date, units, timezone/date convention, and methodology.
2. Validate each metric against an independent source or a reproducible calculation where inputs are available.
3. Document missing values as true gaps, unavailable history, or rolling warm-up; never silently fill them.
4. Merge into the wide master by normalized UTC date while preserving original provider fields and source metadata.
5. Keep Production frozen unless the separate parity/coverage/no-look-ahead review and explicit promotion process pass.

## Current decision

- **NUPL and MVRV Z:** retain the existing validated BlockHorizon status; no Production/master promotion.
- **SOPR, Supply in Profit, 200WMA, Miner Revenue, Realized Price:** structurally reviewed only; do not mark as independently validated yet.
- **Authoritative master and Production:** unchanged.

## Follow-up numerical sanity checks

A second pass computed basic ranges from the full CSV contents:

- **SOPR:** 0.6720–2.1324; latest exported value 1.0042 on 2026-10-06. The range is plausible for SOPR, but plausibility is not independent validation.
- **Supply in Profit:** 3.49 million–19.93 million units; latest 15.28 million on 2026-10-06. The scale is plausible for BTC supply, but the provider's exact supply definition remains to be recorded.
- **Realized-price export:** latest BTC price 85,553.52; Realized Price 53,761.98; 2-Year Realized Price 86,730.07; Realized Price (STS) 74,284.65 on 2026-10-06. These fields have different methodologies; do not treat the 2-Year or STS variants as interchangeable with the ordinary realized price.
- **200WMA:** latest exported value 66,525.51 on 2026-10-06. A diagnostic comparison against a simple rolling mean of the previous 1,400 daily price rows did **not** match exactly (latest simple daily mean 66,189.22). This is not automatically a defect: a true 200-week moving average is normally based on weekly observations/candles, not a simple 1,400-day mean. Validate against the provider's weekly calculation and benchmark candle convention instead of replacing the series with a daily rolling average.
- **Miner Revenue: Total (Daily):** latest exported value 490.0327, with observed range 200–34,600. The CSV itself does not encode a unit. These magnitudes are not enough to establish whether the field is BTC-denominated, fiat-denominated, scaled, or otherwise transformed. **Do not calculate Puell from this series until its units and definition are confirmed.**

These checks increase confidence that the data is parseable and broadly plausible, but they do not replace source documentation or an independent metric-level parity test.

