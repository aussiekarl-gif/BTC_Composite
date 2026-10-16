"""Deterministic tests for research-only self-financing SMSF tax-lot replay."""
import unittest

import pandas as pd

from engines.research.adaptive_dca_execution import simulate_adaptive
from engines.research.smsf_self_financing_replay import (
    AuditSmsfAccount, evaluate, matched_buy_and_hold, replay,
)


def case(n=190):
    prices=[100.+1.7*(i%27) for i in range(n)]
    risks=[.08]*32+[.50]*33+[.81]*58+[.15]*(n-123)
    return pd.DataFrame(
        {"btc_price_aud":prices,"risk_score":risks},
        index=pd.date_range("2018-01-01",periods=n,freq="W-MON",tz="UTC"),
    )


class SmsfSelfFinancingTests(unittest.TestCase):
    def test_effective_smsf_15pct_until_more_than_calendar_year(self):
        short=AuditSmsfAccount(1000)
        long=AuditSmsfAccount(1000)
        buy=pd.Timestamp("2020-01-01",tz="UTC")
        short.buy(buy,100,1)
        long.buy(buy,100,1)
        short.sell(pd.Timestamp("2021-01-01",tz="UTC"),200,1)
        long.sell(pd.Timestamp("2021-01-02",tz="UTC"),200,1)
        gain=(1000-3)/100*200-3-1000
        self.assertAlmostEqual(short.total_tax,gain*.15)
        self.assertAlmostEqual(long.total_tax,gain*.10)

    def test_fifo_buy_and_sell_and_brokerage_exact(self):
        a=AuditSmsfAccount(2500)
        a.buy(pd.Timestamp("2020-01-01"),100,.40)
        a.buy(pd.Timestamp("2020-03-01"),200,.40)
        before=a.btc
        a.sell(pd.Timestamp("2022-01-01"),300,.50)
        self.assertAlmostEqual(a.btc,before*.5)
        self.assertEqual(len(a.orders),3)
        self.assertAlmostEqual(a.total_fees,9)
        self.assertGreater(a.total_tax,0)
        self.assertGreaterEqual(a.cash,0)

    def test_realised_capital_loss_carried_to_later_gain(self):
        a=AuditSmsfAccount(1000)
        a.buy(pd.Timestamp("2020-01-01"),100,1.)
        a.sell(pd.Timestamp("2021-01-02"),50,1.)
        self.assertEqual(a.total_tax,0)
        self.assertGreater(a.loss_carry,0)
        before_loss=a.loss_carry
        a.buy(pd.Timestamp("2021-01-03"),50,1.)
        a.sell(pd.Timestamp("2022-02-04"),100,1.)
        self.assertLess(a.loss_carry,before_loss)
        self.assertGreaterEqual(a.total_tax,0)

    def test_zero_tax_replay_matches_original_execution_account(self):
        data=case()
        reference=simulate_adaptive(data,confirm_drawdown=.10)
        same=replay(data,reference["trades"],policy="adaptive",tax=False)
        self.assertAlmostEqual(
            same["ending_marked_equity_aud"],
            reference["ending_equity_aud"],
            delta=reference["ending_equity_aud"]*2e-5)
        self.assertEqual(same["total_brokerage_aud"],3*same["actual_orders"])
        self.assertAlmostEqual(same["cash_aud"]+same["btc"]*data["btc_price_aud"].iloc[-1],
                               same["ending_marked_equity_aud"],delta=.5)

    def test_no_future_changes_earlier_orders(self):
        data=case()
        cutoff=140
        events=simulate_adaptive(data,confirm_drawdown=.10)["trades"]
        histdata=data.iloc[:cutoff].copy()
        earlier=[e for e in events if pd.Timestamp(e["date"])<histdata.index[-1]]
        one=replay(histdata,earlier,policy="trend_reserve",tax=True)
        modified=data.copy()
        modified.iloc[cutoff:]=[10000.,.99]
        two=replay(modified,earlier,policy="trend_reserve",tax=True)
        first=one["orders"]
        second=[x for x in two["orders"]
                if pd.Timestamp(x["date"])<histdata.index[-1]]
        self.assertEqual(first,second)

    def test_benchmark_and_final_liquidation_not_higher_for_winner(self):
        data=case()
        benchmark=matched_buy_and_hold(data,tax=True)
        self.assertGreater(benchmark["ending_marked_equity_aud"],0)
        self.assertLessEqual(
            benchmark["hypothetical_final_liquidation_after_cgt_aud"],
            benchmark["ending_marked_equity_aud"]+1e-4)

    def test_full_evaluation_all_3_policies_with_and_without_tax(self):
        d=evaluate(case())
        self.assertEqual(d["original_signal_opportunities"]>0,True)
        self.assertEqual(len(d["replayed_portfolios"]),6)
        self.assertEqual({x["policy"] for x in d["replayed_portfolios"]},
                         {"adaptive","constant_rate","trend_reserve"})
        for s in d["replayed_portfolios"]:
            self.assertGreaterEqual(s["cash_aud"],0)
            self.assertGreaterEqual(s["btc"],0)
            self.assertGreaterEqual(s["total_brokerage_aud"],0)
            self.assertTrue(s["max_account_drawdown_pct"]<=0)


if __name__=="__main__":
    unittest.main()
