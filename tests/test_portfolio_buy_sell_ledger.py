"""Real ledger compatibility, exact recorded balances and SQLite persist tests."""
import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from engines.shared.portfolio_transactions import (
    append_executed_trade,append_with_stale_guard,
    merge_legacy_purchase_editor,portfolio_positions,
)
from engines.shared.portfolio_store import save_portfolio,load_portfolio
from engines.research.cycle_trading_dashboard_model import portfolio_snapshot


def initial():
    return {"starting_capital_aud":500000.,"rows":[
        {"Date":"19/06/26","Asset":"ASX:IBIT","AUD Spent":1700.,
         "Brokerage / Fee AUD":3.,"Units / BTC Received":100.,
         "BTC AUD Price":170000.},
        {"Date":"01/09/26","Asset":"Direct BTC","AUD Spent":2000.,
         "Brokerage / Fee AUD":0.,"Units / BTC Received":.01,
         "BTC AUD Price":200000.},
    ],"personal_note":"do not overwrite"}


class PortfolioBuySellLedgerTests(unittest.TestCase):
    def test_legacy_buy_only_is_same_quantity_and_not_mutated(self):
        saved=initial()
        original=copy.deepcopy(saved)
        p=portfolio_positions(saved)
        self.assertEqual(p["ibit_units"],100.)
        self.assertEqual(p["direct_btc"],.01)
        self.assertAlmostEqual(p["cash_remaining_aud"],496297.)
        self.assertFalse(p["has_sales"])
        self.assertEqual(saved,original)

    def test_sell_some_ibit_then_buy_ibit_and_reinvest_cash(self):
        saved=initial()
        after,snap=append_executed_trade(
            saved,side="SELL",asset="ASX:IBIT",
            trade_date="16/10/26",quantity=40.,trade_price_aud=22.4,
            fee_aud=3.,note="executed at broker")
        self.assertEqual(len(saved["rows"]),2)
        self.assertNotIn("sales",saved)
        self.assertEqual(snap["ibit_units"],60.)
        self.assertEqual(snap["direct_btc"],.01)
        self.assertEqual(snap["number_sells"],1)
        self.assertEqual(snap["sell_proceeds_aud"],896.)
        self.assertAlmostEqual(snap["cash_remaining_aud"],497190.)
        self.assertEqual(len(after["sales"]),1)
        self.assertEqual(after["personal_note"],"do not overwrite")
        another,status=append_executed_trade(
            after,side="BUY",asset="ASX:IBIT",trade_date="16/10/26",
            quantity=5,trade_price_aud=20.,fee_aud=3.,
            btc_aud_price=135000.)
        self.assertEqual(status["ibit_units"],65.)
        self.assertEqual(status["number_buys"],3)
        self.assertEqual(status["number_sells"],1)
        self.assertAlmostEqual(status["cash_remaining_aud"],497087.)
        self.assertEqual(status["btc_equivalent_estimate"] is not None,True)
        self.assertEqual(another["rows"][0],saved["rows"][0])

    def test_direct_btc_sells_at_8_decimal_exact_holding(self):
        sold,status=append_executed_trade(
            initial(),side="SELL",asset="Direct BTC",
            trade_date="16/10/26",quantity=.00600001,
            trade_price_aud=150000.,fee_aud=0.)
        self.assertAlmostEqual(status["direct_btc"],.00399999)
        self.assertAlmostEqual(
            status["btc_equivalent_estimate"],.01+.01-.00600001,delta=0.000001)

    def test_oversell_sell_before_buy_and_invalid_qty_all_rejected(self):
        for units in (101,100.5):
            with self.assertRaises(ValueError):
                append_executed_trade(
                    initial(),side="SELL",asset="ASX:IBIT",
                    trade_date="16/10/26",quantity=units,
                    trade_price_aud=22.)
        with self.assertRaisesRegex(ValueError,"bought units"):
            append_executed_trade(
                initial(),side="SELL",asset="ASX:IBIT",
                trade_date="18/06/26",quantity=1,trade_price_aud=25.)
        with self.assertRaises(ValueError):
            append_executed_trade(
                initial(),side="SELL",asset="Direct BTC",
                trade_date="16/10/26",quantity=.01000001,
                trade_price_aud=100000.)
        with self.assertRaisesRegex(ValueError,"exceeds recorded remaining"):
            append_executed_trade(
                initial(),side="BUY",asset="ASX:IBIT",
                trade_date="16/10/26",quantity=100000,
                trade_price_aud=25.,btc_aud_price=150000.)

    def test_unknown_missing_btc_reference_keeps_units_exact_and_exposure_unknown(self):
        p=initial()
        p["rows"][0]["BTC AUD Price"]=0.
        balance=portfolio_positions(p)
        self.assertEqual(balance["ibit_units"],100.)
        self.assertIsNone(balance["btc_equivalent_estimate"])
        view=portfolio_snapshot(p)
        self.assertTrue(view["valid"])
        self.assertEqual(view["unpriced_or_unknown_rows"],1)
        self.assertEqual(view["ibit_units"],100.)

    def test_stale_session_writes_are_rejected(self):
        old=initial()
        updated,status=append_executed_trade(
            old,side="SELL",asset="ASX:IBIT",
            trade_date="16/10/26",quantity=5,trade_price_aud=23.)
        with self.assertRaisesRegex(ValueError,"changed since page load"):
            append_with_stale_guard(
                old,updated,side="BUY",asset="ASX:IBIT",
                trade_date="16/10/26",quantity=1,trade_price_aud=22.,
                btc_aud_price=140000.)

    def test_legacy_editor_preserves_executed_sales(self):
        base=initial()
        after,status=append_executed_trade(
            base,side="SELL",asset="ASX:IBIT",
            trade_date="16/10/26",quantity=5,trade_price_aud=23.)
        buys=copy.deepcopy(after["rows"])
        buys[0]["AUD Spent"]=1800.
        merged=merge_legacy_purchase_editor(
            after,after,edited_buys=buys,starting_capital_aud=500000.)
        self.assertEqual(merged["sales"],after["sales"])
        self.assertEqual(portfolio_positions(merged)["ibit_units"],95.)
        self.assertEqual(merged["personal_note"],"do not overwrite")
        with self.assertRaisesRegex(ValueError,"changed elsewhere"):
            merge_legacy_purchase_editor(
                base,after,edited_buys=buys,starting_capital_aud=500000.)

    def test_google_compatible_shared_json_save_and_reload_in_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"portfolio.sqlite3"
            original=initial()
            ok,err=save_portfolio(original,db_path=path)
            self.assertTrue(ok,err)
            loaded,e=load_portfolio(path)
            self.assertIsNone(e)
            latest,status=append_with_stale_guard(
                loaded,loaded,side="SELL",asset="ASX:IBIT",
                trade_date="16/10/26",quantity=25,
                trade_price_aud=23.4,fee_aud=3.)
            ok,e=save_portfolio(latest,db_path=path)
            self.assertTrue(ok,e)
            stored,e=load_portfolio(path)
            self.assertIsNone(e)
            self.assertEqual(stored["sales"],latest["sales"])
            self.assertEqual(portfolio_snapshot(stored)["ibit_units"],75.)
            self.assertAlmostEqual(portfolio_snapshot(stored)["cash_remaining_aud"],496879.)

    def test_invalid_sell_fee_and_future_date_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"exceed brokerage"):
            append_executed_trade(initial(),side="SELL",asset="ASX:IBIT",
                trade_date="16/10/26",quantity=1,trade_price_aud=2.,fee_aud=3.)
        future=(dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=3))
        with self.assertRaisesRegex(ValueError,"future"):
            append_executed_trade(initial(),side="BUY",asset="ASX:IBIT",
                trade_date=future,quantity=1,trade_price_aud=20.,
                btc_aud_price=140000.)


if __name__=="__main__":
    unittest.main()
