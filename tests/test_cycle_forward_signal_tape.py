"""Immutable prospective-only Cycle Trading market-signal tape.

No real GitHub/network/portfolios required; all price data are synthetic.
"""
import unittest
import datetime as dt

import numpy as np
import pandas as pd

from engines.research.cycle_forward_signal_tape import (
    GENESIS, OUTCOME_COLUMNS, SIGNAL_COLUMNS, HORIZONS,
    _read_rows, append_snapshot, append_due_outcomes,
    build_snapshot, _prior_annual_volatility,
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
        data.loc[p.index[p.index>a.index[-1]]]=p.loc[
            p.index[p.index>a.index[-1]],"btc_usd"]
        asof=pd.Timestamp("2026-10-17",tz="UTC")
        ref=_prior_annual_volatility(data,asof)
        data.loc[asof]=9999.
        self.assertAlmostEqual(_prior_annual_volatility(data,asof),ref)


if __name__=="__main__":
    unittest.main()
