from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path

import pandas as pd

from engines.shared.portfolio_buy_tables import (
    add_btc_usd_reference,
    parse_portfolio_date,
)


ROOT = Path(__file__).resolve().parents[1]


class SharedPortfolioBuyTablesTests(unittest.TestCase):
    def test_both_apps_use_the_same_purchase_and_calculated_table_renderers(self):
        for relative in (
            "engines/production/production_app.py",
            "engines/research/research_app.py",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("render_purchase_editor(", source)
            self.assertIn("render_calculated_transactions(", source)
            self.assertIn("add_btc_usd_reference(", source)
            self.assertNotIn('st.subheader("Purchases")', source)
            self.assertNotIn('st.subheader("Calculated Transactions")', source)

    def test_date_parser_accepts_australian_and_iso_dates(self):
        self.assertEqual(parse_portfolio_date("16/11/26"), dt.date(2026, 11, 16))
        self.assertEqual(parse_portfolio_date("2026-11-16"), dt.date(2026, 11, 16))
        self.assertIsNone(parse_portfolio_date("not a date"))

    def test_btc_usd_is_same_date_or_previous_observation_only(self):
        today = dt.date(2026, 11, 16)
        frame = pd.DataFrame({
            "Date": ["14/11/26", "15/11/26", "16/11/26", "17/11/26"],
            "Asset": ["ASX:IBIT"] * 4,
        })
        history = pd.DataFrame(
            {"price": [100_000.0, 101_000.0]},
            index=pd.to_datetime(["2026-11-14", "2026-11-16"], utc=True),
        )
        calls = []
        def fetch(start, end):
            calls.append((start, end))
            return history

        result = add_btc_usd_reference(frame, fetch, today=today)
        self.assertEqual(result["BTC Price (USD)"].tolist()[:3],
                         [100_000.0, 100_000.0, 101_000.0])
        self.assertTrue(pd.isna(result.loc[3, "BTC Price (USD)"]))
        self.assertEqual(len(calls), 1)

    def test_reference_lookup_does_not_mutate_authoritative_rows(self):
        frame = pd.DataFrame({"Date": ["16/11/26"], "AUD Spent": [1234.0]})
        history = pd.DataFrame(
            {"price": [101_000.0]},
            index=pd.to_datetime(["2026-11-16"], utc=True),
        )
        result = add_btc_usd_reference(frame, lambda *_: history,
                                       today=dt.date(2026, 11, 16))
        self.assertNotIn("BTC Price (USD)", frame.columns)
        self.assertEqual(frame.loc[0, "AUD Spent"], 1234.0)
        self.assertEqual(result.loc[0, "BTC Price (USD)"], 101_000.0)


if __name__ == "__main__":
    unittest.main()
