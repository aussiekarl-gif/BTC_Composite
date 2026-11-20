# Puell archive reconciliation — source calendar mismatch (9 November 2026)

**RESEARCH / AUDIT ONLY. NOT TRADING VALIDATED. PR #69 REMAINS BLOCKED.**

## Comparison sources

Read-only analysis of the PRIVATE btc-audit-data main-branch
btc_audit_backup.csv as retrieved 2026-11-09:

- Coin Metrics cm__IssTotNtv and cm__PriceUSD have approximately 5,957–5,958
  observations back to 2010; reconstruct 365-calendar-day
  sum(issuance_native × price_USD) Puell.
- Protected master column Puell Multiple has 5,592 derived observations
  from 2011-07-18 to 2026-11-07. It reproduces the same underlying
  Coin Metrics calculation and **is not independent validation**.
- Separately archived raw__puell_multiple__puellmultiple contains
  1,461 observations 2022-09-10 to 2026-09-09, apparently from an
  external historical export, but its original timestamp convention,
  release/publication time, revision policy and exact metric definition
  remain to be independently established.
- NEVER copy this private master into the public BTC_Composite repository.

## Numerical same-date and shifted diagnostic

Coin Metrics direct reconstruction versus separately archived raw values,
using complete 365-calendar-day issuance/price windows, 1,461 overlaps:

| Comparison | Pearson correlation | Mean absolute Puell error |
|---|---:|---:|
| Same raw and calculated date | 0.9356 | 0.07675 |
| Raw date D versus calculated D+1 | 0.9826 | 0.02736 |

A global one-day shift would be **incorrect**. There are strong
changes in the correspondence convention:

- On **837 consecutive dates from 2022-09-10 through 2024-12-24**,
  the raw observation matches the following day's calculated metric
  within 0.004 (rather than the same-day value).
- From **2024-12-25**, the raw series generally corresponds instead
  to the **same** calculated date for several months.
- Beginning **2025-05-15**, a further long run of next-day
  correspondence appears, while 2026 becomes a mix of close
  same-date and unresolved differences. Neither same-day nor next-day
  alignment is reliably universal over the full raw archive.
- This is a source-calendar/definition discrepancy, **not proof of
  which provider is wrong**. All observation-date labels, time zones,
  vintage dates and data-merging transformations need source-level
  verification. The raw series may also share upstream methodology
  with the self-calculated metric, so its independence is incomplete.

### Concrete halving-date example

| UTC date label | Calculated Puell | Archived raw Puell |
|---|---:|---:|
| 2024-04-19 | 1.67849 | 0.745 |
| 2024-04-20 | 0.74529 | 0.803 |

The *raw observation labelled 2024-04-19* closely matches the
*calculated value for 2024-04-20*, immediately around the halving.
Interpreting the former as already available on April 19 could
introduce a one-day look-ahead signal.

There are also 60 of 1,461 same-date threshold disagreements for
Puell below 1.0, and 98 for Puell below 0.75. A valuation-trigger
study based on the unverified raw dates is therefore unreliable.

## Correct release action

1. Keep original raw dates and values unmodified; do not silently
   interpolate, shift, overwrite or fill missing dates.
2. Confirm exact provider sources and time conventions for each
   archived acquisition segment: timestamp UTC, date-of-observation
   vs date-of-publication, earliest trade-availability timestamp,
   methodological definition and whether fees are included.
3. Obtain provider-original point-in-time snapshots or historical
   vintage records, especially around 2024-04-19/20 and 2025
   alignment transitions. Avoid backtest decisions using values
   published only after the simulated trade.
4. Independently validate metric definition and threshold stability,
   then test Puell's incremental strategy value against the frozen
   baseline with a dated, after-cost matched protocol. This cannot
   be inferred from high correlation with the same underlying data.
5. Keep Production V5.8.2, Cycle Trading, public master CSV,
   Streamlit and ntfy unchanged.

New read-only reproducible diagnostic:
engines/audit/puell_archive_date_alignment_audit.py
takes --csv pointing to the PRIVATE local archive. Unit tests use
synthetic data in the existing Puell calendar research CI workflow.

**Decision: PR #69 remains draft, and ready_for_production =
ready_for_trading = false. Successful deterministic unit tests alone
must never count as provider timestamp validation.**
