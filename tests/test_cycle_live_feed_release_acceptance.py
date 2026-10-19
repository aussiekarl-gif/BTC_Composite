"""Live source acceptance and code-only rollback rehearsals; strictly offline."""
import datetime as dt
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from engines.research.cycle_live_feed_release_acceptance import accept

NOW=dt.datetime(2026,10,19,3,40,tzinfo=dt.timezone.utc)
TODAY=pd.Timestamp("2026-10-19",tz="UTC")
Q={"symbol":"ASX:IBIT","price_aud":22.42,
   "timestamp_utc":"2026-10-19T03:00:00+00:00"}
H={"last_halving_date":"2024-04-20","halving_date_verified":True}


def fixtures(*,last_raw="2026-10-15",kraken_last="2026-10-18"):
    hist=pd.date_range("2021-01-01","2026-10-05",freq="D",tz="UTC")
    archive=pd.DataFrame({"price_usd":np.full(len(hist),100.)},index=hist)
    public=pd.date_range("2026-09-24",last_raw,freq="D",tz="UTC")
    raw=pd.DataFrame({"btc_usd":np.full(len(public),100.)},index=public)
    kl=pd.date_range("2026-09-19",kraken_last,freq="D",tz="UTC")
    kraken=pd.DataFrame({"btc_usd":np.full(len(kl),100.)},index=kl)
    fx_index=pd.date_range("2026-09-01","2026-10-19",freq="D",tz="UTC")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fx_index),1.5)},index=fx_index)
    return archive,raw,fx,kraken


def run(archive=None,raw=None,fx=None,k=None,halving=None,now=NOW):
    a,b,c,d=fixtures()
    return accept(archive if archive is not None else a,
                  raw if raw is not None else b,
                  fx if fx is not None else c,
                  k if k is not None else d,
                  halving if halving is not None else H,
                  now=now,quote=Q)


class LiveAcceptanceAndRollbackTests(unittest.TestCase):
    def test_four_day_rescue_passes_but_rollback_refuses_stale_input(self):
        r=run()
        self.assertEqual(r["completed_UTC_BTC_close_date"],"2026-10-18")
        self.assertEqual(r["default_style_market_watch"],"HOLD")
        self.assertEqual(r["rollback_rehearsal_status"],"FAIL_CLOSED")
        self.assertEqual(r["verified_Kraken_Blockchain_recent_overlap_days"]>=3,True)
        self.assertEqual(r["actual_verified_Kraken_bridge_dates"],[
            "2026-10-15","2026-10-16","2026-10-17","2026-10-18"])
        self.assertEqual(r["missing_Kraken_day_test"],"REJECTED_MISSING_REAL_KRAKEN_CLOSE")
        self.assertTrue(r["rollback_retains_correct_Blockchain_D_minus_1_label"])
        self.assertEqual(r["notifications_sent"],0)
        self.assertEqual(r["broker_orders"],0)
        self.assertEqual(r["portfolio_writes"],0)

    def test_three_day_source_rollback_changes_no_price_or_signal(self):
        a,_,fx,k=fixtures()
        _,raw,_,_=fixtures(last_raw="2026-10-16")
        r=run(archive=a,raw=raw,fx=fx,k=k)
        self.assertEqual(r["rollback_rehearsal_status"],"VERIFIED_AVAILABLE")
        self.assertTrue(r["ntfy_message_matches_shared_Streamlit_market_calculation"])

    def test_causally_eligible_prior_close_buy_signal(self):
        a,raw,fx,k=fixtures()
        k.loc[pd.Timestamp("2026-10-17",tz="UTC"),"btc_usd"]=60.
        k.loc[pd.Timestamp("2026-10-18",tz="UTC"),"btc_usd"]=105.
        r=run(archive=a,raw=raw,fx=fx,k=k)
        self.assertEqual(r["default_style_market_watch"],"BUY WATCH")
        self.assertEqual(r["market_buy_pct_remaining_cash"],2.5)
        self.assertEqual(r["market_sell_pct_remaining_holdings"],0)

    def test_missing_required_kraken_day_is_rejected(self):
        a,b,fx,k=fixtures()
        k=k.drop(pd.Timestamp("2026-10-16",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"consecutive"):
            run(archive=a,raw=b,fx=fx,k=k)

    def test_conflicting_exchange_source_cannot_be_accepted(self):
        a,b,fx,k=fixtures()
        k.loc[pd.Timestamp("2026-10-13",tz="UTC"),"btc_usd"]=120.
        with self.assertRaisesRegex(ValueError,"disagreement"):
            run(archive=a,raw=b,fx=fx,k=k)

    def test_kraken_missing_yesterday_never_fabricated(self):
        a,b,fx,k=fixtures()
        k=k.drop(pd.Timestamp("2026-10-18",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"yesterday"):
            run(archive=a,raw=b,fx=fx,k=k)

    def test_reference_older_than_allowed_boundary(self):
        a,_,fx,k=fixtures()
        _,old,_,_=fixtures(last_raw="2026-10-10")
        with self.assertRaisesRegex(ValueError,"too old"):
            run(archive=a,raw=old,fx=fx,k=k)

    def test_unverified_halving_prevents_market_allocation(self):
        with self.assertRaisesRegex(ValueError,"Halving epoch unverified"):
            run(halving={"halving_date_verified":False})

    def test_unknown_prior_aud_fx_prevents_market_allocation(self):
        a,b,fx,k=fixtures()
        fx=fx.iloc[0:0]
        with self.assertRaises((ValueError,IndexError)):
            run(archive=a,raw=b,fx=fx,k=k)

    def test_inputs_not_mutated_after_rollback_rehearsal(self):
        a,b,fx,k=fixtures()
        before=[x.copy(deep=True) for x in (a,b,fx,k)]
        run(archive=a,raw=b,fx=fx,k=k)
        for orig,observed in zip(before,(a,b,fx,k)):
            pd.testing.assert_frame_equal(orig,observed)

    def test_feed_wiring_was_verified_without_browser_or_broker(self):
        x=run()
        self.assertTrue(x["code_wiring"]["Streamlit_and_ntfy_use_same_shared_BTC_market_module"])
        self.assertFalse(x["code_wiring"]["Streamlit_browser_UI_end_to_end_tested"])
        self.assertFalse(x["code_wiring"]["account_specific_whole_IBIT_order_parity_asserted"])
        self.assertFalse(x["new_strategy_approved"])

    def test_future_or_naive_instant_refused(self):
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            run(now=NOW.replace(tzinfo=None))


if __name__=="__main__":
    unittest.main()
