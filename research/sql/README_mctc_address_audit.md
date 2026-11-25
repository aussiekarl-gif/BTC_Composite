# Consolidated BigQuery miner-address balance prototype

This research package contains two bounded BigQuery scripts for the September–October 2024 diagnostic cohort.

## Script 1 — daily partial balance

File: `cowen_mctc_persistent_address_balance_audit.sql`

1. Reads the September and October 2024 partitions from the public Bitcoin transactions table.
2. Identifies addresses with positive, single-address coinbase outputs in both months.
3. Collects all single-address outputs to those addresses during the two-month window, including ordinary receipts.
4. Matches spent outpoints against inputs observed during the same window.
5. Produces one UTC daily row from 1 September through 31 October with the partial cohort balance and separate coinbase-origin / ordinary-origin balances.

The user executed this script successfully on 22 November 2026. It returned 61 daily rows for the 95-address retrospective cohort. At 31 October, cumulative in-window receipts were 28,182.77566003 BTC and the remaining partial balance was 1,851.47460192 BTC (1,601.72205710 coinbase-origin; 249.75254482 ordinary-origin). Duplicate spend-reference count was zero on all dates.

## Script 2 — spend destination trace

File: `cowen_mctc_spend_destination_audit.sql`

This follow-up script uses the same cohort rule and traces cohort outputs spent on 27 September and 30 October 2024. It returns one row per spending transaction, with:
- each matched cohort input outpoint, source address, value and source transaction;
- the total BTC contributed by cohort outpoints to that spending transaction;
- every output of the spending transaction, including decoded single-address destinations where available.

The script is designed to determine whether large balance reductions reflect wallet sweeps, payouts, transfers to other addresses, or mixed transactions. A transaction may contain inputs from outside the cohort; therefore its total outputs cannot be attributed solely to cohort funds. The field `cohort_input_minus_all_tx_outputs_btc_not_transaction_fee` is explicitly not a transaction-fee calculation. Destination address reuse is evidence of an on-chain flow, not proof of common ownership or a sale.

## How to run the follow-up

In BigQuery Studio, open a new SQL query, paste the complete contents of:

`research/sql/cowen_mctc_spend_destination_audit.sql`

Run it once as a multi-statement script. Export the final result grid as CSV and upload that single CSV to the BTC DCA research chat. Do not rerun the first daily-balance script.

## Interpretation limits

- Both scripts are bounded prototypes, not a final historical mCTC series.
- The cohort is selected retrospectively using both September and October; it is not a point-in-time cohort suitable for a historical trading replay.
- The daily balance script excludes all UTXOs received before 1 September 2024, so its balance is partial.
- A Bitcoin address is not necessarily a miner. Pool, custodian and payout addresses may aggregate many entities.
- Coinbase-origin and ordinary-origin balances classify the currently unspent output by the transaction that created it. If a coinbase output is spent and change returns, that change is classified as ordinary.
- Only outputs with exactly one decoded address are included to avoid assigning a multisig output's full value to multiple addresses.
- No result from these scripts is Cowen's exact mCTC, a validated miner-cap estimate, or a DCA signal.

The next engineering stage, after tracing the large outflows, is a cost-estimated historical UTXO reconstruction with point-in-time cohort formation, explicit script/address coverage, and tests against independent block/UTXO invariants. It must not be expanded to all history or promoted into Production without a separate validation gate.
