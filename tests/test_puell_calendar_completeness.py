"""Isolated Puell calendar completeness tests without importing Streamlit UI."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

SOURCE = Path(__file__).resolve().parents[1] / "engines/audit/public_model_audit.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_free_indicator_cache")
code = compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec")

class PuellCalendarTests(unittest.TestCase):
    def compute(self, series):
        scope = {"pd": pd, "np": np, "_cm_get": lambda metric, *_:
                 series.get(metric, pd.Series(dtype=float))}
        exec(code, scope)
        return scope["build_free_indicator_cache"]("2024-01-01", "2026-01-01")

    def test_direct_issuance_365_consecutive_days(self):
        idx = pd.date_range("2024-01-01", periods=365, tz="UTC")
        out, statuses = self.compute({"IssTotUSD": pd.Series(100., index=idx)})
        self.assertAlmostEqual(float(out["Puell Multiple"].dropna().iloc[-1]), 1.)
        self.assertTrue(any("from IssTotUSD" in x["Status"] for x in statuses))

    def test_nonconsecutive_direct_falls_back_to_complete_native(self):
        idx = pd.date_range("2024-01-01", periods=400, tz="UTC")
        direct = pd.Series(100., index=idx).drop(idx[200])
        native = pd.Series(2., index=idx)
        price = pd.Series(50., index=idx)
        out, statuses = self.compute({"IssTotUSD": direct, "IssTotNtv": native, "PriceUSD": price})
        self.assertAlmostEqual(float(out["Puell Multiple"].dropna().iloc[-1]), 1.)
        self.assertTrue(any("IssTotNtv * PriceUSD" in x["Status"] for x in statuses))

    def test_direct_missing_day_with_no_fallback_stays_unavailable(self):
        idx = pd.date_range("2024-01-01", periods=365, tz="UTC")
        direct = pd.Series(100., index=idx).drop(idx[100])
        out, statuses = self.compute({"IssTotUSD": direct})
        self.assertNotIn("Puell Multiple", out.columns)
        self.assertTrue(any("Could not calculate" in x["Status"] for x in statuses))

    def test_native_missing_day_falls_back_to_revenue_minus_fees(self):
        idx = pd.date_range("2024-01-01", periods=365, tz="UTC")
        native = pd.Series(2., index=idx).drop(idx[180])
        revenue = pd.Series(2.5, index=idx)
        fees = pd.Series(0.5, index=idx)
        price = pd.Series(50., index=idx)
        out, statuses = self.compute({"IssTotNtv": native, "RevNtv": revenue,
                                      "FeeTotNtv": fees, "PriceUSD": price})
        self.assertAlmostEqual(float(out["Puell Multiple"].dropna().iloc[-1]), 1.)
        self.assertTrue(any("RevNtv - FeeTotNtv fallback" in x["Status"] for x in statuses))

    def test_zero_issuance_does_not_create_infinite_puell(self):
        idx = pd.date_range("2024-01-01", periods=365, tz="UTC")
        out, _ = self.compute({"IssTotUSD": pd.Series(0., index=idx)})
        self.assertTrue(out["Puell Multiple"].dropna().empty)

    def test_misaligned_native_price_dates_never_create_false_window(self):
        idx = pd.date_range("2024-01-01", periods=365, tz="UTC")
        native = pd.Series(2., index=idx)
        price = pd.Series(50., index=idx + pd.Timedelta(days=1))
        out, _ = self.compute({"IssTotNtv": native, "PriceUSD": price})
        self.assertTrue(out["Puell Multiple"].dropna().empty)

    def test_incomplete_all_sources_do_not_invent_puell(self):
        idx = pd.date_range("2024-01-01", periods=200, tz="UTC")
        out, statuses = self.compute({"IssTotUSD": pd.Series(100., index=idx)})
        self.assertNotIn("Puell Multiple", out.columns)
        self.assertTrue(any("Could not calculate" in x["Status"] for x in statuses))

if __name__ == "__main__":
    unittest.main()
