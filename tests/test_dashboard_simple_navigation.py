"""Keep the public Streamlit sidebar simple without changing trading rules.

The standalone experimental 200WMA Trading Model (10 buy / 10 sell
tiers) is intentionally removed from navigation, NOT deleted from
research. Cycle Trading MUST keep its prior-200WMA BUY condition.
"""
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app.py"

class SimplifiedLauncherTests(unittest.TestCase):
    def test_four_dashboard_choices_and_cycle_remains_default(self):
        tree=ast.parse(APP.read_text(encoding="utf-8"))
        radios=[
            n for n in ast.walk(tree)
            if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Attribute)
            and n.func.attr=="radio"
        ]
        self.assertEqual(len(radios),1)
        radio=radios[0]
        self.assertIsInstance(radio.args[1],ast.List)
        choices=ast.literal_eval(radio.args[1])
        self.assertEqual(choices,[
            "Cycle Trading — Research","Production","Research",
            "Bottom Signal Timeline",
        ])
        named={kw.arg:kw.value for kw in radio.keywords}
        self.assertEqual(ast.literal_eval(named["index"]),0)
        self.assertEqual(ast.literal_eval(named["key"]),
                         "combined_app_section_selector")

    def test_independent_tier_page_not_linked_or_removed_from_repo(self):
        source=APP.read_text(encoding="utf-8")
        self.assertNotIn('"200WMA Trading Model"',source)
        self.assertNotIn("wma_tier_app.py",source)
        self.assertTrue((ROOT/"engines"/"research"/"wma_tier_app.py").exists())

    def test_all_four_launch_targets_remain_available(self):
        expected=[
            ROOT/"engines"/"research"/"cycle_trading_app.py",
            ROOT/"engines"/"production"/"production_app.py",
            ROOT/"engines"/"research"/"research_app.py",
            ROOT/"engines"/"audit"/"bottom_signal_timeline_app.py",
        ]
        for target in expected:
            with self.subTest(file=target.name):
                self.assertTrue(target.is_file())
                compile(target.read_text(encoding="utf-8"),str(target),"exec")

    def test_cycle_trading_retains_prior_200wma_market_gate_and_allocation(self):
        from engines.research.cycle_trade_allocation import (
            calculate_allocation_signal,
        )
        source=(ROOT/"engines"/"research"/"cycle_trade_allocation.py").read_text(
            encoding="utf-8")
        self.assertIn("previous_close_below_200wma",source)
        self.assertIn("SELL_REVIEW_DAY_WEIGHTS",source)
        self.assertTrue(callable(calculate_allocation_signal))

if __name__=="__main__":
    unittest.main()
