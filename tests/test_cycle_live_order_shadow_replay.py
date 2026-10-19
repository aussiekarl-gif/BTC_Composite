"""Isolated shadow parity tests: actual live decision, no user portfolio I/O."""
import copy
import datetime as dt
import unittest
from dataclasses import replace
from zoneinfo import ZoneInfo

import pandas as pd

from engines.research.cycle_live_order_shadow_replay import Session, run_shadow
from engines.research.cycle_trade_allocation import SELL_REVIEW_DAY_WEIGHTS
from engines.shared.portfolio_transactions import portfolio_positions

SYDNEY=ZoneInfo("Australia/Sydney")
START=dt.date(2026,8,17)


def initial(capital=150000.,units=1000):
    return {"starting_capital_aud":capital,"rows":[{
        "Date":"01/05/26","Asset":"ASX:IBIT","AUD Spent":15000.,
        "Brokerage / Fee AUD":3.,"Units / BTC Received":units,
        "BTC AUD Price":120000.,"Notes":"Fixture only"}],"sales":[]}


def market(asof="2026-08-14",kind="buy",cycle_day=700):
    last=pd.Timestamp(asof,tz="UTC")
    history=pd.Series(80000.,index=pd.date_range(end=last,periods=1500,freq="D",tz="UTC"))
    return {
      "price_history":history,"asof_date":asof,
      "previous_close_usd":80000.,
      "btc_price_usd":80000.,"btc_price_aud_estimate":120000.,
      "prior_200wma_usd":100000. if kind=="buy" else 50000.,
      "previous_close_below_200wma":kind=="buy",
      "usd_aud_prior":1.5,
      "fx_source_date":str((last-dt.timedelta(days=1)).date()),
      "halving_day":cycle_day,
    }


def session(day=START, *, asof="2026-08-14", kind="buy", cycle_day=700,
            bid=19.99,ask=20.01):
    exec_dt=dt.datetime.combine(day,dt.time(10,6),SYDNEY).astimezone(dt.timezone.utc)
    quote_dt=exec_dt-dt.timedelta(minutes=1)
    return Session(trading_date_sydney=day,execution_at_utc=exec_dt,
                   quote_at_utc=quote_dt,bid_aud=bid,ask_aud=ask,
                   market=market(asof,kind,cycle_day),asx_session_verified=True)


class LiveOrderShadowParityTests(unittest.TestCase):
    def test_buy_exact_live_2_5pct_of_remaining_cash_and_whole_ibit(self):
        s=session()
        p=initial()
        original=copy.deepcopy(p)
        result=run_shadow(p,[s])
        self.assertEqual(p,original)
        t=result["sessions"][0]
        self.assertEqual((t["market_signal"],t["shared_live_rule_action"]),("BUY WATCH","BUY"))
        self.assertEqual(t["hypothetical_ibit_units_executed"],168)
        self.assertEqual(t["hypothetical_ibit_unit_price_aud"],20.01)
        self.assertEqual(result["remaining_ibit_whole_units"],1168)
        self.assertEqual(result["new_actual_orders"],0)
        self.assertFalse(result["historical_day500_backtest_parity_verified"])

    def test_buy_then_weekly_cooldown_reuse_actual_ledger(self):
        s1=session()
        s2=session(day=dt.date(2026,8,20),asof="2026-08-19")
        s3=session(day=dt.date(2026,8,24),asof="2026-08-21")
        r=run_shadow(initial(),[s1,s2,s3])
        self.assertEqual([x["shared_live_rule_action"] for x in r["sessions"]],
                         ["BUY","HOLD","BUY"])
        self.assertTrue(r["sessions"][2]["hypothetical_ibit_units_executed"]>0)

    def test_sells_remaining_holdings_not_original_units(self):
        day2=dt.date(2026,8,24)
        r=run_shadow(initial(),[
            session(kind="sell",cycle_day=500),
            session(day=day2,asof="2026-08-21",kind="sell",cycle_day=525),
        ])
        self.assertEqual([x["shared_live_rule_action"] for x in r["sessions"]],
                         ["SELL","SELL"])
        self.assertEqual(r["sessions"][0]["hypothetical_ibit_units_executed"],50)
        self.assertEqual(r["sessions"][1]["hypothetical_ibit_units_executed"],228)
        self.assertEqual(r["remaining_ibit_whole_units"],722)
        self.assertNotEqual(228,int(1000*SELL_REVIEW_DAY_WEIGHTS[525]))

    def test_sell_tax_escrow_blocks_certain_rebuy_cash(self):
        s=session(kind="sell",cycle_day=500)
        r=run_shadow(initial(),[s],tax_escrow_fraction_of_sale_proceeds=0.2)
        self.assertEqual(r["tax_cash_escrow_not_CGT"],199.90)
        self.assertFalse(r["tax_liability_calculated"])
        self.assertAlmostEqual(
            r["sessions"][0]["free_cash_after_escrow_aud"],
            r["sessions"][0]["cash_before_tax_aud"]-199.90,places=2)

    def test_zero_position_or_missing_first_purchase_fails(self):
        with self.assertRaisesRegex(ValueError,"starting portfolio"):
            run_shadow({"rows":[],"starting_capital_aud":50000},[session()])

    def test_session_no_verified_asx_close(self):
        with self.assertRaisesRegex(ValueError,"ASX:IBIT session"):
            run_shadow(initial(),[replace(session(),asx_session_verified=False)])

    def test_weekend_cannot_fill(self):
        s=session(day=dt.date(2026,8,22),asof="2026-08-21")
        with self.assertRaisesRegex(ValueError,"ASX:IBIT session"):
            run_shadow(initial(),[s])

    def test_asx_ibit_did_not_trade_in_2017(self):
        s=session(day=dt.date(2017,8,17),asof="2017-08-16")
        with self.assertRaisesRegex(ValueError,"ASX:IBIT session"):
            run_shadow(initial(),[s])

    def test_future_market_asof_rejected(self):
        s=session()
        m=market(asof="2026-08-18")
        with self.assertRaisesRegex(ValueError,"Future BTC"):
            run_shadow(initial(),[replace(s,market=m)])

    def test_history_after_market_asof_rejected(self):
        s=session()
        m=market(asof="2026-08-14")
        m["price_history"]=pd.concat([
            m["price_history"],pd.Series([90000.],index=[
                pd.Timestamp("2026-08-16",tz="UTC")])
        ])
        with self.assertRaisesRegex(ValueError,"Future BTC"):
            run_shadow(initial(),[replace(s,market=m)])

    def test_future_fx_rejected(self):
        s=session()
        m=market();m["fx_source_date"]="2026-08-18"
        with self.assertRaisesRegex(ValueError,"Stale or future FX"):
            run_shadow(initial(),[replace(s,market=m)])

    def test_crossed_or_stale_quote_rejected(self):
        s=session()
        with self.assertRaisesRegex(ValueError,"Crossed"):
            run_shadow(initial(),[replace(s,bid_aud=21.,ask_aud=20.)])
        with self.assertRaisesRegex(ValueError,"stale"):
            run_shadow(initial(),[replace(s,quote_at_utc=s.quote_at_utc-dt.timedelta(minutes=16))])

    def test_duplicate_date_and_late_quote_rejected(self):
        s=session()
        with self.assertRaisesRegex(ValueError,"strictly increasing"):
            run_shadow(initial(),[s,s])
        with self.assertRaisesRegex(ValueError,"stale"):
            run_shadow(initial(),[replace(s,quote_at_utc=s.execution_at_utc+dt.timedelta(seconds=1))])

    def test_unrecognized_provenance_rejected(self):
        with self.assertRaisesRegex(ValueError,"provenance"):
            run_shadow(initial(),[replace(session(),quote_provenance="fake_broker_fill")])

    def test_no_after_tax_profit_claim_and_fee_accounting(self):
        r=run_shadow(initial(),[session()])
        self.assertFalse(r["actual_ASX_IBIT_broker_fills_verified"])
        self.assertFalse(r["tax_liability_calculated"])
        self.assertAlmostEqual(r["total_recorded_synthetic_execution_fees_aud"],6.)
        self.assertEqual(r["portfolio_writes"],0)
        self.assertEqual(r["new_notifications"],0)

    def test_stale_market_is_hold_not_cash_consumption(self):
        s=session()
        m=market(asof="2026-08-10")
        r=run_shadow(initial(),[replace(s,market=m)])
        self.assertEqual(r["sessions"][0]["shared_live_rule_action"],"HOLD")
        self.assertEqual(r["remaining_ibit_whole_units"],1000)

    def test_replay_prefix_is_invariant(self):
        s1=session()
        s2=session(day=dt.date(2026,8,24),asof="2026-08-21")
        initial_state=initial()
        once=run_shadow(initial_state,[s1])["sessions"][0]
        long=run_shadow(initial_state,[s1,s2])["sessions"][0]
        self.assertEqual(once,long)

    def test_no_rows_or_sessions_cannot_be_granted_success(self):
        with self.assertRaisesRegex(ValueError,"No known ASX"):
            run_shadow(initial(),[])

if __name__=="__main__":
    unittest.main()
