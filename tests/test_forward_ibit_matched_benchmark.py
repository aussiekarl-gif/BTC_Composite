"""Genuine forward row provenance and equal-AUD paper benchmark invariants."""
import datetime as dt
import unittest

from engines.research.cycle_forward_signal_tape import (
    SIGNAL_COLUMNS, append_snapshot,
)
from engines.research.ibit_asx_forward_close_tape import (
    COLUMNS as IBIT_COLUMNS, PROVIDER, append_market_observation,
)
from engines.research.forward_ibit_matched_benchmark import (
    grade, EPOCH, INITIAL_AUD,
)

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,15,12,tzinfo=UTC)


def signal(day="2026-10-18",captured="2026-10-19T03:00:00+00:00",
           kind="HOLD",diff="0.05",buy="0.0000",sell="0.0000"):
    from engines.research.cycle_forward_signal_tape import STRATEGY_LABEL
    r={k:"fixture" for k in SIGNAL_COLUMNS
       if k not in ("prior_row_hash","row_hash")}
    r.update({
        "observation_date_utc":day,"captured_at_utc":captured,
        "model_name":STRATEGY_LABEL,"trade_executable":"False",
        "point_in_time_onchain_risk_status":"NOT_VERIFIED_NOT_INCLUDED",
        "source_crosscheck_max_diff_pct":diff,"signal":kind,
        "buy_pct_of_remaining_available_cash":buy,
        "sell_pct_of_current_holdings":sell,
    })
    return r


def quote(day="2026-10-20",captured=None,close="20.0",low="19.0",
          high="21.0",provider=PROVIDER):
    # Summer Sydney is UTC+11; 18:05 Sydney converts to 07:05 UTC
    d=dt.date.fromisoformat(day)
    local=dt.datetime.combine(d,dt.time(18,5),
                              dt.timezone(dt.timedelta(hours=11)))
    cap=captured or local.astimezone(UTC).isoformat()
    stamp=(local-dt.timedelta(hours=7)).astimezone(UTC).isoformat()
    r={k:"fixture" for k in IBIT_COLUMNS
       if k not in ("prior_row_hash","row_hash")}
    r.update({
        "market_session_date_sydney":day,
        "captured_at_utc":cap,
        "provider_daily_candle_timestamp_utc":stamp,
        "symbol":"ASX:IBIT","currency":"AUD",
        "reported_close_aud":close,"daily_low_aud":low,
        "daily_high_aud":high,"daily_volume":"1000",
        "provider":provider,
        "single_provider_unverified_execution":"True",
        "is_confirmed_broker_fill":"False",
    })
    return r


def tape_signal(*rows):
    c=""
    for row in rows:
        c,wrote=append_snapshot(c,row)
        if not wrote:raise AssertionError("Unexpected duplicate fixture")
    return c


def tape_asx(*rows):
    c=""
    for row in rows:
        c,wrote=append_market_observation(c,row)
        if not wrote:raise AssertionError("Unexpected duplicate fixture")
    return c


class ForwardAUDPaperBenchmarkTests(unittest.TestCase):
    def test_zero_available_ibit_observations_never_invents_perf(self):
        r=grade(tape_signal(signal()),"",as_of_utc=NOW)
        self.assertEqual(r["verified_indicative_ASX_sessions"],0)
        self.assertIsNone(r["policies"]["initial_buy_and_hold"]
                          ["final_indicative_before_tax_mark_aud"])
        self.assertFalse(r["sufficient_for_preliminary_exploratory_review"])
        self.assertIsNone(r["comparative_live_strategy_winner"])
        self.assertFalse(r["after_cost_and_tax_outperformance_proven"])
        self.assertFalse(r["approved_for_model_change"])

    def test_matched_three_account_capital_and_buy_gate(self):
        c=tape_signal(signal(kind="BUY WATCH",buy="2.5000"))
        a=tape_asx(quote())
        r=grade(c,a,as_of_utc=NOW)
        accounts=r["policies"]
        self.assertEqual(r["verified_indicative_ASX_sessions"],1)
        self.assertEqual(accounts["Cycle_live_market_watch"]["IBIT_whole_units"],124)
        self.assertEqual(accounts["Cycle_live_market_watch"]["paper_orders_count"],1)
        self.assertEqual(accounts["initial_buy_and_hold"]["IBIT_whole_units"],4987)
        self.assertEqual(accounts["fixed_weekly_20wk_AUD_DCA"]["IBIT_whole_units"],249)
        self.assertTrue(all(x["initial_cash_aud"]==INITIAL_AUD for x in accounts.values()))
        self.assertEqual(r["matched_sessions"][0]["Cycle_shadow_action"],"PAPER_BUY")
        self.assertEqual(r["real_orders_placed"],0)
        self.assertEqual(r["portfolio_writes"],0)
        self.assertEqual(r["new_ntfy_messages"],0)

    def test_late_captured_signal_cannot_trade_in_earlier_asx_session(self):
        c=tape_signal(signal(day="2026-10-19",
                  captured="2026-10-20T03:00:00+00:00",
                  kind="BUY WATCH",buy="2.5000"))
        a=tape_asx(quote("2026-10-20"))
        r=grade(c,a,as_of_utc=NOW)
        self.assertEqual(r["policies"]["Cycle_live_market_watch"]["paper_orders_count"],0)
        self.assertEqual(r["matched_sessions"][0]["Cycle_shadow_action"],
                         "NO_FRESH_PREOPEN_SIGNAL")

    def test_non_prospective_october_15_late_capture_excluded(self):
        c=tape_signal(signal(day="2026-10-15",
                  captured="2026-10-18T07:49:45+00:00",
                  kind="BUY WATCH",buy="2.5000"))
        a=tape_asx(quote("2026-10-20"))
        r=grade(c,a,as_of_utc=NOW)
        self.assertEqual(r["cycle_excluded_signals"]
                         ["predates_paper_benchmark_enrolment"],1)
        self.assertEqual(r["policies"]["Cycle_live_market_watch"]["IBIT_whole_units"],0)

    def test_source_conflict_over_one_percent_excluded_not_rewritten(self):
        c=tape_signal(signal(kind="BUY WATCH",buy="2.5000",diff="6.29"))
        a=tape_asx(quote())
        r=grade(c,a,as_of_utc=NOW)
        self.assertEqual(r["cycle_excluded_signals"]["provider_crosscheck_over_one_pct"],1)
        self.assertEqual(r["policies"]["Cycle_live_market_watch"]["IBIT_whole_units"],0)

    def test_live_sell_of_remaining_units_with_weekly_cooldown(self):
        c=tape_signal(
            signal(kind="BUY WATCH",buy="2.5000"),
            signal(day="2026-10-26",captured="2026-10-27T03:00:00+00:00",
                   kind="SELL WATCH",sell="25.0000"))
        a=tape_asx(quote("2026-10-20"),quote("2026-10-21"),
                   quote("2026-10-28",close="25.0",low="24.5",high="25.5"))
        r=grade(c,a,as_of_utc=NOW)
        cyc=r["policies"]["Cycle_live_market_watch"]
        self.assertEqual(cyc["paper_orders_count"],2)
        self.assertEqual(cyc["paper_orders"][0]["side"],"BUY")
        self.assertEqual(cyc["paper_orders"][1]["side"],"SELL")
        self.assertEqual(cyc["paper_orders"][1]["whole_IBIT_units"],31)
        self.assertEqual(cyc["IBIT_whole_units"],93)
        self.assertEqual(cyc["fee_paid_aud"],6)
        self.assertEqual(r["matched_sessions"][1]["Cycle_shadow_action"],
                         "HOLD_7DAY_COOLDOWN")

    def test_stale_market_signal_never_creates_new_order(self):
        c=tape_signal(signal(kind="BUY WATCH",buy="2.5000"))
        a=tape_asx(quote("2026-10-28"))
        r=grade(c,a,as_of_utc=NOW)
        self.assertEqual(r["policies"]["Cycle_live_market_watch"]["paper_orders_count"],0)

    def test_no_change_in_prior_session_when_append_future_date(self):
        c=tape_signal(signal(kind="BUY WATCH",buy="2.5000"))
        first=tape_asx(quote("2026-10-20"))
        longer=tape_asx(quote("2026-10-20"),quote("2026-10-21",close="24",low="23",high="25"))
        a=grade(c,first,as_of_utc=NOW)
        b=grade(c,longer,as_of_utc=NOW)
        self.assertEqual(a["matched_sessions"][0],b["matched_sessions"][0])

    def test_tampered_kraken_or_ibit_earlier_row_rejected(self):
        c=tape_signal(signal())
        a=tape_asx(quote())
        damaged=a.replace("20.0","200.0")
        with self.assertRaisesRegex(ValueError,"Modified"):
            grade(c,damaged,as_of_utc=NOW)
        with self.assertRaisesRegex(ValueError,"Modified"):
            grade(c.replace("0.0500","6.2900"),a,as_of_utc=NOW)

    def test_wrong_market_or_fabricated_broker_fill_refused(self):
        c=tape_signal(signal())
        for revised in (quote(provider="Fake_Provider"),quote()):
            if revised["provider"]==PROVIDER:
                revised["is_confirmed_broker_fill"]="True"
            with self.assertRaisesRegex(ValueError,"Wrong ASX"):
                grade(c,tape_asx(revised),as_of_utc=NOW)

    def test_capture_before_asx_close_rejected(self):
        c=tape_signal(signal())
        a=tape_asx(quote(captured="2026-10-20T03:00:00+00:00"))
        with self.assertRaisesRegex(ValueError,"completed"):
            grade(c,a,as_of_utc=NOW)

    def test_source_future_observation_rejected(self):
        c=tape_signal(signal())
        a=tape_asx(quote())
        with self.assertRaisesRegex(ValueError,"Future ASX"):
            grade(c,a,as_of_utc=dt.datetime(2026,10,19,3,0,tzinfo=UTC))

    def test_no_weekend_asx_close(self):
        c=tape_signal(signal())
        a=tape_asx(quote("2026-10-24"))
        with self.assertRaisesRegex(ValueError,"Weekend"):
            grade(c,a,as_of_utc=NOW)

    def test_invalid_asx_quote_close_high_low_fails_closed(self):
        c=tape_signal(signal())
        a=tape_asx(quote(close="25",low="19",high="21"))
        with self.assertRaisesRegex(ValueError,"Inconsistent"):
            grade(c,a,as_of_utc=NOW)

    def test_no_tax_or_real_broker_execution_claim(self):
        r=grade(tape_signal(signal()),tape_asx(quote()),as_of_utc=NOW)
        self.assertTrue(r["smsf_tax_unverified_NOT_calculated"])
        self.assertTrue(r["ASX_close_proxy_NOT_available_as_guaranteed_preclose_execution"])
        self.assertTrue(r["market_source_single_provider_yahoo_not_broker_quote"])
        self.assertFalse(r["after_cost_and_tax_outperformance_proven"])

    def test_naive_asof_refused(self):
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            grade("","",as_of_utc=NOW.replace(tzinfo=None))


if __name__=="__main__":
    unittest.main()
