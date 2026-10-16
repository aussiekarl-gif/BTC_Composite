"""Live-account original-lot shadow vs exact old historical BTC sell replay."""
import unittest
import pandas as pd

from engines.research.cycle_account_shadow import shadow_original_btc_exit
from engines.research.day500_dynamic_dca_out import staged_day500_dynamic_exit
from engines.research.shared_cycle_policy import exit_review_days
from engines.research.top_signal_horse_race import read_exported_history


def bought(date,units,asset="Direct BTC"):
    return {"Date":pd.Timestamp(date).strftime("%d/%m/%y"),
            "Asset":asset,"Units / BTC Received":units,
            "AUD Spent":2000.*units,
            "Brokerage / Fee AUD":0.,
            "BTC AUD Price":2000.}


def sold(date,units,asset="Direct BTC"):
    return {"Date":pd.Timestamp(date).strftime("%d/%m/%y"),
            "Asset":asset,"Units Sold":units,
            "AUD Proceeds":max(.01,round(100000.*units,2)),
            "Brokerage / Fee AUD":0.}


class AccountShadowParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history=read_exported_history()["price_usd"]

    def test_historical_shadow_order_quantities_match_replay(self):
        for halving in ("2016-07-09","2020-05-11","2024-04-20"):
            h=pd.Timestamp(halving,tz="UTC")
            for review in (600,730):
                if h+pd.Timedelta(days=review)>self.history.index[-1]:
                    continue
                policy="maturity_90pct_holdback20pct"
                reference=staged_day500_dynamic_exit(
                    self.history,h,policy=policy,review_day=review)
                ref_by_day={r["halving_day"]:r["btc_sold"]
                            for r in reference["sale_detail"]}
                saved={"starting_capital_aud":500000.,
                       "rows":[bought(h,1.0)],"sales":[]}
                for day in exit_review_days(review_day=review):
                    if day>review:continue
                    at=h+pd.Timedelta(days=day)
                    shadow=shadow_original_btc_exit(
                        self.history,h,saved,asof=at,
                        asset="Direct BTC",policy=policy)
                    with self.subTest(halving=halving,review=review,day=day):
                        expected=float(ref_by_day.get(day,0.))
                        self.assertAlmostEqual(
                            shadow["quantity"],expected,delta=2e-8)
                        self.assertEqual(shadow["research_only"],True)
                        self.assertFalse(shadow["place_order"])
                    if shadow["quantity"]>0:
                        saved["sales"].append(sold(at,shadow["quantity"]))
                total=sum(float(r["Units Sold"]) for r in saved["sales"])
                self.assertAlmostEqual(
                    total,reference["btc_sold"],delta=5e-7)

    def test_2026_bought_ibit_cannot_retroactively_sell_in_2025(self):
        saved={"starting_capital_aud":500000.,
               "rows":[bought("2026-01-01",1000,asset="ASX:IBIT")]}
        result=shadow_original_btc_exit(
            self.history,"2024-04-20",saved,
            asof="2025-09-02",asset="ASX:IBIT")
        self.assertEqual(result["action"],"HOLD")
        self.assertIn("No recorded original holdings",result["reason"])
        result=shadow_original_btc_exit(
            self.history,"2024-04-20",saved,
            asof="2026-10-15",asset="ASX:IBIT")
        self.assertEqual(result["action"],"HOLD")
        self.assertIn("expired",result["reason"])

    def test_whole_etf_unit_rounding_against_original_position(self):
        h="2024-04-20"
        saved={"starting_capital_aud":500000.,
               "rows":[bought("2024-05-01",105,asset="ASX:IBIT")]}
        result=shadow_original_btc_exit(
            self.history,h,saved,asof="2025-09-02",
            asset="ASX:IBIT")
        self.assertEqual(result["quantity"],5.)
        self.assertEqual(result["original_position"],105.)
        self.assertEqual(result["pct_original"],5.)
        self.assertEqual(result["action"],"SELL REVIEW")

    def test_only_review_dates_and_no_executable_orders(self):
        saved={"starting_capital_aud":500000.,
               "rows":[bought("2024-05-01",300,asset="ASX:IBIT")]}
        r=shadow_original_btc_exit(
            self.history,"2024-04-20",saved,asof="2025-09-03")
        self.assertEqual(r["action"],"HOLD")
        self.assertIn("Not a scheduled",r["reason"])
        self.assertFalse(r["place_order"])


if __name__=="__main__":
    unittest.main()
