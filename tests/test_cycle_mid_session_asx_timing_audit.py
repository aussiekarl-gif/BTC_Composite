"""Prospective same-session/next recorded AUD ETF close timing, never fills."""
import datetime as dt
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zoneinfo import ZoneInfo

import pandas as pd

from engines.research.cycle_forward_signal_tape import (
    GENESIS,_dump_rows,_signature,
)
from engines.research.cycle_mid_session_signal_tape import (
    COLUMNS as MID_COLUMNS,append as append_mid,build_observation,
)
from engines.research.forward_ibit_matched_benchmark import (
    FROZEN_CYCLE_MODEL_CODE_SHA256,
)
from engines.research.ibit_asx_forward_close_tape import (
    COLUMNS as ASX_COLUMNS, PROVIDER, append_market_observation,
)
from engines.research.cycle_mid_session_asx_timing_audit import report

UTC=dt.timezone.utc
SYD=ZoneInfo("Australia/Sydney")
NOW=dt.datetime(2026,11,15,12,tzinfo=UTC)


def mid(day=20,signal="HOLD",version=FROZEN_CYCLE_MODEL_CODE_SHA256,
        source_diff="0.0500"):
    local=dt.datetime(2026,10,day,12,30,tzinfo=SYD)
    stamp=local.astimezone(UTC)
    last=(stamp.date()-dt.timedelta(days=1))
    data={key:"fixture" for key in MID_COLUMNS
          if key not in ("prior_row_hash","row_hash")}
    data.update({
        "research_sydney_date":local.date().isoformat(),
        "captured_at_utc":stamp.isoformat(),
        "source_btc_close_utc_date":last.isoformat(),
        "btc_usd_verified_completed_close":"82000.000000",
        "prior_200wma_usd":"66700.000000",
        "prior_fx_aud_per_usd":"1.44000000",
        "fx_source_date_utc":(last-dt.timedelta(days=1)).isoformat(),
        "halving_date":"2024-04-20",
        "model_name":"shared_cycle_trade_allocation_market_v1_not_historical_wallet",
        "model_code_sha256":version,
        "buy_style":"adaptive_recovery",
        "market_signal":signal,
        "buy_pct_remaining_cash":"2.5000" if signal=="BUY WATCH" else "0.0000",
        "sell_pct_current_holdings":"5.0000" if signal=="SELL WATCH" else "0.0000",
        "kraken_blockchain_max_overlap_diff_pct":source_diff,
        "strict_close_date_verified":"True",
        "provider_archive_prices_preserved":"True",
        "asx_order_executable":"False",
        "independent_notification_delivery_verified":"False",
    })
    return data


def mids(*rows):
    with TemporaryDirectory() as folder:
        path=Path(folder)/"mid.csv"
        for data in rows:append_mid(path,data)
        return path.read_text() if path.exists() else ""


def close(day=20,px="20",captured=None):
    today=dt.date(2026,10,day)
    local=dt.datetime.combine(today,dt.time(18,10),SYD)
    instant=dt.datetime.fromisoformat(captured) if captured else local
    candle=dt.datetime.combine(today,dt.time(16,10),SYD)
    data={k:"test_fixture" for k in ASX_COLUMNS
          if k not in ("prior_row_hash","row_hash")}
    data.update({
        "market_session_date_sydney":today.isoformat(),
        "captured_at_utc":instant.astimezone(UTC).isoformat(),
        "provider_daily_candle_timestamp_utc":candle.astimezone(UTC).isoformat(),
        "symbol":"ASX:IBIT","currency":"AUD",
        "reported_close_aud":str(px),
        "daily_low_aud":str(float(px)-.5),
        "daily_high_aud":str(float(px)+.5),
        "daily_volume":"3123","provider":PROVIDER,
        "single_provider_unverified_execution":"True",
        "is_confirmed_broker_fill":"False",
    })
    return data


def closes(*entries):
    content=""
    for data in entries:
        content,saved=append_market_observation(content,data)
        if not saved:raise AssertionError("Duplicate fixture date")
    return content


class MidSessionTimingTests(unittest.TestCase):
    def test_no_rows_no_artificial_timing_edge(self):
        r=report("","",as_of_utc=NOW)
        self.assertEqual(r["paired_same_and_next_actual_ASX_closes"],0)
        self.assertIsNone(r["mean_directional_close_delay_pct_exploratory"])
        self.assertFalse(r["new_strategy_outperformance_or_better_execution_proven"])
        self.assertEqual(r["real_trades"],0)

    def test_buy_price_rise_means_next_close_worse_not_profit(self):
        r=report(mids(mid(signal="BUY WATCH")),
                 closes(close(20,"20"),close(21,"21")),as_of_utc=NOW)
        self.assertEqual(r["paired_non_hold_events"],1)
        self.assertAlmostEqual(r["mean_directional_close_delay_pct_exploratory"],5)
        self.assertEqual(r["observations"][0]["outcome_status"],
                         "OBSERVED_CLOSE_TO_CLOSE_NOT_EXECUTABLE")
        self.assertEqual(r["observations"][0]["next_real_recorded_session_date"],
                         "2026-10-21")
        self.assertFalse(r["closing_price_trade_fills_demonstrated"])
        self.assertFalse(r["ntfy_delivery_payload_or_time_confirmed"])

    def test_sell_price_fall_means_waiting_for_next_close_worse(self):
        r=report(mids(mid(signal="SELL WATCH")),
                 closes(close(20,"20"),close(21,"18")),as_of_utc=NOW)
        self.assertEqual(r["observations"][0]["same_vs_next_close_pct"],-10)
        self.assertEqual(r["observations"][0]
                         ["directional_cost_of_waiting_next_close_pct"],10)

    def test_hold_is_retained_but_never_sign_adjusted(self):
        r=report(mids(mid()),closes(close(20),close(21,"21")),as_of_utc=NOW)
        self.assertEqual(r["paired_same_and_next_actual_ASX_closes"],1)
        self.assertEqual(r["paired_non_hold_events"],0)
        self.assertIsNone(r["observations"][0]["directional_cost_of_waiting_next_close_pct"])

    def test_only_same_day_price_is_pending_not_future_result(self):
        r=report(mids(mid(signal="BUY WATCH")),closes(close(20)),as_of_utc=NOW)
        self.assertEqual(r["observations"][0]["outcome_status"],
                         "WAITING_NEXT_ASX_SESSION_CLOSE")
        self.assertIsNone(r["observations"][0]["same_vs_next_close_pct"])

    def test_missing_same_day_never_uses_later_as_entry(self):
        r=report(mids(mid(signal="BUY WATCH")),closes(close(21)),as_of_utc=NOW)
        self.assertEqual(r["observations"][0]["outcome_status"],
                         "MISSING_SAME_DAY_ASX_CLOSE")
        self.assertIsNone(r["observations"][0]["same_session_asx_indicative_close_aud"])

    def test_gap_longer_than_four_calendar_days_not_interpolated(self):
        r=report(mids(mid(signal="BUY WATCH")),closes(close(20),close(26)),as_of_utc=NOW)
        self.assertEqual(r["observations"][0]["outcome_status"],
                         "NEXT_SOURCE_DATE_TOO_FAR_OR_MISSING")
        self.assertEqual(r["paired_non_hold_events"],0)

    def test_missing_middle_weekday_not_passed_off_as_next_session(self):
        r=report(mids(mid(signal="BUY WATCH")),
                 closes(close(20),close(22,"21")),as_of_utc=NOW)
        self.assertEqual(r["observations"][0]["outcome_status"],
                         "NEXT_BUSINESS_DAY_NOT_CONFIRMED_NO_BACKFILL")
        self.assertEqual(r["paired_non_hold_events"],0)
        self.assertIsNone(r["mean_directional_close_delay_pct_exploratory"])

    def test_friday_to_monday_three_calendar_days_accepted(self):
        r=report(mids(mid(day=23,signal="BUY WATCH")),
                 closes(close(23),close(26,"21")),as_of_utc=NOW)
        self.assertEqual(r["observations"][0]["elapsed_calendar_days_to_next"],3)
        self.assertEqual(r["paired_non_hold_events"],1)

    def test_changed_model_sha_is_excluded(self):
        r=report(mids(mid(version="f"*64)),closes(close(20),close(21)),as_of_utc=NOW)
        self.assertEqual(r["excluded_research_rows"]
                         ["cycle_market_model_code_vintage_changed"],1)
        self.assertEqual(r["paired_same_and_next_actual_ASX_closes"],0)

    def test_conflicting_source_is_excluded(self):
        r=report(mids(mid(source_diff="6.2900")),closes(close(20),close(21)),as_of_utc=NOW)
        self.assertEqual(r["excluded_research_rows"]["source_disagreement_gt_1pct"],1)

    def test_hash_tampering_detected_by_source_reader(self):
        content=mids(mid(signal="BUY WATCH"))
        modified=content.replace("BUY WATCH","SELL WATCH")
        with self.assertRaisesRegex(ValueError,"Modified"):
            report(modified,closes(close(20),close(21)),as_of_utc=NOW)

    def test_future_source_not_scored(self):
        with self.assertRaisesRegex(ValueError,"Future mid-session"):
            report(mids(mid()),"",as_of_utc=dt.datetime(2026,10,20,0,0,tzinfo=UTC))

    def test_bad_asx_currency_refused_even_with_valid_hash(self):
        bad=close(20);bad["currency"]="USD"
        with self.assertRaisesRegex(ValueError,"not a completed indicative"):
            report(mids(mid()),closes(bad),as_of_utc=NOW)

    def test_bad_asx_close_low_high_refused(self):
        bad=close(20);bad["daily_low_aud"]="30"
        with self.assertRaisesRegex(ValueError,"Inconsistent"):
            report(mids(mid()),closes(bad),as_of_utc=NOW)

    def test_asx_row_captured_before_close_rejected(self):
        instant=dt.datetime(2026,10,20,15,0,tzinfo=SYD)
        with self.assertRaisesRegex(ValueError,"not a completed indicative"):
            report(mids(mid()),closes(close(20,captured=instant.isoformat())),as_of_utc=NOW)

    def test_naive_asof_invalid(self):
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            report("","",as_of_utc=NOW.replace(tzinfo=None))


if __name__=="__main__":
    unittest.main()
