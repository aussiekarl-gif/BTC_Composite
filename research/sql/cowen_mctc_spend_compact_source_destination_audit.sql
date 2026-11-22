-- Compact follow-up for the two MinerCap cohort balance-drop dates.
-- Research only. Rebuilds the same retrospective Sep-Oct 2024 cohort.
-- Unlike the first spend-destination audit, this exports source and destination
-- breakdowns as compact JSON STRINGs grouped by address/script, avoiding very
-- large nested arrays that may be blank in CSV exports.
--
-- One final row per spending transaction. No inference of ownership or sale.

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
  o.value AS satoshis,
  t.is_coinbase
FROM month_transactions AS t
CROSS JOIN UNNEST(t.outputs) AS o
WHERE ARRAY_LENGTH(o.addresses) = 1
  AND o.addresses[SAFE_OFFSET(0)] IN (SELECT address FROM persistent_cohort)
  AND o.value > 0;

CREATE TEMP TABLE cohort_spend_inputs AS
SELECT
  DATE(spend_tx.block_timestamp) AS spent_date,
  spend_tx.block_timestamp AS spent_timestamp_utc,
  spend_tx.tx_hash AS spending_tx_hash,
  i.index AS spending_input_index,
  o.address AS source_address,
  o.satoshis AS cohort_input_satoshis,
  o.is_coinbase AS source_output_was_coinbase
FROM month_transactions AS spend_tx
CROSS JOIN UNNEST(spend_tx.inputs) AS i
JOIN cohort_outputs AS o
  ON o.tx_hash = i.spent_transaction_hash
 AND o.output_index = i.spent_output_index
WHERE DATE(spend_tx.block_timestamp) IN (DATE '2024-09-27', DATE '2024-10-30');

CREATE TEMP TABLE source_summary AS
SELECT
  spending_tx_hash,
  source_address,
  COUNT(*) AS cohort_input_outpoint_count,
  SUM(cohort_input_satoshis) AS cohort_input_satoshis,
  SUM(IF(source_output_was_coinbase, cohort_input_satoshis, 0)) AS coinbase_origin_satoshis,
  SUM(IF(NOT source_output_was_coinbase, cohort_input_satoshis, 0)) AS ordinary_origin_satoshis
FROM cohort_spend_inputs
GROUP BY spending_tx_hash, source_address;

CREATE TEMP TABLE transaction_summary AS
SELECT
  spending_tx_hash,
  MIN(spent_date) AS spent_date,
  MIN(spent_timestamp_utc) AS spent_timestamp_utc,
  COUNT(*) AS cohort_input_outpoint_count,
  COUNT(DISTINCT source_address) AS cohort_source_address_count,
  SUM(cohort_input_satoshis) AS cohort_input_satoshis
FROM cohort_spend_inputs
GROUP BY spending_tx_hash;

CREATE TEMP TABLE destination_summary AS
SELECT
  t.tx_hash AS spending_tx_hash,
  IF(ARRAY_LENGTH(o.addresses) = 1, o.addresses[SAFE_OFFSET(0)], NULL) AS destination_address,
  o.type AS output_script_type,
  ARRAY_LENGTH(o.addresses) AS address_count,
  COUNT(*) AS output_count,
  SUM(o.value) AS output_satoshis
FROM month_transactions AS t
JOIN transaction_summary AS s
  ON s.spending_tx_hash = t.tx_hash
CROSS JOIN UNNEST(t.outputs) AS o
GROUP BY
  t.tx_hash,
  destination_address,
  output_script_type,
  address_count;

CREATE TEMP TABLE output_totals AS
SELECT
  t.tx_hash AS spending_tx_hash,
  SUM(o.value) AS all_output_satoshis
FROM month_transactions AS t
JOIN transaction_summary AS s
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
  ROUND(o.all_output_satoshis / 100000000.0, 8) AS transaction_all_outputs_btc,
  TO_JSON_STRING(ARRAY(
    SELECT AS STRUCT
      x.source_address,
      x.cohort_input_outpoint_count,
      ROUND(x.cohort_input_satoshis / 100000000.0, 8) AS cohort_input_btc,
      ROUND(x.coinbase_origin_satoshis / 100000000.0, 8) AS coinbase_origin_btc,
      ROUND(x.ordinary_origin_satoshis / 100000000.0, 8) AS ordinary_origin_btc
    FROM source_summary AS x
    WHERE x.spending_tx_hash = s.spending_tx_hash
    ORDER BY x.cohort_input_satoshis DESC
  )) AS cohort_source_breakdown_json,
  TO_JSON_STRING(ARRAY(
    SELECT AS STRUCT
      x.destination_address,
      x.output_script_type,
      x.address_count,
      x.output_count,
      ROUND(x.output_satoshis / 100000000.0, 8) AS output_btc
    FROM destination_summary AS x
    WHERE x.spending_tx_hash = s.spending_tx_hash
    ORDER BY x.output_satoshis DESC
  )) AS destination_breakdown_json
FROM transaction_summary AS s
JOIN output_totals AS o USING (spending_tx_hash)
ORDER BY s.spent_date, s.spent_timestamp_utc, s.spending_tx_hash;
