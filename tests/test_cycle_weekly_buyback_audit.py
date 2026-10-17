"""Original 200WMA weekly BUY ledger: parity, attribution and no future buys."""
import copy
import unittest
import numpy as np
import pandas as pd

from engines.research.cycle_weekly_buyback_audit import weekly_original_buyback_ledger
from engines.research.shared_cycle_policy import recovery_buy_budget_fraction
from engines.research.cycle_real_sale_budget import original_sale_cash_reconciliation

H="2024-04-20"
ASOF="2026-10-15"


def market():
    days=pd.date_range(pd.Timestamp("2018-01-01",tz="UTC"),
                       pd.Timestamp(ASOF,tz="UTC"),freq="D")
    close=pd.Series(np.full(len(days),100.0),index=days)
    close.loc[close.index>=pd.Timestamp("2026-05-03",tz="UTC")]=50.
    return close


def buy(date,qty,cost,fee=3,asset="ASX:IBIT",tag=None,cycle=None):
    row={"Date":date,"Asset":asset,"Units / BTC Received":qty,
         "AUD Spent":cost,"Brokerage / Fee AUD":fee,
         "BTC AUD Price":100000.}
    if tag:row["Funding Source"]=tag
    if cycle:row["Funding Cycle Halving"]=cycle
    return row


def saved():
    return {"starting_capital_aud":500000.,
            "rows":[buy("01/05/24",100,10000,20),
                    buy("11/05/26",3,1000,3),
                    buy("18/05/26",5,2000,5)],
            "sales":[{"Date":"02/09/25","Asset":"ASX:IBIT",
                      "Units Sold":50,"AUD Proceeds":20000,
                      "Brokerage / Fee AUD":10}]}


class DatedWeeklyBuyAuditTests(unittest.TestCase):
    def test_unreviewed_ledger_reconciles_exactly_with_budget(self):
        portfolio=saved()
        a=weekly_original_buyback_ledger(market(),H,portfolio,asof=ASOF)
        b=original_sale_cash_reconciliation(portfolio,H,asof=ASOF)
        self.assertTrue(a["research_only"])
        self.assertFalse(a["live_trade_parity_verified"])
        self.assertFalse(a["broker_order_allowed"])
        self.assertEqual(a["recorded_total_debited_spent_aud"],
                         b["all_later_buys_including_fees_aud"])
        self.assertEqual(a["recorded_unreviewed_spent_aud"],3008.)
        self.assertEqual(a["recorded_cycle_tagged_spent_aud"],0.)
        self.assertEqual(a["recorded_independent_spent_aud"],0.)
        self.assertGreater(a["review_count"],8)
        self.assertEqual(a["days_since_current_review"],3)
        self.assertEqual(a["review_history"][1][
            "recorded_unreviewed_or_other_cycle_aud"],1003.)
        self.assertEqual(a["review_history"][2][
            "recorded_unreviewed_or_other_cycle_aud"],2005.)

    def test_same_original_model_fraction_used_at_each_review(self):
        series=market()
        result=weekly_original_buyback_ledger(series,H,saved(),asof=ASOF)
        for row in result["review_history"]:
            t=pd.Timestamp(row["review_date"],tz="UTC")
            step=recovery_buy_budget_fraction(series.loc[:t],t,style="adaptive_recovery")
            self.assertEqual(row["pct_original_aftertax_buyback_budget"],
                             step["pct_of_initial_buyback_cash"])
            self.assertTrue(row["last_completed_review_not_current_order"])

    def test_attested_cycle_and_independent_funding_separated(self):
        p=saved()
        p["rows"][1]["Funding Source"]="Original cycle sale proceeds"
        p["rows"][1]["Funding Cycle Halving"]=H
        p["rows"][2]["Funding Source"]="Independent cash"
        a=weekly_original_buyback_ledger(market(),H,p,asof=ASOF)
        b=original_sale_cash_reconciliation(p,H,asof=ASOF)
        self.assertEqual(a["recorded_cycle_tagged_spent_aud"],1003.)
        self.assertEqual(a["recorded_unreviewed_spent_aud"],0.)
        self.assertEqual(a["recorded_independent_spent_aud"],2005.)
        self.assertEqual(a["recorded_total_debited_spent_aud"],
                         b["all_later_buys_including_fees_aud"])
        self.assertEqual(a["review_history"][1]["recorded_cycle_funding_provenance"],
                         "User-labelled this cycle (not broker verified)")

    def test_early_purchases_count_cash_but_never_prove_weekly_buy(self):
        p=saved()
        p["rows"].append(buy("04/05/26",2,700))
        series=market()
        # Prior close trigger will activate on 2026-05-04; 2026-05-05 is
        # first non-scheduled date but belongs to first weekly window.
        p["rows"].append(buy("05/05/26",1,210))
        a=weekly_original_buyback_ledger(series,H,p,asof=ASOF)
        self.assertEqual(a["recorded_prior_to_trigger_spent_aud"],0.)
        self.assertEqual(a["review_history"][0][
            "recorded_unreviewed_or_other_cycle_aud"],916.)

    def test_future_purchase_is_not_used_until_its_own_date(self):
        p=saved()
        a=weekly_original_buyback_ledger(market(),H,p,asof="2026-05-17")
        p2=copy.deepcopy(p)
        p2["rows"].append(buy("19/05/26",1,300))
        b=weekly_original_buyback_ledger(market(),H,p2,asof="2026-05-17")
        self.assertEqual(a,b)
        self.assertEqual(a["recorded_unreviewed_spent_aud"],1003.)
        self.assertEqual(a["review_count"],2)

    def test_future_price_cannot_affect_existing_weekly_history(self):
        original=market()
        end=pd.Timestamp("2026-06-07",tz="UTC")
        earlier=weekly_original_buyback_ledger(original,H,saved(),asof=str(end.date()))
        changed=original.copy()
        changed.loc[changed.index>end]=1000000.
        later=weekly_original_buyback_ledger(changed,H,saved(),asof=str(end.date()))
        self.assertEqual(earlier,later)

    def test_cannot_make_cycle_budget_from_only_new_2026_btc(self):
        p={"starting_capital_aud":500000.,
           "rows":[buy("01/01/26",100,10000)],"sales":[]}
        a=weekly_original_buyback_ledger(market(),H,p,asof=ASOF)
        self.assertTrue(a["original_sale_cash_budget_is_zero"])
        self.assertEqual(a["review_count"],0)
        self.assertIsNone(a["historical_research_activation_date"])

    def test_corrupt_or_missing_daily_prices_fail_closed(self):
        px=market().drop(pd.Timestamp("2026-05-11",tz="UTC"))
        with self.assertRaises(ValueError):
            weekly_original_buyback_ledger(px,H,saved(),asof=ASOF)
        p=saved()
        p["rows"][1]["Funding Source"]="Unsupported tax treatment"
        with self.assertRaisesRegex(ValueError,"Unknown BUY Funding Source"):
            weekly_original_buyback_ledger(market(),H,p,asof=ASOF)


if __name__=="__main__":
    unittest.main()
