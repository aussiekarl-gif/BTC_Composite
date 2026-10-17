"""Frozen original cycle first-alert / date-lag audit: causal tests."""
import copy
import unittest

import numpy as np
import pandas as pd

from engines.research.cycle_indicator_timing_audit import (
    first_alert_timing,original_calendar_events,_weighted_prices,
    _window_peak,_window_low,
)

HALVING=pd.Timestamp("2016-07-09",tz="UTC")


def synthetic(*,low_day=780):
    idx=pd.date_range("2012-01-01","2020-01-01",freq="D",tz="UTC")
    price=pd.Series(np.full(len(idx),100.),index=idx)
    # Historical peak score is a hindsight label ONLY, not a signal.
    peak=HALVING+pd.Timedelta(days=550)
    price.loc[peak]=500.
    # Keep subsequent pre-trough closes above the prior WMA. Otherwise
    # a one-day synthetic 500 spike lifts WMA above flat 100 and causes a
    # *genuine earlier* strict below-WMA signal on halving day744.
    price.loc[price.index>peak]=150.
    low=HALVING+pd.Timedelta(days=low_day)
    price.loc[price.index>=low]=60.
    price.loc[price.index>=low+pd.Timedelta(days=24)]=210.
    return price


class FirstAlertTimingTests(unittest.TestCase):
    def test_first_actual_alert_not_retrospective_nearest_peak(self):
        price=synthetic()
        idx=price.index
        fake=pd.DataFrame({
            "trend_reversal":pd.Series(False,index=idx),
        },index=idx)
        early=HALVING+pd.Timedelta(days=400)
        peaknear=HALVING+pd.Timedelta(days=548)
        fake.loc[early,"trend_reversal"]=True
        fake.loc[peaknear,"trend_reversal"]=True
        out=first_alert_timing(
            fake,price,HALVING,HALVING+pd.Timedelta(days=850),
            family="trend_reversal")
        self.assertEqual(out["first_alert_date"],str(early.date()))
        self.assertEqual(out["alerts_in_window"],2)
        self.assertNotEqual(out["first_alert_date"],str(peaknear.date()))
        self.assertTrue(out["first_alert_selected_without_peak_knowledge"])

    def test_missed_alert_is_recorded_as_missing_not_an_ideal_peak_sale(self):
        px=synthetic()
        false=pd.DataFrame({"pi_top_cross":False},index=px.index)
        result=first_alert_timing(
            false,px,HALVING,HALVING+pd.Timedelta(days=850),
            family="pi_top_cross")
        self.assertIsNone(result["first_alert_date"])
        self.assertEqual(result["alerts_in_window"],0)
        self.assertEqual(result["event_dates"],[])

    def test_alert_result_no_future_high_leak(self):
        px=synthetic()
        sig=pd.DataFrame({"cycle_maturity_warning":False},index=px.index)
        alarm=HALVING+pd.Timedelta(days=370)
        sig.loc[alarm,"cycle_maturity_warning"]=True
        horizon=HALVING+pd.Timedelta(days=450)
        early=first_alert_timing(sig.loc[:horizon],px.loc[:horizon],
            HALVING,horizon,family="cycle_maturity_warning")
        later=px.copy()
        later.loc[later.index>horizon]=1e8
        second=first_alert_timing(sig,later,HALVING,horizon,
            family="cycle_maturity_warning")
        self.assertEqual(early,second)

    def test_invalid_indicator_does_not_get_optimised_into_race(self):
        px=synthetic()
        with self.assertRaisesRegex(ValueError,"Unrecognised"):
            first_alert_timing(
                pd.DataFrame(index=px.index),px,HALVING,
                HALVING+pd.Timedelta(days=900),family="lookahead_best")

    def test_retrospective_peak_low_are_scoring_only_and_censored(self):
        px=synthetic()
        end=HALVING+pd.Timedelta(days=880)
        peak=_window_peak(px,HALVING,end)
        low=_window_low(px,HALVING,end)
        self.assertTrue(peak["full_350_to_800_window_observed"])
        self.assertFalse(low["complete_day1150_observed"])
        self.assertEqual(peak["date"],str((HALVING+pd.Timedelta(days=550)).date()))

    def test_strict_prior_wma_activation_and_weekly_recovery_persistence(self):
        px=synthetic()
        terminal=HALVING+pd.Timedelta(days=845)
        out=original_calendar_events(px,HALVING,terminal)
        activation=HALVING+pd.Timedelta(days=781)
        self.assertEqual(out["first_buy_activation_date"],str(activation.date()))
        self.assertTrue(out["original_sell_events"])
        self.assertEqual(out["original_sell_events"][0]["halving_day"],500)
        self.assertAlmostEqual(out["original_sell_events"][0][
            "original_btc_fraction"],.05,places=9)
        buy=out["buy_events"]
        self.assertEqual(buy[0]["date"],str(activation.date()))
        self.assertEqual(
            [(pd.Timestamp(x["date"],tz="UTC")-activation).days for x in buy],
            list(range(0,(terminal-activation).days+1,7)))
        self.assertTrue(any(
            x["previous_close_to_prior_200wma"]>1 for x in buy))
        self.assertLessEqual(out["total_buy_budget_deployed_pct"],100.)

    def test_frozen_signal_prefix_identical_when_future_prices_changed(self):
        px=synthetic()
        endpoint=HALVING+pd.Timedelta(days=840)
        original=original_calendar_events(px.loc[:endpoint],HALVING,endpoint)
        changed=px.copy()
        changed.loc[changed.index>endpoint]=1e7
        second=original_calendar_events(changed,HALVING,endpoint)
        self.assertEqual(original,second)

    def test_execution_delay_measured_not_used_to_select_signal(self):
        px=synthetic()
        end=HALVING+pd.Timedelta(days=855)
        out=original_calendar_events(px,HALVING,end)
        for direction,events in (
            ("SELL",out["original_sell_events"]),
            ("BUY",out["buy_events"])):
            scores=_weighted_prices(px.loc[:end],events,kind=direction)
            self.assertEqual(set(scores),{"0","1","3","7"})
            self.assertGreater(scores["0"]["event_count"],0)
            self.assertGreater(scores["7"]["event_count"],0)
            self.assertGreater(scores["0"]["usd_weighted_close"],0)
        # The original signal is frozen, never moved to a better date.
        self.assertEqual(out["buy_events"][0]["date"],
                         str((HALVING+pd.Timedelta(days=781)).date()))

    def test_delay_never_reads_beyond_observation_cutoff(self):
        px=synthetic()
        day=HALVING+pd.Timedelta(days=550)
        rows=[{
            "date":str(day.date()),"original_btc_fraction":.5
        }]
        truncated=px.loc[:day]
        scores=_weighted_prices(truncated,rows,kind="SELL")
        self.assertEqual(scores["0"]["event_count"],1)
        self.assertEqual(scores["1"]["event_count"],0)
        self.assertIsNone(scores["7"]["usd_weighted_close"])

    def test_missing_btc_calendar_date_fails_closed(self):
        px=synthetic()
        px=px.drop(HALVING+pd.Timedelta(days=600))
        with self.assertRaisesRegex(ValueError,"Missing historical"):
            original_calendar_events(
                px,HALVING,HALVING+pd.Timedelta(days=820))


if __name__=="__main__":
    unittest.main()
