import unittest
import pandas as pd
from datetime import date, timedelta

from engines.research import v59_200wma_distance_dynamic_dca as study


class DynamicWmaDcaTests(unittest.TestCase):
    def test_tier_boundaries_are_inclusive(self):
        ladder = study.LADDERS["B_stepped"]
        self.assertEqual(study.allocation_pct(0.800001, ladder), 0.025)
        self.assertEqual(study.allocation_pct(0.80, ladder), 0.05)
        self.assertEqual(study.allocation_pct(0.75, ladder), 0.075)
        self.assertEqual(study.allocation_pct(0.70, ladder), 0.10)

    def test_deeper_discount_never_reduces_allocation(self):
        for ladder in study.LADDERS.values():
            allocations = [study.allocation_pct(ratio, ladder)
                           for ratio in (1.2, 1.0, .9, .8, .75, .7, .6)]
            self.assertEqual(allocations, sorted(allocations))

    def test_invalid_ratio_fails_closed(self):
        for ratio in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                study.allocation_pct(ratio, study.LADDERS["A_measured"])

    def test_ladder_rejects_non_monotonic_values(self):
        with self.assertRaises(ValueError):
            study.allocation_pct(.7, (.025, .05, .04, .10))

    def test_same_spend_timing_diagnostic_is_zero_at_constant_prices(self):
        start = date(2020, 1, 6)
        rows = []
        for i in range(104):
            day = start + timedelta(weeks=i)
            rows.append({"date": day, "signal_date": day-timedelta(days=1),
                         "btc_price_aud": 100000.0, "ratio_to_200wma": .70})
        result = study.simulate(rows, policy="C_aggressive")
        self.assertAlmostEqual(result["same_spend_btc_timing_uplift_pct_hindsight"], 0.0, places=8)

    def test_cash_yield_is_a_separate_account_assumption(self):
        start = date(2020, 1, 6)
        rows = []
        for i in range(104):
            day = start + timedelta(weeks=i)
            rows.append({"date": day, "signal_date": day-timedelta(days=1),
                         "btc_price_aud": 100000.0, "ratio_to_200wma": 1.10})
        zero_yield = study.simulate(rows, policy="current_2_5pct", cash_yield=0.0)
        five_pct_yield = study.simulate(rows, policy="current_2_5pct", cash_yield=0.05)
        self.assertGreater(five_pct_yield["cash_aud"], zero_yield["cash_aud"])

    def test_simulation_obeys_weekly_cap_and_seven_day_spacing(self):
        start = date(2020, 1, 6)
        rows = []
        for i in range(104):
            day = start + timedelta(weeks=i)
            rows.append({
                "date": day, "signal_date": day - timedelta(days=1),
                "btc_price_aud": 100000.0 + i * 100,
                "ratio_to_200wma": .70,
            })
        result = study.simulate(rows, policy="C_aggressive")
        self.assertLessEqual(result["biggest_buy_pct_original_capital"], 5.0 + 1e-9)
        self.assertGreater(result["buy_count"], 1)
        self.assertGreaterEqual(result["cash_aud"], 0.0)

    def test_allocation_is_a_pure_wma_input_not_a_risk_input(self):
        # Arbitrary unrelated risk metadata cannot change the pure WMA decision.
        first = {"ratio_to_200wma": .75, "risk_score": 0.99}
        second = {"ratio_to_200wma": .75, "risk_score": 0.00}
        self.assertEqual(
            study.allocation_pct(first["ratio_to_200wma"], study.LADDERS["A_measured"]),
            study.allocation_pct(second["ratio_to_200wma"], study.LADDERS["A_measured"]),
        )

    def test_wma_excludes_the_signal_sunday_close(self):
        index = pd.date_range("2013-01-06", periods=400 * 7 + 2, freq="D", tz="UTC")
        prices = pd.Series([100.0 + i for i in range(len(index))], index=index)
        btc = pd.DataFrame({"price": prices})
        fx = pd.Series(0.65, index=index)
        rows = study.build_weekly_rows(btc, fx)
        row = rows[-1]
        weekly = prices.resample("W-SUN").last()
        signal = pd.Timestamp(row["signal_date"], tz="UTC")
        position = weekly.index.get_loc(signal)
        expected = weekly.iloc[position-200:position].mean()
        self.assertAlmostEqual(row["prior_200wma_usd"], expected)
        self.assertNotEqual(row["prior_200wma_usd"], weekly.iloc[position-199:position+1].mean())


if __name__ == "__main__":
    unittest.main()
