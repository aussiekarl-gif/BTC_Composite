"""Synthetic invariants of matched historical AUD SMSF cycle replay.

All synthetic series are strictly dated and use fabricated constant AUD/USD
rates; real history and historical FX are exercised in Actions separately.
"""
import unittest

import numpy as np
import pandas as pd

from engines.research.staged_tax_aware_roundtrip import (
    replay_roundtrip,BUY_START_DAY,SELLERS,BUYERS,
)

HALVING=pd.Timestamp("2020-05-11",tz="UTC")


def synthetic(end_day=1170):
    idx=pd.date_range(HALVING-pd.Timedelta(days=1600),
                      HALVING+pd.Timedelta(days=end_day),
                      freq="D",tz="UTC")
    offsets=(idx-HALVING).days.to_numpy(float)
    px=np.interp(offsets,
                 [-1600,-1000,-200,0,400,525,560,700,850,1170],
                 [100,120,140,200,300,700,650,250,150,400])
    price=pd.Series(px,index=idx)
    fx_idx=pd.date_range(idx[0]-pd.Timedelta(days=10),idx[-1],
                         freq="D",tz="UTC")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fx_idx),1.5)},index=fx_idx)
    return price,fx


class TaxAwareRoundtripTests(unittest.TestCase):
    def test_synthetic_fixed_seller_same_initial_and_sell_quantity(self):
        price,fx=synthetic()
        terminal=HALVING+pd.Timedelta(days=1150)
        a=replay_roundtrip(price,fx,HALVING,terminal,
                           seller="fixed_525_to_560",buyer=BUYERS[0])
        b=replay_roundtrip(price,fx,HALVING,terminal,
                           seller="fixed_525_to_560",buyer=BUYERS[1])
        self.assertTrue(a["complete_window"])
        self.assertTrue(b["complete_window"])
        self.assertEqual(a["original_btc"],b["original_btc"])
        self.assertEqual(a["sell_fills"],6)
        self.assertEqual(b["sell_fills"],6)
        self.assertEqual(a["sales"],b["sales"])
        self.assertAlmostEqual(a["btc_sold"],a["original_btc"],places=6)
        self.assertGreater(a["smsf_tax_escrow_paid_aud"],0)
        self.assertGreater(b["smsf_tax_escrow_paid_aud"],0)
        self.assertGreaterEqual(a["cash_remaining_aud"],0)
        self.assertGreaterEqual(b["cash_remaining_aud"],0)
        self.assertTrue(a["no_external_cash"])
        self.assertTrue(b["no_external_cash"])
        self.assertGreaterEqual(a["net_sale_proceeds_reinvested_pct"],0)
        self.assertLessEqual(b["net_sale_proceeds_reinvested_pct"],100.001)
        self.assertGreater(a["hold_btc"],0)
        self.assertGreater(b["hold_after_hypothetical_liquidation_cgt_aud"],0)

    def test_post_cutoff_prices_are_not_used_by_prior_decisions(self):
        price,fx=synthetic()
        end=HALVING+pd.Timedelta(days=910)
        a=replay_roundtrip(price,fx,HALVING,end,
                           seller="fixed_525_to_560",buyer=BUYERS[1])
        modified=price.copy()
        modified.loc[modified.index>end]=1e8
        b=replay_roundtrip(modified,fx,HALVING,end,
                           seller="fixed_525_to_560",buyer=BUYERS[1])
        self.assertEqual(a,b)
        self.assertIsNone(a["meets_20pct_vwap_with_50pct_deployment"])
        self.assertIsNone(a["meets_25pct_vwap_with_50pct_deployment"])

    def test_dynamic_seller_is_self_financing_on_same_start(self):
        price,fx=synthetic()
        end=HALVING+pd.Timedelta(days=1150)
        accounts=[replay_roundtrip(price,fx,HALVING,end,
                    seller="dynamic_90pct_holdback20pct",buyer=b)
                  for b in BUYERS]
        self.assertEqual(accounts[0]["original_btc"],accounts[1]["original_btc"])
        self.assertGreaterEqual(accounts[0]["btc_sold"],0)
        self.assertTrue(all(x["cash_remaining_aud"]>=0 for x in accounts))
        self.assertTrue(all(x["btc_remaining"]>=0 for x in accounts))
        self.assertTrue(all(x["liquidated_aud_vs_hold_pct"] is not None
                            for x in accounts))

    def test_missing_prior_fx_fails_closed(self):
        price,fx=synthetic()
        fx=fx.loc[:HALVING+pd.Timedelta(days=530)]
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            replay_roundtrip(price,fx,HALVING,
                             HALVING+pd.Timedelta(days=1150),
                             seller=SELLERS[0],buyer=BUYERS[1])

    def test_never_sells_or_buys_with_future_observation(self):
        price,fx=synthetic()
        end=HALVING+pd.Timedelta(days=860)
        out=replay_roundtrip(price,fx,HALVING,end,
                             seller=SELLERS[0],buyer=BUYERS[1])
        dates=[pd.Timestamp(row["date"]) for row in out["buybacks"]]
        self.assertTrue(all(d>=pd.Timestamp(HALVING+pd.Timedelta(days=BUY_START_DAY)).tz_localize(None)
                            for d in dates))
        self.assertTrue(all(d<=end.tz_localize(None) for d in dates))
        self.assertTrue(all((right-left).days>=7 for left,right in zip(dates,dates[1:])))
        sale_dates={x["date"] for x in out["sales"]}
        self.assertFalse(any(b["date"] in sale_dates for b in out["buybacks"]))

    def test_adverse_fill_slippage_reduces_after_tax_terminal_value(self):
        price,fx=synthetic()
        end=HALVING+pd.Timedelta(days=1150)
        values=[
            replay_roundtrip(price,fx,HALVING,end,
                seller=SELLERS[0],buyer=BUYERS[1],
                execution_slippage_bps=bps)
            for bps in (0,100,200)
        ]
        self.assertGreater(values[0]["account_after_hypothetical_liquidation_cgt_aud"],
                           values[1]["account_after_hypothetical_liquidation_cgt_aud"])
        self.assertGreater(values[1]["account_after_hypothetical_liquidation_cgt_aud"],
                           values[2]["account_after_hypothetical_liquidation_cgt_aud"])
        self.assertEqual([v["execution_slippage_bps"] for v in values],
                         [0.0,100.0,200.0])
        for value in values:
            self.assertGreaterEqual(value["cash_remaining_aud"],0)
            self.assertTrue(value["no_external_cash"])

    def test_policy_and_insufficient_history_fail_closed(self):
        price,fx=synthetic()
        end=HALVING+pd.Timedelta(days=900)
        with self.assertRaisesRegex(ValueError,"Unrecognised"):
            replay_roundtrip(price,fx,HALVING,end,
                             seller=SELLERS[0],buyer="unverified_new_model")
        with self.assertRaisesRegex(ValueError,"bounded adverse"):
            replay_roundtrip(price,fx,HALVING,end,seller=SELLERS[0],
                             buyer=BUYERS[1],execution_slippage_bps=-50)
        with self.assertRaisesRegex(ValueError,"Terminal outside"):
            replay_roundtrip(price,fx,HALVING,
                             HALVING+pd.Timedelta(days=500),
                             seller=SELLERS[0],buyer=BUYERS[1])


if __name__=="__main__":
    unittest.main()
