"""Prospective original-200WMA adaptation: no backdating, stable AUD budget."""
import copy
import unittest

import numpy as np
import pandas as pd

from engines.research.cycle_forward_cash_dca import (
    CONFIG_KEY,make_forward_cash_enrolment,enrol_with_stale_guard,
    forward_cash_dca_status,
)

TODAY="2026-10-17"
START=pd.Timestamp(TODAY,tz="UTC")


def price_history():
    idx=pd.date_range(pd.Timestamp("2018-01-01",tz="UTC"),
                      pd.Timestamp("2026-12-10",tz="UTC"),freq="D")
    vals=np.full(len(idx),100.,dtype=float)
    vals[idx>=pd.Timestamp("2026-11-01",tz="UTC")]=50.
    return pd.Series(vals,index=idx)


def buy(date,qty,spent,source=None,asset="ASX:IBIT"):
    row={
        "Date":date,"Asset":asset,"Units / BTC Received":qty,
        "AUD Spent":spent,"Brokerage / Fee AUD":3.,
        "BTC AUD Price":100000.,
    }
    if source is not None: row["Funding Source"]=source
    return row


def portfolio():
    return {
        "starting_capital_aud":500000.,
        "rows":[buy("01/05/26",20,20000.)],
        "sales":[],
    }


def enroll(p=None,*,initial=20000.,broker=100000.):
    return make_forward_cash_enrolment(
        portfolio() if p is None else p,
        start_date=TODAY,budget_aud=initial,
        broker_available_after_reserves_aud=broker,
        confirmed=True,today=TODAY,
    )


class ForwardFixedCashDCATests(unittest.TestCase):
    def test_reconciled_new_cash_budget_cannot_invent_2025_sale(self):
        p=enroll()
        self.assertNotIn("sales",p[CONFIG_KEY])
        self.assertEqual(p[CONFIG_KEY]["initial_budget_aud"],20000.)
        self.assertEqual(p[CONFIG_KEY]["start_date"],TODAY)
        self.assertIn("NOT historical day500",p[CONFIG_KEY]["basis"])
        self.assertEqual(p["rows"],portfolio()["rows"])
        self.assertEqual(p["sales"],[])
        self.assertTrue(p[CONFIG_KEY]["research_only"])
        view=forward_cash_dca_status(price_history(),p,asof="2026-11-02",
                                      broker_cash_after_reserves_aud=10000.)
        self.assertEqual(view["trigger_date"],"2026-11-02")
        self.assertEqual(view["phase"],"REVIEW_RESEARCH_ONLY")
        self.assertEqual(view["current_review_pct_original_budget"],2.5)
        self.assertEqual(view["research_review_aud"],500.)
        self.assertEqual(view["original_fresh_cash_budget_aud"],20000.)
        self.assertEqual(view["spent_since_enrolment_aud"],0.)
        self.assertFalse(view["broker_order_allowed"])
        self.assertFalse(view["historical_live_parity_verified"])

    def test_frozen_original_denominator_not_remaining_cash(self):
        p=enroll()
        p["rows"].append(buy("03/11/26",1,850.))
        v=forward_cash_dca_status(price_history(),p,asof="2026-11-09",
                                  broker_cash_after_reserves_aud=100000.)
        self.assertEqual(v["phase"],"ALREADY_RECORDED_BUY_THIS_WEEK")
        self.assertEqual(v["original_fresh_cash_budget_aud"],20000.)
        self.assertEqual(v["spent_since_enrolment_aud"],853.)
        self.assertEqual(v["remaining_unspent_budget_aud"],19147.)
        self.assertIsNone(v["research_review_aud"])
        # On the following weekly date the next tranche is 2.5% of ORIGINAL
        # 20000, NOT 2.5% of 19147.
        v=forward_cash_dca_status(price_history(),p,asof="2026-11-16",
                                  broker_cash_after_reserves_aud=100000.)
        self.assertEqual(v["phase"],"REVIEW_RESEARCH_ONLY")
        self.assertEqual(v["research_review_aud"],500.)

    def test_no_retroactive_trigger_and_between_week_no_order(self):
        p=enroll()
        v=forward_cash_dca_status(price_history(),p,asof="2026-10-18",
                                  broker_cash_after_reserves_aud=10000.)
        self.assertEqual(v["phase"],"WAITING_BELOW_200WMA")
        self.assertIsNone(v["trigger_date"])
        later=forward_cash_dca_status(price_history(),p,asof="2026-11-04",
                                      broker_cash_after_reserves_aud=10000.)
        self.assertEqual(later["phase"],"BETWEEN_WEEKLY_REVIEWS")
        self.assertEqual(later["last_completed_review_date"],"2026-11-02")
        self.assertEqual(later["next_review_date"],"2026-11-09")
        self.assertIsNone(later["current_review_pct_original_budget"])
        self.assertIsNone(later["research_review_aud"])

    def test_research_cash_quote_requires_verified_broker_after_reserves(self):
        p=enroll()
        no_cash=forward_cash_dca_status(price_history(),p,asof="2026-11-02")
        self.assertEqual(no_cash["phase"],"BROKER_CASH_REQUIRED")
        self.assertIsNone(no_cash["research_review_aud"])
        small=forward_cash_dca_status(price_history(),p,asof="2026-11-02",
                                     broker_cash_after_reserves_aud=200.)
        self.assertEqual(small["research_review_aud"],200.)
        zero=forward_cash_dca_status(price_history(),p,asof="2026-11-02",
                                    broker_cash_after_reserves_aud=0.)
        self.assertEqual(zero["research_review_aud"],0.)

    def test_same_review_trade_blocks_repeated_allocation(self):
        p=enroll()
        p["rows"].append(buy("02/11/26",1,350.))
        v=forward_cash_dca_status(price_history(),p,asof="2026-11-02",
                                  broker_cash_after_reserves_aud=100000.)
        self.assertEqual(v["phase"],"ALREADY_RECORDED_BUY_THIS_WEEK")
        self.assertIsNone(v["research_review_aud"])
        self.assertEqual(v["spent_since_enrolment_aud"],353.)

    def test_independent_cash_does_not_create_extra_broker_cash(self):
        p=enroll()
        p["rows"].append(buy("03/11/26",1,1000.,"Independent cash"))
        v=forward_cash_dca_status(price_history(),p,asof="2026-11-16",
                                  broker_cash_after_reserves_aud=100.)
        self.assertEqual(v["remaining_unspent_budget_aud"],20000.)
        self.assertEqual(v["independently_funded_spending_aud"],1003.)
        self.assertEqual(v["research_review_aud"],100.)
        self.assertEqual(v["recorded_account_cash_aud"],478994.)

    def test_edited_past_trades_invalidate_frozen_budget(self):
        p=enroll()
        edited=copy.deepcopy(p)
        edited["rows"][0]["AUD Spent"]=20001.
        with self.assertRaisesRegex(ValueError,"Pre-enrolment"):
            forward_cash_dca_status(price_history(),edited,asof="2026-11-02")
        p["rows"].append(buy("03/11/26",1,300.))
        v=forward_cash_dca_status(price_history(),p,asof="2026-11-16",
                                  broker_cash_after_reserves_aud=100000.)
        self.assertEqual(v["remaining_unspent_budget_aud"],19697.)

    def test_cannot_backdate_enrollment_or_use_unverified_cash(self):
        p=portfolio()
        with self.assertRaisesRegex(ValueError,"today only"):
            make_forward_cash_enrolment(
                p,start_date="2026-09-01",budget_aud=20000.,
                broker_available_after_reserves_aud=20000.,
                confirmed=True,today=TODAY)
        with self.assertRaisesRegex(ValueError,"Confirm"):
            make_forward_cash_enrolment(
                p,start_date=TODAY,budget_aud=20000.,
                broker_available_after_reserves_aud=20000.,
                confirmed=False,today=TODAY)
        with self.assertRaisesRegex(ValueError,"exceeds verified"):
            make_forward_cash_enrolment(
                p,start_date=TODAY,budget_aud=20000.,
                broker_available_after_reserves_aud=1000.,
                confirmed=True,today=TODAY)
        with self.assertRaisesRegex(ValueError,"already configured"):
            enroll(enroll())

    def test_stale_guard_and_future_recorded_rows(self):
        p=portfolio()
        older=copy.deepcopy(p)
        newer=copy.deepcopy(p)
        newer["rows"].append(buy("02/10/26",1,200.))
        with self.assertRaisesRegex(ValueError,"changed since page load"):
            enrol_with_stale_guard(
                older,newer,start_date=TODAY,budget_aud=2000.,
                broker_available_after_reserves_aud=2000.,
                confirmed=True,today=TODAY)
        p["rows"].append(buy("18/10/26",1,400.))
        with self.assertRaisesRegex(ValueError,"Future-dated"):
            enroll(p)

    def test_missing_market_and_unverified_price_never_quote(self):
        p=enroll()
        stale=forward_cash_dca_status(price_history(),p,asof="2026-11-02",
                                      feed_verified=False,
                                      broker_cash_after_reserves_aud=100000.)
        self.assertEqual(stale["phase"],"UNVERIFIED_PRICE_FEED")
        self.assertIsNone(stale["research_review_aud"])
        missing=price_history().drop(pd.Timestamp("2026-11-02",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"Dated, complete"):
            forward_cash_dca_status(missing,p,asof="2026-11-02",
                                    broker_cash_after_reserves_aud=100000.)

    def test_future_prices_do_not_change_past_review(self):
        p=enroll()
        first=forward_cash_dca_status(price_history(),p,asof="2026-11-02",
                                      broker_cash_after_reserves_aud=100000.)
        future=price_history().copy()
        future.loc[future.index>pd.Timestamp("2026-11-02",tz="UTC")]=1e7
        second=forward_cash_dca_status(future,p,asof="2026-11-02",
                                       broker_cash_after_reserves_aud=100000.)
        self.assertEqual(first,second)


if __name__=="__main__":
    unittest.main()
