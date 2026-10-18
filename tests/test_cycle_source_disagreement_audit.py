"""Source attribution tests: a max historical deviation is NOT today's BTC price."""
import unittest
import pandas as pd
import numpy as np

from engines.research.cycle_source_disagreement_audit import (
    source_overlap_audit,
)

DATE="2026-10-18"


def sources(*,worst_public=106.29, worst_archive=100.,
            blockchain_latest=100.,third=True):
    idx=pd.date_range("2015-01-01","2026-10-05",freq="D",tz="UTC")
    archive=pd.DataFrame({"price_usd":np.full(len(idx),100.)},
                         index=idx)
    archive.loc["2026-10-04","price_usd"]=worst_archive
    pidx=pd.date_range("2026-09-01","2026-10-17",freq="D",tz="UTC")
    public=pd.DataFrame({"btc_usd":np.full(len(pidx),100.)},index=pidx)
    public.loc["2026-10-04","btc_usd"]=worst_public
    public.loc["2026-10-05","btc_usd"]=blockchain_latest
    kraken=None
    if third:
        kraken=pd.DataFrame({"btc_usd":np.full(len(pidx),100.)},index=pidx)
    return archive,public,kraken


class SourceDisagreementAttributionTests(unittest.TestCase):
    def test_six_point_two_nine_is_archive_overlap_max_not_last_close(self):
        archive,public,kraken=sources()
        r=source_overlap_audit(
            archive,public,kraken=kraken,asof=DATE)
        ab=r["source_pairs"][0]
        self.assertEqual(ab["maximum_absolute_pct"],6.29)
        self.assertEqual(ab["maximum_deviation_date_utc"],"2026-10-04")
        self.assertEqual(ab["last_overlap_date"],"2026-10-05")
        self.assertEqual(ab["latest_pair_absolute_pct"],0.)
        self.assertEqual(ab["dates_exceeding_5pct"],["2026-10-04"])
        self.assertEqual(r["archive_latest_date"],"2026-10-05")
        self.assertEqual(r["blockchain_latest_completed_date"],"2026-10-17")
        self.assertEqual(r["third_source_assessment_on_worst_date"],
                         "KRAKEN_CLOSER_TO_ARCHIVE_ON_WORST_DAY")
        self.assertTrue(r["manual_data_provenance_review_required"])
        self.assertFalse(r["eligible_to_change_live_source_or_signal"])
        self.assertFalse(r["prices_overwritten"])

    def test_third_source_corroborating_blockchain_is_separately_identified(self):
        a,b,k=sources()
        k.loc["2026-10-04","btc_usd"]=106.29
        r=source_overlap_audit(a,b,kraken=k,asof=DATE)
        self.assertEqual(r["third_source_assessment_on_worst_date"],
                         "KRAKEN_CLOSER_TO_BLOCKCHAIN_ON_WORST_DAY")

    def test_without_kraken_report_uncertainty_not_illusory_independence(self):
        a,b,_=sources(third=False)
        r=source_overlap_audit(a,b,asof=DATE)
        self.assertEqual(r["third_source_assessment_on_worst_date"],
                         "UNAVAILABLE_NO_THIRD_SOURCE")
        self.assertEqual(len(r["source_pairs"]),1)
        self.assertIsNone(r["worst_blockchain_archive_overlap_day"][
                          "kraken_BTC_USD"])

    def test_strict_200wma_flip_is_separate_sensitivity_not_live_signal(self):
        a,b,k=sources(worst_archive=95.,worst_public=106.29)
        k.loc["2026-10-04","btc_usd"]=95.
        r=source_overlap_audit(a,b,kraken=k,asof=DATE)
        flip=r["potential_200wma_crossing_disagreement_dates"]
        self.assertIn("2026-10-04",flip)
        x=r["worst_blockchain_archive_overlap_day"]
        self.assertTrue(x["strict_prior_200wma_sensitivity"][
                        "potential_different_single_day_gate"])
        self.assertTrue(r["local_gate_sensitivity_uses_archived_200wma_for_all_prices"])
        self.assertFalse(r["eligible_to_change_live_source_or_signal"])

    def test_midnight_chart_day_shift_can_eliminate_false_daily_error(self):
        a,b,k=sources()
        for date in a.loc["2026-08-30":].index:
            a.loc[date,"price_usd"]=100+(date-pd.Timestamp(
                "2026-08-30",tz="UTC")).days
        for date in b.index:
            prior=date-pd.Timedelta(days=1)
            if prior in a.index:
                b.loc[date,"btc_usd"]=float(a.loc[prior,"price_usd"])
        report=source_overlap_audit(a,b,asof=DATE)
        raw=report["source_pairs"][0]
        corrected=report[
            "archive_vs_blockchain_if_chart_timestamp_marks_end_of_previous_day"]
        self.assertGreater(raw["maximum_absolute_pct"],.5)
        self.assertEqual(corrected["maximum_absolute_pct"],0.)
        self.assertEqual(corrected["latest_pair_absolute_pct"],0.)
        self.assertFalse(report["eligible_to_change_live_source_or_signal"])

    def test_shadow_shared_market_restores_real_completed_UTC_day(self):
        from engines.research.cycle_source_disagreement_audit import (
            shadow_live_feed_alignment,
        )
        a,b,k=sources()
        b=b.loc[:"2026-10-15"]
        fx=pd.DataFrame({"aud_per_usd":np.full(40,1.5)},
                        index=pd.date_range("2026-09-09",periods=40,
                                            freq="D",tz="UTC"))
        out=shadow_live_feed_alignment(
            a,b,k,fx,asof=DATE)
        base=out["main_live_source_unmodified"]
        shadow=out["corrected_chart_date_plus_completed_Kraken_SHADOW"]
        self.assertEqual(base["observed_BTC_close_UTC_date"],"2026-10-15")
        self.assertEqual(shadow["observed_BTC_close_UTC_date"],"2026-10-17")
        self.assertEqual(base["signal_from_SHARED_UNCHANGED_market_code"],
                         shadow["signal_from_SHARED_UNCHANGED_market_code"])
        self.assertEqual(out["Kraken_last_completed_day_bridge"][
            "appended_dates"],[
                "2026-10-15","2026-10-16","2026-10-17"])
        self.assertTrue(out["shadow_only_no_implemented_live_change"])
        self.assertEqual(shadow["BUY_pct_remaining_AUD_cash"],0.)

    def test_shadow_rejects_unavailable_recent_completed_exchange_closes(self):
        from engines.research.cycle_source_disagreement_audit import (
            shadow_live_feed_alignment,
        )
        a,b,k=sources()
        b=b.loc[:"2026-10-15"]
        fx=pd.DataFrame({"aud_per_usd":np.full(40,1.5)},
                        index=pd.date_range("2026-09-09",periods=40,
                                            freq="D",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"consecutive"):
            shadow_live_feed_alignment(
                a,b,k.loc[:"2026-10-14"],fx,asof=DATE)
        with self.assertRaisesRegex(ValueError,"independently"):
            shadow_live_feed_alignment(a,b,None,fx,asof=DATE)

    def test_post_archive_new_public_days_check_against_kraken(self):
        a,b,k=sources()
        b.loc["2026-10-14","btc_usd"]=110.
        result=source_overlap_audit(a,b,kraken=k,asof=DATE)
        newer=result["post_archive_new_daily_Blockchain_vs_Kraken"]
        self.assertTrue(newer["available"])
        self.assertEqual(newer["first_overlap_date"],"2026-10-06")
        self.assertEqual(newer["last_overlap_date"],"2026-10-17")
        self.assertEqual(newer["maximum_deviation_date_utc"],"2026-10-14")
        self.assertEqual(newer["maximum_absolute_pct"],9.09091)
        self.assertEqual(newer["latest_pair_absolute_pct"],0.)

    def test_chart_daily_date_offset_triangulation_is_diagnostic_only(self):
        a,b,k=sources()
        idx=k.index
        k["btc_usd"]=100+np.arange(len(idx),dtype=float)
        b["btc_usd"]=k["btc_usd"].shift(1)
        b.iloc[0,0]=float(k.iloc[0,0])
        report=source_overlap_audit(a,b,kraken=k,asof=DATE)
        shift=report["prior_overlap_Blockchain_Kraken_date_shift_diagnostic"]
        self.assertTrue(shift["available"])
        self.assertEqual(shift[
            "lowest_median_absolute_deviation_offset_days"],-1)
        self.assertTrue(shift[
            "possible_different_daily_timestamp_convention"])
        self.assertTrue(shift[
            "diagnostic_only_never_changes_prices_or_trade_dates"])
        self.assertFalse(report["prices_overwritten"])

    def test_missing_independent_exchange_returns_missing_diagnostics(self):
        a,b,k=sources(third=False)
        r=source_overlap_audit(a,b,asof=DATE)
        self.assertIsNone(r["post_archive_new_daily_Blockchain_vs_Kraken"])
        self.assertIsNone(r[
            "prior_overlap_Blockchain_Kraken_date_shift_diagnostic"])

    def test_future_current_day_candle_excluded(self):
        a,b,k=sources()
        b.loc[pd.Timestamp("2026-10-18",tz="UTC")]=999999.
        k.loc[pd.Timestamp("2026-10-18",tz="UTC")]=1.
        r=source_overlap_audit(a,b,kraken=k,asof=DATE)
        self.assertEqual(r["blockchain_latest_completed_date"],"2026-10-17")
        self.assertEqual(r["source_pairs"][0]["maximum_absolute_pct"],6.29)

    def test_duplicate_undated_and_missing_overlap_fail_closed(self):
        a,b,k=sources()
        with self.assertRaisesRegex(ValueError,"Invalid"):
            source_overlap_audit(a,b.iloc[::-1],asof=DATE)
        with self.assertRaisesRegex(ValueError,"Invalid"):
            source_overlap_audit(a,b.loc[b.index.repeat(2)],asof=DATE)
        with self.assertRaisesRegex(ValueError,"Not enough"):
            source_overlap_audit(a,b.loc["2026-10-10":],asof=DATE)
        with self.assertRaisesRegex(ValueError,"Invalid"):
            source_overlap_audit(a.iloc[:0],b,asof=DATE)

    def test_lookback_uses_real_calendar_date_not_future_after_archive(self):
        a,b,k=sources()
        r=source_overlap_audit(a,b,kraken=k,asof=DATE)
        ab=r["source_pairs"][0]
        self.assertEqual(ab["first_overlap_date"],"2026-09-05")
        self.assertEqual(ab["last_overlap_date"],"2026-10-05")
        self.assertEqual(ab["overlap_days"],31)
        self.assertTrue(all(x["date_utc"]<="2026-10-05"
                            for x in r["source_observations"]))


if __name__=="__main__":
    unittest.main()
