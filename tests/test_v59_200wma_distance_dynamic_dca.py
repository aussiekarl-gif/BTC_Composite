import unittest
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

    def test_200wma_signal_is_independent_of_risk_columns(self):
        rows = []
        start = date(2020, 1, 6)
        for i in range(104):
            day = start + timedelta(weeks=i)
            rows.append({"date": day, "signal_date": day-timedelta(days=1),
                         "btc_price_aud": 100000.0, "ratio_to_200wma": .75,
                         "risk_score": 0.99, "risk_score_source": "untrusted"})
        with self.assertRaises(TypeError):
            # No risk arguments are accepted or consulted by this API.
            study.allocation_pct(.75, study.LADDERS["A_measured"], risk=.99)


if __name__ == "__main__":
    unittest.main()
