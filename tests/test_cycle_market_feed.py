"""One online BTC price crosscheck shared by the dashboard and daily ntfy."""
import unittest
import pandas as pd
from engines.research.cycle_market_feed import merge_verified_cycle_prices


class CycleMarketFeedTests(unittest.TestCase):
    def prices(self):
        dates=pd.date_range("2026-10-01",periods=6,freq="D",tz="UTC")
        archive=pd.DataFrame({"price_usd":[80.,81.,82.,83.,84.,85.]},index=dates)
        other=pd.date_range("2026-10-01",periods=9,freq="D",tz="UTC")
        public=pd.DataFrame({"btc_usd":[80.,81.,82.,83.,84.,85.,86.,87.,5000.]},index=other)
        return archive,public

    def test_live_day_excluded_and_archive_unchanged(self):
        archive,public=self.prices()
        before=archive.copy(deep=True)
        combined,report=merge_verified_cycle_prices(
            archive,public,utc_today="2026-10-09")
        self.assertEqual(str(combined.index[-1].date()),"2026-10-08")
        self.assertEqual(combined.iloc[-1],87.)
        self.assertEqual(report["added_dates"],2)
        self.assertEqual(report["price_staleness_days"],1)
        pd.testing.assert_frame_equal(archive,before)

    def test_archive_prices_not_revised_by_public(self):
        archive,public=self.prices()
        public.loc[pd.Timestamp("2026-10-05",tz="UTC"),"btc_usd"]=85.
        combined,report=merge_verified_cycle_prices(
            archive,public,utc_today="2026-10-09")
        self.assertEqual(combined.loc["2026-10-05"],84.)

    def test_large_disagreement_and_no_overlap_fail_closed(self):
        archive,public=self.prices()
        public["btc_usd"]*=2
        with self.assertRaisesRegex(ValueError,"conflicts"):
            merge_verified_cycle_prices(archive,public,utc_today="2026-10-09")
        with self.assertRaisesRegex(ValueError,"overlap"):
            merge_verified_cycle_prices(archive,public.loc["2026-10-07":],
                                        utc_today="2026-10-09")

    def test_public_data_can_be_old_but_reports_age(self):
        archive,public=self.prices()
        combined,report=merge_verified_cycle_prices(
            archive,public,utc_today="2026-10-20")
        self.assertEqual(report["price_staleness_days"],11)
        # Consumer explicitly blocks transaction if stale;
        # stale public prices cannot silently be today's quote.
        self.assertEqual(str(combined.index[-1].date()),"2026-10-09")

    def test_no_current_utc_day_stored(self):
        archive,public=self.prices()
        combined,report=merge_verified_cycle_prices(
            archive,public,utc_today="2026-10-07")
        self.assertEqual(str(combined.index[-1].date()),"2026-10-06")


if __name__=="__main__":
    unittest.main()
