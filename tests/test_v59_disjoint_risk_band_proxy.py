"""Deterministic acceptance checks; synthetic data only, no live alerts."""
import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from engines.research.v59_disjoint_risk_band_proxy import (
    load_proxy_weekly, simulate, compare_windows,
)


class DisjointRiskBandProxyTests(unittest.TestCase):
    def setUp(self):
        start = date(2026, 1, 5)
        self.rows = [
            dict(date=start + timedelta(days=i*7), btc_price_aud=100000.,
                 risk_score=0.01, risk_score_source="Walk-forward Power Law")
            for i in range(8)
        ]
        self.params = dict(
            capital_aud=500000., reserve_aud=100000.,
            review_date=date(2027, 12, 31),
        )

    def test_aggressive_accumulates_more_when_low_risk(self):
        a = simulate(self.rows, policy="risk_1x", **self.params)
        b = simulate(self.rows, policy="risk_2x", **self.params)
        c = simulate(self.rows, policy="risk_3x", **self.params)
        self.assertLess(a["btc_held"], b["btc_held"])
        self.assertLess(b["btc_held"], c["btc_held"])
        self.assertTrue(all(x["cash_aud"] >= 100000. for x in (a, b, c)))
        self.assertTrue(all(x["filled_orders"] == 7 for x in (a, b, c)))

    def test_prior_risk_not_current_risk_drives_buy(self):
        dates = self.rows[:2]
        dates[0] = dict(dates[0], risk_score=.51)
        dates[1] = dict(dates[1], risk_score=.01)
        no_buy = simulate(dates, policy="risk_3x", **self.params)
        self.assertEqual(no_buy["filled_orders"], 0)
        dates[0] = dict(dates[0], risk_score=.01)
        dates[1] = dict(dates[1], risk_score=.99)
        yes_buy = simulate(dates, policy="risk_3x", **self.params)
        self.assertEqual(yes_buy["filled_orders"], 1)

    def test_costs_and_reserve(self):
        with_cost = simulate(self.rows, policy="risk_3x", **self.params)
        no_cost = simulate(self.rows, policy="risk_3x",
                           capital_aud=500000., reserve_aud=100000.,
                           review_date=date(2027, 12, 31),
                           flat_fee_aud=0., variable_cost_fraction=0.)
        self.assertLess(with_cost["btc_held"], no_cost["btc_held"])
        self.assertGreater(with_cost["total_cost_aud"], 0.)
        self.assertAlmostEqual(with_cost["cash_aud"], no_cost["cash_aud"])
        self.assertGreaterEqual(with_cost["cash_aud"], 100000.)

    def test_above_half_risk_causes_no_buy(self):
        rows = [dict(row, risk_score=.50001) for row in self.rows]
        for pol in ("risk_1x", "risk_2x", "risk_3x"):
            result = simulate(rows, policy=pol, **self.params)
            self.assertEqual(result["btc_held"], 0.)
            self.assertEqual(result["cash_aud"], 500000.)

    def test_weekly_ceiling_limits_even_aggressive(self):
        rows = self.rows[:2]
        result = simulate(rows, policy="risk_3x",
                          capital_aud=500000., reserve_aud=0.,
                          review_date=date(2026, 1, 12),
                          weekly_cap_fraction=.05)
        self.assertLessEqual(result["invested_aud"], 25000. + 1e-8)

    def test_decline_stress_cannot_increase_equity(self):
        result = simulate(self.rows, policy="risk_3x", **self.params)
        self.assertLess(result["equity_after_immediate_50pct_btc_drop_aud"],
                        result["equity_aud"])

    def test_rejects_invalid_inputs_or_weekly_gaps(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    simulate(self.rows, policy="risk_3x", **dict(self.params, capital_aud=bad))
                with self.assertRaises(ValueError):
                    simulate(self.rows, policy="risk_3x", **self.params,
                             variable_cost_fraction=bad)
        with self.assertRaises(ValueError):
            simulate(self.rows, policy="risk_3x", **self.params,
                     weekly_cap_fraction=0.)
        with self.assertRaises(ValueError):
            simulate([self.rows[0], self.rows[2]], policy="risk_3x", **self.params)

    def test_loader_rejects_missing_duplicate_and_unexpected_risk_source(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "proxy.csv"
            cols = ["date", "btc_price_aud", "risk_score", "risk_score_source"]

            def write(items):
                with path.open("w", encoding="utf-8", newline="") as handle:
                    w = csv.DictWriter(handle, fieldnames=cols)
                    w.writeheader()
                    w.writerows(items)

            items = [
                dict(date="2026-01-05 00:00:00+00:00",
                     btc_price_aud="100000", risk_score="0",
                     risk_score_source="Walk-forward Power Law"),
                dict(date="2026-01-12 00:00:00+00:00",
                     btc_price_aud="110000", risk_score="0.25",
                     risk_score_source="Walk-forward Power Law"),
            ]
            write(items)
            self.assertEqual(len(load_proxy_weekly(path)), 2)
            write(items[:1] + items[:1])
            with self.assertRaises(ValueError):
                load_proxy_weekly(path)
            write(items[:1] + [dict(items[1], risk_score_source="Production")])
            with self.assertRaises(ValueError):
                load_proxy_weekly(path)

    def test_partial_2026_not_mislabelled_as_complete_cycle(self):
        report = compare_windows(self.rows, capital_aud=500000.,
                                 reserves=(0., 100000.))
        period = report["windows"]["2026-2027-PARTIAL"]
        self.assertFalse(period["completed_window"])
        self.assertEqual(period["review_date"], "2027-12-31")
        self.assertTrue(report["not_production_v582_or_v59"])
        self.assertEqual(set(period["reserves"]), {"0", "100000"})
        self.assertEqual(period["prior_observation_executions"], 7)

    def test_comparators_use_identical_inputs(self):
        results = compare_windows(self.rows, reserves=(0.,))
        period = results["windows"]["2026-2027-PARTIAL"]["reserves"]["0"]
        self.assertEqual(period["risk_1x"]["filled_orders"], 7)
        self.assertEqual(period["plain_weekly"]["filled_orders"], 7)
        self.assertEqual(period["lump_next_week"]["filled_orders"], 1)
        self.assertLess(period["risk_1x"]["btc_held"],
                        period["risk_3x"]["btc_held"])


if __name__ == "__main__":
    unittest.main()
