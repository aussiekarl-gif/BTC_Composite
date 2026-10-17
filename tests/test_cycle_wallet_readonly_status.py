"""Original-cycle read-only shadow refuses 2026 retroactive trades."""
import unittest
import numpy as np
import pandas as pd
from engines.research.cycle_wallet_readonly_status import historical_cycle_wallet_status

HALVING=pd.Timestamp("2024-04-20",tz="UTC")


def prices():
    dates=pd.date_range(pd.Timestamp("2018-01-01",tz="UTC"),
                        pd.Timestamp("2026-10-15",tz="UTC"),freq="D")
    values=np.linspace(32000.,80000.,len(dates))
    return pd.Series(values,index=dates)


def position(date,asset="ASX:IBIT",units=100):
    return {"starting_capital_aud":500000.,"rows":[{
        "Date":date,"Asset":asset,"Units / BTC Received":units,
        "AUD Spent":10000.,"Brokerage / Fee AUD":3.0,
        "BTC AUD Price":80000.,
    }],"sales":[]}


class ReadonlyOriginalWalletTests(unittest.TestCase):
    def test_real_2026_ibit_cannot_get_historical_sell_or_repurchase(self):
        s=historical_cycle_wallet_status(
            prices(),HALVING,position("01/01/26"),asof="2026-10-15")
        self.assertEqual(s["phase"],"NO_ORIGINAL_POSITION")
        self.assertEqual(s["action"],"HOLD")
        self.assertEqual(s["original_ibit_units"],0.)
        self.assertEqual(s["recorded_ibit_units"],100.)
        self.assertIsNone(s["original_aftertax_buyback_budget_aud"])
        self.assertFalse(s["place_order"])
        self.assertFalse(s["parity_to_current_ntfy_verified"])

    def test_day500_uses_original_units_not_remaining_2p5pct_cash(self):
        epoch=HALVING
        day500=epoch+pd.Timedelta(days=500)
        s=historical_cycle_wallet_status(
            prices(),epoch,position("01/05/24",units=100),
            asof=str(day500.date()))
        self.assertEqual(s["action"],"SELL REVIEW — VERIFY")
        self.assertEqual(s["sale_review_ibit_units"],5.)
        self.assertEqual(s["original_ibit_units"],100.)
        self.assertFalse(s["place_order"])

    def test_live_buyback_never_guesses_net_proceeds_or_tax(self):
        px=prices().copy()
        # A preceding below-200WMA observation after day744 activates
        # historical market phase, but no personal buy amount.
        day=HALVING+pd.Timedelta(days=790)
        px.loc[px.index>=day-pd.Timedelta(days=7)]=3000.
        state=historical_cycle_wallet_status(
            px,HALVING,position("01/05/24"),asof=str(day.date()))
        self.assertEqual(state["phase"],
                         "HISTORICAL_BUYBACK_ACTIVE_NO_VERIFIED_BUDGET")
        self.assertIsNone(state["original_aftertax_buyback_budget_aud"])
        self.assertIsNotNone(state["buyback_pct_original_budget"])
        self.assertEqual(state["action"],"HOLD")

    def test_invalid_sale_does_not_create_fictitious_sell(self):
        snapshot=position("01/05/24",units=2)
        snapshot["sales"]=[{"Date":"02/09/25","Asset":"ASX:IBIT",
            "Units Sold":100,"AUD Proceeds":2000.,
            "Brokerage / Fee AUD":3.}]
        with self.assertRaisesRegex(ValueError,"exceeds"):
            historical_cycle_wallet_status(
                prices(),HALVING,snapshot,asof="2026-10-15")

    def test_never_uses_missing_future_btc_closes(self):
        with self.assertRaisesRegex(ValueError,"Observed as-of"):
            historical_cycle_wallet_status(
                prices(),HALVING,position("01/05/24"),
                asof="2030-01-01")


if __name__=="__main__":
    unittest.main()
