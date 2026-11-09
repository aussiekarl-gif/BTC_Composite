"""Deterministic research replay acceptance tests; no live market data."""
import csv
import tempfile
import unittest
from pathlib import Path
from datetime import date, timedelta
from engines.research.v59_runway_cap_replay import replay_runway_cap
from engines.research.v59_runway_cap_backtest import load_rows


class RunwayCapReplayTests(unittest.TestCase):
    def setUp(self):
        start = date(2026, 11, 9)
        self.rows = [dict(date=start + timedelta(days=7*i),
                          signal_date=start + timedelta(days=7*i-1),
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

    def test_rejects_undated_same_day_and_future_signals(self):
        for bad_signal in (None, self.rows[0]["date"], self.rows[0]["date"] + timedelta(days=1)):
            with self.subTest(signal=bad_signal):
                bad = [dict(self.rows[0], signal_date=bad_signal)]
                with self.assertRaises(ValueError):
                    replay_runway_cap(bad, cap=1., **self.options)
        with self.assertRaises(ValueError):
            replay_runway_cap([{k: v for k, v in self.rows[0].items()
                                if k != "signal_date"}], cap=1., **self.options)

    def test_executed_orders_preserve_prior_signal_date(self):
        result = replay_runway_cap(self.rows, cap=1., **self.options)
        self.assertEqual(result["orders"][0]["signal_date"], "2026-11-08")
        self.assertTrue(all(o["signal_date"] < o["date"] for o in result["orders"]))

    def test_nonfinite_capital_cap_and_costs_fail_closed(self):
        for invalid in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    replay_runway_cap(self.rows, cap=invalid, **self.options)
                with self.assertRaises(ValueError):
                    replay_runway_cap(self.rows, cap=1., fee_pct=invalid, **self.options)
                with self.assertRaises(ValueError):
                    replay_runway_cap(self.rows, cap=1., slippage_pct=invalid, **self.options)
                with self.assertRaises(ValueError):
                    replay_runway_cap(self.rows, cap=1., capital_aud=invalid,
                                      reserve_aud=0, review_date=self.options["review_date"])

    def test_cli_loader_requires_earlier_signal_date(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "history.csv"
            def write(columns, signal):
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=columns)
                    writer.writeheader()
                    data = dict(date="2026-11-09", signal_date=signal,
                                btc_price_aud="100000", raw_risk_weight="2")
                    writer.writerow({k: data[k] for k in columns})
            columns = ["date", "signal_date", "btc_price_aud", "raw_risk_weight"]
            write(columns[:-3] + columns[-2:], "2026-11-08")
            with self.assertRaises(ValueError):
                load_rows(path)
            for invalid in ("2026-11-09", "2026-11-10"):
                write(columns, invalid)
                with self.assertRaises(ValueError):
                    load_rows(path)
            write(columns, "2026-11-08")
            self.assertEqual(load_rows(path)[0]["signal_date"], date(2026, 11, 8))


if __name__ == "__main__":
    unittest.main()
