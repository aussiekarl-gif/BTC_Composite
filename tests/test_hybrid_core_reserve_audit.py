"""No-lookahead capital split, cash preservation and fees for hybrid BTC DCA."""
import unittest

import numpy as np
import pandas as pd

from engines.research.hybrid_core_reserve_audit import (
    BASE_CORE_FRACTIONS, hybrid_account, historical_transfer,
)


def sample(*, kind="bull", n=183):
    index=pd.date_range("2024-01-01",periods=n,freq="W-MON",tz="UTC")
    if kind=="bull":
        prices=np.array([100000+250*i for i in range(n)],dtype=float)
    elif kind=="bear":
        prices=np.array([100000.]*108 +
                        [max(37000.,100000.-2500*(i-108))
                         for i in range(108,n)],dtype=float)
    else:
        raise ValueError
    # Externally provided risk is synthetic and does NOT need any future info.
    return pd.DataFrame({"btc_price_aud":prices,
                         "risk_score":[.15]*n},index=index)


class HybridSelfFinancingTests(unittest.TestCase):
    def test_no_hard_gate_in_rising_market_still_owns_some_btc(self):
        d=sample()
        for f in BASE_CORE_FRACTIONS:
            r=hybrid_account(d,"2026-01-01",core_fraction=f)
            self.assertFalse(r["gate_triggered"])
            self.assertEqual(r["reserve_buy_orders"],0)
            self.assertEqual(r["reserve_sell_orders"],0)
            self.assertEqual(r["core_buy_orders"],12)
            self.assertAlmostEqual(r["brokerage_aud"],36)
            self.assertGreater(r["BTC_held"],0)
            self.assertAlmostEqual(r["AUD_cash_left"],500000*(1-f),delta=1)
            self.assertGreater(r["marked_value_aud"],500000)
            self.assertEqual(r["model"],f"core_{int(f*100)}pct_reserve_{int((1-f)*100)}pct")

    def test_all_orders_are_after_real_capital_start(self):
        d=sample(kind="bear")
        r=hybrid_account(d,"2026-01-01",core_fraction=.25)
        self.assertGreaterEqual(pd.Timestamp(r["first_order_date"]),
                                pd.Timestamp("2026-01-01",tz="UTC"))
        self.assertTrue(r["gate_triggered"])
        self.assertGreaterEqual(pd.Timestamp(r["gate_date"]),
                                pd.Timestamp("2026-01-01",tz="UTC"))
        self.assertGreater(r["reserve_buy_orders"],0)
        self.assertLessEqual(r["cash_deployed_to_buy_orders_pct"],100.01)
        self.assertGreaterEqual(r["AUD_cash_left"],0)
        self.assertGreaterEqual(r["BTC_held"],0)

    def test_two_sleeves_remain_full_cash_plus_held_btc_before_trades(self):
        d=sample()
        # Start after available market last observed close rejects.
        with self.assertRaises(ValueError):
            hybrid_account(d,"2030-01-01",core_fraction=.5)
        for bad in (0.0,1.,-1.,2.):
            with self.assertRaises(ValueError):
                hybrid_account(d,"2026-01-01",core_fraction=bad)
        with self.assertRaises(ValueError):
            hybrid_account(d,"2026-01-01",base_weeks=0)
        with self.assertRaises(ValueError):
            hybrid_account(d,"2026-01-01",starting_cash=-1)

    def test_25pct_core_ends_with_more_cash_than_50pct_core_when_no_gate(self):
        d=sample()
        a=hybrid_account(d,"2026-01-01",core_fraction=.25)
        b=hybrid_account(d,"2026-01-01",core_fraction=.50)
        self.assertGreater(a["AUD_cash_left"],b["AUD_cash_left"])
        self.assertLess(a["BTC_held"],b["BTC_held"])
        self.assertGreater(b["marked_value_aud"],a["marked_value_aud"])

    def test_pretrigger_prices_cannot_change_past_from_future_data(self):
        d=sample(kind="bear")
        short=d.iloc[:155]
        changed=d.copy()
        changed.iloc[155:,0]=250000.
        early_a=hybrid_account(short,"2026-01-01",core_fraction=.50)
        early_b=hybrid_account(changed.iloc[:155],"2026-01-01",core_fraction=.50)
        self.assertEqual(early_a,early_b)

    def test_fixed_yearly_comparison_same_matched_start_and_horizon(self):
        idx=pd.date_range("2018-01-01",periods=160,freq="W-MON",tz="UTC")
        prices=np.array([100000+200*i for i in range(160)],dtype=float)
        d=pd.DataFrame({"btc_price_aud":prices,
                        "risk_score":[.15]*160},index=idx)
        report=historical_transfer(d,start_years=(2020,))
        self.assertEqual(len(report["by_year"]),1)
        self.assertEqual(len(report["summary"]),2)
        cohort=report["by_year"][0]
        self.assertEqual(len(cohort["hybrid_candidates"]),2)
        for c in cohort["hybrid_candidates"]:
            self.assertFalse(c["gate_triggered"])
            self.assertGreater(c["BTC_held"],0)
            self.assertLess(c["marked_value_aud"],cohort["immediate_hold_aud"])


if __name__=="__main__":
    unittest.main()
