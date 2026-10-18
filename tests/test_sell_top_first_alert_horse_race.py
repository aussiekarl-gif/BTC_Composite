"""Causal first-event exit overlay, independent against original wallet."""
import unittest

import numpy as np
import pandas as pd

from engines.research.cycle_chronological_wallet import (
    replay_chronological_wallet,
)
from engines.research.sell_top_first_alert_horse_race import (
    FAMILIES,SIGNAL_START_DAY,SIGNAL_END_DAY,SELL_FRACTION_OF_ORIGINAL,
    replay_first_alert_overlay,
)

HALVING=pd.Timestamp("2020-05-11",tz="UTC")
START=HALVING-pd.Timedelta(days=1500)
TERMINAL=HALVING+pd.Timedelta(days=940)
INDEX=pd.date_range(START,TERMINAL,freq="D",tz="UTC")


def fake_inputs():
    price=pd.Series(110.,index=INDEX)
    elapsed=(price.index-HALVING).days
    price.iloc[:]=np.where(elapsed<250,110.,
                           np.where(elapsed<700,230.,65.))
    fx_index=pd.date_range(START-pd.Timedelta(days=10),
                           TERMINAL,freq="D",tz="UTC")
    fx=pd.DataFrame({"aud_per_usd":1.5},index=fx_index)
    signals=pd.DataFrame(False,index=price.index,
                         columns=FAMILIES[1:],dtype=bool)
    return price,fx,signals


class FirstTopAlertTests(unittest.TestCase):
    def test_baseline_matches_chronological_wallet(self):
        price,fx,signals=fake_inputs()
        a=replay_first_alert_overlay(
            price,fx,signals,HALVING,TERMINAL,
            family="original_no_extra_sell")
        b=replay_chronological_wallet(price,fx,HALVING,TERMINAL)
        self.assertEqual(a["terminal_after_illustrative_cgt_aud"],
                         b["after_hypothetical_liquidation_cgt_aud"])
        self.assertEqual(a["ending_btc"],b["btc_held"])
        self.assertEqual(a["ending_cash_aud"],b["cash_remaining_aud"])
        self.assertEqual(a["sell_count"],b["sell_count"])
        self.assertEqual(a["buyback_count"],b["buyback_count"])
        self.assertIsNone(a["overlay_first_date"])

    def test_first_signal_executes_20pct_once_before_day500(self):
        price,fx,signals=fake_inputs()
        signal_day=HALVING+pd.Timedelta(days=410)
        signals.loc[signal_day:signal_day+pd.Timedelta(days=20),
                    "classic_euphoria"]=True
        r=replay_first_alert_overlay(
            price,fx,signals,HALVING,TERMINAL,family="classic_euphoria")
        self.assertEqual(r["overlay_first_date"],str(signal_day.date()))
        self.assertAlmostEqual(r["overlay_fraction_original_pct"],
                               SELL_FRACTION_OF_ORIGINAL*100,places=4)
        self.assertEqual(sum(x["reason"]=="classic_euphoria"
                             for x in r["executions"]),1)
        self.assertTrue(r["research_only"])
        self.assertFalse(r["live_execution_parity_verified"])

    def test_first_eligible_alert_after_day350_not_before(self):
        price,fx,signals=fake_inputs()
        signals.loc[HALVING+pd.Timedelta(days=349),"pi_top_cross"]=True
        signals.loc[HALVING+pd.Timedelta(days=350),"pi_top_cross"]=True
        r=replay_first_alert_overlay(
            price,fx,signals,HALVING,TERMINAL,family="pi_top_cross")
        self.assertEqual(r["overlay_first_date"],str((
            HALVING+pd.Timedelta(days=350)).date()))

    def test_alerts_after_day730_never_add_a_trade(self):
        price,fx,signals=fake_inputs()
        signals.loc[HALVING+pd.Timedelta(days=731),"late_trend_break"]=True
        base=replay_first_alert_overlay(
            price,fx,signals,HALVING,TERMINAL,
            family="original_no_extra_sell")
        later=replay_first_alert_overlay(
            price,fx,signals,HALVING,TERMINAL,
            family="late_trend_break")
        self.assertIsNone(later["overlay_first_date"])
        self.assertEqual(later["terminal_after_illustrative_cgt_aud"],
                         base["terminal_after_illustrative_cgt_aud"])

    def test_absent_indicator_must_equal_original(self):
        price,fx,signals=fake_inputs()
        base=replay_first_alert_overlay(
            price,fx,signals,HALVING,TERMINAL,
            family="original_no_extra_sell")
        for family in FAMILIES[1:]:
            v=replay_first_alert_overlay(
                price,fx,signals,HALVING,TERMINAL,family=family)
            self.assertEqual(v["terminal_after_illustrative_cgt_aud"],
                             base["terminal_after_illustrative_cgt_aud"])
            self.assertEqual(v["ending_btc"],base["ending_btc"])

    def test_repainting_future_prices_cannot_change_first_executed_trade(self):
        price,fx,signals=fake_inputs()
        alert=HALVING+pd.Timedelta(days=410)
        signals.loc[alert,"maturity_confirmed_reversal"]=True
        x=replay_first_alert_overlay(
            price,fx,signals,HALVING,TERMINAL,
            family="maturity_confirmed_reversal")
        altered=price.copy()
        altered.loc[alert+pd.Timedelta(days=1):]*=3.0
        y=replay_first_alert_overlay(
            altered,fx,signals,HALVING,TERMINAL,
            family="maturity_confirmed_reversal")
        first=lambda result:next(z for z in result["executions"]
                                 if z["reason"]=="maturity_confirmed_reversal")
        self.assertEqual(first(x),first(y))

    def test_bad_prices_indicator_alignment_or_family_fail_closed(self):
        price,fx,signals=fake_inputs()
        kws=dict(family="trend_reversal")
        for bad in (signals.iloc[:-1],signals.drop(columns=["trend_reversal"])):
            with self.assertRaises(ValueError):
                replay_first_alert_overlay(
                    price,fx,bad,HALVING,TERMINAL,**kws)
        with self.assertRaisesRegex(ValueError,"Unknown"):
            replay_first_alert_overlay(
                price,fx,signals,HALVING,TERMINAL,
                family="best_looking_in_hindsight")
        malformed=price.copy()
        malformed.loc[HALVING+pd.Timedelta(days=100)]=np.nan
        with self.assertRaisesRegex(ValueError,"finite"):
            replay_first_alert_overlay(
                malformed,fx,signals,HALVING,TERMINAL,**kws)

    def test_sale_lot_and_tax_withholding_change_terminal_value(self):
        price,fx,signals=fake_inputs()
        signals.loc[HALVING+pd.Timedelta(days=410),"relative_euphoria"]=True
        a=replay_first_alert_overlay(
            price,fx,signals,HALVING,TERMINAL,family="relative_euphoria")
        b=replay_first_alert_overlay(
            price,fx,signals,HALVING,TERMINAL,
            family="original_no_extra_sell")
        self.assertEqual(sum(e["reason"]=="relative_euphoria"\n                             for e in a["executions"]),1)\n        self.assertLess(a["overlay_first_date"],\n                        next(e["date"] for e in b["executions"]\n                             if e["side"]=="SELL"))
        self.assertGreater(a["realised_tax_escrow_aud"],0)
        self.assertNotEqual(a["terminal_after_illustrative_cgt_aud"],
                            b["terminal_after_illustrative_cgt_aud"])


if __name__=="__main__":
    unittest.main()
