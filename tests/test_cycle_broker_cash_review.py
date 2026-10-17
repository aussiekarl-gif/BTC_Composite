"""FIFO tax scenario and verified spendable cash are advisory, never orders."""
import copy
import unittest

from engines.research.cycle_broker_cash_review import (
    fifo_sales_and_inventory,
    projected_ibit_sell_tax,
    broker_reconciled_trade_preview,
)


def buy(date,units,cost,*,asset="ASX:IBIT",fee=3.):
    return {
        "Date":date,"Asset":asset,"Units / BTC Received":units,
        "AUD Spent":cost,"Brokerage / Fee AUD":fee,
        "BTC AUD Price":100000.,
    }


def sell(date,units,proceeds,*,asset="ASX:IBIT",fee=3.):
    return {
        "Date":date,"Asset":asset,"Units Sold":units,
        "AUD Proceeds":proceeds,"Brokerage / Fee AUD":fee,
    }


def portfolio():
    return {
        "starting_capital_aud":500000.,
        "rows":[buy("01/05/24",100,10000,fee=20)],
        "sales":[sell("02/09/25",50,20000,fee=10)],
    }


def decision(action="BUY",pct=2.5,units=10):
    return {
        "action":action,"buy_pct_total_cash":pct,
        "sell_pct_total_holdings":5.,
        "suggested_ibit_units":units,
        "action_aud":100000.,
        "market_signal":"BUY WATCH" if action=="BUY" else "SELL WATCH",
    }


class BrokerReconciliationTests(unittest.TestCase):
    def test_historical_fifo_sale_aud_gain_and_positive_only_tax(self):
        state=fifo_sales_and_inventory(portfolio(),asof="2026-10-17")
        self.assertEqual(state["recorded_net_ibit_units"],50)
        self.assertEqual(state["recorded_cash_before_tax_aud"],509970.)
        self.assertEqual(state["gross_positive_only_tax_projection_aud"],1498.)
        self.assertEqual(len(state["realized_sales"]),1)
        self.assertEqual(state["realized_sales"][0]["estimated_fifo_cost_base_aud"],5010.)
        self.assertEqual(state["realized_sales"][0]["estimated_realised_gain_aud"],14980.)
        self.assertEqual(state["by_financial_year"][0]["financial_year"],"2025/26")
        self.assertFalse(state["tax_already_paid_known"])
        self.assertFalse(state["fund_pension_phase_verified"])

    def test_later_btc_purchase_does_not_change_original_fifo_lot_basis(self):
        x=portfolio()
        x["rows"].append(buy("01/01/26",10,900,asset="Direct BTC"))
        x["sales"].append(sell("01/04/26",5,1000,asset="Direct BTC"))
        state=fifo_sales_and_inventory(x,asof="2026-10-17")
        self.assertEqual(state["recorded_net_ibit_units"],50)
        self.assertEqual(state["recorded_direct_btc_units"],5)
        self.assertEqual(state["realized_sales"][0]["estimated_fifo_cost_base_aud"],5010.)
        # Newer BTC short-held gain = 1,000 - 3 - 451.5 = 545.5
        self.assertAlmostEqual(state["realized_sales"][1][
            "indicative_positive_only_tax_aud"],81.825,places=2)

    def test_projected_etf_sale_uses_only_remaining_old_lots(self):
        state=projected_ibit_sell_tax(
            portfolio(),asof="2026-10-17",
            units=10,price_aud=300.,fee_aud=3.)
        self.assertEqual(state["illustrative_sell_gross_aud"],3000.)
        self.assertEqual(state["illustrative_FIFO_cost_basis_aud"],1002.)
        self.assertEqual(state["illustrative_realized_gain_aud"],1995.)
        self.assertEqual(state["illustrative_positive_only_cgt_provision_aud"],199.5)
        self.assertEqual(state["illustrative_net_after_cgt_provision_aud"],2797.5)
        self.assertTrue(state["tax_paid_or_pension_phase_unverified"])

    def test_unrealized_new_holdings_never_count_as_taxable_sale(self):
        p=portfolio()
        p["sales"]=[]
        result=fifo_sales_and_inventory(p,asof="2026-10-17")
        self.assertEqual(result["gross_positive_only_tax_projection_aud"],0.)
        self.assertEqual(result["by_financial_year"],[])

    def test_tax_losses_are_not_assumed_offsets_to_positive_gains(self):
        p={
            "starting_capital_aud":500000.,
            "rows":[buy("01/01/25",10,1000,fee=0),
                    buy("01/02/26",10,6000,fee=0)],
            "sales":[sell("01/08/26",20,5000,fee=0)],
        }
        result=fifo_sales_and_inventory(p,asof="2026-10-17")
        self.assertEqual(result["realized_sales"][0]["estimated_realised_gain_aud"],-2000.)
        self.assertEqual(result["by_financial_year"][0]["gross_positive_parcel_gains_aud"],1500.)
        self.assertEqual(result["gross_positive_only_tax_projection_aud"],150.)
        self.assertFalse(result["tax_already_paid_known"])

    def test_buy_read_only_uses_verified_free_cash_not_gross_sale_proceeds(self):
        p=portfolio()
        state=broker_reconciled_trade_preview(
            p,decision("BUY",2.5),asof="2026-10-17",
            confirmed_broker_cash_after_reserves_aud=20000,
            verified_broker_ibit_price_aud=30,
            confirmed=True)
        self.assertEqual(state["phase"],"BUY_RESEARCH_PREVIEW")
        self.assertEqual(state["max_cash_without_reconciling_other_liabilities_aud"],20000)
        self.assertEqual(state["reconciled_research_gross_aud"],500.)
        self.assertEqual(state["reconciled_whole_ibit_units"],16)
        self.assertFalse(state["place_order"])
        self.assertFalse(state["new_trade_authorized"])
        self.assertFalse(state["estimated_tax_is_unpaid_liability"])
        # User-confirmed available cash is ALREADY net of unpaid liabilities
        # and should not have illustrative tax deducted a second time.
        self.assertEqual(state["confirmed_free_broker_cash_aud"],20000.)

    def test_broker_confirmation_never_expands_manual_original_candidate(self):
        p=portfolio()
        d=decision("BUY",2.5)
        d["action_aud"]=120.
        q=broker_reconciled_trade_preview(
            p,d,asof="2026-10-17",
            confirmed_broker_cash_after_reserves_aud=100000.,
            verified_broker_ibit_price_aud=30.,confirmed=True)
        self.assertEqual(q["reconciled_research_gross_aud"],120.)
        self.assertEqual(q["reconciled_whole_ibit_units"],3)
        self.assertEqual(q["estimated_whole_unit_spend_including_fee_aud"],93.)
        self.assertEqual(q[
            "estimated_preview_cash_unspent_due_to_rounding_aud"],27.)
        self.assertFalse(q["place_order"])
        d["action_aud"]=90.
        blocked=broker_reconciled_trade_preview(
            p,d,asof="2026-10-17",
            confirmed_broker_cash_after_reserves_aud=100000.,
            verified_broker_ibit_price_aud=30.,confirmed=True)
        self.assertEqual(blocked["phase"],"BROKER_CASH_TOO_SMALL")
        self.assertEqual(blocked["reconciled_research_gross_aud"],0.)
        self.assertEqual(blocked["reconciled_whole_ibit_units"],0)

    def test_auto_cash_cannot_be_overridden_by_unconfirmed_amount(self):
        p=portfolio()
        state=broker_reconciled_trade_preview(
            p,decision("BUY"),asof="2026-10-17",
            confirmed_broker_cash_after_reserves_aud=500000,
            verified_broker_ibit_price_aud=30,confirmed=False)
        self.assertEqual(state["phase"],"NEEDS_BROKER_CONFIRMATION")
        self.assertIsNone(state["reconciled_research_gross_aud"])
        self.assertEqual(state["conservative_estimate_of_total_historic_cgt_aud"],1498.)
        with self.assertRaisesRegex(ValueError,"AFTER tax"):
            broker_reconciled_trade_preview(
                p,decision("BUY"),asof="2026-10-17",
                confirmed=True,verified_broker_ibit_price_aud=30)
        with self.assertRaisesRegex(ValueError,"broker quote"):
            broker_reconciled_trade_preview(
                p,decision("BUY"),asof="2026-10-17",
                confirmed=True,confirmed_broker_cash_after_reserves_aud=10000)

    def test_broker_cash_above_ledger_cannot_create_more_spendable_cash(self):
        p=portfolio()
        preview=broker_reconciled_trade_preview(
            p,decision("BUY",2.5),asof="2026-10-17",
            confirmed=True,
            confirmed_broker_cash_after_reserves_aud=1000000,
            verified_broker_ibit_price_aud=30)
        self.assertEqual(preview["max_cash_without_reconciling_other_liabilities_aud"],509970.)
        self.assertAlmostEqual(preview["reconciled_research_gross_aud"],12749.25)

    def test_too_little_cash_or_expensive_units_cannot_create_order(self):
        p=portfolio()
        q=broker_reconciled_trade_preview(
            p,decision("BUY",2.5),asof="2026-10-17",
            confirmed=True,
            confirmed_broker_cash_after_reserves_aud=800,
            verified_broker_ibit_price_aud=250)
        self.assertEqual(q["phase"],"BROKER_CASH_TOO_SMALL")
        self.assertEqual(q["reconciled_whole_ibit_units"],0)
        self.assertEqual(q["reconciled_research_gross_aud"],0)

    def test_existing_hold_cannot_be_promoted_by_manual_cash(self):
        q=broker_reconciled_trade_preview(
            portfolio(),decision("HOLD"),asof="2026-10-17",
            confirmed=True,
            confirmed_broker_cash_after_reserves_aud=500000)
        self.assertEqual(q["phase"],"HOLD_REMAINS_HOLD")
        self.assertIsNone(q["reconciled_research_gross_aud"])

    def test_sell_projection_has_fifo_tax_and_actual_quote_but_not_order(self):
        p=portfolio()
        x=broker_reconciled_trade_preview(
            p,decision("SELL",units=10),asof="2026-10-17",
            confirmed=True,
            verified_broker_ibit_price_aud=300)
        self.assertEqual(x["phase"],"SELL_RESEARCH_PREVIEW")
        self.assertEqual(x["reconciled_whole_ibit_units"],10)
        self.assertEqual(x["reconciled_research_net_sale_aud_after_illustrative_tax"],2797.5)
        self.assertFalse(x["new_trade_authorized"])
        self.assertEqual(len(p["sales"]),1)

    def test_future_dated_transactions_not_in_past_scenario(self):
        x=portfolio()
        x["rows"].append(buy("20/10/26",20,2000))
        v=fifo_sales_and_inventory(x,asof="2026-10-17")
        self.assertTrue(v["newer_ledger_trades_excluded"])
        self.assertEqual(v["recorded_net_ibit_units"],50.)

    def test_invalid_future_sale_cash_and_missing_cost_fails_closed(self):
        p=portfolio()
        p["sales"].append(sell("01/01/26",1000,10000))
        with self.assertRaisesRegex(ValueError,"exceeds"):
            fifo_sales_and_inventory(p,asof="2026-10-17")
        p=portfolio()
        p["rows"][0]["AUD Spent"]=None
        with self.assertRaises(ValueError):
            fifo_sales_and_inventory(p,asof="2026-10-17")


if __name__=="__main__":
    unittest.main()
