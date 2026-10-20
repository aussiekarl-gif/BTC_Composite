"""First genuine forward ASX session acceptance is paper-only and causal."""
import datetime as dt
import unittest

from engines.research.cycle_forward_signal_tape import (
    SIGNAL_COLUMNS, STRATEGY_LABEL, append_snapshot,
)
from engines.research.ibit_asx_forward_close_tape import (
    COLUMNS as ASX_COLUMNS, PROVIDER, append_market_observation,
)
from engines.research.forward_ibit_matched_benchmark import (
    FROZEN_CYCLE_MODEL_CODE_SHA256,
)
from engines.research.forward_ibit_first_session_acceptance import first_actual_session

UTC=dt.timezone.utc
NOW=dt.datetime(2026,10,25,12,tzinfo=UTC)


def bitcoin(*,day="2026-10-18",captured="2026-10-19T03:14:01+00:00",
            action="HOLD",buy="0.0000",sell="0.0000",disagreement="0.05"):
    r={k:"synthetic_fixture" for k in SIGNAL_COLUMNS
       if k not in ("prior_row_hash","row_hash")}
    r.update({
        "observation_date_utc":day,
        "captured_at_utc":captured,
        "model_name":STRATEGY_LABEL,
        "model_code_sha256":FROZEN_CYCLE_MODEL_CODE_SHA256,
        "trade_executable":"False",
        "point_in_time_onchain_risk_status":"NOT_VERIFIED_NOT_INCLUDED",
        "source_crosscheck_max_diff_pct":disagreement,
        "signal":action,
        "buy_pct_of_remaining_available_cash":buy,
        "sell_pct_of_current_holdings":sell,
    })
    return r


def etf(*,day="2026-10-20",close="22.299999",
        captured="2026-10-20T06:57:04+00:00"):
    r={k:"synthetic_fixture" for k in ASX_COLUMNS
       if k not in ("prior_row_hash","row_hash")}
    r.update({
        "market_session_date_sydney":day,
        "captured_at_utc":captured,
        "provider_daily_candle_timestamp_utc":"2026-10-20T04:23:32+00:00",
        "symbol":"ASX:IBIT","currency":"AUD",
        "reported_close_aud":close,
        "daily_low_aud":"22.110001" if day=="2026-10-20" else "21.0000",
        "daily_high_aud":"22.469999" if day=="2026-10-20" else "24.0000",
        "daily_volume":"5252","provider":PROVIDER,
        "single_provider_unverified_execution":"True",
        "is_confirmed_broker_fill":"False",
    })
    return r


def cycle_tape(*events):
    t=""
    for row in events:
        t,ok=append_snapshot(t,row)
        if not ok:raise AssertionError("Unexpected duplicate fixture")
    return t


def asx_tape(*events):
    t=""
    for row in events:
        t,ok=append_market_observation(t,row)
        if not ok:raise AssertionError("Unexpected duplicate source")
    return t


class GenuineFirstSessionAcceptanceTests(unittest.TestCase):
    def test_no_ibt_quote_ever_means_no_cash_allocation_claim(self):
        r=first_actual_session(cycle_tape(bitcoin()),"",as_of_utc=NOW)
        self.assertFalse(r["eligible_first_session_found"])
        self.assertIsNone(r["three_way_performance_winner"])
        self.assertEqual(r["ntfy_sent"],0)

    def test_oct20_realistic_HOLD_proves_100k_reconciled_three_policies(self):
        r=first_actual_session(
            cycle_tape(bitcoin()),
            asx_tape(etf()),as_of_utc=NOW)
        self.assertTrue(r["eligible_first_session_found"])
        self.assertEqual(r["first_session_sydney"],"2026-10-20")
        self.assertEqual(r["Cycle_source_observed_completed_close_utc"],"2026-10-18")
        self.assertEqual(r["Cycle_source_market_watch_if_valid"],"HOLD")
        self.assertEqual(r["first_Cycle_action"],"HOLD")
        a=r["policies"]
        self.assertEqual(a["Cycle_live_market_watch"]["research_only_whole_ASX_IBIT_units"],0)
        self.assertEqual(a["Cycle_live_market_watch"]["paper_AUD_cash_remaining"],100000.)
        self.assertEqual(a["fixed_weekly_20wk_AUD_DCA"]["research_only_whole_ASX_IBIT_units"],223)
        self.assertEqual(a["fixed_weekly_20wk_AUD_DCA"]["paper_AUD_cash_remaining"],95011.67)
        self.assertEqual(a["fixed_weekly_20wk_AUD_DCA"]["single_provider_indicative_mark_at_close_AUD"],99984.57)
        self.assertEqual(a["initial_buy_and_hold"]["research_only_whole_ASX_IBIT_units"],4472)
        self.assertEqual(a["initial_buy_and_hold"]["paper_AUD_cash_remaining"],22.09)
        self.assertEqual(a["initial_buy_and_hold"]["single_provider_indicative_mark_at_close_AUD"],99747.69)
        self.assertFalse(r["first_session_can_prove_strategy_winner"])
        self.assertIsNone(r["three_way_performance_winner"])
        self.assertFalse(r["cash_account_comparison_not_yet_aftertax_or_risk_adjusted"] is False)
        self.assertEqual(r["real_orders"],0)

    def test_later_after_open_BUY_must_not_rewrite_first_preopen_HOLD(self):
        old=bitcoin()
        new=bitcoin(day="2026-10-19",captured="2026-10-20T06:57:02+00:00",
                    action="BUY WATCH",buy="2.5000")
        r=first_actual_session(cycle_tape(old,new),asx_tape(etf()),as_of_utc=NOW)
        self.assertEqual(r["Cycle_source_market_watch_if_valid"],"HOLD")
        self.assertEqual(r["Cycle_source_actual_capture_utc"],"2026-10-19T03:14:01+00:00")
        self.assertEqual(r["policies"]["Cycle_live_market_watch"]
                         ["research_only_whole_ASX_IBIT_units"],0)

    def test_no_preopen_market_source_remains_unavailable_not_filled(self):
        later=bitcoin(day="2026-10-19",
                      captured="2026-10-20T03:00:00+00:00",
                      action="BUY WATCH",buy="2.5000")
        r=first_actual_session(cycle_tape(later),asx_tape(etf()),as_of_utc=NOW)
        self.assertFalse(r["Cycle_market_signal_available_pre_ASX_open"])
        self.assertEqual(r["first_Cycle_action"],"NO_FRESH_PREOPEN_SIGNAL")
        self.assertIsNone(r["Cycle_source_market_watch_if_valid"])

    def test_verified_preopen_BUY_reconciles_bought_cycle_units(self):
        r=first_actual_session(
            cycle_tape(bitcoin(action="BUY WATCH",buy="2.5000")),
            asx_tape(etf()),as_of_utc=NOW)
        cyc=r["policies"]["Cycle_live_market_watch"]
        self.assertEqual(r["first_Cycle_action"],"PAPER_BUY")
        self.assertGreater(cyc["research_only_whole_ASX_IBIT_units"],0)
        self.assertLess(cyc["paper_AUD_cash_remaining"],100000.)
        self.assertGreater(cyc["first_session_assumed_broker_fees_AUD"],0)
        self.assertTrue(cyc["NOT_ACTUALLY_TRADED"])

    def test_future_ASX_close_is_not_known_yet(self):
        with self.assertRaisesRegex(ValueError,"Future ASX"):
            first_actual_session(cycle_tape(bitcoin()),asx_tape(etf()),
                as_of_utc=dt.datetime(2026,10,20,0,tzinfo=UTC))

    def test_after_append_next_session_first_paper_result_unchanged(self):
        start=first_actual_session(cycle_tape(bitcoin()),asx_tape(etf()),as_of_utc=NOW)
        second=etf(day="2026-10-21",close="22.8500",
                   captured="2026-10-21T07:10:00+00:00")
        later=first_actual_session(
            cycle_tape(bitcoin()),asx_tape(etf(),second),as_of_utc=NOW)
        self.assertEqual(start,later)

    def test_corrupt_saved_source_sha_does_not_make_new_execution(self):
        btc=cycle_tape(bitcoin())
        etf_record=asx_tape(etf())
        with self.assertRaisesRegex(ValueError,"Modified"):
            first_actual_session(btc,etf_record.replace("5252","9999"),as_of_utc=NOW)

    def test_wrong_aud_instrument_or_broker_status_is_rejected(self):
        wrong=etf();wrong["currency"]="USD"
        with self.assertRaisesRegex(ValueError,"Wrong ASX"):
            first_actual_session(cycle_tape(bitcoin()),
                                 asx_tape(wrong),as_of_utc=NOW)

    def test_stale_quality_failure_never_falls_back_to_old_BTC_buy(self):
        old=bitcoin(action="BUY WATCH",buy="2.5000")
        conflict=bitcoin(day="2026-10-19",captured="2026-10-20T03:00:00+00:00",
                         disagreement="6.29")
        r=first_actual_session(cycle_tape(old,conflict),
                               asx_tape(etf(day="2026-10-21",
                                            close="22.3000",
                                            captured="2026-10-21T07:10:00+00:00")),
                               as_of_utc=NOW)
        self.assertFalse(r["Cycle_market_signal_available_pre_ASX_open"])
        self.assertEqual(r["first_Cycle_action"],
                         "LATEST_PREOPEN_SIGNAL_FAILED_QUALITY_OR_VERSION_GATE")


if __name__=="__main__":
    unittest.main()
