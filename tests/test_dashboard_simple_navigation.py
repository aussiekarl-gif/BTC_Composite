"""Keep the public dashboard limited to frozen Production and V6.0 Research."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


class SimplifiedLauncherTests(unittest.TestCase):
    def test_only_production_research_and_timeline_are_in_navigation(self):
        tree = ast.parse(APP.read_text(encoding="utf-8"))
        radios = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "radio"
        ]
        self.assertEqual(len(radios), 1)
        radio = radios[0]
        self.assertIsInstance(radio.args[1], ast.List)
        self.assertEqual(ast.literal_eval(radio.args[1]), [
            "Production", "Research", "Bottom Signal Timeline",
        ])
        named = {kw.arg: kw.value for kw in radio.keywords}
        self.assertEqual(ast.literal_eval(named["index"]), 0)
        self.assertEqual(ast.literal_eval(named["key"]), "combined_app_section_selector")

    def test_v59_and_cycle_trading_are_archived_not_deleted(self):
        source = APP.read_text(encoding="utf-8")
        self.assertNotIn('"Cycle Trading — Research"', source)
        self.assertNotIn('"engines" / "research" / "research_app.py"', source)
        self.assertNotIn('"research_app.py"', source)
        self.assertTrue((ROOT / "engines" / "research" / "research_app.py").is_file())
        self.assertTrue((ROOT / "engines" / "research" / "cycle_trading_app.py").is_file())
        self.assertTrue((ROOT / "engines" / "research" / "v59_200wma_prospective_paper_tape.py").is_file())

    def test_all_active_launch_targets_exist_and_compile(self):
        expected = [
            ROOT / "engines" / "production" / "production_app.py",
            ROOT / "engines" / "research" / "v60_research_app.py",
            ROOT / "engines" / "audit" / "bottom_signal_timeline_app.py",
        ]
        for target in expected:
            with self.subTest(file=target.name):
                self.assertTrue(target.is_file())
                compile(target.read_text(encoding="utf-8"), str(target), "exec")

    def test_v60_research_app_is_independent_and_non_executable(self):
        source = (ROOT / "engines" / "research" / "v60_research_app.py").read_text(encoding="utf-8")
        self.assertNotIn("v59_", source)
        self.assertNotIn("production_model", source)
        self.assertIn("V6.0", source)
        self.assertIn("trade_executable", source)

    def test_retired_tier_page_remains_unlinked(self):
        source = APP.read_text(encoding="utf-8")
        self.assertNotIn('"200WMA Trading Model"', source)
        self.assertNotIn("wma_tier_app.py", source)


if __name__ == "__main__":
    unittest.main()
