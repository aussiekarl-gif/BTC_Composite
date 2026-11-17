import datetime as dt
import unittest

from engines.shared.broker_portfolio_snapshot import (
    snapshot_as_portfolio_positions,
    validate_broker_snapshot, merge_broker_snapshot,
)


def snapshot(**overrides):
    value = {
        "as_of": "2026-11-17",
        "starting_capital_aud": 510000.0,
        "aaa_units": 5329,
        "aaa_market_value_aud": 267355.93,
        "aaa_liquidatable": True,
        "ibit_units": 11250,
        "ibit_market_value_aud": 205087.50,
        "cash_aud": 8500.0,
    }
    value.update(overrides)
    return value


class BrokerPortfolioSnapshotTests(unittest.TestCase):
    def test_user_snapshot_separates_cash_aaa_reserve_and_ibit(self):
        result = validate_broker_snapshot(snapshot(), today=dt.date(2026, 11, 17))
        self.assertEqual(result["cash_aud"], 8500.0)
        self.assertEqual(result["aaa_reserve_aud"], 267355.93)
        self.assertEqual(result["deployable_reserve_aud"], 275855.93)
        self.assertEqual(result["ibit_units"], 11250.0)
        self.assertEqual(result["total_market_value_aud"], 480943.43)

    def test_aaa_not_deployable_without_explicit_liquidation_confirmation(self):
        result = validate_broker_snapshot(
            snapshot(aaa_liquidatable=False), today=dt.date(2026, 11, 17)
        )
        self.assertEqual(result["cash_aud"], 8500.0)
        self.assertEqual(result["aaa_reserve_aud"], 0.0)
        self.assertEqual(result["deployable_reserve_aud"], 8500.0)

    def test_dca_positions_adapter_uses_cash_plus_confirmed_aaa_reserve(self):
        result = snapshot_as_portfolio_positions(
            snapshot(), today=dt.date(2026, 11, 17)
        )
        self.assertEqual(result["starting_capital_aud"], 510000.0)
        self.assertEqual(result["cash_remaining_aud"], 275855.93)
        self.assertEqual(result["broker_cash_aud"], 8500.0)
        self.assertEqual(result["ibit_units"], 11250.0)
        self.assertIsNone(result["btc_equivalent_estimate"])

    def test_stale_future_dated_and_invalid_snapshots_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_broker_snapshot(snapshot(), today=dt.date(2026, 11, 25))
        with self.assertRaisesRegex(ValueError, "future-dated"):
            validate_broker_snapshot(snapshot(as_of="2026-11-18"), today=dt.date(2026, 11, 17))
        with self.assertRaisesRegex(ValueError, "non-negative"):
            validate_broker_snapshot(snapshot(cash_aud=-1), today=dt.date(2026, 11, 17))
        with self.assertRaisesRegex(ValueError, "explicitly confirmed"):
            validate_broker_snapshot(snapshot(aaa_liquidatable=None), today=dt.date(2026, 11, 17))

    def test_merge_snapshot_preserves_all_historical_transactions(self):
        existing = {
            "starting_capital_aud": 510000.0,
            "rows": [{"Date": "01/10/26", "Asset": "ASX:IBIT", "Units / BTC Received": 100}],
            "sales": [{"Date": "02/10/26", "Asset": "ASX:IBIT", "Units Sold": 2}],
            "custom_metadata": "preserve",
        }
        merged = merge_broker_snapshot(existing, snapshot())
        self.assertEqual(merged["rows"], existing["rows"])
        self.assertEqual(merged["sales"], existing["sales"])
        self.assertEqual(merged["custom_metadata"], "preserve")
        self.assertEqual(merged["broker_snapshot"], snapshot())

    def test_merge_snapshot_into_empty_durable_store_does_not_invent_trades(self):
        merged = merge_broker_snapshot({}, snapshot())
        self.assertEqual(merged["rows"], [])
        self.assertNotIn("sales", merged)
        self.assertEqual(merged["starting_capital_aud"], 510000.0)

    def test_zero_holdings_are_valid_only_when_units_and_value_both_zero(self):
        result = validate_broker_snapshot(
            snapshot(aaa_units=0, aaa_market_value_aud=0),
            today=dt.date(2026, 11, 17),
        )
        self.assertEqual(result["aaa_reserve_aud"], 0.0)
        with self.assertRaisesRegex(ValueError, "both be zero or both be positive"):
            validate_broker_snapshot(
                snapshot(aaa_units=0), today=dt.date(2026, 11, 17)
            )


if __name__ == "__main__":
    unittest.main()
