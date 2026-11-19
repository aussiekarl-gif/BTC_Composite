import unittest
from datetime import date, timedelta

from engines.research.v582_v59_matched_backtest import replay


def cohort():
    start = date(2021, 1, 4)
    rows = []
    for i in range(104):
        day = start + timedelta(weeks=i)
        signal = day - timedelta(days=1)
        rows.append({
            "date": day, "signal_date": signal,
            "btc_price_aud": 50000.0 * (1.004 ** i),
            "v582_risk": 0.05, "v59_risk": 0.05,
            "review_date": start + timedelta(weeks=104),
        })
    return rows


class MatchedV582V59BacktestTests(unittest.TestCase):
    def test_same_path_and_same_inputs_give_identical_risk_replays(self):
        rows = cohort()
        prod = replay(rows, risk_key="v582_risk")
        research = replay(rows, risk_key="v59_risk")
        for key in ("final_equity_aud", "btc_accumulated", "cash_remaining_aud",
                    "fills", "max_drawdown_pct"):
            self.assertAlmostEqual(prod[key], research[key], places=8)

    def test_future_risk_change_cannot_rewrite_earlier_orders(self):
        original = cohort()
        changed = cohort()
        switch = changed[52]["date"]
        for row in changed:
            if row["date"] >= switch:
                row["v59_risk"] = 0.8
        a = replay(original, risk_key="v59_risk")
        b = replay(changed, risk_key="v59_risk")
        before = lambda x: [o for o in x["orders"] if date.fromisoformat(o["date"]) < switch]
        self.assertEqual(before(a), before(b))

    def test_fixed_dca_control_is_independent_of_risk_series(self):
        rows = cohort()
        a = replay(rows, risk_key="v582_risk", fixed_weekly=True)
        for row in rows:
            row["v582_risk"] = 0.99
        b = replay(rows, risk_key="v582_risk", fixed_weekly=True)
        self.assertEqual(a, b)

    def test_risk_replay_rejects_missing_or_invalid_scores(self):
        rows = cohort()
        rows[20]["v582_risk"] = float("nan")
        with self.assertRaisesRegex(ValueError, "Missing or invalid"):
            replay(rows, risk_key="v582_risk")

    def test_missing_week_is_rejected(self):
        rows = cohort()
        rows.pop(20)
        with self.assertRaisesRegex(ValueError, "exactly 104"):
            replay(rows, risk_key="v59_risk")

    def test_common_execution_requires_prior_sunday_signal(self):
        rows = cohort()
        rows[10]["signal_date"] = rows[10]["date"]
        with self.assertRaisesRegex(ValueError, "previous Sunday's signal"):
            replay(rows, risk_key="v59_risk")


if __name__ == "__main__":
    unittest.main()
