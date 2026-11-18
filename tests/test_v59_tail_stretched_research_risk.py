"""Tests for the V5.9 tail-stretched raw Power Law risk scale."""
import math
import unittest

from engines.research.research_model import research_tail_stretched_power_law_risk


class ResearchTailStretchedRiskTests(unittest.TestCase):
    def test_published_knots_are_exact(self):
        knots = [(-.32, 0.0), (-.31, .01), (-.30, .02), (-.25, .03),
                 (-.10, .049), (-.04, .20), (.02, .40), (.20, 1.0)]
        for residual, expected in knots:
            with self.subTest(residual=residual):
                self.assertAlmostEqual(
                    research_tail_stretched_power_law_risk(residual), expected, places=12
                )

    def test_interpolation_and_clamping(self):
        self.assertEqual(research_tail_stretched_power_law_risk(-.50), 0.0)
        self.assertEqual(research_tail_stretched_power_law_risk(.50), 1.0)
        self.assertAlmostEqual(
            research_tail_stretched_power_law_risk(-.306834399744635),
            .013165600255365, places=10
        )

    def test_zero_risk_is_confined_to_deep_tail(self):
        self.assertEqual(research_tail_stretched_power_law_risk(-.32), 0.0)
        self.assertGreater(research_tail_stretched_power_law_risk(-.319999), 0.0)
        self.assertGreater(research_tail_stretched_power_law_risk(-.10), 0.01)

    def test_invalid_residual_is_missing_not_zero(self):
        for value in (None, float("nan"), float("inf"), "bad"):
            with self.subTest(value=value):
                self.assertTrue(math.isnan(research_tail_stretched_power_law_risk(value)))

    def test_mapping_is_monotonic(self):
        values = [research_tail_stretched_power_law_risk(x / 1000) for x in range(-500, 301)]
        self.assertEqual(values, sorted(values))


if __name__ == "__main__":
    unittest.main()
