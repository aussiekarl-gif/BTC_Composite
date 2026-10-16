"""Deterministic ex-post execution quality checks: audit only, no live orders."""
import unittest

import pandas as pd

from engines.research.full_cycle_reinvestment import simulate
from engines.research.execution_error_audit import (
    run_audit, score_execution_plans, summarize,
)


def frame(prices, risks):
    return pd.DataFrame({"btc_price_aud": prices, "risk_score": risks},
                        index=pd.date_range("2019-01-07", periods=len(prices),
                                            freq="W-MON", tz="UTC"))


class ExecutionPriceAuditTests(unittest.TestCase):
    def test_dca_uses_actual_btc_quantity_weighted_execution_price(self):
        prices = [100.0] * 160
        prices[1], prices[2] = 50.0, 100.0
        risk = [0.5] * 160
        risk[0] = 0
        data = frame(prices, risk)
        sim = simulate(data, initial_cash=1000, buy_risk=.35,
                       sell_risk=.60, buy_weeks=2, sell_weeks=2,
                       fee_rate=0)
        rows = score_execution_plans(
            data, sim, buy_weeks=2, sell_weeks=2, initial_cash=1000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["orders"], 2)
        self.assertAlmostEqual(rows[0]["quantity_btc"], 15)
        self.assertAlmostEqual(rows[0]["execution_vwap_aud"], 66.67, places=2)
        self.assertFalse(rows[0]["eligible"])

    def test_sell_peak_miss_and_buy_bottom_miss_measured_without_oracle_trading(self):
        prices = [100.0] * 190
        prices[80] = 200.0
        prices[120] = 50.0
        risk = [0.5] * len(prices)
        risk[0] = 0.1    # initial BUY at week 1
        risk[74] = 0.9   # SELL at week 75
        risk[115] = 0.1  # next BUY at week 116
        data = frame(prices, risk)
        sim = simulate(data, initial_cash=1000, buy_weeks=1, sell_weeks=1,
                       buy_risk=.35, sell_risk=.60, fee_rate=0)
        rows = score_execution_plans(data, sim, buy_weeks=1, sell_weeks=1)
        self.assertEqual([r["side"] for r in rows], ["BUY", "SELL", "BUY"])
        self.assertFalse(rows[0]["eligible"])  # cannot look back a full year
        self.assertTrue(rows[1]["eligible"])
        self.assertTrue(rows[2]["eligible"])
        self.assertAlmostEqual(rows[1]["error_pct"], 50)
        self.assertAlmostEqual(rows[2]["error_pct"], 100)
        totals = summarize(rows)
        self.assertEqual(totals["completed_sell_then_rebuy_pairs"]["n"], 1)
        self.assertEqual(totals["completed_sell_then_rebuy_pairs"]["both_within_threshold_counts"]["25"], 0)

    def test_perfect_price_within_25_percent(self):
        prices = [100.0] * 190
        risk = [0.5] * len(prices)
        risk[0], risk[74], risk[115] = 0.1, 0.9, 0.1
        data = frame(prices, risk)
        sim = simulate(data, initial_cash=1000, buy_weeks=1, sell_weeks=1,
                       buy_risk=.35, sell_risk=.60, fee_rate=0)
        rows = score_execution_plans(data, sim, buy_weeks=1, sell_weeks=1)
        totals = summarize(rows)
        self.assertEqual(totals["completed_sell_then_rebuy_pairs"]["both_within_threshold_counts"]["25"], 1)
        self.assertEqual(totals["by_side"]["SELL"]["within_threshold_counts"]["25"], 1)

    def test_predeclared_12_and_16_week_scenarios(self):
        prices = [100 + 5*(i % 14) for i in range(190)]
        risk = [0.5] * 190
        for i in range(0, 12):
            risk[i] = 0.1
        for i in range(64, 85):
            risk[i] = 0.8
        for i in range(125, 156):
            risk[i] = 0.1
        output = run_audit(frame(prices, risk), fee_rate=0)
        self.assertEqual({x["candidate"] for x in output["candidates"]},
                         {"simple_12", "simple_16", "confirmed_12", "confirmed_16"})
        for c in output["candidates"]:
            self.assertIn("plans_scorable", c["summary"])
            self.assertGreaterEqual(c["ending_equity_aud"], 0)
        self.assertEqual(output["oracle_half_width_observations"], 52)


if __name__ == "__main__":
    unittest.main()
