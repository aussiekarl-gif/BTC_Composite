"""Immutable prospective-only Cycle Trading market-signal tape.

No real GitHub/network/portfolios required; all price data are synthetic.
"""
import unittest
import datetime as dt
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from engines.research.cycle_forward_signal_tape import (
    GENESIS, OUTCOME_COLUMNS, SIGNAL_COLUMNS, HORIZONS,
    _read_rows, append_snapshot, append_due_outcomes,
    build_snapshot, _prior_annual_volatility,
    _was_captured_prospectively, run_once,
)

ASOF=pd.Timestamp("2026-10-18T12:30:00+00:00")


def sources(*,buy=True,price_stale=False,fx_stale=False):
    historic=pd.date_range("2021-01-01","2026-10-05",freq="D",tz="UTC")
    archive=pd.DataFrame({
        "price_usd":np.full(len(historic),100.)
    },index=historic)
    final="2026-10-13" if price_stale else "2026-10-17"
    public_index=pd.date_range("2026-10-01",final,freq="D",tz="UTC")
    values=np.full(len(public_index),100.)
    if buy and not price_stale:
        values[-2:]=[65.,64.]
    public=pd.DataFrame({"btc_usd":values},index=public_index)
    fx_end="2026-09-30" if fx_stale else "2026-10-17"
    fx_idx=pd.date_range("2026-09-25",fx_end,freq="D",tz="UTC")
    fx=pd.DataFrame({
        "aud_per_usd":np.full(len(fx_idx),1.50)
    },index=fx_idx)
    return archive,public,fx


def snapshot(*,buy=True):
    a,p,fx=sources(buy=buy)
    return build_snapshot(
        a,p,fx,captured_at_utc=ASOF,
        verified_halving_date="2024-04-20",
        code_sha256="a"*64)


class ForwardTapeTests(unittest.TestCase):
    def test_buy_snapshot_uses_exact_same_market_model_and_prior_completed_close(self):
        s=snapshot()
        self.assertEqual(s["observation_date_utc"],"2026-10-17")
        self.assertEqual(s["signal_input_last_prior_close_date_utc"],
                         "2026-10-16")
        self.assertEqual(s["signal"],"BUY WATCH")
        self.assertEqual(s["buy_pct_of_remaining_available_cash"],
                         "2.5000")
        self.assertEqual(s["sell_pct_of_current_holdings"],"0.0000")
        self.assertEqual(s["btc_usd_observed_close"],"64.000000")
        self.assertEqual(s["prior_btc_usd_close"],"65.000000")
        self.assertEqual(s["trade_executable"],"False")
        self.assertIn("NOT_VERIFIED",s["point_in_time_onchain_risk_status"])
        self.assertNotIn("portfolio",str(s.keys()).lower())
        self.assertEqual(s["model_code_sha256"],"a"*64)

    def test_hold_snapshot_and_actual_prior_only_signal(self):
        s=snapshot(buy=False)
        self.assertEqual(s["signal"],"HOLD")
        self.assertEqual(s["buy_pct_of_remaining_available_cash"],"0.0000")
        self.assertEqual(s["sell_pct_of_current_holdings"],"0.0000")
        a,p,fx=sources(buy=True)
        observed=build_snapshot(
            a,p,fx,captured_at_utc=ASOF,
            verified_halving_date="2024-04-20",code_sha256="b"*64)
        # Today (17 Oct) execution price is not an input to BUY eligibility.
        p.loc["2026-10-17","btc_usd"]=100000.
        other=build_snapshot(
            a,p,fx,captured_at_utc=ASOF,
            verified_halving_date="2024-04-20",code_sha256="b"*64)
        self.assertEqual(observed["signal"],other["signal"])
        self.assertEqual(observed["buy_pct_of_remaining_available_cash"],
                         other["buy_pct_of_remaining_available_cash"])
        self.assertNotEqual(observed["btc_usd_observed_close"],
                            other["btc_usd_observed_close"])

    def test_unverified_halving_conflicting_market_and_stale_fx_fail_closed(self):
        a,p,fx=sources()
        with self.assertRaisesRegex(ValueError,"Unverified halving"):
            build_snapshot(a,p,fx,captured_at_utc=ASOF,
                           verified_halving_date=None,code_sha256="a"*64)
        p.loc["2026-10-03","btc_usd"]=200.
        with self.assertRaisesRegex(ValueError,"conflicts"):
            build_snapshot(a,p,fx,captured_at_utc=ASOF,
                           verified_halving_date="2024-04-20",
                           code_sha256="a"*64)
        a,p,fx=sources(price_stale=True)
        with self.assertRaisesRegex(ValueError,"Stale or incomplete"):
            build_snapshot(a,p,fx,captured_at_utc=ASOF,
                           verified_halving_date="2024-04-20",
                           code_sha256="a"*64)
        a,p,fx=sources(fx_stale=True)
        with self.assertRaisesRegex(ValueError,"Stale or absent"):
            build_snapshot(a,p,fx,captured_at_utc=ASOF,
                           verified_halving_date="2024-04-20",
                           code_sha256="a"*64)

    def test_signal_ledger_immutable_and_chain_verifies_on_read(self):
        a=snapshot()
        text,added=append_snapshot("",a)
        self.assertTrue(added)
        records=_read_rows(text,SIGNAL_COLUMNS,
                           date_key="observation_date_utc")
        self.assertEqual(records[0]["prior_row_hash"],GENESIS)
        self.assertEqual(len(records[0]["row_hash"]),64)
        # Another 2026-10-17 read cannot overwrite first saved value.
        forged={**a,"btc_usd_observed_close":"9999.000000",
                "captured_at_utc":"2026-10-18T23:59:00+00:00"}
        same,added=append_snapshot(text,forged)
        self.assertFalse(added)
        self.assertEqual(text,same)
        altered=text.replace("64.000000","67.000000")
        self.assertNotEqual(altered,text)
        with self.assertRaisesRegex(ValueError,"Modified"):
            append_snapshot(altered,a)
        earlier={**a,"observation_date_utc":"2026-10-16"}
        with self.assertRaisesRegex(ValueError,"backfill forbidden"):
            append_snapshot(text,earlier)

    def test_score_outcomes_only_from_newer_frozen_daily_rows(self):
        original=snapshot()
        tape,_=append_snapshot("",original)
        scores,added=append_due_outcomes(
            "",tape,evaluated_at_utc=ASOF)
        self.assertEqual((scores,added),("",0))
        # Later rows captured on later days, one immutable daily snapshot.
        start=pd.Timestamp("2026-10-17",tz="UTC")
        for i in range(1,8):
            later=start+pd.Timedelta(days=i)
            record={
                **original,
                "observation_date_utc":str(later.date()),
                "captured_at_utc":(later+pd.Timedelta(days=1,hours=12)).isoformat(),
                "signal_input_last_prior_close_date_utc":str(
                    (later-pd.Timedelta(days=1)).date()),
                "btc_usd_observed_close":f"{64+i:.6f}",
            }
            tape,_=append_snapshot(tape,record)
        scored,n=append_due_outcomes(
            "",tape,evaluated_at_utc="2026-10-26T12:00:00Z")
        self.assertEqual(n,1)
        rows=_read_rows(scored,OUTCOME_COLUMNS)
        self.assertEqual(rows[0]["base_observation_date_utc"],"2026-10-17")
        self.assertEqual(rows[0]["future_observation_date_utc"],"2026-10-24")
        self.assertEqual(rows[0]["horizon_days"],"7")
        self.assertAlmostEqual(float(rows[0]["btc_price_change_pct"]),
                               100*((64+7)/64-1),places=4)
        self.assertGreater(float(rows[0]["signal_signed_price_change_pct"]),0.)
        frozen,n=append_due_outcomes(
            scored,tape,evaluated_at_utc="2026-10-27T12:00:00Z")
        self.assertEqual((frozen,n),(scored,0))
        no90=[r for r in rows if r["horizon_days"]=="90"]
        self.assertEqual(no90,[])

    def test_missing_day_in_window_prevents_scoring_no_interpolation(self):
        first=snapshot()
        tape,_=append_snapshot("",first)
        for offset in (1,2,3,5,6,7):
            date=pd.Timestamp("2026-10-17",tz="UTC")+pd.Timedelta(days=offset)
            record={**first,
                    "observation_date_utc":str(date.date()),
                    "captured_at_utc":(date+pd.Timedelta(days=1)).isoformat(),
                    "btc_usd_observed_close":f"{64+offset:.6f}"}
            tape,_=append_snapshot(tape,record)
        out,n=append_due_outcomes(
            "",tape,evaluated_at_utc="2026-10-27T11:00:00Z")
        self.assertEqual(n,0)
        self.assertEqual(out,"")

    def test_future_prices_do_not_rewrite_past_signal_or_model_code(self):
        original=snapshot()
        first,_=append_snapshot("",original)
        a,p,fx=sources()
        p.loc["2026-10-17","btc_usd"]=300.
        new=build_snapshot(a,p,fx,captured_at_utc=ASOF,
                           verified_halving_date="2024-04-20",
                           code_sha256="b"*64)
        still,added=append_snapshot(first,new)
        self.assertEqual((still,added),(first,False))

    def test_volatility_snapshot_uses_exact_thirty_prior_returns(self):
        a,p,fx=sources()
        data=a["price_usd"].copy()
        added=p.loc[p.index>a.index[-1],"btc_usd"]
        data=pd.concat([data,added]).sort_index()
        asof=pd.Timestamp("2026-10-17",tz="UTC")
        ref=_prior_annual_volatility(data,asof)
        data.loc[asof]=9999.
        self.assertAlmostEqual(_prior_annual_volatility(data,asof),ref)


    def test_two_day_source_delay_rejected_as_forward_signal(self):
        archive,public,fx=sources()
        # Existing application may tolerate up to three days of market
        # age, but the forward research recorder must not backdate.
        public=public.loc[:"2026-10-16"]
        with self.assertRaisesRegex(ValueError,"Stale or incomplete"):
            build_snapshot(archive,public,fx,captured_at_utc=ASOF,
                           verified_halving_date="2024-04-20",
                           code_sha256="a"*64)

    def test_first_real_stale_capture_retained_but_not_forward_scored(self):
        # First published record (observed Oct15, captured Oct18)
        # must remain hash-verifiable and MUST NOT be scored as
        # prospectively actionable even if its next seven close dates
        # are eventually observed and frozen.
        original=snapshot()
        late={
            **original,
            "observation_date_utc":"2026-10-15",
            "signal_input_last_prior_close_date_utc":"2026-10-14",
        }
        self.assertFalse(_was_captured_prospectively(late))
        tape,_=append_snapshot("",late)
        d0=pd.Timestamp("2026-10-15",tz="UTC")
        for i in range(1,8):
            date=d0+pd.Timedelta(days=i)
            item={
                **original,
                "observation_date_utc":str(date.date()),
                "captured_at_utc":(
                    date+pd.Timedelta(days=1,hours=12)).isoformat(),
                "signal_input_last_prior_close_date_utc":str(
                    (date-pd.Timedelta(days=1)).date()),
                "btc_usd_observed_close":f"{64+i:.6f}",
            }
            self.assertTrue(_was_captured_prospectively(item))
            tape,_=append_snapshot(tape,item)
        rows=_read_rows(tape,SIGNAL_COLUMNS,
                        date_key="observation_date_utc")
        self.assertEqual(len(rows),8)
        self.assertEqual(rows[0]["observation_date_utc"],"2026-10-15")
        self.assertFalse(_was_captured_prospectively(rows[0]))
        outcomes,count=append_due_outcomes(
            "",tape,evaluated_at_utc="2026-10-25T12:00:00Z")
        self.assertEqual(outcomes,"")
        self.assertEqual(count,0)

    def test_stale_external_provider_is_reported_as_skip_no_csv_file(self):
        archive,public,fx=sources()
        public=public.loc[:"2026-10-15"]
        # Mock the prospective Kraken fallback too: no network, and no
        # consecutive eligible dates through yesterday, so record SKIP.
        kraken=pd.DataFrame(
            {"btc_usd":np.full(len(public.index),100.)},
            index=public.index)
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("engines.research.cycle_forward_signal_tape.read_exported_history",
                      return_value=archive),
                patch("engines.research.cycle_forward_signal_tape.fetch_public_series",
                      return_value=(public,fx)),
                patch("engines.research.cycle_forward_signal_tape.fetch_halving_countdown",
                      return_value={}),
                patch("engines.research.cycle_forward_signal_tape.normalise_halving_epoch_metadata",
                      return_value={"last_halving_date":"2024-04-20",
                                    "halving_date_verified":True}),
                patch("engines.research.cycle_forward_signal_tape.fetch_completed_kraken_daily",
                      return_value=kraken),
            ):
                result=run_once(out_dir=Path(directory),now=ASOF)
            self.assertEqual(
                result["status"],"skipped_kraken_verified_bridge_unavailable")
            self.assertFalse(result["wrote_snapshot"])
            self.assertFalse(result["wrote_outcomes"])
            self.assertFalse(list(Path(directory).iterdir()))


if __name__=="__main__":
    unittest.main()
