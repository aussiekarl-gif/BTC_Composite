"""Offline safety and causal unit tests for the append-only V5.9 forward tape."""
from datetime import datetime,timedelta,timezone,date
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from engines.research import v59_forward_dca_tape as t


def snapshot(d=date(2026,11,15),risk=.05,ratio=1.02,residual=-.10):
    captured=datetime.combine(d+timedelta(days=1),datetime.min.time(),timezone.utc)+timedelta(hours=1)
    sunday=d-timedelta(days=(d.weekday()+1)%7)
    # WMA is a completed Sunday on or before signal
    price=100000.
    return {
        "status":"RESEARCH_SIGNAL_SNAPSHOT_READY","risk_and_fx_fresh":True,
        "captured_at_utc":captured.isoformat(),
        "closed_risk_observation_utc":datetime.combine(d,datetime.min.time(),timezone.utc).isoformat(),
        "risk_score_source":"Walk-forward Power Law","r2_sizing_risk":risk,
        "power_law_residual":residual,
        "btc_usd_closed_price":price,"usd_per_aud":.70,
        "btc_usd_200wma_last_completed_sunday":price/ratio,
        "daily_closed_btc_usd_to_last_completed_200wma_ratio":ratio,
        "btc_usd_200wma_week_ending_utc":sunday.isoformat(),
        "fx_observation_date_utc":(d-timedelta(days=min((d.weekday()-4)%7,4))).isoformat(),
        "fingerprint":"fixture-"+d.isoformat(),
        "risk_model":"Research WF Power Law",
        "risk_provider":"Blockchain.com market-price daily UTC",
        "fx_provider":"Frankfurter USD/AUD business-day",
    }


def row(d,risk=.05,ratio=1.02,price=100000.,residual=-.10):
    s=snapshot(d,risk,ratio,residual)
    s["btc_usd_closed_price"]=price
    s["btc_usd_200wma_last_completed_sunday"]=price/ratio
    return t.to_observation(s)


class ForwardDcaTapeTests(unittest.TestCase):
    def test_rejects_fallback_stale_unclosed_and_future_fx(self):
        r=snapshot()
        self.assertEqual(t.to_observation(r)["signal_date"],"2026-11-15")
        for key,value in [
            ("status","BLOCKED_SOURCE_OR_FRESHNESS"),
            ("risk_and_fx_fresh",False),
            ("risk_score_source","Neutral fallback"),
            ("btc_usd_200wma_week_ending_utc","2026-11-16"),
            ("usd_per_aud",float("nan")),
            ("r2_sizing_risk",1.4),
            ("daily_closed_btc_usd_to_last_completed_200wma_ratio",.5),
        ]:
            with self.subTest(key=key):
                with self.assertRaises((ValueError,TypeError)):
                    t.to_observation(dict(r,**{key:value}))

    def test_append_only_and_idempotence(self):
        first=row(date(2026,11,15))
        rows,added=t.add_observation([],first)
        self.assertTrue(added)
        duplicate=row(date(2026,11,15),price=111000.)
        rows,added=t.add_observation(rows,duplicate)
        self.assertFalse(added)
        self.assertEqual(rows[0]["btc_usd"],100000.)
        second=row(date(2026,11,16),price=98000.)
        rows,added=t.add_observation(rows,second)
        self.assertTrue(added)
        with self.assertRaisesRegex(ValueError,"older"):
            t.add_observation(rows,first)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"tape.jsonl"
            p.write_text("".join(json.dumps(r)+"\n" for r in rows))
            self.assertEqual(len(t.read_tape(p)),2)

    def test_yield_and_empty_future_does_not_claim_win(self):
        r=[row(date(2026,11,15))]
        sc=t.scorecard(r,True)
        self.assertEqual(sc["prospective_shadow"]["matched_prospective_monday_fills"],0)
        self.assertEqual(sc["matured_paper_BTC_AUD_returns"]["84d"]["observed_exact_horizon_pairs"],0)

    def test_paper_monday_requires_previous_sunday_and_monday_capture(self):
        r=[row(date(2026,11,15)),row(date(2026,11,16),price=95000.)]
        stats=t.paper_portfolios(r)
        self.assertEqual(stats["matched_prospective_monday_fills"],1)
        strict=stats["strategies"]["risk_3x_risk_le_020"]
        self.assertEqual(strict["paper_buy_count"],1)
        self.assertGreater(strict["additional_purchase_aud"],0)
        self.assertLessEqual(strict["additional_purchase_aud"],25500.)
        self.assertFalse(stats["broker_fills_verified"])
        only_monday=t.paper_portfolios(r[1:])
        self.assertEqual(only_monday["matched_prospective_monday_fills"],0)

    def test_piecewise_tail_shadow_uses_only_saved_raw_residual(self):
        deep=row(date(2026,11,15),risk=.05,residual=-.32)
        self.assertEqual(t.multipliers(deep)["piecewise_tail_3x_mid"],10.)
        near_deep=row(date(2026,11,15),risk=.05,residual=-.31)
        self.assertEqual(t.multipliers(near_deep)["piecewise_tail_3x_mid"],5.)
        mid=row(date(2026,11,15),risk=.05,residual=-.10)
        self.assertEqual(t.multipliers(mid)["piecewise_tail_3x_mid"],3.)
        # Legacy rows have no raw residual and cannot be retroactively scored.
        legacy=dict(mid)
        legacy.pop("power_law_residual")
        self.assertEqual(t.multipliers(legacy)["piecewise_tail_3x_mid"],0.)
        # The shadow is separate from the current live-risk multiplier.
        self.assertEqual(t.multipliers(mid)["risk_3x"],2.)

    def test_200wma_proximity_gate_and_high_risk_stop(self):
        cheap=row(date(2026,11,15),risk=.05,ratio=.98)
        self.assertEqual(t.multipliers(cheap)["below_200wma"],2.)
        above=row(date(2026,11,15),risk=.05,ratio=1.15)
        self.assertEqual(t.multipliers(above)["below_to_plus10"],0.)
        high=row(date(2026,11,15),risk=.51,ratio=.85)
        self.assertTrue(all(v==0 for v in t.multipliers(high).values()))
        medium=row(date(2026,11,15),risk=.33,ratio=1.05)
        self.assertEqual(t.multipliers(medium)["risk_3x_risk_le_020"],0.)


    def test_asx_ibit_reference_is_dated_indicative_and_never_a_broker_fill(self):
        captured=datetime(2026,11,16,1,23,tzinfo=timezone.utc)
        fresh={
            "symbol":"ASX:IBIT","provider":"Yahoo Finance delayed quote",
            "price_aud":20.81,"timestamp_utc":"2026-11-16T01:00:00+00:00",
            "age_hours":.383,"indicative_only":True,
        }
        result=t.normalize_ibit_reference(fresh,captured)
        self.assertEqual(result["status"],"DATED_INDICATIVE_ASX_IBIT_REFERENCE")
        self.assertTrue(result["usable_for_comparison"])
        self.assertTrue(result["indicative_only"])
        self.assertFalse(result["broker_fill_verified"])
        stale=dict(fresh,timestamp_utc="2026-11-14T01:00:00+00:00",age_hours=48.383)
        result=t.normalize_ibit_reference(stale,captured)
        self.assertFalse(result["usable_for_comparison"])
        self.assertFalse(result["broker_fill_verified"])
        wrong=dict(fresh,symbol="NASDAQ:IBIT")
        self.assertEqual(t.normalize_ibit_reference(wrong,captured)["status"],
                         "INVALID_QUOTE_REFERENCE")
        self.assertEqual(t.normalize_ibit_reference(None,captured)["status"],
                         "UNAVAILABLE")

    def test_ibit_capture_timestamp_is_after_provider_response(self):
        received = datetime(2026,11,16,1,23,10,tzinfo=timezone.utc)
        market_stamp = received - timedelta(minutes=1)
        quote = {
            "symbol":"ASX:IBIT","provider":"Yahoo Finance delayed quote",
            "price_aud":20.81,"timestamp_utc":market_stamp.isoformat(),
            "age_hours":1/60,
        }

        class ReceiptClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return received if tz else received.replace(tzinfo=None)

        with patch.object(t,"datetime",ReceiptClock), \
             patch.object(t,"fetch_ibit_quote",return_value=quote) as fetch:
            result=t.capture_ibit_reference()
        fetch.assert_called_once_with()
        self.assertEqual(result["captured_at_utc"],received.isoformat())
        self.assertAlmostEqual(result["age_hours"],1/60,places=2)
        self.assertFalse(result["broker_fill_verified"])

        with patch.object(t,"datetime",ReceiptClock), \
             patch.object(t,"fetch_ibit_quote",side_effect=ValueError("unavailable")):
            unavailable=t.capture_ibit_reference()
        self.assertEqual(unavailable["status"],"UNAVAILABLE")
        self.assertEqual(unavailable["captured_at_utc"],received.isoformat())

    def test_no_lookahead_matured_return(self):
        start=date(2026,11,15)
        first=row(start)
        later=row(start+timedelta(days=7),price=120000.)
        self.assertEqual(t.matured_returns([first])["7d"]["observed_exact_horizon_pairs"],0)
        output=t.matured_returns([first,later])["7d"]
        self.assertEqual(output["observed_exact_horizon_pairs"],1)
        self.assertGreater(output["btc_aud_excess_over_5pct_cash_on_signals_pct"]["risk_3x"]["mean_pct"],19.)

    def test_offline_weekly_replay_is_deterministic_and_self_financing(self):
        first=date(2026,11,15)
        entries=[]
        for week in range(14):
            sun=first+timedelta(weeks=week)
            mon=sun+timedelta(days=1)
            entries.append(row(sun,price=100000.*(.98**week),ratio=1.00))
            entries.append(row(mon,price=100000.*(.98**week)))
        out=t.paper_portfolios(entries)
        self.assertEqual(out["matched_prospective_monday_fills"],14)
        for p in out["strategies"].values():
            self.assertGreaterEqual(p["remaining_cash_aud"],0.)
            self.assertGreaterEqual(p["paper_btc_reference_units"],0.)
            self.assertLessEqual(p["additional_purchase_aud"],14*25500.+1e-6)
        self.assertAlmostEqual(out["strategies"]["risk_3x"]["portfolio_aud"],
                               out["strategies"]["below_200wma"]["portfolio_aud"],places=5)


if __name__=="__main__":
    unittest.main()
