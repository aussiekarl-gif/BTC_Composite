"""Exact Cycle SELL market replay vs unlike original BTC-denominator sellers."""
import unittest
import numpy as np
import pandas as pd

from engines.research.live_cycle_sell_parity_audit import (
    POLICIES, day, sell_market_tape, replay_sellers,
)
from engines.research.cycle_trade_allocation import (
    SELL_REVIEW_DAY_WEIGHTS,SCHEDULE_REMAINING_IF_ALL_TRIGGERED,
)

H=pd.Timestamp("2018-01-01",tz="UTC")
END=H+pd.Timedelta(days=730)


def synthetic(kind="strong"):
    dates=pd.date_range("2015-01-01","2021-01-01",freq="D",tz="UTC")
    prices=pd.Series(100.,index=dates,dtype=float)
    if kind=="strong":
        prices.loc["2019-04-01":]=240.
    elif kind=="breakdown":
        prices.loc["2019-04-01":]=240.
        prices.loc[H+pd.Timedelta(days=578):]=175.
    elif kind=="flat":
        pass
    elif kind=="late_close":
        prices.loc["2019-04-01":]=240.
        prices.loc[H+pd.Timedelta(days=500)]=400.
    else:
        raise ValueError("Unknown synthetic price test")
    fx=pd.DataFrame(
        {"aud_per_usd":np.full(len(dates),1.5)},index=dates)
    return prices,fx


class LiveSellParityTests(unittest.TestCase):
    def test_actual_seven_stage_current_remaining_compound_not_original(self):
        remaining=1.
        for pct in SELL_REVIEW_DAY_WEIGHTS.values():
            remaining*=1-pct
        self.assertAlmostEqual(remaining,SCHEDULE_REMAINING_IF_ALL_TRIGGERED)
        self.assertGreater(remaining,.35)
        self.assertLess(remaining,.4)
        self.assertAlmostEqual(100*(1-remaining),62.68,delta=.05)

    def test_flat_market_no_live_sells_but_historical_stage_can_sell(self):
        px,fx=synthetic("flat")
        tape=sell_market_tape(px,H,END)
        self.assertEqual(tape,[])
        results=replay_sellers(px,fx,halving=H,terminal=END,
                               capital_aud=40000.)
        self.assertEqual(results["live_late_rollover_watch_days"],0)
        for policy in ("live_with_experimental_late_rollover",
                       "live_scheduled_only","buy_and_hold"):
            self.assertEqual(results["accounts"][policy]["actual_sell_count"],0)
            self.assertEqual(results["accounts"][policy]["btc_sold_total"],0)
        self.assertGreater(results["accounts"][
            "research_original_btc_90pct"]["actual_sell_count"],0)

    def test_strong_market_executes_current_remaining_percentages(self):
        px,fx=synthetic("strong")
        result=replay_sellers(px,fx,halving=H,terminal=END,
                              capital_aud=40000.)
        market=result["accounts"]["live_scheduled_only"]
        self.assertGreater(market["actual_sell_count"],0)
        self.assertLessEqual(market["actual_sell_count"],7)
        self.assertEqual(result["live_late_rollover_watch_days"],0)
        self.assertEqual(result["accounts"][
            "live_with_experimental_late_rollover"]["sell_orders"],
                         market["sell_orders"])
        orders=market["sell_orders"]
        self.assertTrue(any(x["day"]==500 for x in orders))
        self.assertAlmostEqual(orders[0]["fraction_remaining_before_pct"],5.)
        self.assertAlmostEqual(orders[0]["fraction_original_pct"],5.)
        for previous,later in zip(orders,orders[1:]):
            self.assertGreaterEqual(
                (day(later["date"])-day(previous["date"])).days,7)
            self.assertIn(later["day"],SELL_REVIEW_DAY_WEIGHTS)
            self.assertAlmostEqual(
                later["fraction_remaining_before_pct"],
                SELL_REVIEW_DAY_WEIGHTS[later["day"]]*100,places=3)
        self.assertLessEqual(market["original_btc_sold_pct"],62.69)

    def test_2021_style_late_top_can_issue_multiple_5pct_remaining(self):
        px,fx=synthetic("breakdown")
        watched=sell_market_tape(px,H,END)
        candidates=[r for r in watched if r["kind"]=="late_rollover"]
        self.assertGreater(len(candidates),0)
        result=replay_sellers(px,fx,halving=H,terminal=END,
                              capital_aud=40000.)
        original=result["accounts"]["live_scheduled_only"]
        experimental=result["accounts"][
            "live_with_experimental_late_rollover"]
        self.assertGreater(experimental["actual_sell_count"],
                           original["actual_sell_count"])
        self.assertGreater(experimental["original_btc_sold_pct"],
                           original["original_btc_sold_pct"])
        rows=[x for x in experimental["sell_orders"]
              if x["sell_kind"]=="late_rollover"]
        self.assertGreater(len(rows),0)
        self.assertTrue(all(abs(x["fraction_remaining_before_pct"]-5.)<.01
                            for x in rows))
        self.assertTrue(all((day(y["date"])-day(x["date"])).days>=7
                            for x,y in zip(experimental["sell_orders"],
                                           experimental["sell_orders"][1:])))

    def test_same_day_price_spike_cannot_generate_same_date_sell(self):
        px,fx=synthetic("strong")
        original=sell_market_tape(px,H,END)
        spike=px.copy()
        execution=H+pd.Timedelta(days=500)
        spike.loc[execution]*=20.
        altered=sell_market_tape(spike,H,END)
        before=lambda x: [y for y in x if y["date"]<=execution]
        self.assertEqual(before(original),before(altered))

    def test_tax_and_cash_are_self_financing_and_0_hold_buy(self):
        px,fx=synthetic("strong")
        r=replay_sellers(px,fx,halving=H,terminal=END,capital_aud=40000.)
        self.assertEqual(set(r["accounts"]),set(POLICIES))
        hold=r["accounts"]["buy_and_hold"]
        self.assertEqual(hold["actual_sell_count"],0)
        self.assertEqual(hold["fees_aud"],3.)
        self.assertEqual(hold["cash_aud_after_tax"],0.)
        for name,z in r["accounts"].items():
            self.assertGreaterEqual(z["cash_aud_after_tax"],0)
            self.assertGreaterEqual(z["btc_left"],0)
            self.assertLessEqual(z["original_btc_sold_pct"],100.0001)
            self.assertGreater(z["aftertax_hypothetical_liquidation_aud"],0)
            self.assertLessEqual(z["btc_left"],z["original_btc"]+.000001)

    def test_trading_signal_rejects_missing_price_days_and_bad_capital(self):
        px,fx=synthetic("strong")
        with self.assertRaisesRegex(ValueError,"consecutive"):
            sell_market_tape(px.drop(H+pd.Timedelta(days=551)),H,END)
        with self.assertRaisesRegex(ValueError,"initial AUD"):
            replay_sellers(px,fx,halving=H,terminal=END,capital_aud=0.)
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            replay_sellers(px,fx.loc[:"2018-02-01"],halving=H,terminal=END,
                           capital_aud=40000.)

    def test_stage_denominator_not_silently_treated_as_remaining(self):
        px,fx=synthetic("strong")
        r=replay_sellers(px,fx,halving=H,terminal=END,capital_aud=40000.)
        stage=r["accounts"]["research_original_btc_90pct"]
        self.assertGreater(stage["actual_sell_count"],0)
        # Original-denominator policies produce different quantities from
        # currently remaining BTC schedule after their first sale.
        self.assertNotEqual(
            stage["original_btc_sold_pct"],
            r["accounts"]["live_scheduled_only"]["original_btc_sold_pct"])
        self.assertTrue(r["historic_staged_pct_of_original_btc"])


if __name__=="__main__":
    unittest.main()
