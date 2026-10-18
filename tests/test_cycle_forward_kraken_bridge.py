"""Kraken spot candle bridge: timestamp fidelity, crosschecks, no live writes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from engines.research.cycle_forward_kraken_bridge import (
    append_verified_kraken_after_blockchain,
    parse_kraken_completed_daily,
)
from engines.research.cycle_forward_signal_tape import (
    run_once, _read_rows, SIGNAL_COLUMNS,
)

NOW=pd.Timestamp("2026-10-18T12:30:00Z")


def market_data(*,conflict=False,missing_day=False,late=False):
    dates=pd.date_range("2026-09-27","2026-10-15",freq="D",tz="UTC")
    known=pd.DataFrame({"btc_usd":np.full(len(dates),100.)},index=dates)
    exchange_days=pd.date_range("2026-10-01",
                  "2026-10-16" if late else "2026-10-18",
                  freq="D",tz="UTC")
    exchange=pd.DataFrame({
        "btc_usd":np.full(len(exchange_days),100.)
    },index=exchange_days)
    if conflict:
        exchange.loc["2026-10-14","btc_usd"]=200.
    if missing_day:
        exchange=exchange.drop(pd.Timestamp("2026-10-16",tz="UTC"))
    return known,exchange


def kraken_raw(*,include_today=True,invalid_trade=False):
    dates=pd.date_range("2026-10-01",
             "2026-10-18" if include_today else "2026-10-17",
             freq="D",tz="UTC")
    candles=[]
    for i,t in enumerate(dates):
        candles.append([
            int(t.timestamp()),"100","100","100","100",
            "100","1","0" if invalid_trade and i==4 else "10",
        ])
    return {"error":[],"result":{"XXBTZUSD":candles,"last":int(
        dates[-1].timestamp())}}


def full_app_lookback():
    dates=pd.date_range("2021-01-01","2026-10-05",freq="D",tz="UTC")
    archive=pd.DataFrame({"price_usd":np.full(len(dates),100.)},
                         index=dates)
    public_dates=pd.date_range("2026-10-01","2026-10-15",
                                freq="D",tz="UTC")
    public=pd.DataFrame({
        "btc_usd":np.full(len(public_dates),100.)
    },index=public_dates)
    fx_dates=pd.date_range("2026-09-30","2026-10-18",
                            freq="D",tz="UTC")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fx_dates),1.5)},
                    index=fx_dates)
    return archive,public,fx


class KrakenResearchOnlyBridgeTests(unittest.TestCase):
    def test_unfinished_current_day_candle_is_always_discarded(self):
        parsed=parse_kraken_completed_daily(
            kraken_raw(),utc_today=NOW)
        self.assertEqual(str(parsed.index[-1].date()),"2026-10-17")
        self.assertNotIn(pd.Timestamp("2026-10-18",tz="UTC"),
                         parsed.index)

    def test_reject_wrong_market_api_errors_broken_candles(self):
        with self.assertRaisesRegex(ValueError,"API error"):
            parse_kraken_completed_daily(
                {"error":["EGeneral:Permission denied"],
                 "result":{}},utc_today=NOW)
        with self.assertRaisesRegex(ValueError,"one spot"):
            parse_kraken_completed_daily({
                "error":[],
                "result":{"BTCUSD":[],"XBTUSD":[],"last":0},
            },utc_today=NOW)
        bad=kraken_raw(invalid_trade=True)
        with self.assertRaisesRegex(ValueError,"historical"):
            parse_kraken_completed_daily(bad,utc_today=NOW)
        bad=kraken_raw()
        bad["result"]["XXBTZUSD"][0][0]+=60
        with self.assertRaisesRegex(ValueError,"midnight"):
            parse_kraken_completed_daily(bad,utc_today=NOW)

    def test_bridge_only_two_prior_completed_dates_and_preserves_history(self):
        blockchain,raw=market_data()
        kraken=raw.loc[raw.index<NOW.normalize()]
        result,meta=append_verified_kraken_after_blockchain(
            blockchain,kraken,utc_today=NOW)
        self.assertEqual(meta["appended_dates"],[
            "2026-10-16","2026-10-17"])
        self.assertTrue(meta["existing_market_closes_preserved"])
        pd.testing.assert_frame_equal(result.loc[blockchain.index],
                                      blockchain)
        self.assertEqual(str(result.index[-1].date()),"2026-10-17")
        self.assertEqual(meta["reference_was_lagged_days"],2)

    def test_conflict_no_bridge_and_no_existing_date_overwrite(self):
        blockchain,kraken=market_data(conflict=True)
        with self.assertRaisesRegex(ValueError,"conflicts"):
            append_verified_kraken_after_blockchain(
                blockchain,kraken,utc_today=NOW)

    def test_fail_closed_no_recent_overlap_missing_day_and_gap_too_long(self):
        known,exchange=market_data(missing_day=True)
        with self.assertRaisesRegex(ValueError,"consecutive"):
            append_verified_kraken_after_blockchain(
                known,exchange,utc_today=NOW)
        with self.assertRaisesRegex(ValueError,"overlap"):
            append_verified_kraken_after_blockchain(
                known,exchange.loc["2026-10-15":],utc_today=NOW)
        old=known.loc[:"2026-10-10"]
        with self.assertRaisesRegex(ValueError,"short safe"):
            append_verified_kraken_after_blockchain(
                old,exchange,utc_today=NOW)

    def test_end_to_end_research_only_capture_with_delayed_blockchain(self):
        archive,blockchain,fx=full_app_lookback()
        kraken=parse_kraken_completed_daily(
            kraken_raw(),utc_today=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("engines.research.cycle_forward_signal_tape.read_exported_history",
                      return_value=archive),
                patch("engines.research.cycle_forward_signal_tape.fetch_public_series",
                      return_value=(blockchain,fx)),
                patch("engines.research.cycle_forward_signal_tape.fetch_halving_countdown",
                      return_value={}),
                patch("engines.research.cycle_forward_signal_tape.normalise_halving_epoch_metadata",
                      return_value={"last_halving_date":"2024-04-20",
                                    "halving_date_verified":True}),
                patch("engines.research.cycle_forward_signal_tape.fetch_completed_kraken_daily",
                      return_value=kraken),
            ):
                x=run_once(out_dir=Path(tmp),now=NOW)
                y=run_once(out_dir=Path(tmp),now=NOW)
            self.assertTrue(x["recorded_new_prospective_close"])
            self.assertTrue(x["kraken_bridge_used"])
            self.assertIn("Kraken",x["research_provider_label"])
            self.assertFalse(y["recorded_new_prospective_close"])
            self.assertEqual(x["observation_date_utc"],"2026-10-17")
            self.assertTrue(x["no_user_portfolio_or_ntfy_write"])
            ledger=Path(tmp)/"cycle_market_signals.csv"
            rows=_read_rows(ledger.read_text(),SIGNAL_COLUMNS,
                            date_key="observation_date_utc")
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["observation_date_utc"],"2026-10-17")
            self.assertEqual(rows[0]["btc_usd_observed_close"],"100.000000")
            self.assertIn("Kraken",rows[0]["market_data_provider"])

    def test_no_future_kraken_bar_can_change_decision_date_history(self):
        archive,known,fx=full_app_lookback()
        candles=parse_kraken_completed_daily(
            kraken_raw(),utc_today=NOW)
        future=candles.copy()
        future.loc["2026-10-18","btc_usd"]=1.0
        first,m1=append_verified_kraken_after_blockchain(
            known,candles,utc_today=NOW)
        second,m2=append_verified_kraken_after_blockchain(
            known,future,utc_today=NOW)
        pd.testing.assert_frame_equal(first,second)
        self.assertEqual(m1,m2)


if __name__=="__main__":
    unittest.main()
