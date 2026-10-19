"""Immutable date-label correction candidate tests; no HTTP, portfolios or live rules."""
import copy
import datetime as dt
import unittest

import pandas as pd
import numpy as np

from engines.research.cycle_public_daily_timestamp_candidate import (
    build_corrected_source_candidate, strict_previous_utc_close,
)
from engines.research.verified_recent_price_bridge import parse_blockchain_price

UTC=dt.timezone.utc
NOW=dt.datetime(2026,10,19,2,30,tzinfo=UTC)
DAY1=pd.Timestamp("2026-10-01",tz="UTC")


def value(date):
    date=pd.Timestamp(date)
    date=date.tz_localize("UTC") if date.tzinfo is None else date.tz_convert("UTC")
    return float(80000+(date-DAY1).days*100)


def inputs():
    historic=pd.date_range("2026-10-01","2026-10-13",freq="D",tz="UTC")
    archive=pd.DataFrame({"price_usd":[value(d) for d in historic]},index=historic)
    public=pd.date_range("2026-10-04","2026-10-16",freq="D",tz="UTC")
    raw={"values":[{"x":int((d+pd.Timedelta(days=1)).timestamp()),"y":value(d)}
                   for d in public]}
    kdays=pd.date_range("2026-10-07","2026-10-18",freq="D",tz="UTC")
    kraken=pd.DataFrame({"btc_usd":[value(d) for d in kdays]},index=kdays)
    return archive,raw,kraken


class DailyDateAlignmentTests(unittest.TestCase):
    def test_raw_midnight_label_D_maps_to_D_minus_one(self):
        a,raw,k=inputs()
        aligned=strict_previous_utc_close(raw,captured_at_utc=NOW)
        self.assertEqual(str(aligned.index[0].date()),"2026-10-04")
        self.assertEqual(str(aligned.index[-1].date()),"2026-10-16")
        self.assertEqual(str(parse_blockchain_price(raw).index[-1].date()),"2026-10-17")
        self.assertAlmostEqual(float(aligned["btc_usd"].iloc[-1]),value("2026-10-16"))
        self.assertEqual(aligned.index.tz,UTC)

    def test_full_independent_source_bridge_and_archive_preservation(self):
        archive,raw,kraken=inputs()
        original=archive.copy(deep=True)
        out=build_corrected_source_candidate(archive,raw,kraken,captured_at_utc=NOW)
        self.assertEqual(out["latest_verified_full_close_utc"],"2026-10-18")
        self.assertEqual(out["kraken_bridge_appended_dates"],["2026-10-17","2026-10-18"])
        self.assertEqual(out["max_archive_overlap_difference_pct"],0)
        self.assertEqual(out["max_recent_kraken_overlap_difference_pct"],0)
        self.assertTrue(out["original_archive_prices_preserved"])
        pd.testing.assert_frame_equal(archive,original)
        pd.testing.assert_series_equal(
            out["candidate_history"].loc[archive.index],archive["price_usd"],
        )
        self.assertFalse(out["available_for_live_trading"])
        self.assertFalse(out["live_parser_modified"])
        self.assertFalse(out["portfolio_or_ntfy_modified"])

    def test_current_utc_day_never_labelled_as_completed_close(self):
        _,raw,_=inputs()
        raw["values"].append({"x":int(pd.Timestamp("2026-10-20",tz="UTC").timestamp()),
                              "y":200000})
        with self.assertRaisesRegex(ValueError,"not captured"):
            strict_previous_utc_close(raw,captured_at_utc=NOW)

    def test_intraday_epoch_date_semantics_refused(self):
        _,raw,_=inputs()
        raw["values"][2]["x"]+=3600
        with self.assertRaisesRegex(ValueError,"Non-midnight"):
            strict_previous_utc_close(raw,captured_at_utc=NOW)

    def test_duplicate_source_chart_point_refused(self):
        _,raw,_=inputs()
        raw["values"].append(dict(raw["values"][-1]))
        with self.assertRaisesRegex(ValueError,"duplicated"):
            strict_previous_utc_close(raw,captured_at_utc=NOW)

    def test_unsorted_source_chart_dates_refused(self):
        _,raw,_=inputs()
        raw["values"][1],raw["values"][2]=raw["values"][2],raw["values"][1]
        with self.assertRaisesRegex(ValueError,"Out of order"):
            strict_previous_utc_close(raw,captured_at_utc=NOW)

    def test_wrong_future_or_nonfinite_price_refused(self):
        _,raw,_=inputs()
        raw["values"][0]["y"]="nan"
        with self.assertRaisesRegex(ValueError,"Invalid BTC"):
            strict_previous_utc_close(raw,captured_at_utc=NOW)

    def test_missing_source_chart_points(self):
        with self.assertRaisesRegex(ValueError,"No public"):
            strict_previous_utc_close({"values":[]},captured_at_utc=NOW)

    def test_non_aware_receipt_rejected(self):
        _,raw,_=inputs()
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            strict_previous_utc_close(raw,captured_at_utc=NOW.replace(tzinfo=None))

    def test_chart_epoch_must_be_exact_UTC_midnight(self):
        _,raw,_=inputs()
        raw["values"][0]["x"]+=.25
        with self.assertRaisesRegex(ValueError,"Fractional"):
            strict_previous_utc_close(raw,captured_at_utc=NOW)

    def test_archive_disagreement_aborts_candidate(self):
        a,raw,k=inputs()
        a.loc["2026-10-12","price_usd"]*=.75
        with self.assertRaisesRegex(ValueError,"historic archive"):
            build_corrected_source_candidate(a,raw,k,captured_at_utc=NOW)

    def test_kraken_disagreement_aborts_candidate(self):
        a,raw,k=inputs()
        k.loc["2026-10-15","btc_usd"]*=1.09
        with self.assertRaisesRegex(ValueError,"conflicts with completed Kraken"):
            build_corrected_source_candidate(a,raw,k,captured_at_utc=NOW)

    def test_missing_kraken_bridge_day_refuses_synthetic_close(self):
        a,raw,k=inputs()
        k=k.drop(pd.Timestamp("2026-10-17",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"consecutive"):
            build_corrected_source_candidate(a,raw,k,captured_at_utc=NOW)

    def test_no_independent_recent_exchange_cannot_approve(self):
        a,raw,k=inputs()
        k=k.loc[:"2026-10-08"]
        with self.assertRaisesRegex(ValueError,"No recent independent"):
            build_corrected_source_candidate(a,raw,k,captured_at_utc=NOW)

    def test_older_than_three_days_kraken_bridge_rejected(self):
        a,raw,k=inputs()
        # Missing too many days after the last independently labelled close.
        raw["values"]=raw["values"][:-3]
        with self.assertRaisesRegex(ValueError,"short safe Kraken bridge"):
            build_corrected_source_candidate(a,raw,k,captured_at_utc=NOW)

    def test_future_kraken_daily_candle_must_not_enter_candidate(self):
        a,raw,k=inputs()
        k.loc[pd.Timestamp("2026-10-19",tz="UTC"),"btc_usd"]=92000.
        with self.assertRaisesRegex(ValueError,"unfinished"):
            build_corrected_source_candidate(a,raw,k,captured_at_utc=NOW)

    def test_explicit_archive_price_copy_not_mutated_on_failure(self):
        a,raw,k=inputs()
        prior=copy.deepcopy(a)
        raw["values"][0]["y"]=-1
        with self.assertRaises(ValueError):
            build_corrected_source_candidate(a,raw,k,captured_at_utc=NOW)
        pd.testing.assert_frame_equal(a,prior)


if __name__ == "__main__":
    unittest.main()
