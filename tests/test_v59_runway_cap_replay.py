"""Deterministic research replay acceptance tests; no live market data."""
import unittest
from datetime import date, timedelta
from engines.research.v59_runway_cap_replay import replay_runway_cap


class RunwayCapReplayTests(unittest.TestCase):
    def setUp(self):
        start = date(2026, 11, 9)
        self.rows = [dict(date=start + timedelta(days=7*i),
                          btc_price_aud=100000.0, raw_risk_weight=2.0)
                     for i in range(4)]
        self.options = dict(capital_aud=500000., reserve_aud=100000.,
                            review_date=date(2027, 1, 4))

    def test_cap_order_and_reserve(self):
        a = [replay_runway_cap(self.rows, cap=cap, **self.options)
             for cap in (1., 1.5, 2.)]
        self.assertLess(a[0]["invested_aud"], a[1]["invested_aud"])
        self.assertLess(a[1]["invested_aud"], a[2]["invested_aud"])
        self.assertTrue(all(x["cash_aud"] >= 100000. for x in a))

    def test_no_forced_final_spend(self):
        x = replay_runway_cap(self.rows[:1], cap=1., **self.options)
        self.assertGreater(x["cash_aud"], 100000.)

    def test_missing_risk_is_rejected(self):
        bad = [dict(self.rows[0], raw_risk_weight=float("nan"))]
        with self.assertRaises(ValueError):
            replay_runway_cap(bad, cap=1., **self.options)

    def test_fee_and_slippage_reduce_btc(self):
        a = replay_runway_cap(self.rows, cap=1., **self.options)
        b = replay_runway_cap(self.rows, cap=1., fee_pct=0.001,
                              slippage_pct=0.002, **self.options)
        self.assertLess(b["btc_held"], a["btc_held"])
        self.assertAlmostEqual(b["cash_aud"], a["cash_aud"])

    def test_no_deployment_when_fully_reserved(self):
        x = replay_runway_cap(self.rows, cap=2., capital_aud=500000.,
                              reserve_aud=500000., review_date=date(2027, 1, 4))
        self.assertEqual(x["btc_held"], 0.)

    def test_duplicate_dates_rejected(self):
        with self.assertRaises(ValueError):
            replay_runway_cap(self.rows[:1]*2, cap=1., **self.options)


if __name__ == "__main__":
    unittest.main()
