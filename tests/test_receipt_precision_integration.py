"""Regression guard for source receipt precision; legacy records are not rewritten."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "engines/research/btc_spot_depth_forward.py",
    ROOT / "engines/research/coinbase_trade_samples.py",
)


class ReceiptPrecisionTests(unittest.TestCase):
    def test_both_capture_modules_preserve_microseconds(self):
        for path in SOURCES:
            with self.subTest(module=path.name):
                source = path.read_text(encoding="utf-8")
                ast.parse(source)
                self.assertIn('isoformat(timespec="microseconds")', source)
                self.assertNotIn('isoformat(timespec="seconds")', source)

    def test_legacy_seconds_and_new_microseconds_are_parseable(self):
        import datetime as dt
        old = dt.datetime.fromisoformat("2026-11-07T07:00:01+00:00")
        new = dt.datetime.fromisoformat("2026-11-07T07:00:01.123456+00:00")
        self.assertLess(old, new)
        self.assertEqual(new.isoformat(timespec="microseconds"),
                         "2026-11-07T07:00:01.123456+00:00")


if __name__ == "__main__":
    unittest.main()
