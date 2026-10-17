"""Counterfactual delayed-bottom stress safety checks, not a forecast."""
import unittest
import numpy as np
import pandas as pd

from engines.research.staged_dca_delayed_bottom_stress import (
    delayed_bottom_path,evaluate_stress,
)
from engines.research.staged_tax_aware_roundtrip import replay_roundtrip

HALVING=pd.Timestamp("2020-05-11",tz="UTC")


def synthetic_history():
    idx=pd.date_range("2014-01-01",HALVING+pd.Timedelta(days=1160),
                      freq="D",tz="UTC")
    day=np.array((idx-HALVING).days,dtype=float)
    vals=np.interp(day,[-2500,-1700,-1000,0,400,525,560,700,850,1060,1160],
                   [120,95,105,150,325,550,460,300,245,235,330])
    price=pd.Series(vals,index=idx)
    fx_idx=pd.date_range(idx.min()-pd.Timedelta(days=10),
                         idx.max(),freq="D",tz="UTC")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fx_idx),1.5)},index=fx_idx)
    return price,fx


def fx_stub(_halving,_terminal):
    return synthetic_history()[1]


class DelayedBottomStressTests(unittest.TestCase):
    def test_counterfactual_changes_nothing_until_shock(self):
        prices,_=synthetic_history()
        stress=delayed_bottom_path(prices,HALVING,
            shock_start_day=780,loss_fraction=.70,
            terminal_price_fraction=.55)
        start=HALVING+pd.Timedelta(days=780)
        low=HALVING+pd.Timedelta(days=1060)
        end=HALVING+pd.Timedelta(days=1150)
        pd.testing.assert_series_equal(prices.loc[:start],stress.loc[:start],
                                       check_names=True)
        self.assertAlmostEqual(float(stress.loc[low]),
                               float(prices.loc[start])*.30,places=8)
        self.assertAlmostEqual(float(stress.loc[end]),
                               float(prices.loc[start])*.55,places=8)
        self.assertTrue(stress.gt(0).all())

    def test_no_artificial_future_in_pre_shock_ledger(self):
        prices,fx=synthetic_history()
        end=HALVING+pd.Timedelta(days=1150)
        original=replay_roundtrip(prices,fx,HALVING,end,
                                 seller="fixed_525_to_560",
                                 buyer="staged_value_recovery")
        shock=delayed_bottom_path(prices,HALVING,
            shock_start_day=900,loss_fraction=.5,
            terminal_price_fraction=.55)
        stressed=replay_roundtrip(shock,fx,HALVING,end,
                                 seller="fixed_525_to_560",
                                 buyer="staged_value_recovery")
        prior=HALVING+pd.Timedelta(days=900)
        def prefix(orders):
            return [o for o in orders if pd.Timestamp(o["date"])<=prior]
        self.assertEqual(prefix(original["orders"]),prefix(stressed["orders"]))
        self.assertEqual(original["sales"],stressed["sales"])
        self.assertNotEqual(original["buybacks"],stressed["buybacks"])
        self.assertLessEqual(stressed["account_max_marked_drawdown_pct"],0)
        self.assertLessEqual(stressed["hold_max_marked_drawdown_pct"],0)

    def test_matched_shock_comparison_without_outside_cash(self):
        px,_=synthetic_history()
        result=evaluate_stress(
            px,fx_fetcher=fx_stub,cycles=("2021",),
            sellers=("fixed_525_to_560",),starts=(780,),
            losses=(.70,),recoveries=(.55,))
        rows=result["scenario_results"]
        self.assertEqual(len(rows),1)
        scenario=rows[0]
        self.assertEqual(scenario["shock_start_day"],780)
        self.assertEqual(scenario["loss_from_shock_price_pct"],70)
        self.assertTrue(scenario["forced_trough_is_observed_window_low"])
        self.assertTrue(0<=scenario["staged"]["spent_before_forced_low_pct_of_net_sales"]<=100.01)
        self.assertGreaterEqual(scenario["staged"]["cash_remaining_aud"],0)
        self.assertGreater(scenario["staged"]["original_sale_proceeds_aud"],0)
        self.assertIsInstance(scenario["staged_worse_than_existing"],bool)
        self.assertEqual(len(result["aftertax_stress_summary"]),1)
        self.assertEqual(result["aftertax_stress_summary"][
            "2021 | fixed_525_to_560"]["scenario_count"],1)

    def test_scenario_input_validation(self):
        prices,_=synthetic_history()
        for args in (
            dict(shock_start_day=1050,loss_fraction=.5,
                 terminal_price_fraction=.55,trough_day=1000),
            dict(shock_start_day=780,loss_fraction=1.0,
                 terminal_price_fraction=.55),
            dict(shock_start_day=780,loss_fraction=.5,
                 terminal_price_fraction=0),
        ):
            with self.assertRaises(ValueError):
                delayed_bottom_path(prices,HALVING,**args)

    def test_no_early_buy_when_drawdown_and_wma_gate_absent(self):
        # Historical no-op shallow bull regime must not be retroactively
        # scored a false BUY just because an ex-post low occurs later.
        from engines.research.staged_value_dca_challenger import candidate_buy_signal
        from engines.research.cycle_trading_dashboard_model import build_dashboard_market
        prices,_=synthetic_history()
        p=prices.loc[:HALVING+pd.Timedelta(days=780)].copy()
        p.iloc[-365:]=300.0
        market=build_dashboard_market(p,pd.DataFrame())
        market["prior_200wma_usd"]=260.
        market["previous_close_below_200wma"]=False
        self.assertEqual(candidate_buy_signal(market)["buy_pct_cash"],0.)


if __name__=="__main__":
    unittest.main()
