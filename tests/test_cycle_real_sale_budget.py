"""Prove original FIFO proceeds, optional verified reserve, dated cash controls."""
import copy
import unittest

import numpy as np
import pandas as pd

from engines.research.cycle_real_sale_budget import (
    original_sale_cash_reconciliation,original_buyback_preview,
)

H=pd.Timestamp("2024-04-20",tz="UTC")
ASOF="2026-10-15"
SELL_DATE="02/09/25"
BUY_AFTER="11/05/26"


def prices():
    idx=pd.date_range("2018-01-01","2026-10-15",freq="D",tz="UTC")
    price=pd.Series(np.full(len(idx),100.0),index=idx)
    price.loc[price.index>=pd.Timestamp("2026-05-03",tz="UTC")]=50.
    return price


def buy(date,qty,spent,fee=3,asset="ASX:IBIT"):
    return {"Date":date,"Asset":asset,"Units / BTC Received":qty,
            "AUD Spent":spent,"Brokerage / Fee AUD":fee,
            "BTC AUD Price":100000.}


def sell(date,qty,proceeds,fee=3,asset="ASX:IBIT"):
    return {"Date":date,"Asset":asset,"Units Sold":qty,
            "AUD Proceeds":proceeds,"Brokerage / Fee AUD":fee}


def portfolio(*,new_2026=False,has_sale=True,has_rebuy=False):
    p={"starting_capital_aud":500000.,"rows":[
        buy("01/01/26" if new_2026 else "01/05/24",100,10000,20),
    ],"sales":[]}
    if has_sale:
        p["sales"].append(sell(SELL_DATE,50,20000,10))
    if has_rebuy:
        p["rows"].append(buy(BUY_AFTER,3,1000,3))
    return p


class RealSaleCashBudgetTests(unittest.TestCase):
    def test_original_fifo_sale_net_proceeds_and_tax_estimate(self):
        s=original_sale_cash_reconciliation(
            portfolio(),H,asof=ASOF)
        self.assertEqual(s["original_holdings_at_day500"]["ASX:IBIT"],100)
        self.assertEqual(s["original_units_sold_in_review"]["ASX:IBIT"],50)
        self.assertEqual(s["original_net_sale_proceeds_before_cgt_aud"],19990)
        # Half of A$10,020 acquisition basis=5,010; gain 14,980.
        self.assertEqual(s["illustrative_unpaid_smsf_cgt_reserve_aud"],1498)
        self.assertEqual(s["illustrative_aftertax_sale_cash_aud"],18492)
        self.assertEqual(s["qualifying_sale_count"],1)
        self.assertFalse(s["tax_reserve_verified"])
        self.assertFalse(s["place_order"])

    def test_new_2026_ibit_sale_cannot_be_a_historical_2025_sale(self):
        s=original_sale_cash_reconciliation(
            portfolio(new_2026=True,has_sale=False),H,asof=ASOF)
        self.assertEqual(s["original_holdings_at_day500"]["ASX:IBIT"],0)
        self.assertEqual(s["original_net_sale_proceeds_before_cgt_aud"],0)
        p=portfolio(new_2026=True,has_sale=False)
        p["sales"]=[sell("01/06/26",50,20000,10)]
        s=original_sale_cash_reconciliation(p,H,asof=ASOF)
        self.assertEqual(s["qualifying_sale_count"],0)
        self.assertIsNone(original_buyback_preview(
            p,prices(),H,asof=ASOF)["read_only_historical_review_aud"])

    def test_unconfirmed_tax_reserve_blocks_dollar_preview(self):
        p=portfolio(has_rebuy=True)
        info=original_buyback_preview(p,prices(),H,asof=ASOF)
        self.assertTrue(info["buyback_phase_observed"])
        self.assertIsNotNone(info["last_review_buy_pct_of_original_budget"])
        self.assertIsNone(info["read_only_historical_review_aud"])
        self.assertIsNone(info["reconciled_original_aftertax_budget_aud"])
        self.assertFalse(info["broker_order_allowed"])

    def test_confirmed_tax_floor_debits_all_later_buys_once(self):
        p=portfolio(has_rebuy=True)
        t=original_buyback_preview(
            p,prices(),H,asof=ASOF,
            verified_unpaid_tax_reserve_aud=1498,
            verified_broker_cash_before_tax_aud=100000,confirmation=True)
        self.assertTrue(t["tax_reserve_verified"])
        self.assertEqual(t["reconciled_original_aftertax_budget_aud"],18492)
        self.assertEqual(t["all_later_buys_including_fees_aud"],1003)
        self.assertEqual(t["reconciled_unused_buyback_budget_aud"],17489)
        self.assertEqual(t["last_review_buy_pct_of_original_budget"],2.5)
        self.assertEqual(t["read_only_historical_review_aud"],462.30)
        self.assertFalse(t["broker_order_allowed"])
        self.assertFalse(t["place_order"])

    def test_confirmed_available_broker_cash_is_strict_cap(self):
        p=portfolio()
        preview=original_buyback_preview(
            p,prices(),H,asof=ASOF,
            verified_unpaid_tax_reserve_aud=1498,
            verified_broker_cash_before_tax_aud=1600,
            confirmation=True)
        self.assertEqual(preview["cash_net_unpaid_tax_escrow_aud"],102)
        self.assertEqual(preview["read_only_historical_review_aud"],102)
        zero=original_buyback_preview(
            p,prices(),H,asof=ASOF,
            verified_unpaid_tax_reserve_aud=1498,
            verified_broker_cash_before_tax_aud=1000,
            confirmation=True)
        self.assertEqual(zero["read_only_historical_review_aud"],0)
        with self.assertRaisesRegex(ValueError,"broker available cash"):
            original_buyback_preview(
                p,prices(),H,asof=ASOF,
                verified_unpaid_tax_reserve_aud=1498,confirmation=True)

    def test_same_research_review_buy_prevents_second_preview(self):
        p=portfolio(has_rebuy=False)
        q=original_buyback_preview(
            p,prices(),H,asof=ASOF,verified_unpaid_tax_reserve_aud=1498,
            verified_broker_cash_before_tax_aud=100000,
            confirmation=True)
        review=pd.Timestamp(q["last_weekly_research_review_date"])
        p["rows"].append(buy(review.strftime("%d/%m/%y"),2,400,3))
        s=original_buyback_preview(
            p,prices(),H,asof=ASOF,verified_unpaid_tax_reserve_aud=1498,
            verified_broker_cash_before_tax_aud=100000,
            confirmation=True)
        self.assertTrue(s["already_recorded_buy_on_review_day"])
        self.assertEqual(s["read_only_historical_review_aud"],0)

    def test_tax_reserve_must_be_in_range_and_confirmed(self):
        p=portfolio()
        for value in (-1,20000,float("inf")):
            with self.assertRaises(ValueError):
                original_buyback_preview(
                    p,prices(),H,asof=ASOF,
                    verified_unpaid_tax_reserve_aud=value,
                    verified_broker_cash_before_tax_aud=100000,
                    confirmation=True)
        with self.assertRaisesRegex(ValueError,"required"):
            original_buyback_preview(
                p,prices(),H,asof=ASOF,confirmation=True)

    def test_future_trades_do_not_influence_asof_budget(self):
        p=portfolio(has_rebuy=False)
        first=original_sale_cash_reconciliation(p,H,asof=ASOF)
        q=copy.deepcopy(p)
        q["rows"].append(buy("16/10/26",2,300,3))
        second=original_sale_cash_reconciliation(q,H,asof=ASOF)
        self.assertEqual(first["ledger_fingerprint"],second["ledger_fingerprint"])
        self.assertEqual(first["original_net_sale_proceeds_before_cgt_aud"],
                         second["original_net_sale_proceeds_before_cgt_aud"])
        self.assertTrue(second["unrecorded_future_transactions_ignored"])

    def test_nonoriginal_sales_after_day730_not_counted(self):
        p=portfolio()
        p["sales"].append(sell("01/10/26",25,30000,10))
        s=original_sale_cash_reconciliation(p,H,asof=ASOF)
        self.assertEqual(s["original_holdings_at_day500"]["ASX:IBIT"],100)
        self.assertEqual(s["original_units_sold_in_review"]["ASX:IBIT"],50)
        self.assertEqual(s["original_net_sale_proceeds_before_cgt_aud"],19990)

    def test_oversold_or_missing_cost_basis_fails_closed(self):
        p=portfolio()
        p["sales"].append(sell("01/10/26",60,50000,10))
        with self.assertRaisesRegex(ValueError,"exceeds"):
            original_sale_cash_reconciliation(p,H,asof=ASOF)
        p=portfolio()
        p["rows"][0]["AUD Spent"]=None
        with self.assertRaises(ValueError):
            original_sale_cash_reconciliation(p,H,asof=ASOF)


if __name__=="__main__":
    unittest.main()
