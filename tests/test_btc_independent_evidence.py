"""Network-free research evidence safeguards."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from engines.research.btc_independent_evidence import Evidence, evaluate_evidence

NOW = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)


def vote(family, direction):
    return Evidence(family=family, direction=direction,
                    observed_at=NOW-timedelta(hours=3),
                    captured_at=NOW-timedelta(hours=1),
                    source="dated verified observation",
                    rationale="hypothesis only")


class EvidenceGateTests(unittest.TestCase):
    def test_two_buys_watch_not_order(self):
        r = evaluate_evidence([vote("cycle", "BUY"), vote("spot_flow", "BUY")], as_of_utc=NOW)
        self.assertEqual((r.status, r.candidate_direction), ("RESEARCH_WATCH", "BUY"))
        self.assertFalse(r.executable)
        self.assertTrue(r.paper_only)
        self.assertEqual(r.executable_order_aud, 0)

    def test_two_sells_watch_not_order(self):
        r = evaluate_evidence([vote("cycle", "SELL"), vote("onchain", "SELL")], as_of_utc=NOW)
        self.assertEqual((r.status, r.candidate_direction), ("RESEARCH_WATCH", "SELL"))
        self.assertEqual(r.executable_order_aud, 0)

    def test_correlated_price_models_not_independent(self):
        r = evaluate_evidence([vote("cycle", "BUY"), vote("valuation", "BUY")], as_of_utc=NOW)
        self.assertEqual(r.status, "INSUFFICIENT_EVIDENCE")

    def test_opposite_vote_vetoes(self):
        r = evaluate_evidence([vote("cycle", "BUY"), vote("spot_flow", "BUY"),
                               vote("onchain", "SELL")], as_of_utc=NOW)
        self.assertEqual(r.status, "CONFLICT")
        self.assertEqual(r.executable_order_aud, 0)

    def test_one_family_cannot_decide(self):
        self.assertEqual(evaluate_evidence([vote("onchain", "BUY")], as_of_utc=NOW).status,
                         "INSUFFICIENT_EVIDENCE")

    def test_duplicate_family_never_counts(self):
        r = evaluate_evidence([vote("cycle", "BUY"), vote("cycle", "BUY"),
                               vote("valuation", "BUY")], as_of_utc=NOW)
        self.assertEqual(r.status, "INSUFFICIENT_EVIDENCE")
        self.assertTrue(any("duplicate" in x for x in r.rejected))

    def test_stale_never_votes(self):
        v = replace(vote("spot_flow", "BUY"), observed_at=NOW-timedelta(hours=40),
                    captured_at=NOW-timedelta(hours=39))
        r = evaluate_evidence([vote("cycle", "BUY"), v], as_of_utc=NOW)
        self.assertEqual(r.status, "INSUFFICIENT_EVIDENCE")
        self.assertTrue(any("stale" in x for x in r.rejected))

    def test_future_observation_rejected(self):
        v = replace(vote("onchain", "BUY"), observed_at=NOW+timedelta(hours=1),
                    captured_at=NOW+timedelta(hours=2))
        r = evaluate_evidence([vote("cycle", "BUY"), v], as_of_utc=NOW)
        self.assertEqual(r.status, "INSUFFICIENT_EVIDENCE")
        self.assertTrue(any("future" in x for x in r.rejected))

    def test_observation_after_capture_rejected(self):
        v = replace(vote("spot_flow", "BUY"), observed_at=NOW,
                    captured_at=NOW-timedelta(hours=1))
        self.assertEqual(evaluate_evidence([vote("cycle", "BUY"), v], as_of_utc=NOW).status,
                         "INSUFFICIENT_EVIDENCE")

    def test_source_missing(self):
        v = replace(vote("onchain", "BUY"), source="")
        self.assertEqual(evaluate_evidence([vote("cycle", "BUY"), v], as_of_utc=NOW).status,
                         "INSUFFICIENT_EVIDENCE")

    def test_unusable_source(self):
        v = replace(vote("onchain", "BUY"), usable=False)
        self.assertEqual(evaluate_evidence([vote("cycle", "BUY"), v], as_of_utc=NOW).status,
                         "INSUFFICIENT_EVIDENCE")

    def test_all_hold_is_not_buy(self):
        r = evaluate_evidence([vote("cycle", "HOLD"), vote("spot_flow", "HOLD")], as_of_utc=NOW)
        self.assertEqual((r.status, r.candidate_direction), ("INSUFFICIENT_EVIDENCE", "NONE"))

    def test_naive_as_of_fails(self):
        with self.assertRaises(ValueError):
            evaluate_evidence([], as_of_utc=datetime(2026,10,19))

    def test_zero_max_age_fails(self):
        with self.assertRaises(ValueError):
            evaluate_evidence([], as_of_utc=NOW,max_age=timedelta(0))


if __name__ == "__main__":
    unittest.main()
