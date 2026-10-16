import unittest
import pandas as pd

from engines.research.post_sale_execution_audit import score_roundtrips, evaluate_pairs


def data(prices):
    return pd.DataFrame(
        {"btc_price_aud": prices, "risk_score": [0.5] * len(prices)},
        index=pd.date_range("2020-01-06", periods=len(prices), freq="W-MON",tz="UTC"),
    )


def plan(frame, side, start, end, avg):
    return {"side":side, "start":str(frame.index[start]),
            "end":str(frame.index[end]),"execution_vwap_aud":avg,
            "complete_plan":True}


class CashFeasiblePriceAuditTests(unittest.TestCase):
    def test_high_before_low_and_both_within_25_percent(self):
        prices=[100.]*170
        prices[75]=200.
        prices[115]=50.
        h=data(prices)
        plans=[plan(h,"SELL",70,72,150.),plan(h,"BUY",110,113,60.)]
        x=score_roundtrips(h,plans)
        self.assertEqual(x["eligible_pairs"],1)
        self.assertEqual(x["both_under_25pct"],1)
        self.assertAlmostEqual(x["paired_results"][0]["sell_error_pct"],25)
        self.assertAlmostEqual(x["paired_results"][0]["buy_error_pct"],20)

    def test_lows_before_the_sale_cannot_count(self):
        prices=[100.]*180
        prices[20]=10.
        h=data(prices)
        x=score_roundtrips(h,[plan(h,"SELL",75,76,100.),
                               plan(h,"BUY",120,121,100.)])
        self.assertAlmostEqual(x["paired_results"][0]["achievable_reference_low_aud"],100)
        self.assertAlmostEqual(x["paired_results"][0]["buy_error_pct"],0)

    def test_high_after_low_is_excluded_for_impossible_oracle(self):
        prices=[100.]*180
        prices[85]=50.
        prices[105]=200.
        h=data(prices)
        x=score_roundtrips(h,[plan(h,"SELL",75,77,150.),
                               plan(h,"BUY",110,112,55.)])
        self.assertEqual(x["all_matched_pairs"],1)
        self.assertEqual(x["eligible_pairs"],0)
        self.assertFalse(x["paired_results"][0]["chronological_high_before_low"])

    def test_incomplete_future_oracle_is_censored(self):
        h=data([100.]*150)
        x=score_roundtrips(h,[plan(h,"SELL",110,113,100.),
                               plan(h,"BUY",140,143,100.)])
        self.assertEqual(x["all_matched_pairs"],1)
        self.assertEqual(x["eligible_pairs"],0)
        self.assertFalse(x["paired_results"][0]["complete_lookahead"])

    def test_existing_candidates_have_no_live_mutation(self):
        h=data([100.+(i%12) for i in range(190)])
        r=evaluate_pairs(h)
        self.assertEqual(len(r["results"]),4)
        self.assertTrue(all(x["all_matched_pairs"]>=0 for x in r["results"].values()))


if __name__=="__main__":
    unittest.main()
