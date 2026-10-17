"""One-screen brief never invents available cash or increases current signal."""
import unittest
from engines.research.cycle_single_screen_brief import one_screen_cycle_brief
from engines.research.cycle_broker_cash_review import broker_reconciled_trade_preview


def ledger():
    return {
        "starting_capital_aud":500000.,
        "rows":[{
            "Date":"01/05/24","Asset":"ASX:IBIT",
            "Units / BTC Received":100,"AUD Spent":10000.,
            "Brokerage / Fee AUD":20.,"BTC AUD Price":100000.,
        },{
            "Date":"01/01/26","Asset":"Direct BTC",
            "Units / BTC Received":1.25,"AUD Spent":150000.,
            "Brokerage / Fee AUD":3.,"BTC AUD Price":120000.,
        }],
        "sales":[{
            "Date":"02/09/25","Asset":"ASX:IBIT",
            "Units Sold":50.,"AUD Proceeds":20000.,
            "Brokerage / Fee AUD":10.,
        }],
    }


def decision(action="BUY",amount=5000.,units=10):
    return {
        "action":action,
        "market_signal":"BUY WATCH" if action=="BUY" else
                        "SELL WATCH" if action=="SELL" else "HOLD",
        "buy_pct_total_cash":2.5,"sell_pct_total_holdings":5.,
        "action_aud":amount,"suggested_ibit_units":units,
        "next_dca_eligible_date":"2026-10-19",
    }


class OneScreenBriefTests(unittest.TestCase):
    def test_current_holdings_cash_and_realized_tax_are_separate(self):
        p=ledger()
        b=one_screen_cycle_brief(p,decision("HOLD"),asof="2026-10-17")
        self.assertEqual(b["recorded_cash_aud"],359967.)
        self.assertEqual(b["recorded_ibit_units"],50.)
        self.assertEqual(b["recorded_direct_btc"],1.25)
        self.assertEqual(b["illustrative_realized_gains_cgt_aud"],1498.)
        self.assertEqual(b["status"],"HOLD")
        self.assertIsNone(b["confirmed_research_gross_aud"])
        self.assertIsNone(b["reconciled_available_cash_aud"])
        self.assertFalse(b["broker_verification"])
        self.assertFalse(b["original_historical_policy_parity_verified"])
        self.assertFalse(b["place_order"])
        self.assertEqual(b["next_eligible_review"],"2026-10-19")

    def test_unconfirmed_buy_is_not_called_actionable(self):
        p=ledger()
        d=decision()
        brief=one_screen_cycle_brief(p,d,asof="2026-10-17")
        self.assertEqual(brief["status"],"BROKER_VERIFICATION_REQUIRED")
        self.assertEqual(brief["action"],"BUY")
        self.assertIsNone(brief["confirmed_research_gross_aud"])
        self.assertIsNone(brief["confirmed_whole_ibit_units"])
        self.assertFalse(brief["broker_verification"])

    def test_confirmed_buy_shows_lesser_cash_and_whole_unit_spend(self):
        p=ledger()
        d=decision(amount=1000.)
        preview=broker_reconciled_trade_preview(
            p,d,asof="2026-10-17",
            confirmed=True,confirmed_broker_cash_after_reserves_aud=20000.,
            verified_broker_ibit_price_aud=30.)
        b=one_screen_cycle_brief(
            p,d,asof="2026-10-17",confirmed_broker_preview=preview)
        self.assertEqual(b["status"],"BUY_RESEARCH_VERIFIED")
        self.assertEqual(b["confirmed_research_gross_aud"],500.)
        self.assertEqual(b["confirmed_whole_ibit_units"],16)
        self.assertEqual(b["estimated_whole_unit_cost_aud"],483.)
        self.assertEqual(b["reconciled_available_cash_aud"],20000.)
        self.assertTrue(b["broker_verification"])
        self.assertFalse(b["place_order"])

    def test_manual_limit_is_respected_end_to_end(self):
        p=ledger()
        d=decision(amount=120.)
        preview=broker_reconciled_trade_preview(
            p,d,asof="2026-10-17",
            confirmed=True,confirmed_broker_cash_after_reserves_aud=100000.,
            verified_broker_ibit_price_aud=30.)
        b=one_screen_cycle_brief(
            p,d,asof="2026-10-17",confirmed_broker_preview=preview)
        self.assertEqual(b["confirmed_research_gross_aud"],120.)
        self.assertEqual(b["confirmed_whole_ibit_units"],3)
        self.assertEqual(b["estimated_whole_unit_cost_aud"],93.)
        self.assertFalse(b["place_order"])

    def test_confirmed_price_cannot_increase_existing_hold(self):
        p=ledger()
        d=decision("HOLD")
        misleading={
            "research_only":True,"place_order":False,
            "new_trade_authorized":False,"model_action":"BUY",
            "phase":"BUY_RESEARCH_PREVIEW","reconciled_research_gross_aud":1000.,
            "reconciled_whole_ibit_units":20,
        }
        b=one_screen_cycle_brief(
            p,d,asof="2026-10-17",confirmed_broker_preview=misleading)
        self.assertEqual(b["status"],"HOLD")
        self.assertIsNone(b["confirmed_research_gross_aud"])
        self.assertFalse(b["broker_verification"])

    def test_sell_illustration_is_separate_from_realized_tax(self):
        p=ledger()
        d=decision("SELL",units=10)
        preview=broker_reconciled_trade_preview(
            p,d,asof="2026-10-17",confirmed=True,
            verified_broker_ibit_price_aud=300.)
        b=one_screen_cycle_brief(
            p,d,asof="2026-10-17",confirmed_broker_preview=preview)
        self.assertEqual(b["status"],"SELL_RESEARCH_VERIFIED")
        self.assertEqual(b["confirmed_whole_ibit_units"],10)
        self.assertEqual(b["confirmed_research_gross_aud"],3000.)
        self.assertEqual(b["estimated_net_after_cgt_aud"],2797.5)
        self.assertEqual(b["illustrative_realized_gains_cgt_aud"],1498.)
        self.assertFalse(b["place_order"])

    def test_mismatched_or_unverified_preview_does_not_display_amount(self):
        p=ledger()
        d=decision()
        fake={
            "research_only":True,"place_order":False,
            "new_trade_authorized":False,"model_action":"SELL",
            "phase":"BUY_RESEARCH_PREVIEW","reconciled_research_gross_aud":10000.,
        }
        b=one_screen_cycle_brief(
            p,d,asof="2026-10-17",confirmed_broker_preview=fake)
        self.assertEqual(b["status"],"BROKER_PREVIEW_MISMATCH")
        self.assertIsNone(b["confirmed_research_gross_aud"])
        fake["model_action"]="BUY"
        fake["reconciled_research_gross_aud"]=1000000.
        fake["reconciled_whole_ibit_units"]=3
        fake["estimated_whole_unit_spend_including_fee_aud"]=93.
        fake["max_cash_without_reconciling_other_liabilities_aud"]=500000.
        b=one_screen_cycle_brief(
            p,d,asof="2026-10-17",confirmed_broker_preview=fake)
        self.assertEqual(b["status"],"BROKER_PREVIEW_MISMATCH")
        self.assertFalse(b["broker_verification"])

    def test_insufficient_broker_cash_stays_zero(self):
        p=ledger()
        d=decision()
        check=broker_reconciled_trade_preview(
            p,d,asof="2026-10-17",
            confirmed=True,confirmed_broker_cash_after_reserves_aud=100.,
            verified_broker_ibit_price_aud=200.)
        b=one_screen_cycle_brief(
            p,d,asof="2026-10-17",confirmed_broker_preview=check)
        self.assertEqual(b["status"],"BROKER_CASH_INSUFFICIENT")
        self.assertIsNone(b["confirmed_research_gross_aud"])
        self.assertIsNone(b["confirmed_whole_ibit_units"])

    def test_oversold_or_missing_purchase_does_not_display_fake_zero(self):
        p=ledger()
        p["sales"][0]["Units Sold"]=1500
        b=one_screen_cycle_brief(p,decision(),asof="2026-10-17")
        self.assertEqual(b["status"],"PORTFOLIO_UNAVAILABLE")
        self.assertIsNone(b["recorded_cash_aud"])
        self.assertIsNone(b["recorded_ibit_units"])
        self.assertFalse(b["broker_verification"])

    def test_asof_snapshot_excludes_future_trades(self):
        p=ledger()
        p["rows"].append({
            "Date":"20/10/26","Asset":"ASX:IBIT",
            "Units / BTC Received":3.,"AUD Spent":100.,
            "Brokerage / Fee AUD":3.,"BTC AUD Price":100000.,
        })
        b=one_screen_cycle_brief(p,decision("HOLD"),asof="2026-10-17")
        self.assertEqual(b["recorded_ibit_units"],50.)
        self.assertEqual(b["recorded_cash_aud"],359967.)


if __name__=="__main__":
    unittest.main()
