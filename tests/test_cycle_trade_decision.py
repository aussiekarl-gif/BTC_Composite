"""Read-only research trade panel and broker-unit reconciliation invariants."""
import unittest
import numpy as np
import pandas as pd

from engines.research.cycle_trade_decision import (
    SELL_REVIEW_DAY_WEIGHTS,make_current_decision,
)
from engines.research.cycle_trading_dashboard_model import build_dashboard_market


def market_fixture():
    idx=pd.date_range("2022-06-01",periods=1600,freq="D",tz="UTC")
    series=pd.Series(50000.+np.arange(len(idx))*40.,index=idx)
    fx=pd.DataFrame({"aud_per_usd":np.full(len(idx),1.5)},index=idx)
    return build_dashboard_market(series,fx),idx[-1].date()


def saved_fixture():
    return {
        "starting_capital_aud":500_000.,
        "rows":[{"Date":"01/08/26","Asset":"ASX:IBIT",
                 "AUD Spent":150_000.,"Brokerage / Fee AUD":3.,
                 "BTC AUD Price":150_000.,
                 "Units / BTC Received":9000.}],
    }


_NOT_SUPPLIED=object()


class CurrentResearchDecisionTests(unittest.TestCase):
    def setUp(self):
        self.market,self.today=market_fixture()
        self.portfolio=saved_fixture()

    def evaluate(self,market=None,portfolio=_NOT_SUPPLIED,**overrides):
        kws=dict(
            today=self.today,usable_cash_aud=10_000.,
            ibit_price_aud=30.,verified_current_ibit_units=None,
            buy_style="adaptive_recovery",feed_verified=True,
        )
        kws.update(overrides)
        return make_current_decision(
            market if market is not None else self.market,
            self.portfolio if portfolio is _NOT_SUPPLIED else portfolio,**kws)

    def undervalued(self):
        m=self.market.copy()
        m["previous_close_below_200wma"]=True
        m["prior_200wma_usd"]=m["previous_close_usd"]/.80
        m["prior_close_vs_200wma_pct"]=-20.
        return m

    def topped(self,cycle_day=500):
        m=self.market.copy()
        m["halving_day"]=cycle_day
        m["prior_200wma_usd"]=m["previous_close_usd"]/1.6
        m["prior_close_vs_200wma_pct"]=60.
        m["previous_close_below_200wma"]=False
        return m

    def test_2026_buy_with_verified_quote_rounds_down_units(self):
        d=self.evaluate(self.undervalued())
        self.assertEqual(d["action"],"BUY")
        self.assertAlmostEqual(d["action_aud"],250.)
        self.assertEqual(d["suggested_ibit_units"],8)
        self.assertEqual(d["estimated_gross_ibit_aud"],243.)
        self.assertFalse(d["place_order"])
        self.assertTrue(d["research_only"])
        self.assertEqual(d["quote_aud"],30.)
        self.assertIn("strict prior 200WMA",d["buy_signal"])

    def test_buy_signals_are_not_fake_broker_quotes(self):
        d=self.evaluate(self.undervalued(),ibit_price_aud=None)
        self.assertEqual(d["action"],"HOLD")
        self.assertEqual(d["market_signal"],"BUY WATCH")
        self.assertEqual(d["action_aud"],0.)
        self.assertIsNone(d["estimated_ibit_units"])
        self.assertTrue(d["quote_required_for_units"])

    def test_value_style_allocates_more_at_deeper_prior_discount(self):
        d=self.evaluate(self.undervalued(),buy_style="adaptive_value")
        self.assertEqual(d["action"],"BUY")
        self.assertAlmostEqual(d["action_aud"],1000.)
        self.assertEqual(d["suggested_ibit_units"],33)
        self.assertEqual(d["estimated_gross_ibit_aud"],993.)

    def test_cash_cannot_exceed_persisted_unspent_portfolio(self):
        d=self.evaluate(self.undervalued(),usable_cash_aud=500000.)
        self.assertEqual(d["action"],"HOLD")
        self.assertEqual(d["action_aud"],0.)
        self.assertTrue(any("cash" in x.lower() for x in d["why"]))

    def test_stale_or_unverified_market_is_always_hold(self):
        d=self.evaluate(self.undervalued(),feed_verified=False)
        self.assertEqual(d["action"],"HOLD")
        d=self.evaluate(self.undervalued(),today=self.today+pd.Timedelta(days=5))
        self.assertEqual(d["action"],"HOLD")
        self.assertFalse(d["data_ok"])

    def test_missing_portfolio_does_not_use_fake_500k(self):
        d=self.evaluate(self.undervalued(),portfolio={})
        self.assertEqual(d["action"],"HOLD")
        self.assertEqual(d["action_aud"],0.)
        d=self.evaluate(self.undervalued(),portfolio=None)
        self.assertEqual(d["action"],"HOLD")

    def test_duplicate_signal_checkbox_blocks_buy_and_sell(self):
        for m in (self.undervalued(),self.topped()):
            d=self.evaluate(m,already_traded_today=True,
                            verified_current_ibit_units=9000.)
            self.assertEqual(d["action"],"HOLD")
            self.assertEqual(d["action_aud"],0.)

    def test_day500_selling_requires_current_broker_inventory(self):
        m=self.topped(500)
        unverified=self.evaluate(m)
        self.assertEqual(unverified["action"],"HOLD")
        self.assertIn("scheduled distribution",unverified["sell_signal"])
        valid=self.evaluate(m,verified_current_ibit_units=9000.)
        self.assertEqual(valid["action"],"SELL")
        self.assertEqual(valid["suggested_ibit_units"],450)
        self.assertEqual(valid["action_aud"],13500.)
        self.assertEqual(valid["estimated_net_sale_aud_before_cgt"],13497.)
        self.assertEqual(valid["brokerage_aud"],3.)
        self.assertFalse(valid["place_order"])

    def test_after_day560_no_backdated_day500_sale(self):
        d=self.evaluate(self.topped(910),
                        verified_current_ibit_units=9000.)
        self.assertEqual(d["action"],"HOLD")
        self.assertIsNone(d["sell_signal"])
        self.assertTrue(any("passed before" in x for x in d["why"]))

    def test_sell_broker_unit_limit_and_quote_are_required(self):
        m=self.topped()
        for qty in (9001., -2.,None,0.):
            d=self.evaluate(m,verified_current_ibit_units=qty)
            self.assertEqual(d["action"],"HOLD")
        d=self.evaluate(m,verified_current_ibit_units=1000.,
                        ibit_price_aud=None)
        self.assertEqual(d["action"],"HOLD")
        self.assertEqual(d["action_aud"],0.)

    def test_sell_tranches_dont_repeat_on_unscheduled_dates(self):
        self.assertEqual(sum(SELL_REVIEW_DAY_WEIGHTS.values()),.90)
        for d in (501,510,530,557,561):
            result=self.evaluate(self.topped(d),
                                 verified_current_ibit_units=9000.)
            self.assertEqual(result["action"],"HOLD")

    def test_signal_does_not_read_current_execution_close(self):
        m=self.topped()
        a=self.evaluate(m,verified_current_ibit_units=9000.)
        alternative=m.copy()
        history=m["price_history"].copy()
        history.iloc[-1]=1_000_000.
        alternative["price_history"]=history
        alternative["btc_price_usd"]=1_000_000.
        b=self.evaluate(alternative,verified_current_ibit_units=9000.)
        self.assertEqual((a["action"],a["action_aud"],a["suggested_ibit_units"]),
                         (b["action"],b["action_aud"],b["suggested_ibit_units"]))

    def test_postwindow_breakdown_behind_strong_prior_rally_is_research_only(self):
        m=self.topped(640)
        h=m["price_history"].copy()
        # Set a strong past peak and accelerating decline over last 90 days
        for i in range(90):
            h.iloc[-91+i]=100_000. if i<5 else 100_000.-320*(i-5)
        h.iloc[-1]=75_000.
        m["price_history"]=h
        m["previous_close_usd"]=float(h.iloc[-2])
        m["prior_200wma_usd"]=m["previous_close_usd"]/1.6
        m["previous_close_below_200wma"]=False
        d=self.evaluate(m,verified_current_ibit_units=9000.)
        self.assertEqual(d["action"],"SELL")
        self.assertEqual(d["suggested_ibit_units"],450)
        self.assertTrue(any("unvalidated" in x for x in d["warnings"]))


if __name__=="__main__":
    unittest.main()
