import datetime as dt
import inspect
import unittest

from engines.research.v60_200wma_paper_tape import (
    PAPER_START_AFTER_UTC, BTC_COLUMNS, ASX_COLUMNS, SIGNAL_COLUMNS,
    EXECUTION_COLUMNS, _append, _dump_rows, _read_rows, _next_asx_session,
    build_paper_signal, build_asx_observation, process_tapes,
)


def sample_btc_row(*, ratio=0.74, signal_date="2026-11-22",
                   observation_date="2026-11-23",
                   captured_at="2026-11-24T09:00:00+00:00"):
    return {
        "observation_date_utc": observation_date,
        "captured_at_utc": captured_at,
        "signal_input_last_prior_close_date_utc": signal_date,
        "btc_usd_observed_close": "74000.000000",
        "prior_btc_usd_close": f"{100000*ratio:.6f}",
        "prior_200wma_usd": "100000.000000",
        "prior_close_div_200wma": f"{ratio:.8f}",
        "fx_observed_prior_aud_per_usd": "1.50000000",
        "fx_prior_date_utc": "2026-11-20",
        "verified_halving_date": "2024-04-20",
        "days_after_halving": "947",
        "signal": "HOLD",
        "buy_pct_of_remaining_available_cash": "0.0000",
        "sell_pct_of_current_holdings": "0.0000",
        "trailing_90day_drawdown_prior_pct": "10.0000",
        "prior_50dma_declining": "False",
        "lagged_30d_annualised_volatility_pct": "40.0000",
        "market_data_provider": "independent completed BTC/USD source",
        "source_crosscheck_max_diff_pct": "0.0100",
        "model_name": "source_cycle_model_not_used_by_v60",
        "model_code_sha256": "a" * 64,
        "point_in_time_onchain_risk_status": "NOT_VERIFIED_NOT_INCLUDED",
        "trade_executable": "False",
        "prior_row_hash": "0" * 64,
        "row_hash": "b" * 64,
    }


class V60ProspectivePaperTapeTests(unittest.TestCase):
    def test_first_eligible_sunday_close_is_after_launch_cutoff(self):
        self.assertEqual(PAPER_START_AFTER_UTC.isoformat(), "2026-11-19T09:05:02+00:00")
        self.assertEqual(dt.date(2026, 11, 22).weekday(), 6)

    def test_threshold_sensitivity_records_both_percentages(self):
        row = build_paper_signal(sample_btc_row(ratio=0.74), model_sha256="c" * 64)
        self.assertEqual(row["baseline_buy_pct_available_cash"], "2.500000")
        self.assertEqual(row["measured_20_25_30_buy_pct_deployable_cash"], "5.000000")
        self.assertEqual(row["measured_20_25_30_scale_0_5_buy_pct_deployable_cash"], "2.500000")
        self.assertEqual(row["measured_20_25_30_scale_0_75_buy_pct_deployable_cash"], "3.750000")
        self.assertEqual(row["measured_10_15_20_buy_pct_deployable_cash"], "7.500000")
        self.assertEqual(row["protected_cash_floor_variants_pct_initial_cash"], "0.000000;30.000000;50.000000")
        self.assertEqual(row["cumulative_spend_cap_variants_pct_initial_cash"], "40.000000;50.000000;60.000000")

    def test_pre_cutoff_and_non_sunday_rows_are_rejected(self):
        old = sample_btc_row(captured_at="2026-11-19T09:00:00+00:00")
        with self.assertRaises(ValueError):
            build_paper_signal(old, model_sha256="c" * 64)
        weekday = sample_btc_row(signal_date="2026-11-23")
        with self.assertRaises(ValueError):
            build_paper_signal(weekday, model_sha256="c" * 64)

    def test_ratio_must_reconcile_to_frozen_close_and_wma(self):
        row = sample_btc_row(ratio=0.74)
        row["prior_close_div_200wma"] = "0.75000000"
        with self.assertRaises(ValueError):
            build_paper_signal(row, model_sha256="c" * 64)

    def test_asx_session_calendar_skips_full_closures_and_fails_unknown_year(self):
        self.assertEqual(_next_asx_session(dt.date(2026, 12, 24)), dt.date(2026, 12, 29))
        with self.assertRaises(ValueError):
            _next_asx_session(dt.date(2027, 12, 31))

    def test_asx_observation_requires_exact_expected_session_and_is_not_fill(self):
        signal = build_paper_signal(sample_btc_row(), model_sha256="c" * 64)
        signal_text, added = _append(
            _dump_rows([], SIGNAL_COLUMNS), signal, SIGNAL_COLUMNS, "btc_observation_date_utc"
        )
        self.assertTrue(added)
        signal = _read_rows(signal_text, SIGNAL_COLUMNS, date_key="btc_observation_date_utc")[0]
        self.assertEqual(signal["expected_next_asx_session_sydney"], "2026-11-25")
        asx = {
            "market_session_date_sydney": "2026-11-25",
            "captured_at_utc": "2026-11-25T08:30:00+00:00",
            "symbol": "ASX:IBIT", "currency": "AUD",
            "reported_close_aud": "20.500000",
            "daily_low_aud": "20.000000", "daily_high_aud": "21.000000",
            "daily_volume": "100000", "provider": "Yahoo_Finance_IBIT.AX_daily_candle_indicative",
            "single_provider_unverified_execution": "True",
            "is_confirmed_broker_fill": "False", "row_hash": "d" * 64,
        }
        result = build_asx_observation(signal, asx)
        self.assertEqual(result["is_confirmed_broker_fill"], "False")
        self.assertAlmostEqual(float(result["indicative_units_per_aud_1000"]), 1000/20.5)
        asx["market_session_date_sydney"] = "2026-11-26"
        with self.assertRaises(ValueError):
            build_asx_observation(signal, asx)

    def test_hash_chained_signal_tape_is_append_only(self):
        row = build_paper_signal(sample_btc_row(), model_sha256="c" * 64)
        empty = _dump_rows([], SIGNAL_COLUMNS)
        updated, added = _append(empty, row, SIGNAL_COLUMNS, "btc_observation_date_utc")
        self.assertTrue(added)
        unchanged, duplicate_added = _append(updated, row, SIGNAL_COLUMNS, "btc_observation_date_utc")
        self.assertFalse(duplicate_added)
        self.assertEqual(unchanged, updated)


    def test_v60_paper_tape_has_no_v59_or_legacy_dashboard_imports(self):
        import engines.research.v60_200wma_paper_tape as tape
        source = inspect.getsource(tape)
        self.assertNotIn("v59_", source)
        self.assertNotIn("cycle_forward_signal_tape", source)
        self.assertNotIn("cycle_trading_dashboard_model", source)

    def test_empty_tape_does_not_create_historical_signals(self):
        btc_text = _dump_rows([], BTC_COLUMNS)
        asx_text = _dump_rows([], ASX_COLUMNS)
        signal_text = _dump_rows([], SIGNAL_COLUMNS)
        execution_text = _dump_rows([], EXECUTION_COLUMNS)
        new_signal, new_execution, status = process_tapes(
            btc_text, asx_text, signal_text, execution_text,
            model_sha256="c" * 64,
        )
        self.assertEqual(new_signal, signal_text)
        self.assertEqual(new_execution, execution_text)
        self.assertEqual(status["signal_rows"], 0)
        self.assertEqual(status["signal_schema_version"], 2)
        self.assertEqual(status["allocation_scale_candidates"], [0.5, 0.75, 1.0])
        self.assertFalse(status["trade_executable"])


if __name__ == "__main__":
    unittest.main()
