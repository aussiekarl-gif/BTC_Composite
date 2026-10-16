"""Safety, historical portability and portfolio read-only dashboard adapter."""
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

from engines.research.cycle_trading_dashboard_model import (
    LAST_CONFIRMED_HALVING,portfolio_snapshot,
    build_dashboard_market,planned_buy_order,historical_one_scenario,
    portfolio_buy_error_from_reported_low,
)


def fake_prices(n=1550,*,last="2026-10-16"):
    i=pd.date_range(end=last,periods=n,freq="D",tz="UTC")
    p=pd.Series(100000.+200*np.arange(n),index=i,name="price_usd")
    # All historical FX strictly earlier than latest observed close.
    f=pd.DataFrame({"aud_per_usd":np.ones(n)*1.5},index=i)
    return p,f


class CycleTradingDashboardModelTests(unittest.TestCase):
    def test_portfolio_is_read_only_and_uses_saved_rows_not_synthetic_examples(self):
        p={"starting_capital_aud":500000.,"rows":[
            {"Date":"19/06/26","Asset":"ASX:IBIT","AUD Spent":1700.,
             "Brokerage / Fee AUD":3.,"Units / BTC Received":100.,
             "BTC AUD Price":170000.},
            {"Date":"01/09/26","Asset":"Direct BTC","AUD Spent":1000.,
             "Brokerage / Fee AUD":3.,"Units / BTC Received":.005,
             "BTC AUD Price":150000.},
        ]}
        frozen=str(p)
        r=portfolio_snapshot(p)
        self.assertEqual(frozen,str(p))
        self.assertEqual(r["rows"],2)
        self.assertAlmostEqual(r["btc_equivalent"],.015)
        self.assertAlmostEqual(r["cash_remaining_aud"],497294.)
        self.assertEqual(r["ibit_units"],100)
        self.assertEqual(r["unpriced_or_unknown_rows"],0)
        self.assertAlmostEqual(r["approx_average_cost_aud_per_btc"],2706/.015)

    def test_portfolio_buy_error_is_usd_fx_and_quantity_weighted(self):
        dates=pd.date_range("2026-06-15",periods=10,freq="D",tz="UTC")
        fx=pd.DataFrame({"aud_per_usd":[1.5]*len(dates)},index=dates)
        saved={"rows":[
            {"Date":"19/06/26","Asset":"ASX:IBIT","AUD Spent":1500.,
             "Brokerage / Fee AUD":3.,
             "BTC AUD Price":150000.},
            {"Date":"20/06/26","Asset":"Direct BTC","AUD Spent":3000.,
             "Brokerage / Fee AUD":3.,"Units / BTC Received":.02},
        ]}
        before=str(saved)
        audit=portfolio_buy_error_from_reported_low(saved,fx,low_usd=57717)
        self.assertEqual(before,str(saved))
        self.assertTrue(audit["available"])
        self.assertEqual(audit["purchases_count"],2)
        self.assertAlmostEqual(audit["btc_equivalent_purchased"],.03)
        self.assertAlmostEqual(audit["effective_avg_usd_per_btc"],100133.33,places=2)
        self.assertAlmostEqual(
            audit["error_above_user_reported_low_pct"],
            100*(100133.3333/57717.-1),places=2)

    def test_missing_fx_or_purchase_price_does_not_show_partial_error(self):
        fx=pd.DataFrame({"aud_per_usd":[1.5]},
                        index=pd.DatetimeIndex(["2026-06-18"],tz="UTC"))
        rows={"rows":[{"Date":"19/06/26","Asset":"ASX:IBIT",
                       "AUD Spent":2500., "BTC AUD Price":0.}]}
        self.assertFalse(
            portfolio_buy_error_from_reported_low(rows,fx)["available"])
        self.assertFalse(
            portfolio_buy_error_from_reported_low(rows,pd.DataFrame())["available"])
        with self.assertRaises(ValueError):
            portfolio_buy_error_from_reported_low(rows,fx,low_usd=0)

    def test_missing_ibit_btc_price_does_not_fabricate_exposure(self):
        r=portfolio_snapshot({"starting_capital_aud":500000,
                              "rows":[{"Asset":"ASX:IBIT","AUD Spent":2500,
                                       "Brokerage / Fee AUD":3,
                                       "Units / BTC Received":120,
                                       "BTC AUD Price":0}]})
        self.assertEqual(r["unpriced_or_unknown_rows"],1)
        self.assertEqual(r["btc_equivalent"],0)
        self.assertIsNone(r["approx_average_cost_aud_per_btc"])

    def test_invalid_or_missing_saved_portfolio_fails_closed(self):
        self.assertFalse(portfolio_snapshot(None)["valid"])
        self.assertFalse(portfolio_snapshot({"rows":"garbage"})["valid"])
        empty=portfolio_snapshot({"rows":[]})
        self.assertEqual(empty["rows"],0)
        self.assertEqual(empty["btc_equivalent"],0)

    def test_causal_market_sma_ignores_execution_close(self):
        price,fx=fake_prices()
        a=build_dashboard_market(price,fx)
        changed=price.copy()
        changed.iloc[-1]=1e6
        b=build_dashboard_market(changed,fx)
        self.assertEqual(a["prior_200wma_usd"],b["prior_200wma_usd"])
        self.assertEqual(a["previous_close_below_200wma"],
                         b["previous_close_below_200wma"])
        self.assertEqual(a["previous_close_usd"],b["previous_close_usd"])
        self.assertNotEqual(a["btc_price_usd"],b["btc_price_usd"])

    def test_fails_closed_on_missing_weekly_samples(self):
        p,fx=fake_prices()
        p=p.drop(p.index[-9])  # last minus 8 days is a required prior-week sample
        with self.assertRaisesRegex(ValueError,"Missing dates"):
            build_dashboard_market(p,fx)

    def test_price_source_staleness_not_ignored_if_no_fx(self):
        p,fx=fake_prices()
        market=build_dashboard_market(p,pd.DataFrame())
        self.assertIsNone(market["btc_price_aud_estimate"])
        plan=planned_buy_order(market,cash_available=100000)
        self.assertEqual(plan["action"],"DATA UNAVAILABLE")
        self.assertEqual(plan["amount_aud"],0)

    def test_day500_passed_not_a_new_entry_to_retro_selling(self):
        price,fx=fake_prices(last="2026-10-16")
        snap=build_dashboard_market(price,fx)
        self.assertEqual(snap["day500_date"],"2025-09-02")
        self.assertEqual(snap["day560_date"],"2025-11-01")
        self.assertEqual(snap["halving_day"],
                         (pd.Timestamp("2026-10-16",tz="UTC")-
                          LAST_CONFIRMED_HALVING).days)

    def test_prior_below_wma_builds_small_hypothetical_order(self):
        p,fx=fake_prices()
        p.iloc[-2]=25000.
        snap=build_dashboard_market(p,fx)
        self.assertTrue(snap["previous_close_below_200wma"])
        x=planned_buy_order(snap,cash_available=100000,
                            style="adaptive_recovery")
        self.assertEqual(x["action"],"ILLUSTRATIVE BUY")
        self.assertEqual(x["amount_aud"],2500.)
        self.assertAlmostEqual(
            x["btc_equivalent_estimate"],
            (2500.-3)/snap["btc_price_aud_estimate"],delta=1e-8)
        with self.assertRaises(ValueError):
            planned_buy_order(snap,cash_available=100000,style="oracle")
        tiny=planned_buy_order(snap,cash_available=1000)
        self.assertEqual(tiny["action"],"NO TRADE")

    def test_no_trade_above_wma_even_with_large_cash(self):
        p,fx=fake_prices()
        snap=build_dashboard_market(p,fx)
        self.assertFalse(snap["previous_close_below_200wma"])
        order=planned_buy_order(snap,cash_available=500000)
        self.assertEqual(order["amount_aud"],0.)

    def test_current_app_navigation_exposes_research_only_page(self):
        app=Path(__file__).resolve().parents[1]/"app.py"
        txt=app.read_text(encoding="utf8")
        self.assertIn('"Cycle Trading — Research"',txt)
        self.assertIn('"Cycle Trading — Research": Path(',txt)
        self.assertIn('"Production": Path(',txt)
        self.assertIn('engines" / "research" / "cycle_trading_app.py"',txt)

    def test_historical_rejects_2013_and_unsupported_variants(self):
        p,fx=fake_prices()
        with self.assertRaisesRegex(ValueError,"2013 excluded"):
            historical_one_scenario(p,fx,cycle="2013")
        with self.assertRaisesRegex(ValueError,"Unknown seller"):
            historical_one_scenario(p,fx,cycle="2021",seller="fake")
        with self.assertRaisesRegex(ValueError,"Unknown buyback"):
            historical_one_scenario(p,fx,cycle="2021",style="oracle")


if __name__=="__main__":
    unittest.main()
