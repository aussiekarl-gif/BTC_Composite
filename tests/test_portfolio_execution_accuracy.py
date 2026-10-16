"""2026 real-portfolio entry VWAP: deterministic tests, no live data writes."""
import unittest

import pandas as pd

from engines.shared.portfolio_execution_accuracy import (
    calculate_portfolio_entry_error, fx_rate_asof,
    DEFAULT_REFERENCE_USD, DEFAULT_REFERENCE_DATE,
)


def example_rows():
    return pd.DataFrame([
        {"Date":"01/06/26","Asset":"ASX:IBIT","AUD Spent":110000.,
         "Brokerage / Fee AUD":3., "BTC Equivalent":1.0},
        {"Date":"08/06/26","Asset":"ASX:IBIT","AUD Spent":140000.,
         "Brokerage / Fee AUD":3., "BTC Equivalent":1.0},
    ])


class PortfolioExecutionErrorTests(unittest.TestCase):
    def test_user_supplied_observed_june_2026_low_reference(self):
        self.assertEqual(DEFAULT_REFERENCE_USD, 57717.0)
        self.assertEqual(DEFAULT_REFERENCE_DATE, pd.Timestamp("2026-06-30"))
        fx=pd.Series([.68,.68],index=["2026-06-01","2026-06-08"])
        result=calculate_portfolio_entry_error(
            example_rows(), reference_price=DEFAULT_REFERENCE_USD,
            reference_currency="USD",usd_per_aud=fx)
        expected_average=(250006*.68)/2
        self.assertAlmostEqual(result["weighted_average_in_reference_currency"],
                               expected_average)
        self.assertAlmostEqual(result["error_pct"],
                               (expected_average/57717-1)*100)

    def test_aud_avg_is_sum_paid_including_fees_divided_by_btc(self):
        x=calculate_portfolio_entry_error(example_rows(),
            reference_price=100000,reference_currency="AUD")
        self.assertAlmostEqual(x["weighted_average_aud"],125003)
        self.assertAlmostEqual(x["error_pct"],25.003)
        self.assertEqual(x["purchase_rows"],2)
        self.assertEqual(x["btc_equivalent"],2)

    def test_true_dynamic_dca_btc_weighted_price_not_mean_of_prices(self):
        rows=pd.DataFrame([
            {"Date":"01/06/26","AUD Spent":150000.,
             "Brokerage / Fee AUD":3.,"BTC Equivalent":150000/110000},
            {"Date":"08/06/26","AUD Spent":50000.,
             "Brokerage / Fee AUD":3.,"BTC Equivalent":50000/140000},
        ])
        out=calculate_portfolio_entry_error(rows,reference_price=100000,
                                             reference_currency="AUD")
        self.assertAlmostEqual(out["weighted_average_aud"],116229.90,delta=.1)
        self.assertAlmostEqual(out["error_pct"],16.23,delta=.1)
        self.assertTrue(out["within_25pct"])

    def test_usd_uses_historical_fx_for_each_buy_not_today(self):
        fx=pd.Series([.6,.7],index=pd.to_datetime(["2026-06-01","2026-06-08"],utc=True))
        v=calculate_portfolio_entry_error(example_rows(),reference_price=58000,
                                          reference_currency="USD",usd_per_aud=fx)
        expected_usd=(110003*.6+140003*.7)/2
        self.assertAlmostEqual(v["weighted_average_in_reference_currency"],expected_usd)
        self.assertAlmostEqual(v["error_pct"],100*(expected_usd/58000-1))

    def test_weekend_uses_prior_fx_and_never_future_rate(self):
        fx=pd.Series([.67,.8],index=["2026-06-05","2026-06-08"])
        self.assertAlmostEqual(fx_rate_asof(fx,pd.Timestamp("2026-06-07")),.67)
        self.assertIsNone(fx_rate_asof(fx,"2026-06-04"))

    def test_no_stale_or_missing_fx_can_produce_falsely_good_metric(self):
        fx=pd.Series([.7],index=["2026-01-01"])
        r=calculate_portfolio_entry_error(example_rows(),reference_price=58000,
                                           reference_currency="USD",usd_per_aud=fx)
        self.assertIsNone(r["error_pct"])
        self.assertTrue(r["issues"])

    def test_pre_2026_synthetic_model_transactions_are_excluded(self):
        v=pd.concat([example_rows(),pd.DataFrame([{"Date":"01/01/20",
            "AUD Spent":10000.,"Brokerage / Fee AUD":3.,
            "BTC Equivalent":10.}])],ignore_index=True)
        r=calculate_portfolio_entry_error(v,reference_price=100000,
                                           reference_currency="AUD")
        self.assertEqual(r["purchase_rows"],2)
        self.assertEqual(r["excluded_pre2026_rows"],1)
        self.assertAlmostEqual(r["weighted_average_aud"],125003)

    def test_missing_btc_exposure_fails_closed(self):
        v=example_rows()
        v.loc[1,"BTC Equivalent"]=0.
        r=calculate_portfolio_entry_error(v,reference_price=58000,
                                           reference_currency="AUD")
        self.assertIsNone(r["error_pct"])
        self.assertTrue(r["issues"])

    def test_negative_error_is_not_silently_clamped(self):
        r=calculate_portfolio_entry_error(example_rows(),
                                           reference_price=130000,
                                           reference_currency="AUD")
        self.assertLess(r["error_pct"],0)
        self.assertTrue(r["within_25pct"])

    def test_starting_capital_not_part_of_average_entry_price(self):
        # The AUD 500k deployment budget is not mistaken for 500k invested.
        r=calculate_portfolio_entry_error(example_rows(),
                                           reference_price=100000,
                                           reference_currency="AUD")
        self.assertEqual(r["aud_paid_including_fees"],250006)
        self.assertNotEqual(r["aud_paid_including_fees"],500000)

    def test_reject_incorrect_currency_or_reference(self):
        with self.assertRaises(ValueError):
            calculate_portfolio_entry_error(example_rows(),reference_price=58000,
                                             reference_currency="EUR")
        with self.assertRaises(ValueError):
            calculate_portfolio_entry_error(example_rows(),reference_price=0)


if __name__=="__main__":
    unittest.main()
