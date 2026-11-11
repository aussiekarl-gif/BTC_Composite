"""Deterministic tests for a research-only, non-promoting V5.9 input gate."""
import csv
from datetime import date
from pathlib import Path
import tempfile
import unittest

from engines.research.v59_input_readiness import audit_file

FIELDS = ["date", "risk_score", "risk_score_source", "btc_price_aud",
          "src__blockchain_btc_usd", "src__frankfurter_usd_per_aud"]


def row(day, *, risk="", source="", aud="", usd="", fx=""):
    return dict(zip(FIELDS, [day, risk, source, aud, usd, fx]))


class ResearchInputReadiness(unittest.TestCase):
    def audit(self, data, asof=date(2026, 11, 11)):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "PRIVATE_SYNTHETIC_ONLY.csv"
            with path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(data)
            return audit_file(path, asof=asof)

    def test_archived_august_power_law_not_live_november_v59(self):
        actual_shape = [
            row("2026-08-31", risk="0", source="Walk-forward Power Law",
                aud="108478.588889", usd="77690.03", fx=".716"),
            row("2026-11-10", usd="75215.41", fx=".6903693476"),
        ]
        report = self.audit(actual_shape)
        self.assertEqual(report["risk_age_days"], 72)
        self.assertEqual(report["risk_latest_date"], "2026-08-31")
        self.assertEqual(report["btc_usd_reference_latest_date"], "2026-11-10")
        self.assertTrue(report["market_reference_fresh"])
        self.assertFalse(report["risk_weekly_fresh"])
        self.assertFalse(report["ready_to_promote_3x"])
        self.assertIn("RISK_SERIES_NOT_LIVE_V59_COMPOSITE", report["reasons"])

    def test_even_fresh_power_law_is_not_reconstructed_v59(self):
        report = self.audit([row("2026-11-10", risk=".2",
                                 source="Walk-forward Power Law", aud="105000",
                                 usd="75000", fx=".714")])
        self.assertTrue(report["risk_weekly_fresh"])
        self.assertFalse(report["is_live_v59_reconstruction"])
        self.assertFalse(report["ready_for_v59_trading_claim"])
        self.assertIn("RISK_SERIES_NOT_LIVE_V59_COMPOSITE", report["reasons"])

    def test_label_alone_cannot_attest_provenance(self):
        report = self.audit([row("2026-11-10", risk=".1", source="V5.9 Composite",
                                 aud="100000", usd="75000", fx=".75")])
        self.assertFalse(report["historical_point_in_time_provenance_verified"])
        self.assertFalse(report["ready_to_promote_3x"])
        self.assertIn("HISTORICAL_PROVIDER_VINTAGES_NOT_ATTESTED", report["reasons"])

    def test_stale_reference_data_reported_separately(self):
        report = self.audit([row("2026-11-01", risk=".3", source="Walk-forward Power Law",
                                 aud="100000", usd="75000", fx=".75")])
        self.assertFalse(report["market_reference_fresh"])
        self.assertIn("MARKET_REFERENCE_STALE_OR_ABSENT", report["reasons"])

    def test_future_date_and_duplicate_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Future-dated"):
            self.audit([row("2026-11-12")])
        with self.assertRaisesRegex(ValueError, "Duplicate or unsorted"):
            self.audit([row("2026-11-10"), row("2026-11-10")])

    def test_incomplete_or_invalid_risk_is_rejected(self):
        for sample in (
            row("2026-11-10", risk=".1", aud="10000"),
            row("2026-11-10", risk="1.1", source="Walk-forward Power Law", aud="10000"),
            row("2026-11-10", risk="nan", source="Walk-forward Power Law", aud="10000"),
            row("2026-11-10", risk=".3", source="Walk-forward Power Law", aud="-1"),
        ):
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                self.audit([sample])

    def test_missing_risk_does_not_inherit_old_score(self):
        report = self.audit([row("2026-11-10", usd="75215.41", fx=".69")])
        self.assertIsNone(report["risk_latest_date"])
        self.assertFalse(report["risk_weekly_fresh"])
        self.assertFalse(report["ready_for_v59_trading_claim"])


if __name__ == "__main__":
    unittest.main()
