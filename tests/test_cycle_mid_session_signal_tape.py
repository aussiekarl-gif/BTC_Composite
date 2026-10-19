"""No-IO mid-session research tape regressions, using actual shared Cycle maths."""
import datetime as dt
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from engines.research.cycle_mid_session_signal_tape import (
    COLUMNS, SYDNEY, build_observation, capture_window, read_tape,
    append, capture, probe_live_market,
)

UTC=dt.timezone.utc
AT=dt.datetime(2026,10,20,1,30,tzinfo=UTC)
HASH="0"*63+"a"


def market(*,buy=False,halving_day=912,close_day="2026-10-19",
           usd=135., prior=130., wma=100.,fx_day="2026-10-16"):
    ix=pd.date_range(end=close_day,periods=180,freq="D",tz="UTC")
    px=pd.Series([prior]*179+[usd],index=ix,dtype=float)
    if buy:
        prior=80.
        px.iloc[:]=80.
        px.iloc[-1]=82.
        usd=82.
    return {
        "asof_date":close_day,"price_history":px,
        "previous_close_usd":float(prior),
        "previous_close_below_200wma":bool(prior<wma),
        "prior_200wma_usd":float(wma),
        "btc_price_usd":float(usd),
        "usd_aud_prior":1.45,
        "fx_source_date":fx_day,
        "halving_date":"2024-04-20",
        "halving_day":halving_day,
    }


def verified():
    return {"strict_close_date_verified":True,
            "archive_raw_prices_preserved":True,
            "recent_kraken_blockchain_max_diff_pct":0.05}


def observation(when=AT,**kw):
    return build_observation(market=market(**kw),verified=verified(),
                             captured_at_utc=when,code_hash=HASH)


class MidSessionCycleTests(unittest.TestCase):
    def test_eligible_sydney_midday_and_utc_receipt(self):
        row=observation()
        self.assertEqual(capture_window(AT).isoformat(),"2026-10-20")
        self.assertEqual(row["source_btc_close_utc_date"],"2026-10-19")
        self.assertEqual(row["research_sydney_date"],"2026-10-20")
        self.assertEqual(row["market_signal"],"HOLD")
        self.assertEqual(row["asx_order_executable"],"False")
        self.assertEqual(row["independent_notification_delivery_verified"],"False")

    def test_buy_is_exact_live_default_2_5pct(self):
        row=observation(buy=True)
        self.assertEqual(row["market_signal"],"BUY WATCH")
        self.assertEqual(row["buy_pct_remaining_cash"],"2.5000")
        self.assertEqual(row["sell_pct_current_holdings"],"0.0000")

    def test_sell_is_exact_prior_top_market_percent(self):
        row=observation(halving_day=500)
        self.assertEqual(row["market_signal"],"SELL WATCH")
        self.assertEqual(row["sell_pct_current_holdings"],"5.0000")

    def test_pre_market_and_after_3pm_sydney_rejected(self):
        with self.assertRaisesRegex(ValueError,"eligible Sydney"):
            observation(when=dt.datetime(2026,10,19,23,30,tzinfo=UTC))
        with self.assertRaisesRegex(ValueError,"eligible Sydney"):
            observation(when=dt.datetime(2026,10,20,6,0,tzinfo=UTC))

    def test_weekend_rejected(self):
        with self.assertRaisesRegex(ValueError,"eligible Sydney"):
            observation(when=dt.datetime(2026,10,24,1,30,tzinfo=UTC))

    def test_previous_utc_close_required(self):
        with self.assertRaisesRegex(ValueError,"previous completed"):
            observation(close_day="2026-10-18")
        with self.assertRaisesRegex(ValueError,"previous completed"):
            observation(close_day="2026-10-20")

    def test_not_verified_source_refused(self):
        v=verified();v["strict_close_date_verified"]=False
        with self.assertRaisesRegex(ValueError,"independently verified"):
            build_observation(market=market(),verified=v,
                              captured_at_utc=AT,code_hash=HASH)

    def test_conflicting_kraken_source_fails_closed(self):
        v=verified();v["recent_kraken_blockchain_max_diff_pct"]=6.29
        with self.assertRaisesRegex(ValueError,"disagreement"):
            build_observation(market=market(),verified=v,
                              captured_at_utc=AT,code_hash=HASH)

    def test_future_or_stale_fx_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"future or stale"):
            observation(fx_day="2026-10-19")
        with self.assertRaisesRegex(ValueError,"future or stale"):
            observation(fx_day="2026-10-01")

    def test_no_wrong_model_fingerprint(self):
        with self.assertRaisesRegex(ValueError,"fingerprint"):
            build_observation(market=market(),verified=verified(),
                              captured_at_utc=AT,code_hash="bad")

    def test_append_idempotent_preserves_first_sample(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"mid.csv"
            original=observation()
            self.assertTrue(append(f,original))
            first=f.read_bytes()
            self.assertFalse(append(f,original))
            self.assertEqual(f.read_bytes(),first)
            rows=read_tape(f)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["prior_row_hash"],"0"*64)

    def test_cannot_backfill_and_can_append_next_eligible_day(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"mid.csv"
            append(f,observation())
            future=dt.datetime(2026,10,21,1,30,tzinfo=UTC)
            self.assertTrue(append(f,observation(when=future,close_day="2026-10-20",
                                                fx_day="2026-10-19")))
            self.assertEqual(len(read_tape(f)),2)
            with self.assertRaisesRegex(ValueError,"backfill"):
                append(f,observation())

    def test_modified_hash_chain_rejected(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"mid.csv"
            append(f,observation())
            f.write_text(f.read_text().replace("HOLD","SELL WATCH"))
            with self.assertRaisesRegex(ValueError,"Modified"):
                read_tape(f)

    def test_capture_success_uses_actual_response_receipt(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"mid.csv"
            t=iter([AT,AT+dt.timedelta(seconds=7)])
            result=capture(path=f,clock=lambda:next(t),
                           market_fetcher=lambda _: (market(),verified()))
            self.assertEqual(result["status"],"NEW_PROSPECTIVE_MID_SESSION_RESEARCH_OBSERVATION")
            self.assertEqual(read_tape(f)[0]["captured_at_utc"],(AT+dt.timedelta(seconds=7)).isoformat())
            self.assertEqual(result["new_ntfy_messages"],0)
            self.assertFalse(result["portfolio_access"])

    def test_duplicate_capture_never_fetches_provider_again(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"mid.csv"
            append(f,observation())
            def fail(_):raise AssertionError("Duplicate must not use network")
            result=capture(path=f,clock=lambda:AT,market_fetcher=fail)
            self.assertEqual(result["status"],"EXISTING_SYDNEY_DATE_NO_REWRITE")

    def test_window_crossed_mid_fetch_must_not_write(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"mid.csv"
            t=iter([AT,dt.datetime(2026,10,20,4,5,tzinfo=UTC)])
            with self.assertRaisesRegex(ValueError,"eligible Sydney"):
                capture(path=f,clock=lambda:next(t),
                        market_fetcher=lambda _: (market(),verified()))
            self.assertFalse(f.exists())

    def test_provider_failure_no_partial_tape(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"mid.csv"
            def fail(_):raise ConnectionError("No source")
            with self.assertRaises(ConnectionError):
                capture(path=f,clock=lambda:AT,market_fetcher=fail)
            self.assertFalse(f.exists())

    def test_live_provider_probe_validates_without_persisting(self):
        result=probe_live_market(now=AT,market_fetcher=lambda _: (market(),verified()))
        self.assertEqual(result["status"],"READ_ONLY_REAL_PUBLIC_MARKET_PROBE_NO_WRITE")
        self.assertEqual(result["BTC_last_completed_utc_close"],"2026-10-19")
        self.assertEqual(result["shared_market_signal"],"HOLD")
        self.assertFalse(result["mid_session_snapshot_recorded"])
        self.assertEqual(result["orders_placed"],0)
        self.assertEqual(result["ntfy_sent"],0)

    def test_probe_can_run_before_mid_session_without_implicitly_recording(self):
        morning=dt.datetime(2026,10,19,20,0,tzinfo=UTC)
        result=probe_live_market(now=morning,market_fetcher=lambda _: (
            market(close_day="2026-10-18",fx_day="2026-10-16"),verified()))
        self.assertEqual(result["BTC_last_completed_utc_close"],"2026-10-18")
        self.assertFalse(result["mid_session_snapshot_recorded"])

    def test_public_probe_rejects_stale_verified_daily_close(self):
        with self.assertRaisesRegex(ValueError,"last completed"):
            probe_live_market(now=AT,market_fetcher=lambda _: (
                market(close_day="2026-10-18"),verified()))

    def test_public_probe_rejects_unverified_cross_source_price(self):
        bad=verified();bad["recent_kraken_blockchain_max_diff_pct"]=6.29
        with self.assertRaisesRegex(ValueError,"diverge"):
            probe_live_market(now=AT,market_fetcher=lambda _: (market(),bad))

    def test_public_probe_refuses_missing_prior_aud_fx(self):
        with self.assertRaisesRegex(ValueError,"FX unavailable"):
            probe_live_market(now=AT,market_fetcher=lambda _: (
                market(fx_day="2026-10-19"),verified()))

    def test_public_probe_invalid_tz_refused(self):
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            probe_live_market(now=AT.replace(tzinfo=None),
                              market_fetcher=lambda _: (market(),verified()))

    def test_explicit_no_notification_or_orders_schema(self):
        row=observation()
        self.assertNotIn("ntfy_topic",COLUMNS)
        self.assertNotIn("broker_price",COLUMNS)
        self.assertNotIn("portfolio_units",COLUMNS)
        self.assertEqual(row["asx_order_executable"],"False")


if __name__=="__main__":
    unittest.main()
