import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from engines.production import production_model as production
from engines.research import research_model as research
from engines.shared.dca_purchase_status import dca_purchase_display


EXPECTED = [
    (0.00, 10.0),
    (0.01, 5.0),
    (0.02, 3.0),
    (0.05, 2.0),
    (0.10, 1.5),
    (0.20, 1.0),
    (0.40, 0.0),
]


class AppRiskLadderTests(unittest.TestCase):
    def test_both_scripts_share_the_same_default_ladder(self):
        self.assertEqual(production.SMART_DCA_POINTS, EXPECTED)
        self.assertEqual(research.SMART_DCA_POINTS, EXPECTED)
        self.assertEqual(production.DEFAULT_ALWAYS_DCA_POINTS, EXPECTED)
        self.assertEqual(research.DEFAULT_ALWAYS_DCA_POINTS, EXPECTED)

    def test_exact_band_boundaries_and_values_in_both_models(self):
        cases = [
            (0.0, 10.0), (0.009999, 10.0),
            (0.01, 5.0), (0.019999, 5.0),
            (0.02, 3.0), (0.049999, 3.0),
            (0.05, 2.0), (0.099999, 2.0),
            (0.10, 1.5), (0.199999, 1.5),
            (0.20, 1.0), (0.399999, 1.0),
            (0.40, 0.0), (0.50, 0.0), (1.0, 0.0),
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

    def _one_row_history(self, risk):
        day = pd.Timestamp("2026-11-16")
        return pd.DataFrame(
            {"price": [100000.0], "usd_per_aud": [0.65], "risk_score": [risk]},
            index=pd.DatetimeIndex([day]),
        )

    def _backtest_params(self):
        day = pd.Timestamp("2026-11-16")
        return {
            "start_date": day,
            "end_date": day,
            "risk_model": "Test fixture",
            "day_of_week": 0,
            "fee_pct": 0.0,
        }

    def test_production_historical_backtest_executes_requested_risk_bands(self):
        for risk, expected_multiplier, expected_buy in (
            (0.00, 10.0, 10000.0),
            (0.01, 5.0, 5000.0),
            (0.02, 3.0, 3000.0),
            (0.05, 2.0, 2000.0),
            (0.10, 1.5, 1500.0),
            (0.20, 1.0, 1000.0),
            (0.40, 0.0, 0.0),
        ):
            with self.subTest(risk=risk):
                with patch.object(production, "add_risk_indicators", side_effect=lambda df, *_: df):
                    result, summary = production.simulate_dca_backtest(
                        self._one_row_history(risk), self._backtest_params(),
                        1000.0, "Weekly", "Risk-Scaled DCA",
                        risk_curve=production.SMART_DCA_POINTS,
                    )
                self.assertEqual(float(result.iloc[0]["dca_multiplier"]), expected_multiplier)
                self.assertEqual(float(result.iloc[0]["actual_buy_aud"]), expected_buy)
                self.assertEqual(summary["buy_count"], int(expected_buy > 0))

    def test_research_historical_backtest_executes_requested_risk_bands(self):
        for risk, expected_multiplier, expected_buy in (
            (0.00, 10.0, 10000.0),
            (0.01, 5.0, 5000.0),
            (0.02, 3.0, 3000.0),
            (0.05, 2.0, 2000.0),
            (0.10, 1.5, 1500.0),
            (0.20, 1.0, 1000.0),
            (0.40, 0.0, 0.0),
        ):
            with self.subTest(risk=risk):
                with patch.object(research, "add_risk_indicators", side_effect=lambda df, *_: df):
                    result, summary = research.simulate_dca_backtest(
                        self._one_row_history(risk), self._backtest_params(),
                        1000.0, "Weekly", "Risk-Scaled DCA",
                        risk_curve=research.SMART_DCA_POINTS,
                    )
                self.assertEqual(float(result.iloc[0]["dca_multiplier"]), expected_multiplier)
                self.assertEqual(float(result.iloc[0]["actual_buy_aud"]), expected_buy)
                self.assertEqual(summary["buy_count"], int(expected_buy > 0))

    def test_dca_today_paths_remove_fixed_weekly_cap_and_stop_at_040(self):
        production_source = Path("engines/production/production_app.py").read_text(encoding="utf-8")
        research_source = Path("engines/research/research_app.py").read_text(encoding="utf-8")
        self.assertIn("risk_band_multiplier(smart_dca_curve, current_risk)", production_source)
        self.assertIn("risk_band_multiplier(smart_dca_curve, current_risk)", research_source)
        self.assertNotIn("float(starting_capital_aud) * 0.05", production_source)
        self.assertNotIn("float(starting_capital_aud) * 0.05", research_source)
        self.assertIn("and current_risk < 0.40", research_source)

    def test_shared_purchase_display_blocks_unverified_portfolio(self):
        result = dca_purchase_display(
            portfolio_verified=False, risk_multiplier=0.05,
            effective_multiplier=10.0, recommended_buy_aud=0.0,
            base_allowance_aud=1000.0, remaining_capital_aud=50000.0,
        )
        self.assertEqual(result["amount"], "BLOCKED")
        self.assertEqual(result["pill"], "PORTFOLIO NOT VERIFIED")
        self.assertEqual(result["allowance"], "Unavailable")
        self.assertEqual(result["remaining"], "Unavailable")

    def test_unverified_portfolio_explains_exact_blocker(self):
        result = dca_purchase_display(
            portfolio_verified=False, risk_multiplier=0.0,
            effective_multiplier=0.0, recommended_buy_aud=0.0,
            base_allowance_aud=0.0, remaining_capital_aud=0.0,
            portfolio_verification_reason="Only a browser-recovery copy is available. Save to server storage.",
        )
        self.assertIn("browser-recovery copy", result["reason_sub"])

    def test_shared_purchase_display_does_not_show_buy_when_cash_is_zero(self):
        result = dca_purchase_display(
            portfolio_verified=True, risk_multiplier=0.05,
            effective_multiplier=16.0, recommended_buy_aud=0.0,
            base_allowance_aud=0.0, remaining_capital_aud=0.0,
        )
        self.assertEqual(result["amount"], "A$ 0")
        self.assertEqual(result["pill"], "NO BUY — NO DEPLOYABLE CASH")
        self.assertEqual(result["pill_class"], "blocked")

    def test_shared_purchase_display_obeys_risk_no_buy_band(self):
        result = dca_purchase_display(
            portfolio_verified=True, risk_multiplier=0.0,
            effective_multiplier=0.0, recommended_buy_aud=0.0,
            base_allowance_aud=1000.0, remaining_capital_aud=10000.0,
        )
        self.assertEqual(result["pill"], "NO BUY THIS WEEK")
        self.assertEqual(result["reason_title"], "Risk policy: NO BUY")

    def test_research_can_explain_040_without_changing_shared_default(self):
        common = dict(
            portfolio_verified=True, risk_multiplier=0.0,
            effective_multiplier=0.0, recommended_buy_aud=0.0,
            base_allowance_aud=1000.0, remaining_capital_aud=10000.0,
        )
        production_default = dca_purchase_display(**common)
        research = dca_purchase_display(**common, no_buy_threshold=0.40)
        self.assertIn("0.50", production_default["reason_sub"])
        self.assertIn("0.40", research["reason_sub"])

    def test_shared_purchase_display_shows_buy_only_for_positive_verified_amount(self):
        result = dca_purchase_display(
            portfolio_verified=True, risk_multiplier=0.05,
            effective_multiplier=16.0, recommended_buy_aud=25000.0,
            base_allowance_aud=2000.0, remaining_capital_aud=50000.0,
        )
        self.assertEqual(result["pill"], "BUY THIS WEEK")
        self.assertEqual(result["amount"], "A$ 25,000")
        self.assertEqual(result["pill_class"], "ready")

    def test_both_dashboards_use_shared_status_and_no_obsolete_claims(self):
        production_source = Path("engines/production/production_app.py").read_text(encoding="utf-8")
        research_source = Path("engines/research/research_app.py").read_text(encoding="utf-8")
        for source in (production_source, research_source):
            self.assertIn("dca_purchase_display(", source)
            self.assertNotIn("V5.8.2 always buys", source)
            self.assertNotIn("Why only 1×?", source)
            self.assertNotIn("R2 raised to at least", source)
        self.assertNotIn("16× / 8× / 4×", research_source)
        self.assertNotIn("5% of starting capital per week", research_source)


if __name__ == "__main__":
    unittest.main()
