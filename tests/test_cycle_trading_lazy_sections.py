"""Cycle Trading UI should avoid eagerly rendering inactive sections."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "engines" / "research" / "cycle_trading_app.py"


class CycleTradingLazySectionTests(unittest.TestCase):
    def test_cycle_sections_are_conditionally_rendered_not_streamlit_tabs(self):
        source = APP.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "tabs"
        ]
        self.assertEqual(calls, [], "st.tabs eagerly executes every section")

        selector = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "radio"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "Cycle Trading section"
        ]
        self.assertEqual(len(selector), 1)

        labels = [
            "Trading decision",
            "My Portfolio — Buy & Sell",
            "Historical sell & buyback",
        ]
        for label in labels:
            self.assertIn(label, source)
        self.assertIn('if cycle_section == "Trading decision":', source)
        self.assertIn('elif cycle_section == "My Portfolio — Buy & Sell":', source)
        self.assertIn('else:  # Historical sell & buyback', source)


if __name__ == "__main__":
    unittest.main()
