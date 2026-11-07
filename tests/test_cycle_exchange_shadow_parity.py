"""Research-only parity and refusal tests for the verified exchange shadow.

The ntfy message is constructed in memory; no notification is sent.
"""
import datetime as dt
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from engines.research.cycle_exchange_shadow_market import shadow_market
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.cycle_trade_allocation import calculate_allocation_signal
from cycle_trading_daily_ntfy import daily_message


class ShadowParityTests(unittest.TestCase):
    def setUp(self):
        self.today="2026-11-07"
        index=pd.date_range("2021-01-01","2026-10-05",freq="D",tz="UTC")
        self.archive=pd.DataFrame({"price_usd":np.full(len(index),100.)},index=index)
        exchange_idx=pd.date_range("2026-09-23","2026-11-06",freq="D",tz="UTC")
        self.coinbase=pd.DataFrame({"btc_usd":np.full(len(exchange_idx),100.)},index=exchange_idx)
        self.kraken=self.coinbase.copy()
        fx_idx=pd.date_range("2026-10-01","2026-11-06",freq="D",tz="UTC")
        self.fx=pd.DataFrame({"aud_per_usd":np.full(len(fx_idx),1.5)},index=fx_idx)

    def test_shadow_matches_unchanged_market_and_in_memory_ntfy(self):
        shadow=shadow_market(self.archive,self.coinbase,self.kraken,utc_today=self.today)
        additions=self.kraken.loc["2026-10-06":,"btc_usd"].rename("price_usd")
        series=pd.concat([self.archive["price_usd"],additions])
        market=build_dashboard_market(series,self.fx,asof=self.today,confirmed_halving_date="2024-04-20")
        signal=calculate_allocation_signal(market)
        self.assertEqual(shadow["completed_close_utc"],market["asof_date"])
        self.assertEqual(shadow["btc_close_usd"],market["btc_price_usd"])
        self.assertEqual(shadow["prior_200wma_usd"],market["prior_200wma_usd"])
        self.assertEqual(shadow["signal"],signal["signal"])
        self.assertEqual(shadow["buy_pct_cash"],signal["buy_pct_cash"])
        self.assertEqual(shadow["sell_pct_held"],signal["sell_pct_held"])
        with patch("cycle_trading_daily_ntfy.fetch_halving_countdown",return_value={"last_halving_date":"2024-04-20","halving_date_verified":True}):
            _,message=daily_message(now=dt.datetime(2026,11,7,1,0,tzinfo=dt.timezone.utc),
                                    quote={"price_aud":20.,"timestamp_utc":"2026-11-06T06:00:00Z"},
                                    market=market)
        self.assertIn("Cycle signal: "+signal["signal"],message)
        self.assertIn(f"BUY allocation: {signal['buy_pct_cash']:.2f}%",message)
        self.assertIn(f"SELL allocation: {signal['sell_pct_held']:.2f}%",message)
        self.assertIn("2026-11-06",message)

    def test_missing_bridge_day_refused(self):
        missing=self.coinbase.drop(pd.Timestamp("2026-10-17",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"Missing consecutive"):
            shadow_market(self.archive,missing,self.kraken,utc_today=self.today)

    def test_disagreement_on_older_bridge_day_refused(self):
        conflicting=self.coinbase.copy()
        conflicting.loc["2026-10-17","btc_usd"]=105.
        with self.assertRaisesRegex(ValueError,"historical bridge"):
            shadow_market(self.archive,conflicting,self.kraken,utc_today=self.today)

    def test_archive_overlap_conflict_refused(self):
        conflicting=self.coinbase.copy()
        conflicting.loc["2026-10-04","btc_usd"]=110.
        with self.assertRaisesRegex(ValueError,"Archive and Coinbase"):
            shadow_market(self.archive,conflicting,self.kraken,utc_today=self.today)


if __name__=="__main__":
    unittest.main()
