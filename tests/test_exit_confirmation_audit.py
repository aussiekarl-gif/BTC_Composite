"""Causal invariance and bookkeeping tests for exploratory confirmed exits."""
import unittest

import pandas as pd

from engines.research.exit_confirmation_audit import (
    evaluate_confirmations, make_confirmed_signals,
)
from engines.research.full_cycle_reinvestment import simulate


def fixture(prices, risks):
    return pd.DataFrame(
        {"btc_price_aud": prices, "risk_score": risks},
        index=pd.date_range("2020-01-06", periods=len(prices), freq="W-MON"),
    )


class ExitConfirmationAuditTests(unittest.TestCase):
    def test_peak_decline_and_trend_confirm_sell_using_prior_signal(self):
        data = fixture([100, 100, 150, 200, 210, 205, 140, 130, 130],
                       [0.1, 0.1, 0.65, 0.7, 0.7, 0.5, 0.5, 0.5, 0.5])
        sig = make_confirmed_signals(data, drawdown_trigger=0.25, trend_weeks=3)
        self.assertEqual(sig["risk_score"].iloc[4], 0.5)
        self.assertEqual(sig["risk_score"].iloc[6], 1.0)
        r = simulate(sig, initial_cash=1000, fee_rate=0,
                     buy_weeks=1, sell_weeks=1)
        self.assertEqual(r["equity_path"][6]["action"], "HOLD")
        self.assertEqual(r["equity_path"][7]["action"], "SELL")
        self.assertEqual(r["sell_plans"], 1)

    def test_rising_bull_with_high_risk_does_not_sell(self):
        data = fixture([100, 110, 120, 140, 180, 200, 250],
                       [0.1, 0.7, 0.8, 0.8, 0.8, 0.8, 0.8])
        sig = make_confirmed_signals(data, trend_weeks=3)
        self.assertFalse((sig["risk_score"] == 1.0).any())

    def test_no_lookahead_prefix_invariance(self):
        data = fixture([100, 105, 135, 160, 150, 120, 200, 150, 90],
                       [0.1, 0.8, 0.8, 0.8, 0.5, 0.5, 0.5, 0.5, 0.5])
        for cut in range(3, len(data)):
            prefix = make_confirmed_signals(data.iloc[:cut], trend_weeks=3)
            full = make_confirmed_signals(data, trend_weeks=3)
            self.assertEqual(list(prefix["risk_score"]), list(full.iloc[:cut]["risk_score"]))

    def test_repeat_exit_suppressed_until_low_risk_reset(self):
        data = fixture([100, 110, 180, 200, 120, 100, 90, 80, 70, 60],
                       [0.1, 0.7, 0.8, 0.7, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        sig = make_confirmed_signals(data, drawdown_trigger=.25, trend_weeks=3)
        self.assertEqual((sig["risk_score"] == 1.0).sum(), 1)

    def test_validation_and_cohorts(self):
        data = fixture([100, 120, 130, 110, 140, 160, 180],
                       [.1, .3, .7, .8, .2, .4, .9])
        report = evaluate_confirmations(data, initial_cash=1000, fee_rate=0)
        self.assertEqual(len(report["records"]), 6)
        self.assertTrue(all(x["ending_equity_aud"] >= 0 for x in report["records"]))
        with self.assertRaises(ValueError):
            make_confirmed_signals(data, trend_weeks=1)
        with self.assertRaises(ValueError):
            make_confirmed_signals(data, drawdown_trigger=0)


if __name__ == "__main__":
    unittest.main()
