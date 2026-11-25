import unittest

from engines.shared.risk_ladder_chart import risk_ladder_chart_labels


LADDER = [(0.00, 16.0), (0.10, 8.0), (0.20, 4.0), (0.30, 2.0), (0.40, 1.0), (0.50, 0.0)]


class RiskLadderChartTests(unittest.TestCase):
    def test_production_lowest_buckets_show_16x(self):
        labels, multipliers = risk_ladder_chart_labels(
            ["0.00–0.01", "0.01–0.02", "0.02–0.05", "0.05–0.10", "0.10–0.20"],
            [0.00, 0.01, 0.02, 0.05, 0.10], LADDER,
        )
        self.assertEqual(multipliers, [16.0, 16.0, 16.0, 16.0, 8.0])
        self.assertIn("16×", labels[0])
        self.assertIn("16×", labels[1])

    def test_research_full_bucket_order_maps_zero_and_point_zero_one_correctly(self):
        labels, multipliers = risk_ladder_chart_labels(
            ["<0.00 (invalid)", "0.000 (floor)", "(0.00, 0.01)", "0.01–0.02",
             "0.02–0.05", "0.05–0.10", "0.10–0.20", "0.20–0.40",
             "0.40–0.60", "0.60–0.80", "0.80–1.00", "1.000 (cap)", ">1.00 (invalid)"],
            [None, 0.00, 0.000000001, 0.01, 0.02, 0.05, 0.10, 0.20,
             0.40, 0.60, 0.80, 1.00, None],
            LADDER,
        )
        self.assertIsNone(multipliers[0])
        self.assertEqual(multipliers[1:6], [16.0, 16.0, 16.0, 16.0, 16.0])
        self.assertEqual(multipliers[6:11], [8.0, 4.0, 1.0, 0.0, 0.0])
        self.assertEqual(multipliers[11], 0.0)
        self.assertIsNone(multipliers[12])
        self.assertNotIn("×", labels[0])
        self.assertIn("16×", labels[1])
        self.assertIn("16×", labels[2])

    def test_boundaries_switch_multiplier_at_exact_threshold(self):
        _, multipliers = risk_ladder_chart_labels(
            ["a", "b", "c", "d", "e"],
            [0.099999, 0.10, 0.20, 0.30, 0.50], LADDER,
        )
        self.assertEqual(multipliers, [16.0, 8.0, 4.0, 2.0, 0.0])

    def test_mismatched_bucket_lengths_fail(self):
        with self.assertRaises(ValueError):
            risk_ladder_chart_labels(["a"], [], LADDER)

    def test_hover_customdata_aligns_price_to_risk_dates_and_shows_na(self):
        import pandas as pd
        from engines.shared.risk_ladder_chart import risk_history_hover_customdata

        risk = pd.Series([0.25, 0.5], index=pd.to_datetime(["2022-01-01", "2022-01-02"]))
        price = pd.Series([42000.0, 43000.0], index=pd.to_datetime(["2022-01-02", "2022-01-03"]))
        custom = risk_history_hover_customdata(risk, price)
        self.assertEqual(custom, [["n/a"], ["$42,000.00"]])

    def test_hover_customdata_without_price_is_explicit_na(self):
        import pandas as pd
        from engines.shared.risk_ladder_chart import risk_history_hover_customdata

        risk = pd.Series([0.2], index=pd.to_datetime(["2022-01-01"]))
        self.assertEqual(risk_history_hover_customdata(risk), [["n/a"]])


if __name__ == "__main__":
    unittest.main()
