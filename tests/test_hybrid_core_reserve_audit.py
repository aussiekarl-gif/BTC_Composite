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
    elif kind=="mild_bear":
        prices=np.array([100000.]*105 +
                        [100000.-100*(i-105) for i in range(105,n)],dtype=float)
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

    def test_reserve_fallback_keeps_participating_when_no_large_drop_arrives(self):
        d=sample(kind="bull")
        for fraction in BASE_CORE_FRACTIONS:
            original=hybrid_account(d,"2026-01-01",core_fraction=fraction)
            with_fallback=hybrid_account(
                d,"2026-01-01",core_fraction=fraction,
                fallback_after_weeks=26,fallback_spread_weeks=26)
            self.assertFalse(with_fallback["gate_triggered"])
            self.assertGreater(with_fallback["fallback_buy_orders"],0)
            self.assertGreater(with_fallback["BTC_held"],original["BTC_held"])
            self.assertLess(with_fallback["AUD_cash_left"],original["AUD_cash_left"])
            self.assertGreater(with_fallback["marked_value_aud"],
                               original["marked_value_aud"])

    def test_fallback_only_starts_after_predeclared_elapsed_calendar_weeks(self):
        d=sample(kind="bull")
        # 2026 baseline starts at index 105; no reserve trade before week 26.
        jan=np.flatnonzero(d.index>=pd.Timestamp("2026-01-01",tz="UTC"))[0]
        first_25=hybrid_account(d.iloc[:jan+26],"2026-01-01",
                                core_fraction=.25,fallback_after_weeks=26)
        self.assertEqual(first_25["fallback_buy_orders"],0)
        after_27=hybrid_account(d.iloc[:jan+27],"2026-01-01",
                                core_fraction=.25,fallback_after_weeks=26)
        self.assertEqual(after_27["fallback_buy_orders"],1)

    def test_prior_drawdown_gate_overrides_calendar_fallback(self):
        d=sample(kind="bear")
        a=hybrid_account(d,"2026-01-01",core_fraction=.25)
        b=hybrid_account(d,"2026-01-01",core_fraction=.25,
                         fallback_after_weeks=26)
        self.assertTrue(a["gate_triggered"])
        self.assertEqual(b["fallback_buy_orders"],0)
        self.assertAlmostEqual(a["marked_value_aud"],b["marked_value_aud"])
        self.assertAlmostEqual(a["BTC_held"],b["BTC_held"])

    def test_trend_fallback_pauses_during_mild_decline_without_gate(self):
        d=sample(kind="mild_bear")
        plain=hybrid_account(d,"2026-01-01",core_fraction=.5,
                             fallback_after_weeks=26)
        filtered=hybrid_account(d,"2026-01-01",core_fraction=.5,
                                fallback_after_weeks=26,
                                fallback_requires_trend=True)
        self.assertFalse(plain["gate_triggered"])
        self.assertFalse(filtered["gate_triggered"])
        self.assertGreater(plain["fallback_buy_orders"],0)
        self.assertEqual(filtered["fallback_buy_orders"],0)
        self.assertGreater(filtered["AUD_cash_left"],plain["AUD_cash_left"])
        self.assertGreater(filtered["marked_value_aud"],plain["marked_value_aud"])

    def test_trend_fallback_has_no_fixed_end_date_and_joins_rally(self):
        d=sample(kind="bull")
        filtered=hybrid_account(d,"2026-01-01",core_fraction=.25,
                                fallback_after_weeks=26,
                                fallback_requires_trend=True)
        self.assertEqual(filtered["fallback_buy_orders"],26)
        self.assertAlmostEqual(filtered["brokerage_aud"],3*(12+26))
        self.assertGreater(filtered["BTC_held"],0)
        self.assertLess(filtered["AUD_cash_left"],1.)

    def test_early_deep_gate_supersedes_both_fallback_styles(self):
        d=sample(kind="bear")
        plain=hybrid_account(d,"2026-01-01",core_fraction=.25)
        filtered=hybrid_account(d,"2026-01-01",core_fraction=.25,
                                fallback_after_weeks=26,
                                fallback_requires_trend=True)
        self.assertTrue(filtered["gate_triggered"])
        self.assertEqual(filtered["fallback_buy_orders"],0)
        self.assertEqual(filtered["BTC_held"],plain["BTC_held"])

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
