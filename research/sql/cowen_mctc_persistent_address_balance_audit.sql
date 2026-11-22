-- Cowen-style mCTC research: consolidated persistent reward-address balance audit
-- Source: bigquery-public-data.crypto_bitcoin.transactions
-- Scope: bounded two-month prototype (September-October 2024), not a full-history series.
-- Run as one BigQuery multi-statement script in BigQuery Studio.
--
-- Cohort rule: addresses receiving at least one positive, single-address coinbase
-- output in BOTH months. This is a retrospective diagnostic cohort, not a
-- point-in-time trading cohort. Address != miner/entity; pools and custodians
-- may aggregate or redistribute funds.
--
-- Balance rule: all single-address outputs received by cohort addresses during
-- the two-month window, including ordinary transactions, less outputs spent
-- by each UTC day-end. Pre-September UTXOs are intentionally excluded.
-- This script does not attribute change outputs to an originating miner and
-- must not be described as Cowen's exact mCTC.

DECLARE start_month DATE DEFAULT DATE '2024-09-01';
DECLARE end_month DATE DEFAULT DATE '2024-10-01';
DECLARE window_start DATE DEFAULT DATE '2024-09-01';
DECLARE window_end DATE DEFAULT DATE '2024-10-31';

-- Read the two partitioned months once, then reuse the bounded temporary table.
CREATE TEMP TABLE month_transactions AS
SELECT
  `hash` AS tx_hash,
  block_timestamp,
  is_coinbase,
  inputs,
  outputs
FROM `bigquery-public-data.crypto_bitcoin.transactions`
WHERE block_timestamp_month BETWEEN start_month AND end_month
  AND DATE(block_timestamp) BETWEEN window_start AND window_end;

-- Persistent reward addresses: at least one positive coinbase output in each month.
CREATE TEMP TABLE persistent_cohort AS
SELECT
  address
FROM (
  SELECT
    DATE_TRUNC(DATE(t.block_timestamp), MONTH) AS reward_month,
    o.addresses[SAFE_OFFSET(0)] AS address
  FROM month_transactions AS t
  CROSS JOIN UNNEST(t.outputs) AS o
  WHERE t.is_coinbase
    AND ARRAY_LENGTH(o.addresses) = 1
    AND o.value > 0
)
GROUP BY address
HAVING COUNT(DISTINCT reward_month) = 2;

-- Keep all single-address receipts to cohort addresses, not just coinbase rewards.
CREATE TEMP TABLE cohort_outputs AS
SELECT
  t.tx_hash,
  o.index AS output_index,
  DATE(t.block_timestamp) AS received_date,
  o.value AS satoshis,
  t.is_coinbase
FROM month_transactions AS t
CROSS JOIN UNNEST(t.outputs) AS o
WHERE ARRAY_LENGTH(o.addresses) = 1
  AND o.addresses[SAFE_OFFSET(0)] IN (SELECT address FROM persistent_cohort)
  AND o.value > 0;

-- Outpoints should be spent at most once. Retain the earliest observed spend
-- and separately count any duplicate spend references as a data-quality warning.
CREATE TEMP TABLE cohort_spends AS
SELECT
  i.spent_transaction_hash AS tx_hash,
  i.spent_output_index AS output_index,
  MIN(DATE(t.block_timestamp)) AS spent_date,
  COUNT(*) AS spend_reference_count
FROM month_transactions AS t
CROSS JOIN UNNEST(t.inputs) AS i
JOIN cohort_outputs AS o
  ON o.tx_hash = i.spent_transaction_hash
 AND o.output_index = i.spent_output_index
GROUP BY tx_hash, output_index;

WITH calendar AS (
  SELECT snapshot_date
  FROM UNNEST(GENERATE_DATE_ARRAY(window_start, window_end)) AS snapshot_date
),
outpoints AS (
  SELECT
    o.*,
    s.spent_date,
    COALESCE(s.spend_reference_count, 0) AS spend_reference_count
  FROM cohort_outputs AS o
  LEFT JOIN cohort_spends AS s
    USING (tx_hash, output_index)
),
daily AS (
  SELECT
    c.snapshot_date,
    COUNT(DISTINCT p.address) AS cohort_addresses,
    COUNT(DISTINCT IF(
      u.received_date <= c.snapshot_date
      AND (u.spent_date IS NULL OR u.spent_date > c.snapshot_date),
      p.address, NULL
    )) AS addresses_with_positive_balance,
    ROUND(SUM(IF(
      u.received_date <= c.snapshot_date
      AND (u.spent_date IS NULL OR u.spent_date > c.snapshot_date),
      u.satoshis, 0
    )) / 100000000, 8) AS partial_total_balance_btc,
    ROUND(SUM(IF(
      u.received_date <= c.snapshot_date
      AND (u.spent_date IS NULL OR u.spent_date > c.snapshot_date)
      AND u.is_coinbase,
      u.satoshis, 0
    )) / 100000000, 8) AS partial_coinbase_origin_balance_btc,
    ROUND(SUM(IF(
      u.received_date <= c.snapshot_date
      AND (u.spent_date IS NULL OR u.spent_date > c.snapshot_date)
      AND NOT u.is_coinbase,
      u.satoshis, 0
    )) / 100000000, 8) AS partial_ordinary_origin_balance_btc,
    ROUND(SUM(IF(
      u.received_date <= c.snapshot_date,
      u.satoshis, 0
    )) / 100000000, 8) AS cumulative_window_receipts_btc,
    COUNTIF(u.spend_reference_count > 1) AS duplicate_spend_reference_outpoints
  FROM calendar AS c
  CROSS JOIN persistent_cohort AS p
  LEFT JOIN outpoints AS u
    ON u.received_date <= c.snapshot_date
   AND u.tx_hash IS NOT NULL
   AND EXISTS (
     SELECT 1
     FROM cohort_outputs AS match_output
     WHERE match_output.tx_hash = u.tx_hash
       AND match_output.output_index = u.output_index
   )
  GROUP BY c.snapshot_date
),
cohort_stats AS (
  SELECT
    COUNT(*) AS persistent_address_count,
    ROUND(SUM(IF(t.is_coinbase AND DATE_TRUNC(DATE(t.block_timestamp), MONTH) = end_month,
      o.value, 0)) / 100000000, 8) AS october_coinbase_rewards_btc
  FROM month_transactions AS t
  CROSS JOIN UNNEST(t.outputs) AS o
  WHERE t.is_coinbase
    AND ARRAY_LENGTH(o.addresses) = 1
    AND o.addresses[SAFE_OFFSET(0)] IN (SELECT address FROM persistent_cohort)
)
SELECT
  d.snapshot_date,
  s.persistent_address_count,
  d.addresses_with_positive_balance,
  d.partial_total_balance_btc,
  d.partial_coinbase_origin_balance_btc,
  d.partial_ordinary_origin_balance_btc,
  d.cumulative_window_receipts_btc,
  d.duplicate_spend_reference_outpoints,
  s.october_coinbase_rewards_btc,
  'PARTIAL: excludes pre-2024-09-01 receipts; retrospective Sep-Oct cohort; address is not verified miner entity'
    AS interpretation
FROM daily AS d
CROSS JOIN cohort_stats AS s
ORDER BY d.snapshot_date;
