"""Forward read-only Cycle quick view keeps original and simplified signals separate."""
import copy
import unittest

import numpy as np
import pandas as pd

from engines.research.cycle_forward_quick_view import cycle_forward_quick_view

HALVING=pd.Timestamp("2024-04-20",tz="UTC")


def prices():
    idx=pd.date_range(pd.Timestamp("2018-01-01",tz="UTC"),
                      pd.Timestamp("2026-10-15",tz="UTC"),freq="D")
    vals=np.full(len(idx),100.)
    vals[idx>=pd.Timestamp("2026-05-03",tz="UTC")]=50.
    return pd.Series(vals,index=idx)


def market(asof="2026-10-15"):
    p=prices().loc[:pd.Timestamp(asof,tz="UTC")]
    return {
        "asof_date":asof,
        "halving_date":str(HALVING.date()),
        "price_history":p,
    }


def decision(signal="HOLD",buy=0.,sell=0.):
    return {
        "market_signal":signal,"buy_pct_total_cash":buy,
        "sell_pct_total_holdings":sell,
        "action":"HOLD","action_aud":0.,
    }


def buy(date,qty=100,cost=10000.):
    return {"Date":date,"Asset":"ASX:IBIT",
            "Units / BTC Received":qty,"AUD Spent":cost,
            "Brokerage / Fee AUD":3.,"BTC AUD Price":100000.}


def sells():
    return [{"Date":"02/09/25","Asset":"ASX:IBIT",
             "Units Sold":50.,"AUD Proceeds":20000.,
             "Brokerage / Fee AUD":3.}]


def saved_2026_only():
    return {"starting_capital_aud":500000.,
            "rows":[buy("01/01/26")],"sales":[]}


def saved_original(with_sale=True):
    return {"starting_capital_aud":500000.,
            "rows":[buy("01/05/24")],
            "sales":sells() if with_sale else []}


class ForwardCycleQuickViewTests(unittest.TestCase):
    def test_new_2026_position_cannot_sell_at_past_day500_or_invent_cash(self):
        view=cycle_forward_quick_view(
            market(),saved_2026_only(),decision("BUY WATCH",2.5),
            feed_verified=True)
        self.assertEqual(view["original_phase"],"NO_PRE_DAY500_HOLDINGS")
        self.assertFalse(view["original_position_eligible"])
        self.assertEqual(view["recorded_ibit_units"],100.)
        self.assertIsNone(view["original_next_review_date"])
        self.assertIsNone(view["original_next_pct_original_holdings"])
        self.assertIsNone(view["recorded_original_sale_cash_before_cgt_aud"])
        self.assertIsNone(view["verified_aftertax_original_buyback_budget_aud"])
        self.assertIn("halving +500",view["original_next_review_label"])
        self.assertEqual(view["simplified_buy_pct_remaining_cash"],2.5)
        self.assertFalse(view["historical_to_live_parity_verified"])
        self.assertFalse(view["place_order"])

    def test_real_original_sale_and_200wma_gate_show_only_past_pct(self):
        old=saved_original()
        view=cycle_forward_quick_view(
            market(),old,decision(),feed_verified=True)
        self.assertEqual(view["original_phase"],"WEEKLY_ORIGINAL_REBUY_RESEARCH")
        self.assertGreater(view["recorded_original_sale_cash_before_cgt_aud"],0.)
        self.assertEqual(view["original_position_ibit_units"],100.)
        self.assertEqual(view["last_completed_recovery_review_date"],"2026-10-12")
        self.assertEqual(view["original_next_review_date"],"2026-10-19")
        self.assertEqual(view["last_completed_recovery_pct_original_budget"],2.5)
        self.assertIsNone(view["original_next_pct_original_budget"])
        self.assertIsNone(view["verified_aftertax_original_buyback_budget_aud"])
        self.assertFalse(view["place_order"])

    def test_original_units_with_no_sales_is_not_aftertax_budget(self):
        view=cycle_forward_quick_view(
            market(),saved_original(with_sale=False),decision(),
            feed_verified=True)
        self.assertEqual(view["original_phase"],"NO_ORIGINAL_SALE_PROCEEDS")
        self.assertEqual(view["recorded_original_sale_cash_before_cgt_aud"],0.)
        self.assertIsNone(view["original_next_review_date"])

    def test_today_historical_original_sell_percent_only_from_prior_data(self):
        review_date=str((HALVING+pd.Timedelta(days=500)).date())
        view=cycle_forward_quick_view(
            market(review_date),saved_original(with_sale=False),
            decision("SELL WATCH",0.,5.),feed_verified=True)
        self.assertEqual(view["original_phase"],"ORIGINAL_SELL_REVIEWS")
        self.assertEqual(view["original_next_review_date"],review_date)
        self.assertEqual(view["original_position_ibit_units"],100.)
        self.assertGreater(view["original_next_pct_original_holdings"],0.)
        self.assertFalse(view["place_order"])
        self.assertNotEqual(view["simplified_sell_pct_remaining_holdings"],None)

    def test_feed_failure_supresses_trade_and_future_percentage(self):
        view=cycle_forward_quick_view(
            market(),saved_original(),decision("BUY WATCH",2.5),
            feed_verified=False)
        self.assertEqual(view["simplified_market_signal"],"UNAVAILABLE")
        self.assertIsNone(view["simplified_buy_pct_remaining_cash"])
        self.assertEqual(view["simplified_action"],"HOLD")
        self.assertEqual(view["original_phase"],"ORIGINAL_SALE_CASH_UNVERIFIED_FEED")
        self.assertIsNone(view["original_next_pct_original_budget"])

    def test_unverified_portfolio_blocks_original_sizing(self):
        a=cycle_forward_quick_view(market(),None,decision(),
                                   feed_verified=True)
        self.assertEqual(a["original_phase"],"PORTFOLIO_UNAVAILABLE")
        self.assertIsNone(a["recorded_ibit_units"])
        b=saved_original()
        b["sales"][0]["Units Sold"]=1000
        out=cycle_forward_quick_view(market(),b,decision(),
                                     feed_verified=True)
        self.assertEqual(out["original_phase"],"PORTFOLIO_UNAVAILABLE")
        self.assertIn("ledger",out["original_blocker"])

    def test_portfolio_future_trade_is_excluded_from_asof_snapshot(self):
        p=saved_original(with_sale=False)
        p["rows"].append(buy("01/10/26",25,2500.))
        view=cycle_forward_quick_view(
            market("2025-09-02"),p,decision(),feed_verified=True)
        self.assertEqual(view["recorded_ibit_units"],100.)
        self.assertEqual(view["original_position_ibit_units"],100.)
        self.assertTrue(view["future_ledger_transactions_excluded"])
        self.assertFalse(view["place_order"])

    def test_before_day500_provides_date_not_unearned_sell_amount(self):
        view=cycle_forward_quick_view(
            market("2025-08-20"),
            {"starting_capital_aud":500000.,"rows":[buy("01/05/24")],"sales":[]},
            decision(),feed_verified=True)
        self.assertEqual(view["original_phase"],"BEFORE_ORIGINAL_EXIT_WINDOW")
        self.assertEqual(view["original_next_review_date"],"2025-09-02")
        self.assertIsNone(view["original_next_pct_original_holdings"])

    def test_next_original_rebuy_pct_never_peeks_into_future(self):
        old=saved_original()
        cutoff="2026-06-20"
        m=market(cutoff)
        first=cycle_forward_quick_view(m,old,decision(),feed_verified=True)
        changed=copy.deepcopy(m)
        extended=prices().copy()
        extended.loc[extended.index>pd.Timestamp(cutoff,tz="UTC")]=1e8
        changed["price_history"]=extended
        second=cycle_forward_quick_view(
            changed,old,decision(),feed_verified=True)
        self.assertEqual(first,second)


if __name__=="__main__":
    unittest.main()
