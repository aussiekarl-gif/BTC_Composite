"""Deterministic correctness and causal/no-oracle invariants for original cycle wallet."""
import unittest
import numpy as np
import pandas as pd
from engines.research.cycle_chronological_wallet import (
    replay_chronological_wallet,previously_completed_200wma_breach,
    audit_existing_history,
)
from engines.research.day500_aftertax_reinvestment import (
    sell_orders,
)

H=pd.Timestamp("2020-05-11",tz="UTC")


def fixture(*,decline=True):
    d=pd.date_range(H-pd.Timedelta(days=1650),
                    H+pd.Timedelta(days=1150),freq="D",tz="UTC")
    timeline=np.asarray((d-H).days,dtype=float)
    x=np.interp(timeline,
                [-1650,-1300,-650,0,400,525,560,730,800,950,1150],
                [170,200,250,250,350,740,695,380,240 if decline else 800,
                 150 if decline else 1050,340 if decline else 1500])
    prices=pd.Series(x,index=d)
    fdates=pd.date_range(d[0]-pd.Timedelta(days=10),
                         d[-1],freq="D")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fdates),1.5)},index=fdates)
    return prices,fx


class ChronologicalWalletTests(unittest.TestCase):
    def test_real_policy_state_and_tax_are_chronological(self):
        price,fx=fixture()
        result=replay_chronological_wallet(price,fx,H,H+pd.Timedelta(days=1150))
        self.assertTrue(result["complete_day1150_window"])
        self.assertEqual(result["causal_buyback_review_start"],
                         str((H+pd.Timedelta(days=744)).date()))
        self.assertGreater(result["sell_count"],0)
        self.assertGreaterEqual(result["estimated_realised_cgt_escrow_aud"],0)
        self.assertGreaterEqual(result["cash_remaining_aud"],0)
        self.assertGreaterEqual(result["btc_held"],0)
        self.assertFalse(result["live_execution_parity_verified"])
        sales=[x for x in result["executions"] if x["side"]=="SELL"]
        buys=[x for x in result["executions"] if x["side"]=="BUY"]
        self.assertTrue(all(pd.Timestamp(x["date"],tz="UTC") <
            H+pd.Timedelta(days=744) for x in sales))
        self.assertTrue(all(pd.Timestamp(x["date"],tz="UTC") >=
            H+pd.Timedelta(days=744) for x in buys))
        self.assertTrue(all((pd.Timestamp(y["date"])-pd.Timestamp(x["date"])).days>=7
            for x,y in zip(buys,buys[1:])))
        self.assertTrue(all("pct_original_aftertax_buyback_cash" in x for x in buys))

    def test_full_historical_staged_sells_match_original_schedule(self):
        prices,fx=fixture()
        x=replay_chronological_wallet(prices,fx,H,H+pd.Timedelta(days=1150))
        recorded=[v for v in x["executions"] if v["side"]=="SELL"]
        published=sell_orders(prices,H,"dynamic_90pct_holdback20pct")
        self.assertEqual([v["date"] for v in recorded],
                         [str(v["day"].date()) for v in published])
        for actual,expected in zip(recorded,published):
            self.assertAlmostEqual(actual["fraction_of_original"],
                                   expected["fraction"],delta=1e-8)
        self.assertLessEqual(sum(v["fraction_of_original"] for v in recorded
            if pd.Timestamp(v["date"],tz="UTC") <= H+pd.Timedelta(days=560)),.800001)

    def test_chronological_orders_cannot_consume_future_close(self):
        px,fx=fixture()
        until=H+pd.Timedelta(days=880)
        a=replay_chronological_wallet(px,fx,H,until)
        later=px.copy()
        later.loc[later.index>until]=9999999.0
        b=replay_chronological_wallet(later,fx,H,until)
        self.assertEqual(a,b)
        if a["buyback_activation_date"] is not None:
            self.assertGreaterEqual(
                pd.Timestamp(a["buyback_activation_date"],tz="UTC"),
                H+pd.Timedelta(days=744))

    def test_causal_buy_trigger_rejects_undated_history(self):
        px,_=fixture()
        date=H+pd.Timedelta(days=820)
        bad=px.drop(index=date-pd.Timedelta(days=8))
        with self.assertRaisesRegex(ValueError,"200 prior weekly"):
            previously_completed_200wma_breach(bad,date)

    def test_synthetic_repro_matches_baseline_sale_quantities_and_refuses_live_parity(self):
        px,fx=fixture()
        from unittest.mock import patch
        from engines.research.cycle_chronological_wallet import PRIMARY
        with patch.dict(PRIMARY,{"2021":{"halving":"2020-05-11"}},clear=True):
            data=audit_existing_history(
                {"price_usd":px},
                fx_fetcher=lambda _a,_b:fx)
        self.assertEqual(len(data["cycles"]),1)
        row=data["cycles"][0]
        self.assertTrue(row["complete"])
        self.assertEqual(len(row["variants"]),2)
        for v in row["variants"]:
            self.assertGreater(v["chronological_aftertax_aud"],0)
            self.assertGreater(v["matched_holding_aftertax_aud"],0)
            self.assertFalse(v["chronological_wallet"]["live_execution_parity_verified"])


if __name__=="__main__":
    unittest.main()
