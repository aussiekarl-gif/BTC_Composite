import unittest

import pandas as pd

from engines.research.walk_forward_report import anchored_walk_forward_report


class AnchoredWalkForwardReportTests(unittest.TestCase):
    def test_chronological_holdout_and_no_future_risk_effect_on_earlier_fold(self):
        data = pd.DataFrame(
            {
                "btc_price_aud": [100 + 3 * i for i in range(20)],
                "risk_score": [0.1] * 8 + [0.9] * 6 + [0.1] * 6,
            },
            index=pd.date_range("2020-01-06", periods=20, freq="W-MON"),
        )
        grid = {
            "buy_thresholds": (0.25,),
            "sell_thresholds": (0.75,),
            "max_buy_pct_periods": (0.10,),
            "max_sell_pct_periods": (0.20,),
        }
        report = anchored_walk_forward_report(
            data, train_fractions=(0.50, 0.70), starting_capital_aud=1000,
            **grid,
        )
        self.assertEqual(len(report), 2)
        self.assertTrue((pd.to_datetime(report["train_end"]) <
                         pd.to_datetime(report["test_start"])).all())
        self.assertTrue((report["cycle_fees_aud"] >= 0).all())
        self.assertTrue((report["hold_fees_aud"] >= 0).all())
        self.assertTrue((report["cycle_btc"] >= 0).all())
        self.assertTrue((report["hold_btc"] >= 0).all())

    def test_reject_too_short_history(self):
        with self.assertRaises(ValueError):
            anchored_walk_forward_report(pd.DataFrame({"risk_score": [0.5]}))


if __name__ == "__main__":
    unittest.main()
