"""Keep Production frozen while exposing independent research pages."""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


class SimplifiedLauncherTests(unittest.TestCase):
    def test_restored_models_and_timeline_are_in_navigation(self):
        tree = ast.parse(APP.read_text(encoding="utf-8"))
        radios = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "radio"
        ]
        self.assertEqual(len(radios), 1)
        radio = radios[0]
        options_assignment = next(
            n for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "MODEL_OPTIONS"
                    for t in n.targets)
        )
        options = ast.literal_eval(options_assignment.value)
        self.assertEqual(options, [
            "Production", "Research 10.0",
            "Cycle Trading — Research", "Bottom Signal Timeline",
        ])
        self.assertEqual(radio.args[1].id, "MODEL_OPTIONS")
        named = {kw.arg: kw.value for kw in radio.keywords}
        self.assertEqual(ast.literal_eval(named["index"]), 0)
        selector_assignment = next(
            n for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "MODEL_SELECTOR_KEY"
                    for t in n.targets)
        )
        self.assertEqual(ast.literal_eval(named["key"]), ast.literal_eval(selector_assignment.value))

    def test_retired_v59_and_cowen_pages_are_not_routed_or_listed(self):
        source = APP.read_text(encoding="utf-8")
        tree = ast.parse(source)
        options_node = next(
            n for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "MODEL_OPTIONS"
                    for t in n.targets)
        )
        options = ast.literal_eval(options_node.value)
        self.assertNotIn("Research V5.9", options)
        self.assertNotIn("Cowen Risk Matrix", options)
        self.assertIn('"Cycle Trading — Research"', source)
        self.assertIn('"Research 10.0"', source)
        self.assertIn('"engines" / "research" / "cycle_trading_app.py"', source)
        self.assertIn('"engines" / "research" / "cowen_onchain_risk_app.py"', source)
        # Retiring navigation must not delete historical research artefacts.
        for name in ("research_app.py", "cycle_trading_app.py",
                     "v59_200wma_prospective_paper_tape.py",
                     "cowen_onchain_risk_app.py"):
            self.assertTrue((ROOT / "engines" / "research" / name).is_file())

    def test_all_active_launch_targets_exist_and_compile(self):
        expected = [
            ROOT / "engines" / "production" / "production_app.py",
            ROOT / "engines" / "research" / "research_app.py",
            ROOT / "engines" / "research" / "cowen_onchain_risk_app.py",
            ROOT / "engines" / "research" / "cycle_trading_app.py",
            ROOT / "engines" / "research" / "v60_200wma_paper_tape.py",
            ROOT / "engines" / "audit" / "bottom_signal_timeline_app.py",
        ]
        for target in expected:
            with self.subTest(file=target.name):
                self.assertTrue(target.is_file())
                compile(target.read_text(encoding="utf-8"), str(target), "exec")

    def test_v60_paper_signal_is_independent_and_percentage_only(self):
        from engines.research.v60_200wma_paper_tape import build_paper_signal
        btc = {
            "observation_date_utc": "2026-11-23",
            "captured_at_utc": "2026-11-24T09:00:00+00:00",
            "signal_input_last_prior_close_date_utc": "2026-11-22",
            "prior_btc_usd_close": "74000.000000",
            "prior_200wma_usd": "100000.000000",
            "prior_close_div_200wma": "0.74000000",
            "source_crosscheck_max_diff_pct": "0.0100",
            "market_data_provider": "verified BTC/USD source",
            "row_hash": "b" * 64,
        }
        row = build_paper_signal(btc, model_sha256="c" * 64)
        self.assertEqual(row["measured_20_25_30_buy_pct_deployable_cash"], "5.000000")
        self.assertEqual(row["measured_10_15_20_buy_pct_deployable_cash"], "7.500000")
        self.assertEqual(row["baseline_buy_pct_available_cash"], "2.500000")
        self.assertEqual(row["expected_next_asx_session_sydney"], "2026-11-25")

    def test_v60_snapshot_discloses_sparse_tiers_and_stress_limits(self):
        snapshot_path = ROOT / "data" / "research_forward_validation" / "v60_dashboard_snapshot_2026-11-19.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        historical = snapshot["historical_replay"]
        self.assertEqual(historical["discount_activation_weeks"]["pre_2022_train_era"]["20%"], 0)
        self.assertEqual(historical["discount_activation_weeks"]["2022_onward_holdout_era"]["20%"], 9)
        self.assertEqual(historical["discount_activation_weeks"]["2022_onward_holdout_era"]["25%"], 9)
        self.assertFalse(snapshot["trade_executable"])
        self.assertEqual(snapshot["prospective_paper_tape"]["status"], "awaiting_first_eligible_sunday_close")
        self.assertEqual(snapshot["prospective_paper_tape"]["signal_rows"], 0)
        self.assertIn("zero prospective observations", " ".join(snapshot["limitations"]))

    def test_retired_tier_page_remains_unlinked(self):
        source = APP.read_text(encoding="utf-8")
        self.assertNotIn('"200WMA Trading Model"', source)
        self.assertNotIn("wma_tier_app.py", source)


if __name__ == "__main__":
    unittest.main()
