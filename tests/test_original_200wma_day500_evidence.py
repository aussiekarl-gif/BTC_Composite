"""Evidence inventory: no re-optimisation, no fabricated live parity."""
import unittest
import numpy as np
import pandas as pd
from engines.research.original_200wma_day500_evidence import (
    frozen_policy_facts,run_original_evidence,ORIGINAL_SELLER,
    ORIGINAL_BUYER,
)

HALVING=pd.Timestamp("2020-05-11",tz="UTC")


def synthetic():
    dates=pd.date_range(pd.Timestamp("2013-01-01",tz="UTC"),
                        HALVING+pd.Timedelta(days=1151),freq="D")
    d=np.asarray((dates-HALVING).days,dtype=float)
    close=np.interp(d,[-2700,-1400,-400,0,450,500,550,600,750,850,950,1151],
                    [100,105,130,150,300,420,500,360,220,110,125,240])
    price=pd.Series(close,index=dates)
    fx_dates=pd.date_range(dates[0]-pd.Timedelta(days=12),
                           dates[-1],freq="D")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fx_dates),1.5)},index=fx_dates)
    return price,fx


class FrozenOriginalPolicyTests(unittest.TestCase):
    def test_original_model_definition_is_still_identifiable(self):
        facts=frozen_policy_facts()
        self.assertFalse(facts["historical_parity_with_live_verified"])
        self.assertFalse(facts["user_2026_holdings_recreated_at_2025_day500"])
        self.assertEqual(facts["historical_seller"],ORIGINAL_SELLER)
        self.assertEqual(facts["historical_buy_style"],ORIGINAL_BUYER)
        self.assertEqual(facts["original_position_pre560_sold_cap_pct"],80.)
        self.assertAlmostEqual(
            facts["live_seven_stages_original_btc_remaining_if_all_fill_pct"],
            37.32,places=2)
        self.assertNotEqual(
            facts["historical_buy_budget"],facts["actual_streamlit_ntfy_buy_budget"])

    def test_evidence_invokes_original_existing_roundtrip_not_new_candidate(self):
        # Synthetic retained as a deterministic harness. One historical cycle
        # only; other histories are exercised on GitHub Actions using exports.
        from unittest.mock import patch
        from engines.research.original_200wma_day500_evidence import PRIMARY
        p,fx=synthetic()
        with patch.dict(PRIMARY,{"2021":{"halving":"2020-05-11"}},clear=True):
            evidence=run_original_evidence(
                {"price_usd":p},
                fx_fetcher=lambda _start,_end:fx,
            )
        self.assertEqual(len(evidence["cycles"]),1)
        item=evidence["cycles"][0]
        self.assertTrue(item["complete_window"])
        self.assertEqual(item["historic_cycle"],"2021")
        self.assertEqual(set(item["outcomes"]),
                         {"adaptive_recovery","adaptive_value"})
        for row in item["outcomes"].values():
            self.assertGreaterEqual(row["sell_count"],1)
            self.assertGreaterEqual(row["btc_held_after_buyback"],0)
            self.assertGreaterEqual(row["cash_remaining_aud"],0)
            self.assertGreater(row["hold_hypothetical_liquidated_after_cgt_aud"],0)
        self.assertFalse(evidence["policy"]["historical_parity_with_live_verified"])

    def test_no_mutation_or_future_price_leakage(self):
        # Input after the terminal cannot change outcomes, including dated FX.
        from unittest.mock import patch
        from engines.research.original_200wma_day500_evidence import PRIMARY
        p,fx=synthetic()
        with patch.dict(PRIMARY,{"2021":{"halving":"2020-05-11"}},clear=True):
            a=run_original_evidence(
                {"price_usd":p},fx_fetcher=lambda *_:fx)
            altered=p.copy()
            altered.loc[altered.index>HALVING+pd.Timedelta(days=1150)]=1e9
            b=run_original_evidence(
                {"price_usd":altered},fx_fetcher=lambda *_:fx)
        self.assertEqual(a,b)


if __name__=="__main__":
    unittest.main()
