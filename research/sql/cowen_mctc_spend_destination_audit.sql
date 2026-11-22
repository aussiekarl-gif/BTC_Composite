-- Follow-up audit: trace cohort UTXOs spent on the two largest balance-drop dates.
-- Research only. This is not an exact MinerCap/mCTC reconstruction.
-- Uses the same retrospective Sep-Oct 2024 address cohort as the first audit.
-- Output: one row per spending transaction, with cohort inputs and destination outputs.
--
-- Run as one BigQuery script. Partition filter is limited to Sep and Oct 2024.

DECLARE start_month DATE DEFAULT DATE '2024-09-01';
DECLARE end_month DATE DEFAULT DATE '2024-10-01';
DECLARE window_start DATE DEFAULT DATE '2024-09-01';
DECLARE window_end DATE DEFAULT DATE '2024-10-31';

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

CREATE TEMP TABLE persistent_cohort AS
SELECT address
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

CREATE TEMP TABLE cohort_outputs AS
SELECT
  o.addresses[SAFE_OFFSET(0)] AS address,
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

-- Each matched input spends one previously received cohort outpoint.
CREATE TEMP TABLE cohort_spend_inputs AS
SELECT
  DATE(spend_tx.block_timestamp) AS spent_date,
  spend_tx.block_timestamp AS spent_timestamp_utc,
  spend_tx.tx_hash AS spending_tx_hash,
  i.index AS spending_input_index,
  o.address AS source_address,
  o.tx_hash AS source_tx_hash,
  o.output_index AS source_output_index,
  o.satoshis AS cohort_input_satoshis,
  o.is_coinbase AS source_output_was_coinbase
FROM month_transactions AS spend_tx
CROSS JOIN UNNEST(spend_tx.inputs) AS i
JOIN cohort_outputs AS o
  ON o.tx_hash = i.spent_transaction_hash
 AND o.output_index = i.spent_output_index
WHERE DATE(spend_tx.block_timestamp) IN (DATE '2024-09-27', DATE '2024-10-30');

CREATE TEMP TABLE cohort_spending_transactions AS
SELECT
  spending_tx_hash,
  MIN(spent_date) AS spent_date,
  MIN(spent_timestamp_utc) AS spent_timestamp_utc,
  COUNT(*) AS cohort_input_outpoint_count,
  COUNT(DISTINCT source_address) AS cohort_source_address_count,
  SUM(cohort_input_satoshis) AS cohort_input_satoshis,
  ARRAY_AGG(STRUCT(
    source_address,
    source_tx_hash,
    source_output_index,
    spending_input_index,
    cohort_input_satoshis / 100000000.0 AS cohort_input_btc,
    source_output_was_coinbase
  ) ORDER BY source_address, source_tx_hash, source_output_index) AS cohort_inputs
FROM cohort_spend_inputs
GROUP BY spending_tx_hash;

CREATE TEMP TABLE destination_outputs AS
SELECT
  t.tx_hash AS spending_tx_hash,
  SUM(o.value) AS all_output_satoshis,
  ARRAY_AGG(STRUCT(
    o.index AS output_index,
    IF(ARRAY_LENGTH(o.addresses) = 1, o.addresses[SAFE_OFFSET(0)], NULL) AS destination_address,
    o.type AS output_script_type,
    ARRAY_LENGTH(o.addresses) AS address_count,
    o.value / 100000000.0 AS output_btc
  ) ORDER BY o.index) AS destinations
FROM month_transactions AS t
JOIN cohort_spending_transactions AS s
  ON s.spending_tx_hash = t.tx_hash
CROSS JOIN UNNEST(t.outputs) AS o
GROUP BY t.tx_hash;

SELECT
  s.spent_date,
  s.spent_timestamp_utc,
  s.spending_tx_hash,
  s.cohort_input_outpoint_count,
  s.cohort_source_address_count,
  ROUND(s.cohort_input_satoshis / 100000000.0, 8) AS cohort_input_btc,
  ROUND(d.all_output_satoshis / 100000000.0, 8) AS spending_transaction_all_outputs_btc,
  ROUND((s.cohort_input_satoshis - d.all_output_satoshis) / 100000000.0, 8)
    AS cohort_input_minus_all_tx_outputs_btc_not_transaction_fee,
  s.cohort_inputs,
  d.destinations
FROM cohort_spending_transactions AS s
JOIN destination_outputs AS d USING (spending_tx_hash)
ORDER BY s.spent_date, s.spent_timestamp_utc, s.spending_tx_hash;
