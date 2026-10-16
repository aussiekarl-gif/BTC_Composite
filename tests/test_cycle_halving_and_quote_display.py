"""Regression checks: auto quote, HOLD wording, halving projections."""
import datetime as dt
import unittest
from unittest.mock import Mock, patch

from engines.research.ibit_quote import (
    parse_ibit_quote, format_ibit_units_for_display,
)
from engines.research.cycle_halving_countdown import (
    estimate_halving_from_height, fetch_halving_countdown,
    normalise_halving_epoch_metadata,
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

    def test_older_streamlit_cache_restores_known_2024_date(self):
        # This is the exact pre-upgrade payload shape left in Streamlit's
        # one-hour cache and previously caused an erroneous red warning.
        old_cached={
            "current_height":971_634,
            "next_halving_height":1_050_000,
            "height_verified":True,
            "days_remaining":545,
            "estimated_date_utc":"2028-04-14",
            "source":"mempool.space",
        }
        fixed=normalise_halving_epoch_metadata(old_cached)
        self.assertEqual(fixed["last_halving_date"],"2024-04-20")
        self.assertTrue(fixed["halving_date_verified"])
        self.assertEqual(fixed["last_halving_height"],840_000)
        self.assertNotIn("last_halving_date",old_cached)
        timeline=build_halving_timeline(
            last_halving_date=fixed["last_halving_date"],
            today=dt.date(2026,10,17),countdown=fixed,
        )
        self.assertEqual(timeline["elapsed_days"],910)
        self.assertEqual(timeline["remaining_days"],545)

    def test_no_fake_verified_future_epoch_from_old_cache(self):
        old_future={
            "current_height":1_050_020,
            "next_halving_height":1_260_000,
            "height_verified":True,
            "days_remaining":1_458,
        }
        fixed=normalise_halving_epoch_metadata(old_future)
        self.assertFalse(fixed["halving_date_verified"])
        self.assertIsNone(fixed.get("last_halving_date"))

    def test_provider_calendar_fallback_cannot_authorize_cycle_trades(self):
        old_offline={
            "current_height":None,"next_halving_height":None,
            "height_verified":False,"days_remaining":550,
        }
        fixed=normalise_halving_epoch_metadata(old_offline)
        self.assertFalse(fixed["halving_date_verified"])

    def test_verified_new_halving_date_is_preserved(self):
        now=dt.datetime(2028,4,26,tzinfo=dt.timezone.utc)
        quote=estimate_halving_from_height(1_050_020,now=now)
        quote.update(last_halving_date="2028-04-25",
                     halving_date_verified=True)
        fixed=normalise_halving_epoch_metadata(quote)
        self.assertEqual(fixed["last_halving_date"],"2028-04-25")
        self.assertTrue(fixed["halving_date_verified"])

    def test_future_halving_block_does_not_guess_event_date(self):
        # Crossing the epoch is different from independently verifying
        # the calendar date when block 1,050,000 was actually mined.
        future=estimate_halving_from_height(1_050_001, now=NOW)
        self.assertEqual(future["next_halving_height"], 1_260_000)
        self.assertEqual(future["last_halving_height"], 1_050_000)
        self.assertIsNone(future["last_halving_date"])
        self.assertFalse(future["halving_date_verified"])

    @patch("engines.research.cycle_halving_countdown.requests.get")
    def test_future_epoch_resolves_real_halving_block_time(self, get):
        # Run the scenario in 2028, not in the present 2026.
        future_now=dt.datetime(2028, 4, 26, tzinfo=dt.timezone.utc)
        block_hash="ab"*32
        height = Mock(text="1050020")
        hash_response = Mock(text=block_hash)
        block_response = Mock()
        block_response.json.return_value={
            "height": 1_050_000,
            "timestamp": int(dt.datetime(2028, 4, 25, 12,
                                          tzinfo=dt.timezone.utc).timestamp()),
        }
        get.side_effect=[height, hash_response, block_response]
        value=fetch_halving_countdown(now=future_now)
        self.assertTrue(value["halving_date_verified"])
        self.assertEqual(value["last_halving_date"],"2028-04-25")
        self.assertEqual(value["next_halving_height"],1_260_000)

    @patch("engines.research.cycle_halving_countdown.requests.get")
    def test_future_epoch_date_uses_alternate_block_provider(self, get):
        future_now=dt.datetime(2028, 4, 26, tzinfo=dt.timezone.utc)
        alternate=Mock()
        alternate.json.return_value={"blocks":[{
            "height":1_050_000,"main_chain":True,
            "time":int(dt.datetime(2028, 4, 24,
                                   tzinfo=dt.timezone.utc).timestamp()),
        }]}
        get.side_effect=[
            Mock(text="1050020"),Mock(text="bad hash"),alternate,
        ]
        result=fetch_halving_countdown(now=future_now)
        self.assertTrue(result["halving_date_verified"])
        self.assertEqual(result["last_halving_date"],"2028-04-24")
        self.assertEqual(get.call_count,3)

    @patch("engines.research.cycle_halving_countdown.requests.get")
    def test_future_epoch_missing_block_event_fails_closed(self, get):
        future_now=dt.datetime(2028, 4, 26, tzinfo=dt.timezone.utc)
        height=Mock(text="1050020")
        bogus_hash=Mock(text="not a block hash")
        alternate=Mock()
        alternate.json.return_value={"blocks":[]}
        get.side_effect=[height,bogus_hash,alternate]
        value=fetch_halving_countdown(now=future_now)
        self.assertFalse(value["halving_date_verified"])
        self.assertIsNone(value["last_halving_date"])
        self.assertIn("No cycle-timed trade",value["cycle_safety_note"])

    def test_future_market_recalculates_age_and_review_dates(self):
        import pandas as pd
        from engines.research.cycle_trading_dashboard_model import build_dashboard_market
        idx=pd.date_range("2022-01-01","2028-04-28",freq="D",tz="UTC")
        price=pd.Series(100_000.,index=idx)
        fx=pd.DataFrame({"aud_per_usd":[1.5]},index=[idx[-2]])
        future=build_dashboard_market(price,fx,
            asof="2028-04-28", confirmed_halving_date="2028-04-25")
        self.assertEqual(future["halving_day"],3)
        self.assertEqual(future["halving_date"],"2028-04-25")
        self.assertEqual(future["day500_date"],"2029-09-07")
        with self.assertRaises(ValueError):
            build_dashboard_market(price,fx,
                asof="2028-04-28", confirmed_halving_date="2028-05-01")

    def test_dashboard_refreshes_session_without_autotrading(self):
        from pathlib import Path
        app=(Path(__file__).resolve().parents[1] /
             "engines/research/cycle_trading_app.py").read_text()
        self.assertIn('st.fragment(run_every="1m")',app)
        self.assertIn('normalise_halving_epoch_metadata(cached_halving_countdown_v2())',app)
        self.assertIn('cached_halving_countdown_v2.clear()',app)
        self.assertIn('cycle_refresh_heartbeat()',app)
        self.assertIn('st.rerun()',app)
        self.assertIn('and staleness<=3 and cycle_feed_verified',app)
        self.assertIn('start=market["halving_date"]',app)
        self.assertNotIn('cycle_fx_source("2024-04-20"',app)

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
