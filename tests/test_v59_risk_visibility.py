"""Regression tests: orange histogram bucket and read-only 3x candidate preview."""
import unittest

from engines.research.v59_risk_visibility import (
    aggressive_candidate_preview, highlighted_histogram_bucket,
)


class RiskHighlightAndCandidateTests(unittest.TestCase):
    def test_histogram_indices_match_13_existing_bucket_labels(self):
        examples = [
            (-0.1, 0), (0, 1), (.005, 2), (.01, 3),
            (.019, 3), (.02, 4), (.05, 5), (.10, 6),
            (.20, 7), (.40, 8), (.60, 9), (.80, 10),
            (1.00, 11), (1.1, 12), (float("inf"), 12),
            (float("-inf"), 0), (float("nan"), -1), (None, -1),
        ]
        for raw, index in examples:
            with self.subTest(raw=raw):
                self.assertEqual(highlighted_histogram_bucket(raw), index)

    def test_current_orange_bin_was_shifted(self):
        # Previously a continuous valuation risk of .075 highlighted bin 3
        # (the 0.01-.02 bar) rather than its correct .05-.10 bar (bin 5).
        self.assertEqual(highlighted_histogram_bucket(.075), 5)

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
            (0, 3), (.10, 3), (.10001, 2), (.20, 2),
            (.20001, 1.5), (.40, 1.5), (.50, 1), (.50001, 0), (1, 0),
        ]:
            with self.subTest(risk=risk):
                r = self.preview(risk)
                self.assertEqual(r["candidate_multiplier"], expected_mult)
                self.assertEqual(r["candidate_buy_aud"], 3_000 * expected_mult)
                self.assertTrue(r["research_only"])
                self.assertTrue(r["not_approved_for_live_trading"])

    def test_max_weekly_and_remaining_cash_caps(self):
        r = aggressive_candidate_preview(
            sizing_risk=.01, base_weekly_aud=20_000,
            deployable_aud=100_000, starting_capital_aud=500_000,
            risk_observation_age_days=1,
        )
        self.assertEqual(r["candidate_buy_aud"], 25_000)
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


if __name__ == "__main__":
    unittest.main()
