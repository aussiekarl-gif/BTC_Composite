import unittest
from pathlib import Path

from engines.production import production_model as production
from engines.research import research_model as research


EXPECTED = [
    (0.00, 16.0),
    (0.10, 8.0),
    (0.20, 4.0),
    (0.30, 2.0),
    (0.40, 1.0),
    (0.50, 0.0),
]


class AppRiskLadderTests(unittest.TestCase):
    def test_both_scripts_share_the_same_default_ladder(self):
        self.assertEqual(production.SMART_DCA_POINTS, EXPECTED)
        self.assertEqual(research.SMART_DCA_POINTS, EXPECTED)
        self.assertEqual(production.DEFAULT_ALWAYS_DCA_POINTS, EXPECTED)
        self.assertEqual(research.DEFAULT_ALWAYS_DCA_POINTS, EXPECTED)

    def test_exact_band_boundaries_and_values_in_both_models(self):
        cases = [
            (0.0, 16.0), (0.099999, 16.0),
            (0.10, 8.0), (0.199999, 8.0),
            (0.20, 4.0), (0.299999, 4.0),
            (0.30, 2.0), (0.399999, 2.0),
            (0.40, 1.0), (0.499999, 1.0),
            (0.50, 0.0), (0.75, 0.0), (1.0, 0.0),
        ]
        for risk, expected in cases:
            with self.subTest(risk=risk, model="production"):
                self.assertEqual(production.risk_band_multiplier(EXPECTED, risk), expected)
            with self.subTest(risk=risk, model="research"):
                self.assertEqual(research.risk_band_multiplier(EXPECTED, risk), expected)

    def test_risk_above_one_or_non_finite_is_rejected(self):
        for model in (production, research):
            for risk in (-0.001, 1.001, float("nan"), float("inf")):
                with self.subTest(model=model.__name__, risk=risk):
                    with self.assertRaises(ValueError):
                        model.risk_band_multiplier(EXPECTED, risk)

    def test_research_historical_backtest_uses_discrete_band_helper(self):
        source = Path("engines/research/research_model.py").read_text(encoding="utf-8")
        self.assertIn("risk_band_multiplier(risk_curve, risk)", source)
        self.assertNotIn("interpolate(risk_curve, risk)", source)

    def test_dca_today_paths_keep_the_five_percent_weekly_cap_and_stop_at_050(self):
        production_source = Path("engines/production/production_app.py").read_text(encoding="utf-8")
        research_source = Path("engines/research/research_app.py").read_text(encoding="utf-8")
        self.assertIn("risk_band_multiplier(smart_dca_curve, current_risk)", production_source)
        self.assertIn("risk_band_multiplier(smart_dca_curve, current_risk)", research_source)
        self.assertIn("float(starting_capital_aud) * 0.05", production_source)
        self.assertIn("float(starting_capital_aud) * 0.05", research_source)
        self.assertIn("and current_risk < 0.50", research_source)


if __name__ == "__main__":
    unittest.main()
