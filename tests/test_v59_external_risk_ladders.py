import unittest
from datetime import date, timedelta

from engines.research.v59_dynamic_risk_policy import (
    BUY_POLICY_BANDS,
    risk_buy_multiplier,
    replay_dynamic_dca,
)


class ExternalRiskLadderTests(unittest.TestCase):
    def test_screenshot_16x_ladder_matches_displayed_bands(self):
        bands = BUY_POLICY_BANDS["screenshot_16x"]
        expected = {
            0.00: 16.0, 0.099: 16.0,
            0.10: 8.0, 0.199: 8.0,
            0.20: 4.0, 0.299: 4.0,
            0.30: 2.0, 0.399: 2.0,
            0.40: 1.0, 0.499: 1.0,
            0.50: 0.0, 0.90: 0.0, 1.0: 0.0,
        }
        for risk, multiplier in expected.items():
            with self.subTest(risk=risk):
                self.assertEqual(risk_buy_multiplier(risk, bands), multiplier)

    def test_cowen_classic_reference_ladder(self):
        bands = BUY_POLICY_BANDS["cowen_classic"]
        self.assertEqual([risk_buy_multiplier(x, bands)
                          for x in (0.05, 0.15, 0.25, 0.35, 0.45, 0.50)],
                         [5.0, 4.0, 3.0, 2.0, 1.0, 0.0])

    def test_cowen_2026_reported_ladder_pauses_at_030(self):
        bands = BUY_POLICY_BANDS["cowen_2026_reported"]
        self.assertEqual([risk_buy_multiplier(x, bands)
                          for x in (0.05, 0.15, 0.25, 0.30, 0.50)],
                         [4.0, 3.0, 2.0, 0.0, 0.0])

    def test_screenshot_16x_nominal_multiplier_still_respects_weekly_cap(self):
        day = date(2026, 11, 17)
        rows = [dict(date=day, btc_price_aud=100000.0, risk_score=0.05)]
        result = replay_dynamic_dca(
            rows, capital_aud=510000.0, reserve_aud=0.0,
            review_date=day + timedelta(days=365),
            max_weekly_fraction=0.05,
            buy_bands=BUY_POLICY_BANDS["screenshot_16x"],
        )
        self.assertEqual(result["orders"][0]["multiplier"], 16.0)
        self.assertEqual(result["orders"][0]["buy_aud"], 25500.0)

    def test_external_ladders_do_not_change_existing_default(self):
        self.assertEqual(risk_buy_multiplier(0.05), 3.0)
        self.assertEqual(risk_buy_multiplier(0.30), 1.5)
        self.assertEqual(risk_buy_multiplier(0.50), 1.0)

    def test_invalid_custom_ladder_rejected(self):
        with self.assertRaises(ValueError):
            risk_buy_multiplier(0.2, ((0.3, 2.0), (0.2, 1.0), (1.0, 0.0)))


if __name__ == "__main__":
    unittest.main()
