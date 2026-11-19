import datetime as dt
import unittest

from engines.research.cycle_forward_signal_tape import (
    SIGNAL_COLUMNS, GENESIS, _signature, _dump_rows,
)
from engines.research.ibit_asx_forward_close_tape import COLUMNS as IBIT_COLUMNS
from engines.research.v59_200wma_prospective_paper_tape import (
    SIGNAL_COLUMNS_PAPER, EXECUTION_COLUMNS, PAPER_START_AFTER_UTC,
    build_paper_signal, build_asx_observation, process_tapes,
)

UTC = dt.timezone.utc


def btc_row(*, signal_date="2026-11-22", observation_date="2026-11-23",
            captured_at="2026-11-24T12:25:00+00:00", ratio=0.74):
    close = 70000.0
    wma = close / ratio
    row = {
        "observation_date_utc": observation_date,
        "captured_at_utc": captured_at,
        "signal_input_last_prior_close_date_utc": signal_date,
        "btc_usd_observed_close": "71000.000000",
        "prior_btc_usd_close": f"{close:.6f}",
        "prior_200wma_usd": f"{wma:.6f}",
        "prior_close_div_200wma": f"{ratio:.8f}",
        "fx_observed_prior_aud_per_usd": "1.50000000",
        "fx_prior_date_utc": "2026-11-22",
        "verified_halving_date": "2024-04-20",
        "days_after_halving": "947",
        "signal": "BUY WATCH",
        "buy_pct_of_remaining_available_cash": "2.5000",
        "sell_pct_of_current_holdings": "0.0000",
        "trailing_90day_drawdown_prior_pct": "25.0000",
        "prior_50dma_declining": "True",
        "lagged_30d_annualised_volatility_pct": "40.0000",
        "market_data_provider": "prospective_test_fixture",
        "source_crosscheck_max_diff_pct": "0.0500",
        "model_name": "fixture",
        "model_code_sha256": "a" * 64,
        "point_in_time_onchain_risk_status": "NOT_VERIFIED_NOT_INCLUDED",
        "trade_executable": "False",
        "prior_row_hash": GENESIS,
    }
    row["row_hash"] = _signature(row, SIGNAL_COLUMNS)
    return row


def asx_row(session="2026-11-25"):
    row = {
        "market_session_date_sydney": session,
        "captured_at_utc": "2026-11-25T07:30:00+00:00",
        "provider_daily_candle_timestamp_utc": "2026-11-25T05:00:00+00:00",
        "symbol": "ASX:IBIT",
        "currency": "AUD",
        "reported_close_aud": "20.500000",
        "daily_low_aud": "20.300000",
        "daily_high_aud": "20.700000",
        "daily_volume": "10000",
        "provider": "Yahoo_Finance_IBIT.AX_daily_candle_indicative",
        "single_provider_unverified_execution": "True",
        "is_confirmed_broker_fill": "False",
        "prior_row_hash": GENESIS,
    }
    row["row_hash"] = _signature(row, IBIT_COLUMNS)
    return row


class Prospective200WmaPaperTapeTests(unittest.TestCase):
    def test_sunday_close_uses_frozen_prior_close_and_measured_ladder(self):
        row = btc_row(ratio=0.74)
        signal = build_paper_signal(row, model_sha256="b" * 64)
        self.assertEqual(signal["signal_date_utc"], "2026-11-22")
        self.assertEqual(signal["btc_usd_sunday_close"], "70000.000000")
        self.assertAlmostEqual(float(signal["discount_below_200wma_pct"]), 26.0)
        self.assertEqual(signal["A_measured_buy_pct_deployable_cash"], "5.000000")
        self.assertEqual(signal["A_measured_protected_cash_floor_pct_initial_cash"], "0.000000")
        self.assertEqual(signal["A_measured_30pct_protected_cash_floor_pct_initial_cash"], "30.000000")
        self.assertEqual(signal["A_measured_30pct_floor_buy_pct_deployable_cash"], "5.000000")
        self.assertEqual(signal["expected_next_asx_weekday_sydney"], "2026-11-25")

    def test_tier_boundaries_are_monotonic(self):
        cases = [(0.81, 2.5), (0.80, 3.5), (0.75, 5.0), (0.70, 7.5)]
        for ratio, expected in cases:
            row = btc_row(ratio=ratio)
            signal = build_paper_signal(row, model_sha256="b" * 64)
            self.assertAlmostEqual(float(signal["A_measured_buy_pct_deployable_cash"]), expected)

    def test_prelaunch_and_non_sunday_inputs_are_rejected(self):
        old = btc_row(captured_at="2026-11-18T12:25:00+00:00")
        with self.assertRaisesRegex(ValueError, "Pre-launch"):
            build_paper_signal(old, model_sha256="b" * 64)
        non_sunday = btc_row(signal_date="2026-11-21")
        with self.assertRaisesRegex(ValueError, "Sunday"):
            build_paper_signal(non_sunday, model_sha256="b" * 64)

    def test_asx_quote_must_be_exact_expected_weekday_and_not_fill(self):
        signal = build_paper_signal(btc_row(), model_sha256="b" * 64)
        obs = build_asx_observation(signal, asx_row())
        self.assertEqual(obs["reported_close_aud"], "20.500000")
        self.assertEqual(obs["is_confirmed_broker_fill"], "False")
        wrong = asx_row(session="2026-11-26")
        with self.assertRaisesRegex(ValueError, "exact next expected"):
            build_asx_observation(signal, wrong)

    def test_missing_expected_session_never_shifts_to_later_quote(self):
        btc = _dump_rows([btc_row()], SIGNAL_COLUMNS)
        asx = _dump_rows([asx_row(session="2026-11-26")], IBIT_COLUMNS)
        signals, executions, status = process_tapes(
            btc, asx, "", "", model_sha256="b" * 64)
        self.assertEqual(status["signal_rows"], 1)
        self.assertEqual(status["asx_observation_rows"], 0)
        self.assertEqual(len(executions), 0)

    def test_exact_session_links_both_source_hashes_and_is_idempotent(self):
        btc = _dump_rows([btc_row()], SIGNAL_COLUMNS)
        asx = _dump_rows([asx_row()], IBIT_COLUMNS)
        signals, executions, status = process_tapes(
            btc, asx, "", "", model_sha256="b" * 64)
        self.assertEqual(status["signal_rows"], 1)
        self.assertEqual(status["asx_observation_rows"], 1)
        again_s, again_e, again_status = process_tapes(
            btc, asx, signals, executions, model_sha256="b" * 64)
        self.assertEqual(again_s, signals)
        self.assertEqual(again_e, executions)

    def test_bad_frozen_ratio_is_rejected(self):
        row = btc_row(ratio=0.74)
        row["prior_close_div_200wma"] = "0.80000000"
        row["row_hash"] = _signature(row, SIGNAL_COLUMNS)
        with self.assertRaisesRegex(ValueError, "does not reconcile"):
            build_paper_signal(row, model_sha256="b" * 64)


if __name__ == "__main__":
    unittest.main()
