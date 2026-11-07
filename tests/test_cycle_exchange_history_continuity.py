import unittest
import pandas as pd
from engines.research.cycle_exchange_history_continuity import audit_continuity


class ContinuityTests(unittest.TestCase):
    def test_agreement_does_not_imply_coverage(self):
        archive = pd.DataFrame({"price_usd": [100.]}, index=pd.date_range("2026-10-05", periods=1, tz="UTC"))
        idx = pd.date_range("2026-10-30", "2026-11-06", tz="UTC")
        exchange = pd.DataFrame({"btc_usd": [100.] * len(idx)}, index=idx)
        report = audit_continuity(archive, exchange, exchange.copy(), utc_today="2026-11-07")
        self.assertEqual(report["exchange_agreement"], "RESEARCH_ONLY_VERIFIED")
        self.assertFalse(report["full_continuity_verified"])
        self.assertEqual(report["first_uncovered_utc"], "2026-10-06")
        self.assertEqual(report["uncovered_days_after_archive"], 24)
        self.assertFalse(report["trading_enabled"])

    def test_complete_coverage(self):
        archive = pd.DataFrame({"price_usd": [100.]}, index=pd.date_range("2026-11-02", periods=1, tz="UTC"))
        idx = pd.date_range("2026-10-30", "2026-11-06", tz="UTC")
        exchange = pd.DataFrame({"btc_usd": [100.] * len(idx)}, index=idx)
        report = audit_continuity(archive, exchange, exchange.copy(), utc_today="2026-11-07")
        self.assertTrue(report["full_continuity_verified"])
        self.assertEqual(report["uncovered_days_after_archive"], 0)


if __name__ == "__main__":
    unittest.main()
