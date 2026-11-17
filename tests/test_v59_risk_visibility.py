"""Regression tests: orange histogram bucket and read-only 3x candidate preview."""
import unittest

from engines.shared.risk_ladder_chart import risk_ladder_chart_labels
from engines.research.v59_risk_visibility import (
    aggressive_candidate_preview, highlighted_histogram_bucket,
)


class RiskHighlightAndCandidateTests(unittest.TestCase):
    def test_histogram_indices_match_13_buckets_with_zero_in_lowest_valid_band(self):
        examples = [
            (-0.1, 0), (0, 1), (.0004, 1), (.005, 1), (.01, 2),
            (.019, 2), (.02, 3), (.05, 4), (.10, 5),
            (.20, 6), (.40, 7), (.50, 8), (.60, 9), (.80, 10),
            (1.00, 11), (1.1, 12), (float("inf"), 12),
            (float("-inf"), 0), (float("nan"), -1), (None, -1),
        ]
        for raw, index in examples:
            with self.subTest(raw=raw):
                self.assertEqual(highlighted_histogram_bucket(raw), index)

    def test_current_orange_bin_was_shifted(self):
        # The merged zero bucket shifts all valid bins one place left.
        self.assertEqual(highlighted_histogram_bucket(.075), 4)
        self.assertEqual(highlighted_histogram_bucket(0.0), 1)

    def preview(self, risk, age=1):
        return aggressive_candidate_preview(
            sizing_risk=risk,
            base_weekly_aud=3_000,
            deployable_aud=100_000,
            starting_capital_aud=500_000,
            risk_observation_age_days=age,
        )

    def test_aggressive_band_schedule_and_high_risk_pause(self):
        for risk, expected_mult in [
            (0, 10), (.00999, 10), (.01, 5), (.01999, 5),
            (.02, 3), (.04999, 3), (.05, 2), (.09999, 2),
            (.10, 1.5), (.19999, 1.5), (.20, 1), (.39999, 1),
            (.40, 0), (.50, 0), (1, 0),
        ]:
            with self.subTest(risk=risk):
                r = self.preview(risk)
                self.assertEqual(r["candidate_multiplier"], expected_mult)
                self.assertEqual(r["candidate_buy_aud"], 3_000 * expected_mult)
                self.assertTrue(r["research_only"])
                self.assertTrue(r["not_approved_for_live_trading"])

    def test_preview_respects_deployable_cash_without_fixed_weekly_cap(self):
        r = aggressive_candidate_preview(
            sizing_risk=.01, base_weekly_aud=20_000,
            deployable_aud=100_000, starting_capital_aud=500_000,
            risk_observation_age_days=1,
        )
        self.assertEqual(r["candidate_buy_aud"], 100_000)
        r = aggressive_candidate_preview(
            sizing_risk=.01, base_weekly_aud=20_000,
            deployable_aud=8_000, starting_capital_aud=500_000,
            risk_observation_age_days=1,
        )
        self.assertEqual(r["candidate_buy_aud"], 8_000)

    def test_stale_or_future_snapshot_never_generates_dollar_preview(self):
        for age in (-1, 4, 72):
            r = self.preview(.01, age=age)
            self.assertIsNone(r["candidate_buy_aud"])
            self.assertEqual(r["status"], "BLOCKED_STALE_OR_FUTURE_RISK")

    def test_invalid_risk_cannot_be_treated_as_zero_risk(self):
        for risk in (-0.1, 1.1, float("nan")):
            with self.assertRaises(ValueError):
                self.preview(risk)


class RiskLadderChartLabelTests(unittest.TestCase):
    LADDER = [(0.00, 10.0), (0.01, 5.0), (0.02, 3.0), (0.05, 2.0), (0.10, 1.5), (0.20, 1.0), (0.40, 0.0)]

    def test_research_chart_matches_revised_bands_on_each_histogram_bucket(self):
        labels, multipliers = risk_ladder_chart_labels(
            ["<0.00 (invalid)", "0.00–0.01", "0.01–0.02",
             "0.02–0.05", "0.05–0.10", "0.10–0.20", "0.20–0.40",
             "0.40–0.50", "0.50–0.60", "0.60–0.80", "0.80–1.00", "1.000 (cap)", ">1.00 (invalid)"],
            [None, 0.00, 0.01, 0.02, 0.05, 0.10, 0.20,
             0.40, 0.50, 0.60, 0.80, 1.00, None],
            self.LADDER,
        )
        self.assertIsNone(multipliers[0])
        self.assertEqual(multipliers[1:8], [10.0, 5.0, 3.0, 2.0, 1.5, 1.0, 0.0])
        self.assertEqual(multipliers[8:12], [0.0, 0.0, 0.0, 0.0])
        self.assertIsNone(multipliers[12])
        self.assertIn("10×", labels[1])

    def test_production_chart_matches_new_first_risk_bands(self):
        labels, multipliers = risk_ladder_chart_labels(
            ["0.00–0.01", "0.01–0.02", "0.02–0.05", "0.05–0.10", "0.10–0.20"],
            [0.00, 0.01, 0.02, 0.05, 0.10],
            self.LADDER,
        )
        self.assertEqual(multipliers, [10.0, 5.0, 3.0, 2.0, 1.5])
        self.assertIn("10×", labels[0])
        self.assertIn("5×", labels[1])


if __name__ == "__main__":
    unittest.main()
