import unittest
from datetime import date, timedelta
from engines.research.v59_adaptive_ceiling_backtest import compare


class AdaptiveCeilingComparisonTests(unittest.TestCase):
    def test_scenarios_share_inputs_and_preserve_cash(self):
        start = date(2026, 1, 5)
        rows = [
            {"date": start + timedelta(days=7*i),
             "btc_price_aud": 100000 + i*1000,
             "risk_score": 0.01 if i < 4 else 0.55}
            for i in range(12)
        ]
        results = compare(rows, capital_aud=100000, reserve_aud=20000,
                          review_date=date(2026, 4, 1))
        self.assertEqual(set(results), {"fixed_5", "adaptive_7_5", "adaptive_10"})
        self.assertGreaterEqual(results["adaptive_10"]["invested_aud"],
                                results["fixed_5"]["invested_aud"])
        for result in results.values():
            self.assertGreaterEqual(result["cash_aud"], 20000)
            self.assertGreaterEqual(result["btc_held"], 0)
            self.assertGreaterEqual(result["worst_drawdown_pct"], -100)


if __name__ == "__main__":
    unittest.main()
