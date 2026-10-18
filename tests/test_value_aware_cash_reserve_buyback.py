"""Value-aware 50% protected reserve vs unchanged Cycle BUY research tests."""
import unittest
import numpy as np
import pandas as pd

from engines.research.live_cycle_self_financing_roundtrip import (
    BUY_STYLES,VALUE_RESERVE_MODE,
    VALUE_RESERVE_WMA_RATIO,VALUE_CORE_SHARE,
    simulate_full_roundtrip,rising_bull_path,day,
)
from engines.research.value_aware_cash_reserve_buyback import compare

H=pd.Timestamp("2018-01-01",tz="UTC")
END=H+pd.Timedelta(days=1150)


def market(kind="deep"):
    idx=pd.date_range("2013-01-01","2024-01-01",tz="UTC",freq="D")
    price=pd.Series(100.,index=idx,dtype=float)
    price.loc[H+pd.Timedelta(days=450):]=240.
    if kind=="deep":
        price.loc[H+pd.Timedelta(days=900):]=70.
        price.loc[H+pd.Timedelta(days=1010):]=45.
    elif kind=="shallow":
        price.loc[H+pd.Timedelta(days=900):]=110.
        price.loc[H+pd.Timedelta(days=960):]=240.
    elif kind=="no_gate":
        pass
    elif kind=="quick_rebound":
        price.loc[H+pd.Timedelta(days=900):
                  H+pd.Timedelta(days=908)]=70.
        price.loc[H+pd.Timedelta(days=909):]=240.
    else:
        raise ValueError(kind)
    fx=pd.DataFrame({"aud_per_usd":np.full(len(idx),1.5)},index=idx)
    return price,fx


class ValueReserveBuybackTests(unittest.TestCase):
    def test_existing_three_modes_remain_byte_for_byte_equal_outcomes(self):
        price,fx=market("deep")
        for old in BUY_STYLES:
            now=simulate_full_roundtrip(
                price,fx,halving=H,terminal=END,
                starting_cash=40000.,buyback_mode=old)
            again=simulate_full_roundtrip(
                price,fx,halving=H,terminal=END,
                starting_cash=40000.,buyback_mode=old)
            self.assertEqual(now,again)
            self.assertFalse(now["research_value_reserve_mode"])
            self.assertTrue(all(
                x["research_value_reserve_spent_aud"]==0
                for x in now["accounts"].values()))

    def test_no_fabricated_entry_if_original_strict_wma_gate_never_opens(self):
        px,fx=market("no_gate")
        out=simulate_full_roundtrip(
            px,fx,halving=H,terminal=END,
            starting_cash=40000.,buyback_mode=VALUE_RESERVE_MODE)
        for acct in out["accounts"].values():
            self.assertIsNone(acct["first_200wma_funded_buyback_trigger"])
            self.assertEqual(acct["actual_buyback_orders"],0)
            self.assertEqual(acct["research_value_reserve_spent_aud"],0.)
            self.assertEqual(acct["research_value_core_spent_aud"],0.)

    def test_all_funded_purchases_and_reserves_nonnegative(self):
        px,fx=market("deep")
        out=simulate_full_roundtrip(
            px,fx,halving=H,terminal=END,
            starting_cash=40000.,buyback_mode=VALUE_RESERVE_MODE)
        self.assertTrue(out["research_value_reserve_mode"])
        self.assertEqual(out["buyback_mode"],VALUE_RESERVE_MODE)
        self.assertEqual(VALUE_RESERVE_WMA_RATIO,.85)
        self.assertEqual(VALUE_CORE_SHARE,.5)
        for seller,acct in out["accounts"].items():
            self.assertGreaterEqual(acct["cash_remaining_aud"],0.)
            self.assertGreaterEqual(acct["research_value_reserve_left_aud"],0.)
            self.assertGreaterEqual(acct["research_value_core_spent_aud"],0.)
            self.assertLessEqual(acct["actual_buyback_orders"],52)
            self.assertGreater(acct["hypothetical_aftertax_liquidation_aud"],0)
            if acct["actual_buyback_orders"]>0:
                buys=[o for o in acct["dated_orders"] if o["side"]=="BUY"]
                self.assertEqual(buys[0]["signal_origin"],
                                 "initial_original_200wma_watch")
                self.assertTrue(all(
                    x["signal_origin"]=="value_reserve_weekly_buy"
                    for x in buys[1:]))
                self.assertTrue(all(
                    (day(b["date"])-day(a["date"])).days>=7
                    for a,b in zip(acct["dated_orders"],
                                   acct["dated_orders"][1:])))

    def test_shallow_recovery_keeps_cash_not_100pct_forced_deployment(self):
        px,fx=market("quick_rebound")
        out=simulate_full_roundtrip(
            px,fx,halving=H,terminal=END,
            starting_cash=40000.,buyback_mode=VALUE_RESERVE_MODE)
        staged=out["accounts"]["research_original_btc_90pct"]
        self.assertGreater(staged["actual_buyback_orders"],1)
        self.assertGreater(staged["cash_remaining_aud"],0)
        self.assertGreater(staged["research_value_reserve_left_aud"],0)

    def test_weekday_only_never_uses_closed_market_btc_close(self):
        px,fx=market("deep")
        out=simulate_full_roundtrip(
            px,fx,halving=H,terminal=END,
            starting_cash=40000.,weekday_only=True,
            buyback_mode=VALUE_RESERVE_MODE)
        for acct in out["accounts"].values():
            self.assertTrue(all(
                day(order["date"]).weekday()<5
                for order in acct["dated_orders"]))

    def test_future_prices_cannot_change_earlier_buy_and_sell_ledger(self):
        px,fx=market("deep")
        early=H+pd.Timedelta(days=1000)
        a=simulate_full_roundtrip(
            px,fx,halving=H,terminal=early,
            starting_cash=40000.,buyback_mode=VALUE_RESERVE_MODE)
        different=px.copy()
        different.loc[different.index>early]*=13.
        b=simulate_full_roundtrip(
            different,fx,halving=H,terminal=early,
            starting_cash=40000.,buyback_mode=VALUE_RESERVE_MODE)
        self.assertEqual(a,b)

    def test_matched_each_sell_policy_initial_wallet_and_cash(self):
        px,fx=market("deep")
        rows=compare(px,fx,halving=H,terminal=END,cycle="test",
                     case="fixture",weekday=False)
        self.assertEqual(len(rows),20)
        for seller in sorted({r["SELL_policy"] for r in rows}):
            matches=[r for r in rows if r["SELL_policy"]==seller]
            self.assertEqual(len(matches),4)
            self.assertEqual(len({r["starting_BTC"] for r in matches}),1)
            self.assertEqual(matches[0]["aftertax_AUD_vs_live_pct"],0.)
            self.assertEqual(matches[0]["BTC_held_vs_original_live_buy_pct"],0.)
            self.assertTrue(all(
                r["AUD_cash_left"]>=0 for r in matches))

    def test_invalid_buyback_code_and_fx_fail_closed(self):
        px,fx=market("deep")
        with self.assertRaisesRegex(ValueError,"buyback policy"):
            simulate_full_roundtrip(
                px,fx,halving=H,terminal=END,
                buyback_mode="deploy all cash before known low")
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            simulate_full_roundtrip(
                px,fx.loc[:"2018-02-01"],halving=H,terminal=END,
                buyback_mode=VALUE_RESERVE_MODE)


if __name__=="__main__":
    unittest.main()
