"""Unified BTC control-room validation; synthetic observations are never trades."""
import datetime as dt
import unittest

from engines.research.btc_unified_research_readiness import build_control_room
from engines.research.cycle_forward_signal_tape import (
    SIGNAL_COLUMNS,append_snapshot,
)
from engines.research.ibit_asx_forward_close_tape import (
    COLUMNS as IBIT_COLUMNS,append_market_observation,
)
from engines.research.cycle_forward_signal_tape import _read_rows

UTC = dt.timezone.utc
NOW = dt.datetime(2026,10,20,12,0,tzinfo=UTC)

def seed_btc(*,dispersion="6.2900"):
    rows=""
    for date,recorded in (("2026-10-15","2026-10-18T07:49:45+00:00"),
                          ("2026-10-17","2026-10-18T08:35:29+00:00")):
        d={key:"test_fixture" for key in SIGNAL_COLUMNS
           if key not in ("prior_row_hash","row_hash")}
        d.update({"observation_date_utc":date, "captured_at_utc":recorded,
                  "signal":"HOLD","source_crosscheck_max_diff_pct":dispersion})
        rows,_=append_snapshot(rows,d)
    return rows

def seed_asx():
    from engines.research.ibit_asx_forward_close_tape import COLUMNS
    d={key:"test_fixture" for key in COLUMNS
       if key not in ("prior_row_hash","row_hash")}
    d.update({
        "market_session_date_sydney":"2026-10-20",
        "captured_at_utc":"2026-10-20T07:10:00+00:00",
        "provider_daily_candle_timestamp_utc":"2026-10-20T00:00:00+00:00",
        "symbol":"ASX:IBIT","currency":"AUD","is_confirmed_broker_fill":"False",
    })
    return append_market_observation("",d)[0]

def book(at="2026-10-19T07:17:00+00:00", bid="65.0", price="80000"):
    instant=dt.datetime.fromisoformat(at)
    slot=instant.replace(hour=instant.hour//6*6,minute=0,second=0,microsecond=0)
    return {
        "slot_utc":slot.isoformat(),"captured_at_utc":at,
        "complete_25bps_band":"True","bid_depth_share_pct_25bps":bid,
        "mid_usd":price,"row_hash":"k"+at,
    }

def trades(at="2026-10-19T07:19:00+00:00",buy="66.0"):
    instant=dt.datetime.fromisoformat(at)
    slot=instant.replace(hour=instant.hour//6*6,minute=0,second=0,microsecond=0)
    return {
        "slot_utc":slot.isoformat(),"captured_at_utc":at,
        "sample_only_not_continuous":"True",
        "sample_duration_seconds":"20.0","last_trade_age_seconds":"0.5",
        "observed_trades":"100","aggressor_buy_share_pct_sample":buy,
        "row_hash":"c"+at,
    }

class UnifiedResearchReadinessTests(unittest.TestCase):
    def audit(self,*,now=NOW,btc=None,asx=None,books=None,flows=None):
        return build_control_room(
            btc if btc is not None else seed_btc(),
            asx if asx is not None else "",
            "",
            books if books is not None else [book()],
            flows if flows is not None else [trades()],
            as_of_utc=now,
        )

    def test_all_five_models_present_without_winner(self):
        r=self.audit()
        self.assertEqual(len(r["model_scoreboard"]),5)
        self.assertFalse(r["model_leader_declared"])
        self.assertIsNone(r["comparative_return_winner"])
        self.assertFalse(r["comparison_is_economically_fair"])
        self.assertFalse(r["approved_for_live_investment_use"])
        self.assertEqual(r["recommended_trade_aud"],0)
        self.assertEqual(r["new_notifications"],0)
        self.assertEqual(r["portfolio_writes"],0)

    def test_historical_source_dispersion_flag_is_visible(self):
        r=self.audit()
        codes={x["code"] for x in r["review_flags"]}
        self.assertIn("BTC_SOURCE_MAX_DISPERSION_GE_5PCT",codes)
        self.assertEqual(
            r["source_health"]["cycle_forward"]["max_historical_BTC_source_crosscheck_dispersion_pct"],6.29)

    def test_threshold_under_five_not_falsely_flagged(self):
        r=self.audit(btc=seed_btc(dispersion="4.99"))
        self.assertNotIn("BTC_SOURCE_MAX_DISPERSION_GE_5PCT",
                         {x["code"] for x in r["review_flags"]})

    def test_below_threshold_does_not_make_model_investable(self):
        r=self.audit(btc=seed_btc(dispersion="0.00"),asx=seed_asx())
        self.assertFalse(r["approved_for_live_investment_use"])

    def test_a_real_matured_btc_mid_move_is_not_etf_profit(self):
        future=book(at="2026-10-19T13:25:00+00:00",price="81000")
        r=self.audit(books=[book(),future])
        micro=r["model_scoreboard"]["BTC Microstructure v1"]
        self.assertEqual(micro["strict_capture_time_paired_rows"],1)
        self.assertEqual(micro["active_6h_price_outcomes"],1)
        self.assertFalse(micro["after_cost_outperformance_verified"])
        self.assertFalse(r["approved_for_live_investment_use"])

    def test_six_minutes_apart_is_not_consensus(self):
        r=self.audit(flows=[trades(at="2026-10-19T07:23:01+00:00")])
        self.assertEqual(r["model_scoreboard"]["BTC Microstructure v1"]
                         ["strict_capture_time_paired_rows"],0)
        self.assertEqual(r["source_health"]["microstructure_exclusions"]
                         ["capture_skew_over_5min"],1)

    def test_no_micro_source_rows_does_not_fabricate_recommendation(self):
        r=self.audit(books=[],flows=[])
        self.assertEqual(r["source_health"]["kraken"]["count"],0)
        self.assertIn("KRAKEN_PUBLIC_FEED_NOT_RECENT",
                      {x["code"] for x in r["review_flags"]})
        self.assertIn("COINBASE_PUBLIC_FEED_NOT_RECENT",
                      {x["code"] for x in r["review_flags"]})
        self.assertFalse(r["model_leader_declared"])

    def test_monday_after_sydney_close_missing_ibit_reports_missing(self):
        r=self.audit()
        self.assertIn("ASX_IBIT_SAME_DAY_REFERENCE_CLOSE_UNAVAILABLE",
                      {x["code"] for x in r["review_flags"]})
        self.assertTrue(r["source_health"]["asx_close_expected_from_calendar_clock"])

    def test_archive_present_same_sydney_session_clears_missing_flag(self):
        r=self.audit(asx=seed_asx())
        self.assertNotIn("ASX_IBIT_SAME_DAY_REFERENCE_CLOSE_UNAVAILABLE",
                         {x["code"] for x in r["review_flags"]})

    def test_sunday_exempt_from_asx_missing_alert(self):
        now=dt.datetime(2026,10,18,11,0,tzinfo=UTC)
        r=self.audit(now=now,books=[],flows=[])
        self.assertFalse(r["source_health"]["asx_close_expected_from_calendar_clock"])
        self.assertNotIn("ASX_IBIT_SAME_DAY_REFERENCE_CLOSE_UNAVAILABLE",
                         {x["code"] for x in r["review_flags"]})

    def test_prior_morning_sydney_no_completed_close_expected(self):
        now=dt.datetime(2026,10,19,1,0,tzinfo=UTC)
        r=self.audit(now=now,books=[],flows=[])
        self.assertFalse(r["source_health"]["asx_close_expected_from_calendar_clock"])

    def test_naive_now_rejected(self):
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            self.audit(now=NOW.replace(tzinfo=None))

    def test_future_micro_observation_rejected(self):
        future=book(at="2026-10-21T07:17:00+00:00")
        with self.assertRaisesRegex(ValueError,"Future tape"):
            self.audit(books=[future])

    def test_source_tamper_refused_by_official_cycle_reader(self):
        damaged=seed_btc().replace("6.2900","0.0000")
        with self.assertRaises(ValueError):
            self.audit(btc=damaged)

    def test_absence_of_asx_data_is_not_a_broker_executable_quote(self):
        r=self.audit(asx="")
        self.assertEqual(r["source_health"]["cycle_forward"]["frozen_ASX_IBIT_Sydney_session_quotes"],0)
        self.assertFalse(r["source_health"]["cycle_forward"]["ASX_close_is_executable_broker_quote"])

    def test_no_sources_on_future_policy_data_still_not_alpha(self):
        r=self.audit(books=[book()],flows=[trades()])
        self.assertFalse(r["model_scoreboard"]["Production V5.8.2"]["after_cost_outperformance_verified"])
        self.assertFalse(r["model_scoreboard"]["Research V5.9"]["after_cost_outperformance_verified"])
        self.assertFalse(r["model_scoreboard"]["Buy-and-hold / fixed DCA benchmark"]
                         ["after_cost_comparable_performance_verified"])

if __name__ == "__main__":
    unittest.main()
