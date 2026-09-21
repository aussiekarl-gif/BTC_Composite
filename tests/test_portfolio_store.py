import tempfile
import unittest
from pathlib import Path

from engines.shared.portfolio_store import load_portfolio, save_portfolio

class PortfolioStoreTests(unittest.TestCase):
    def test_round_trip_and_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "portfolio.sqlite3"
            first = {"starting_capital_aud": 500000.0, "rows": [{"Date": "01/09/26"}]}
            second = {"starting_capital_aud": 500000.0, "rows": [{"Date": "02/09/26"}]}
            self.assertEqual(load_portfolio(db), ({}, None))
            self.assertEqual(save_portfolio(first, db), (True, None))
            self.assertEqual(load_portfolio(db), (first, None))
            self.assertEqual(save_portfolio(second, db), (True, None))
            self.assertEqual(load_portfolio(db), (second, None))

if __name__ == "__main__":
    unittest.main()
