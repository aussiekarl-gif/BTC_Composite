import unittest

import numpy as np
import pandas as pd

from engines.research.verified_recent_price_bridge import (
    append_verified_prices, asof_on_mondays, expanding_aud_powerlaw_risk,
    parse_blockchain_price, parse_frankfurter_fx,
)


def master():
    idx=pd.date_range("2026-07-06", periods=12, freq="W-MON", tz="UTC")
    vals=np.array([100_000.+i*100 for i in range(12)])
    return pd.DataFrame({"btc_price_aud":vals,
                         "risk_score":[.3]*12},index=idx)


class PublicPriceBridgeTests(unittest.TestCase):
    def test_parse_source_chart_and_fx(self):
        prices=parse_blockchain_price({"values":[{"x":1783296000,"y":60000},
                                                      {"x":1783382400,"y":61000}]})
        self.assertEqual(len(prices),2)
        self.assertEqual(float(prices.iloc[0,0]),60000.)
        fx=parse_frankfurter_fx({"rates":{"2026-07-06":{"AUD":1.5},
                                          "2026-07-07":{"AUD":1.6}}})
        self.assertAlmostEqual(float(fx.iloc[0,0]),1.5)

    def test_asof_never_uses_future_fx_or_price(self):
        days=pd.date_range("2026-07-06",periods=36,freq="D",tz="UTC")
        price=pd.DataFrame({"btc_usd":[60000.]*len(days)},index=days)
        fx=pd.DataFrame({"aud_per_usd":[1.5,1.6,1.7,1.8,1.9]},
                        index=pd.to_datetime([
                          "2026-07-06","2026-07-13","2026-07-20",
                          "2026-07-27","2026-08-03"],utc=True))
        w=asof_on_mondays(price,fx,start="2026-07-06",end="2026-08-03")
        self.assertEqual(len(w),5)
        self.assertAlmostEqual(w.iloc[0]["btc_price_aud"],90000.)
        self.assertTrue((w["fx_source_date"]<=w.index).all())
        self.assertTrue((w["price_source_date"]<=w.index).all())

    def test_stale_fx_rejected_not_silently_forwardfilled(self):
        days=pd.date_range("2026-07-06",periods=40,freq="D",tz="UTC")
        price=pd.DataFrame({"btc_usd":[60000.]*len(days)},index=days)
        fx=pd.DataFrame({"aud_per_usd":[1.5]},
                        index=pd.to_datetime(["2026-07-06"],utc=True))
        with self.assertRaisesRegex(ValueError,"Missing/stale"):
            asof_on_mondays(price,fx,start="2026-07-06",end="2026-08-03")

    def test_no_append_when_overlap_mismatch(self):
        d=master()
        p=pd.DataFrame({"btc_price_aud":d["btc_price_aud"]*1.4},index=d.index)
        ix=d.index[-1]+pd.Timedelta(weeks=1)
        p.loc[ix,"btc_price_aud"]=115000
        with self.assertRaisesRegex(ValueError,"overlap mismatch"):
            append_verified_prices(d,p,asof=ix)

    def test_append_keeps_all_original_prices_and_never_extends_old_risk(self):
        d=master()
        p=pd.DataFrame({"btc_price_aud":d["btc_price_aud"]*1.01},
                       index=d.index)
        monday=d.index[-1]+pd.Timedelta(weeks=1)
        p.loc[monday,"btc_price_aud"]=95000.
        merged,audit=append_verified_prices(d,p,asof=monday)
        self.assertEqual(len(merged),len(d)+1)
        self.assertTrue(np.array_equal(merged.loc[d.index,"btc_price_aud"].to_numpy(),
                                      d["btc_price_aud"].to_numpy()))
        self.assertNotIn("risk_score",merged.columns)
        self.assertEqual(audit["new_public_weeks"],1)

    def test_powerlaw_uses_only_prefix_price_information(self):
        idx=pd.date_range("2021-01-04",periods=220,freq="W-MON",tz="UTC")
        vals=np.array([12000.*(1+.01*i) for i in range(len(idx))])
        base=pd.DataFrame({"btc_price_aud":vals},index=idx)
        original=expanding_aud_powerlaw_risk(base)
        revised=base.copy()
        revised.iloc[180:]=1_000_000.
        changed=expanding_aud_powerlaw_risk(revised)
        np.testing.assert_allclose(
            original["risk_score"].iloc[:180].to_numpy(),
            changed["risk_score"].iloc[:180].to_numpy(),
            equal_nan=True)
        self.assertTrue(original["risk_score"].iloc[:104].isna().all())
        self.assertTrue(original["risk_score"].iloc[120:].notna().all())


if __name__ == "__main__":
    unittest.main()
