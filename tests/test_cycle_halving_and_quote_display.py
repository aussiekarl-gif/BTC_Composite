"""Regression checks: auto quote, HOLD wording, halving projections."""
import datetime as dt
import unittest
from unittest.mock import Mock, patch

from engines.research.ibit_quote import (
    parse_ibit_quote, format_ibit_units_for_display,
)
from engines.research.cycle_halving_countdown import (
    estimate_halving_from_height, fetch_halving_countdown,
    build_halving_timeline, build_halving_progress_bar,
)

NOW = dt.datetime(2026, 10, 17, 0, 0, tzinfo=dt.timezone.utc)


class QuoteDisplayTests(unittest.TestCase):
    def test_hold_with_available_quote_never_says_quote_needed(self):
        self.assertEqual(
            format_ibit_units_for_display(
                {"action": "HOLD", "market_signal": "HOLD",
                 "estimated_ibit_units": None}, quote_available=True),
            "No trade",
        )

    def test_real_market_watch_missing_quote_is_explicit(self):
        self.assertEqual(
            format_ibit_units_for_display(
                {"action": "HOLD", "market_signal": "BUY WATCH",
                 "estimated_ibit_units": None}, quote_available=False),
            "Quote unavailable",
        )

    def test_valid_buy_or_sell_quantity(self):
        for action in ("BUY", "SELL"):
            self.assertEqual(
                format_ibit_units_for_display(
                    {"action": action, "market_signal": action,
                     "estimated_ibit_units": 1250}, quote_available=True),
                "1,250",
            )

    def test_yahoo_quote_with_missing_meta_price_uses_dated_asx_aud_close(self):
        stamp = int((NOW - dt.timedelta(hours=22)).timestamp())
        payload = {"chart": {"result": [{
            "meta": {"symbol": "IBIT.AX", "currency": "AUD"},
            "timestamp": [stamp],
            "indicators": {"quote": [{"close": [22.62]}]},
        }]}}
        quote = parse_ibit_quote(payload, now=NOW)
        self.assertEqual(quote["price_aud"], 22.62)
        self.assertTrue(quote["indicative_only"])
        payload["chart"]["result"][0]["meta"]["currency"] = "USD"
        self.assertIsNone(parse_ibit_quote(payload, now=NOW))

    def test_old_chart_close_must_not_be_used(self):
        stamp = int((NOW - dt.timedelta(days=9)).timestamp())
        payload = {"chart": {"result": [{
            "meta": {"symbol": "IBIT.AX", "currency": "AUD"},
            "timestamp": [stamp],
            "indicators": {"quote": [{"close": [22.62]}]},
        }]}}
        self.assertIsNone(parse_ibit_quote(payload, now=NOW))


class HalvingCountdownTests(unittest.TestCase):
    def test_height_around_october_2026(self):
        value = estimate_halving_from_height(971_634, now=NOW)
        self.assertEqual(value["next_halving_height"], 1_050_000)
        self.assertEqual(value["blocks_remaining"], 78_366)
        self.assertEqual(value["days_remaining"], 545)
        self.assertTrue(value["height_verified"])

    def test_boundary_moves_to_following_epoch(self):
        value = estimate_halving_from_height(1_050_000, now=NOW)
        self.assertEqual(value["next_halving_height"], 1_260_000)
        self.assertEqual(value["blocks_remaining"], 210_000)

    def test_reject_invalid_heights(self):
        for value in (-1, 839999, 900000.2, True, None):
            with self.assertRaises(ValueError):
                estimate_halving_from_height(value, now=NOW)

    @patch("engines.research.cycle_halving_countdown.requests.get")
    def test_live_block_height_is_used_and_cached_result_needs_no_manual_input(self, get):
        get.return_value = Mock(text="971634", status_code=200)
        result = fetch_halving_countdown(now=NOW)
        self.assertEqual(result["days_remaining"], 545)
        self.assertEqual(result["source"], "mempool.space")
        self.assertEqual(get.call_count, 1)

    @patch("engines.research.cycle_halving_countdown.requests.get")
    def test_second_provider_if_first_rejects(self, get):
        fail = Mock(text="not a height")
        good = Mock(text="971635")
        get.side_effect = [fail, good]
        result = fetch_halving_countdown(now=NOW)
        self.assertEqual(result["source"], "Blockchain.com")
        self.assertEqual(result["current_height"], 971635)

    @patch("engines.research.cycle_halving_countdown.requests.get")
    def test_offline_estimate_is_clearly_labelled(self, get):
        import requests
        get.side_effect = requests.RequestException("blocked")
        result = fetch_halving_countdown(now=NOW)
        self.assertFalse(result["height_verified"])
        self.assertIsNone(result["current_height"])
        self.assertIn("calendar approximation", result["estimate_basis"])

    def test_cycle_header_dates_and_bar_use_same_countdown(self):
        countdown = {
            "days_remaining": 544,
            "estimated_date_utc": "2028-04-13",
        }
        timeline = build_halving_timeline(
            last_halving_date="2024-04-20",
            today=dt.date(2026, 10, 17),
            countdown=countdown,
        )
        self.assertEqual(timeline["elapsed_days"], 910)
        self.assertEqual(timeline["remaining_days"], 544)
        self.assertEqual(timeline["total_projected_days"], 1454)
        self.assertAlmostEqual(timeline["progress_pct"], 100 * 910 / 1454)
        self.assertEqual(
            [item["day"] for item in timeline["milestones"]],
            [500, 560, 730],
        )
        figure = build_halving_progress_bar(timeline)
        self.assertEqual(len(figure.data), 2)
        self.assertEqual(figure.data[0].x[0], 910)
        self.assertEqual(figure.data[1].x[0], 544)
        # Three historic review milestones + today's orange marker.
        self.assertEqual(len(figure.layout.shapes), 4)
        self.assertEqual(figure.layout.shapes[-1].x0, 910)
        labels = [item.text for item in figure.layout.annotations]
        for label in ("D500", "D560", "D730", "TODAY"):
            self.assertIn(label, labels)

    def test_cycle_timeline_rejects_invalid_calendar_inputs(self):
        with self.assertRaises(ValueError):
            build_halving_timeline(
                last_halving_date="2024-04-20",
                today=dt.date(2023, 10, 17),
                countdown={"days_remaining": 500, "estimated_date_utc": "2028-04-20"},
            )
        with self.assertRaises(ValueError):
            build_halving_timeline(
                last_halving_date="2024-04-20",
                today=dt.date(2026, 10, 17),
                countdown={"days_remaining": -1, "estimated_date_utc": "2028-04-20"},
            )

    def test_cycle_milestones_do_not_extend_beyond_projected_next_halving(self):
        timeline = build_halving_timeline(
            last_halving_date="2024-04-20",
            today=dt.date(2024, 4, 21),
            countdown={"days_remaining": 100, "estimated_date_utc": "2024-07-30"},
        )
        self.assertEqual(timeline["elapsed_days"], 1)
        self.assertEqual(timeline["milestones"], [])

    def test_dashboard_shows_countdown_and_optional_manual_quote(self):
        from pathlib import Path
        app = (Path(__file__).resolve().parents[1] /
               "engines/research/cycle_trading_app.py").read_text()
        self.assertIn('st.metric("Days from last BTC halving"', app)
        self.assertIn('st.metric("Approx. days until next BTC halving"', app)
        self.assertIn('elapsed_col,chart_col,remaining_col=st.columns', app)
        self.assertIn('build_halving_progress_bar(halving_timeline)', app)
        self.assertIn('if manual_quote:', app)
        self.assertNotIn('else "Quote needed"', app)


if __name__ == "__main__":
    unittest.main()
