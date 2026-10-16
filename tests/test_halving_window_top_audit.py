import unittest

import numpy as np
import pandas as pd

from engines.research.halving_window_top_audit import make_sale_schedule


class HalvingClockSaleTests(unittest.TestCase):
    def setUp(self):
        self.halving=pd.Timestamp("2020-05-11",tz="UTC")
        self.days=pd.date_range("2020-05-11",periods=900,freq="D",tz="UTC")
        self.prices=pd.Series(np.linspace(100.,1000.,900),index=self.days)

    def test_fractions_equal_or_front_loaded_and_never_depend_on_future(self):
        for method in ("equal","frontloaded"):
            s=make_sale_schedule(self.prices,self.halving,
                                 day_start=525,day_end=560,method=method)
            self.assertEqual(s["sales"],36)
            self.assertEqual(s["total_fraction_sold"],1.)
            later=self.prices.copy()
            later.iloc[700:]=1e9
            t=make_sale_schedule(later,self.halving,
                                 day_start=525,day_end=560,method=method)
            self.assertEqual(s,t)

    def test_frontloaded_means_better_sale_on_a_declining_market(self):
        prices=pd.Series(1000.-np.arange(900),index=self.days)
        equal=make_sale_schedule(prices,self.halving,
                                 day_start=525,day_end=560,method="equal")
        front=make_sale_schedule(prices,self.halving,
                                 day_start=525,day_end=560,method="frontloaded")
        self.assertGreater(front["gross_vwap_usd_per_btc"],
                           equal["gross_vwap_usd_per_btc"])

    def test_invalid_window_and_missing_day_rejected(self):
        with self.assertRaises(ValueError):
            make_sale_schedule(self.prices,self.halving,day_start=560,day_end=525)
        with self.assertRaises(ValueError):
            make_sale_schedule(self.prices,self.halving,day_start=1,day_end=2,
                               method="future")
        with self.assertRaisesRegex(ValueError,"missing"):
            make_sale_schedule(self.prices.iloc[:-400],self.halving,
                               day_start=525,day_end=560)


if __name__=="__main__":
    unittest.main()
