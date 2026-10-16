"""Current-cycle AUD top/trough percent, using dated, non-future FX."""
import unittest

import pandas as pd

from engines.research.cycle_aud_price_levels import observed_aud_cycle_levels


def fixture():
    dates=pd.date_range("2024-04-20",periods=7,freq="D",tz="UTC")
    usd=pd.Series([100.,190.,210.,140.,100.,130.,150.],index=dates)
    fx=pd.DataFrame({"aud_per_usd":[1.5,2.,1.6,1.5,1.6,1.5,1.5]},index=dates)
    return dates,usd,fx


class ObservedAudCycleLevelsTests(unittest.TestCase):
    def test_aud_peak_and_post_peak_low_with_all_three_percentages(self):
        dates,usd,fx=fixture()
        res=observed_aud_cycle_levels(usd,fx)
        # Peak is Apr21 AUD380 (NOT the Apr22 USD peak $210).
        self.assertEqual(res["cycle_top_date"],"2024-04-21")
        self.assertEqual(res["cycle_top_aud"],380.)
        self.assertEqual(res["cycle_bottom_date"],"2024-04-24")
        self.assertEqual(res["cycle_bottom_aud"],160.)
        self.assertEqual(res["last_price_aud"],225.)
        self.assertAlmostEqual(res["pct_change_from_top"],-40.79,places=2)
        self.assertAlmostEqual(res["pct_change_from_bottom"],40.62,places=2)
        self.assertAlmostEqual(res["position_between_low_high_pct"],29.55,places=2)
        self.assertEqual(res["asof_date"],"2024-04-26")
        self.assertTrue(res["observation_only"])
        self.assertFalse(res["forecast"])

    def test_fx_uses_historical_date_not_today_fx(self):
        dates,usd,fx=fixture()
        baseline=observed_aud_cycle_levels(usd,fx)
        fx2=fx.copy()
        fx2.loc[dates[-1],"aud_per_usd"]=2.5
        updated=observed_aud_cycle_levels(usd,fx2)
        # Past top/bottom never retroactively changed by today's FX.
        self.assertEqual(baseline["cycle_top_aud"],updated["cycle_top_aud"])
        self.assertEqual(baseline["cycle_bottom_aud"],updated["cycle_bottom_aud"])
        self.assertNotEqual(baseline["last_price_aud"],updated["last_price_aud"])

    def test_no_future_prices_affect_an_earlier_asof(self):
        dates,usd,fx=fixture()
        baseline=observed_aud_cycle_levels(usd,fx,asof=dates[-2])
        extended=usd.copy()
        extended.loc[dates[-1]]=100000.
        after=observed_aud_cycle_levels(extended,fx,asof=dates[-2])
        self.assertEqual(baseline,after)

    def test_fx_must_be_on_or_before_date_and_never_stale(self):
        dates,usd,fx=fixture()
        with self.assertRaisesRegex(ValueError,"Missing historical AUD/USD"):
            observed_aud_cycle_levels(
                usd,fx.loc[dates[-1]:])
        with self.assertRaisesRegex(ValueError,"Stale or future"):
            observed_aud_cycle_levels(
                usd,fx.iloc[:1])
        extra=fx.copy()
        extra=pd.concat([extra,fx.iloc[[-1]]])
        with self.assertRaisesRegex(ValueError,"Duplicate historical FX"):
            observed_aud_cycle_levels(usd,extra)

    def test_no_post_top_low_fail_closed_instead_of_claiming_bottom(self):
        dates,usd,fx=fixture()
        all_up=pd.Series(range(100,107),index=dates,dtype=float)
        steady=pd.DataFrame({"aud_per_usd":[1.] * 7},index=dates)
        with self.assertRaisesRegex(ValueError,"No recorded period after observed top"):
            observed_aud_cycle_levels(all_up,steady)

    def test_latest_low_position_zero_and_zero_price_not_accepted(self):
        dates,usd,fx=fixture()
        lower=usd.copy()
        lower.loc[dates[-1]]=50.
        res=observed_aud_cycle_levels(lower,fx)
        self.assertEqual(res["cycle_bottom_date"],"2024-04-26")
        self.assertAlmostEqual(res["position_between_low_high_pct"],0.)
        with self.assertRaisesRegex(ValueError,"Invalid BTC/USD price"):
            lower.iloc[-1]=0.
            observed_aud_cycle_levels(lower,fx)


if __name__=="__main__":
    unittest.main()
