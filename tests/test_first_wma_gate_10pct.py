"""One frozen first-below-200WMA 10%-of-original-cash candidate."""
import unittest

import numpy as np
import pandas as pd

from engines.research.first_wma_gate_10pct import (
    EXPERIMENTAL_FIRST_GATE_FRACTION, ORIGINAL_FIRST_GATE_FRACTION,
    replay_first_gate_allocation, _compare,
)
from engines.research.fresh_cash_200wma_matched_backtest import (
    matched_fresh_cash_replay,
)

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-11-15",tz="UTC")


def fixture(*,down=True,second_crash=False):
    index=pd.date_range("2015-01-01","2021-04-01",freq="D",tz="UTC")
    price=pd.Series(100.,index=index)
    if down:
        price.loc["2020-02-01":]=65.
        if second_crash:
            price.loc["2020-04-01":]=20.
        else:
            price.loc["2020-05-01":]=125.
    fx_index=pd.date_range(index[0]-pd.Timedelta(days=8),
                           index[-1],freq="D",tz="UTC")
    fx=pd.DataFrame({"aud_per_usd":1.5},index=fx_index)
    return price,fx


class FirstGateTests(unittest.TestCase):
    def test_first_prior_gate_buys_exact_ten_percent(self):
        price,fx=fixture()
        out=replay_first_gate_allocation(
            price,fx,start=START,terminal=END,budget_aud=40000.)
        self.assertEqual(out["first_wma_gate"],"2020-02-02")
        self.assertEqual(out["orders"][0]["date"],"2020-02-02")
        self.assertEqual(out["orders"][0]["gross_aud"],4000.)
        self.assertEqual(out["orders"][0]["pct_original_budget"],10.)
        self.assertTrue(out["orders"][0]["first_gate_order"])
        self.assertTrue(all(not z["first_gate_order"] for z in out["orders"][1:]))
        self.assertTrue(out["research_only"])
        self.assertFalse(out["live_trading_parity_validated"])

    def test_original_2p5pct_unchanged_against_independent_engine(self):
        price,fx=fixture()
        check=replay_first_gate_allocation(
            price,fx,start=START,terminal=END,
            first_gate_fraction=ORIGINAL_FIRST_GATE_FRACTION,
            budget_aud=40000.)
        ref=matched_fresh_cash_replay(
            price,fx,start=START,terminal=END,
            policy="forward_original_budget_weekly",budget_aud=40000.)
        for key in ("fill_count","btc_purchased_and_held","cash_left_aud",
                    "cash_left_pct","after_hypothetical_liquidation_cgt_aud",
                    "fee_total_aud"):
            self.assertEqual(check[key],ref[key],key)
        self.assertEqual(check["first_wma_gate"],
                         ref["first_valid_200wma_activation_date"])
        self.assertEqual(check["orders"][0]["gross_aud"],1000.)

    def test_no_new_gate_no_order(self):
        price,fx=fixture(down=False)
        for pct in (ORIGINAL_FIRST_GATE_FRACTION,
                    EXPERIMENTAL_FIRST_GATE_FRACTION):
            v=replay_first_gate_allocation(
                price,fx,start=START,terminal=END,
                first_gate_fraction=pct,budget_aud=40000.)
            self.assertIsNone(v["first_wma_gate"])
            self.assertEqual(v["fill_count"],0)
            self.assertEqual(v["cash_left_pct"],100.)
            self.assertEqual(v["after_hypothetical_liquidation_cgt_aud"],40000.)

    def test_repainting_future_prices_does_not_change_prior_fills(self):
        price,fx=fixture()
        stop=pd.Timestamp("2020-03-31",tz="UTC")
        a=replay_first_gate_allocation(
            price,fx,start=START,terminal=stop,budget_aud=40000.)
        modified=price.copy()
        modified.loc[modified.index>stop]*=3.
        b=replay_first_gate_allocation(
            modified,fx,start=START,terminal=stop,budget_aud=40000.)
        self.assertEqual(a,b)
        longer=replay_first_gate_allocation(
            price,fx,start=START,terminal=END,budget_aud=40000.)
        self.assertEqual(a["orders"],
                         [x for x in longer["orders"] if x["date"]<=str(stop.date())])

    def test_late_lower_bottom_exposes_first_gate_risk(self):
        price,fx=fixture(second_crash=True)
        ref=replay_first_gate_allocation(
            price,fx,start=START,terminal=END,
            first_gate_fraction=ORIGINAL_FIRST_GATE_FRACTION,budget_aud=40000.)
        advanced=replay_first_gate_allocation(
            price,fx,start=START,terminal=END,budget_aud=40000.)
        self.assertEqual(advanced["first_wma_gate"],ref["first_wma_gate"])
        self.assertEqual(advanced["orders"][0]["gross_aud"],4000.)
        self.assertEqual(ref["orders"][0]["gross_aud"],1000.)
        self.assertGreater(advanced["btc_purchased_and_held"],0)
        self.assertNotEqual(advanced["cash_left_aud"],ref["cash_left_aud"])
        self.assertLess(advanced["cash_left_pct"],ref["cash_left_pct"])

    def test_reject_bad_inputs(self):
        price,fx=fixture()
        bad=price.drop(pd.Timestamp("2018-01-20",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"Missing continuous"):
            replay_first_gate_allocation(bad,fx,start=START,terminal=END)
        negative=price.copy()
        negative.loc["2020-08-01"]=-1.
        with self.assertRaisesRegex(ValueError,"Invalid historical"):
            replay_first_gate_allocation(
                negative,fx,start=START,terminal=END)
        with self.assertRaisesRegex(ValueError,"Not a predeclared"):
            replay_first_gate_allocation(
                price,fx,start=START,terminal=END,first_gate_fraction=.50)
        with self.assertRaisesRegex(ValueError,"Invalid cash"):
            replay_first_gate_allocation(
                price,fx,start=START,terminal=END,budget_aud=0)
        with self.assertRaisesRegex(ValueError,"Invalid ordered"):
            replay_first_gate_allocation(
                price,fx,start=END,terminal=END)
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            replay_first_gate_allocation(
                price,fx.loc[:"2020-02-02"],start=START,terminal=END)

    def test_two_model_comparison_parity_and_exact_initial_order(self):
        price,fx=fixture()
        # _compare's production-grade benchmark starts at the fixed 400k
        # audit budget. This test keeps its independent comparison explicit.
        result=_compare(price,fx,start=START,terminal=END)
        self.assertEqual(result["original_first_order_2p5pct"],10000.)
        self.assertEqual(result["first_order_10pct"],40000.)
        self.assertEqual(result["first_gate"],"2020-02-02")


if __name__=="__main__":
    unittest.main()
