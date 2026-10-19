"""Public Cycle daily failure isolation is passive and fail-closed."""
import datetime as dt
import unittest
from unittest.mock import patch

import pandas as pd

from engines.research import cycle_daily_market_diagnostic as d

NOW=dt.datetime(2026,10,19,3,12,tzinfo=dt.timezone.utc)
day=pd.Timestamp("2026-10-18",tz="UTC")
prices=pd.DataFrame({"price_usd":[80000.]},index=pd.DatetimeIndex([day]))
raw=pd.DataFrame({"btc_usd":[80000.]},index=pd.DatetimeIndex([day]))
fx=pd.DataFrame({"aud_per_usd":[1.5]},index=pd.DatetimeIndex([day]))
k=pd.DataFrame({"btc_usd":[80000.]},index=pd.DatetimeIndex([day]))

def args():
    return dict(now=NOW,archive_fetcher=lambda:prices,
                price_fx_fetcher=lambda *,asof:(raw,fx),
                kraken_fetcher=lambda *,utc_today:k,
                halving_fetcher=lambda *,now:{
                    "last_halving_date":"2024-04-20",
                    "halving_date_verified":True})

def market(dte="2026-10-18",fxok=1.5):
    return dict(asof_date=dte,usd_aud_prior=fxok,
                btc_price_usd=80000.,prior_200wma_usd=65000.)


class DailyMarketDiagnosticTests(unittest.TestCase):
    def test_success_unchanged_cycle_math_no_send(self):
        with (patch.object(d,"merge_verified_live_cycle_prices",return_value=(
                  pd.Series([80000],index=pd.DatetimeIndex([day])),
                  {"strict_close_date_verified":True,
                   "recent_kraken_blockchain_max_diff_pct":.02})),
              patch.object(d,"build_dashboard_market",return_value=market()),
              patch.object(d,"calculate_allocation_signal",return_value={
                  "signal":"HOLD","buy_pct_cash":0.,"sell_pct_held":0.})):
            result=d.diagnose(**args())
        self.assertEqual(result["cause"],"NONE_INPUTS_VALID")
        self.assertEqual(result["cycle_watch"],"HOLD")
        self.assertEqual(result["ntfy_messages_sent"],0)
        self.assertEqual(result["portfolio_reads_or_writes"],0)
        self.assertFalse(result["trading_recommendation_or_order"])

    def test_historical_archive_failure(self):
        kwargs=args()
        def fail():raise FileNotFoundError("archive missing")
        kwargs["archive_fetcher"]=fail
        x=d.diagnose(**kwargs)
        self.assertEqual(x["cause"],"ARCHIVED_BTC_HISTORY_FAILED")
        self.assertEqual(x["steps"]["archived_BTC_history"]["error_type"],"FileNotFoundError")

    def test_blockchain_fx_provider_failure(self):
        kwargs=args()
        def fail(*,asof):raise ConnectionError("upstream failure")
        kwargs["price_fx_fetcher"]=fail
        x=d.diagnose(**kwargs)
        self.assertEqual(x["cause"],"BLOCKCHAIN_BTC_AND_PRIOR_AUD_FX_FAILED")
        self.assertNotIn("completed_Kraken_BTC_OHLC",x["steps"])

    def test_kraken_failure_does_not_fabricate_close(self):
        kwargs=args()
        def fail(*,utc_today):raise ValueError("no completed bar")
        kwargs["kraken_fetcher"]=fail
        x=d.diagnose(**kwargs)
        self.assertEqual(x["cause"],"COMPLETED_KRAKEN_BTC_OHLC_FAILED")
        self.assertEqual(x["cycle_watch"],"DATA_UNAVAILABLE")

    def test_crossprovider_alignment_failure(self):
        with patch.object(d,"merge_verified_live_cycle_prices",
                          side_effect=ValueError("source mismatch >1%")):
            x=d.diagnose(**args())
        self.assertEqual(x["cause"],"SHARED_BTC_COMPLETED_CLOSE_ALIGNMENT_FAILED")
        self.assertIn("source mismatch",x["steps"]["shared_BTC_completed_close_alignment"]["error_summary"])

    def test_unknown_halving_blocks_signal(self):
        kwargs=args();kwargs["halving_fetcher"]=lambda *,now:{"halving_date_verified":False}
        with patch.object(d,"merge_verified_live_cycle_prices",
                          return_value=(pd.Series([80000],index=pd.DatetimeIndex([day])),
                                        {"strict_close_date_verified":True})):
            x=d.diagnose(**kwargs)
        self.assertEqual(x["cause"],"HALVING_EPOCH_UNVERIFIED")

    def test_stale_btc_date_fails(self):
        with (patch.object(d,"merge_verified_live_cycle_prices",return_value=(
                  pd.Series([80000],index=pd.DatetimeIndex([day])),
                  {"strict_close_date_verified":True})),
              patch.object(d,"build_dashboard_market",return_value=market(dte="2026-10-17"))):
            x=d.diagnose(**args())
        self.assertEqual(x["cause"],"LATEST_COMPLETED_CLOSE_OR_PRIOR_FX_INVALID")

    def test_missing_aud_fx_fails(self):
        with (patch.object(d,"merge_verified_live_cycle_prices",return_value=(
                  pd.Series([80000],index=pd.DatetimeIndex([day])),
                  {"strict_close_date_verified":True})),
              patch.object(d,"build_dashboard_market",return_value=market(fxok=None))):
            x=d.diagnose(**args())
        self.assertEqual(x["cause"],"LATEST_COMPLETED_CLOSE_OR_PRIOR_FX_INVALID")
        self.assertFalse(x["steps"]["shared_Cycle_market_math"]["FX_available"])

    def test_invalid_asof_instant_rejected(self):
        kwargs=args()
        kwargs["now"]=NOW.replace(tzinfo=None)
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            d.diagnose(**kwargs)

if __name__=="__main__":
    unittest.main()
