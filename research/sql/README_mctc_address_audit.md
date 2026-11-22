# Consolidated BigQuery miner-address balance prototype

This SQL script replaces the repeated September/October exploratory queries with one bounded multi-statement BigQuery run.

## What it does

1. Reads the September and October 2024 partitions from the public Bitcoin transactions table once into a temporary table.
2. Identifies addresses with positive, single-address coinbase outputs in both months.
3. Collects all single-address outputs to those addresses during the two-month window, including ordinary receipts.
4. Matches spent outpoints against inputs observed during the same window.
5. Produces one UTC daily row from 1 September through 31 October with the partial cohort balance and separate coinbase-origin / ordinary-origin balances.

## How to run

Open BigQuery Studio, create a new SQL query, paste the complete contents of:

`research/sql/cowen_mctc_persistent_address_balance_audit.sql`

Then run it once as a multi-statement script. Export the final result grid as CSV and upload that CSV to the BTC DCA research chat. Do not paste all rows into chat.

## Interpretation limits

- This is a bounded prototype, not the final historical mCTC series.
- The cohort is selected retrospectively using both September and October; it is not a point-in-time cohort suitable for a historical trading replay.
- It excludes all UTXOs received before 1 September 2024, so its balance is partial.
- A Bitcoin address is not necessarily a miner. Pool, custodian and payout addresses may aggregate many entities.
- Coinbase-origin and ordinary-origin balances classify the currently unspent output by the transaction that created it. If a coinbase output is spent and change returns, that change is classified as ordinary.
- Only outputs with exactly one decoded address are included to avoid assigning a multisig output's full value to multiple addresses.
- No result from this script is Cowen's exact mCTC, a validated miner-cap estimate, or a DCA signal.

The next engineering stage, after this bounded query runs successfully, is a cost-estimated historical UTXO reconstruction with point-in-time cohort formation, explicit script/address coverage, and tests against independent block/UTXO invariants. It must not be expanded to all history or promoted into Production without a separate validation gate.
