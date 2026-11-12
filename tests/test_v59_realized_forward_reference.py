"""Provider-date acceptance and fail-closed realized-price paper evidence."""
from datetime import date,datetime,timezone,timedelta
from unittest.mock import patch
import unittest

from engines.research import v59_realized_forward_reference as rp
from engines.research import v59_forward_dca_tape as tape


NOW=datetime(2026,11,13,3,0,tzinfo=timezone.utc)
DAY=date(2026,11,12)


class RealizedForwardReferenceTests(unittest.TestCase):
    def test_supported_json_realized_date_and_value(self):
        raw={"d":"2026-11-11","unixTs":1794355200,
             "realizedPrice":54012.25,"delayed":False}
        result=rp.normalized_reference(raw,captured_at_utc=NOW,
                                        closed_signal_date=DAY)
        self.assertTrue(result["usable_for_forward"])
        self.assertEqual(result["provider_observation_date"],"2026-11-11")
        self.assertEqual(result["status"],"VALID_DATED_RESEARCH_REFERENCE")
        self.assertEqual(result["realized_price_usd"],54012.25)
        self.assertEqual(len(result["raw_response_sha256"]),64)
        paired=rp.paired_to_spot(result,82000.,DAY)
        self.assertAlmostEqual(paired["price_to_realized_ratio"],82000/54012.25)

    def test_stale_delayed_future_or_unrecognised_source_never_buys(self):
        for raw in (
            {"d":"2026-11-01","realizedPrice":54000},
            {"d":"2026-11-13","realizedPrice":54000},
            {"d":"2026-11-12","realizedPrice":54000,"delayed":True},
            {"d":"2026-11-12","unexpectedField":54000},
            {"realizedPrice":54000},
            [],
        ):
            with self.subTest(raw=raw):
                result=rp.normalized_reference(raw,captured_at_utc=NOW,
                                                closed_signal_date=DAY)
                self.assertFalse(result["usable_for_forward"])
                self.assertIsNone(result["price_to_realized_ratio"])

    def test_forward_tape_preserves_provenance_and_never_overwrites(self):
        first={
            "status":"VALID_DATED_RESEARCH_REFERENCE",
            "captured_at_utc":NOW.isoformat(),
            "provider_observation_date":"2026-11-12",
            "provider":"BGeometrics",
            "realized_price_usd":54000.,
            "usable_for_forward":True,
        }
        snap={
            "status":"RESEARCH_SIGNAL_SNAPSHOT_READY","risk_and_fx_fresh":True,
            "captured_at_utc":NOW.isoformat(),
            "closed_risk_observation_utc":datetime(2026,11,12,tzinfo=timezone.utc).isoformat(),
            "risk_score_source":"Walk-forward Power Law",
            "r2_sizing_risk":.05,
            "btc_usd_closed_price":54000.,
            "usd_per_aud":.72,
            "btc_usd_200wma_last_completed_sunday":65000.,
            "daily_closed_btc_usd_to_last_completed_200wma_ratio":54000/65000,
            "btc_usd_200wma_week_ending_utc":"2026-11-08",
            "fx_observation_date_utc":"2026-11-12",
            "fingerprint":"fake-valid-live-fingerprint",
            "risk_model":"R2","risk_provider":"Fixture",
            "fx_provider":"Fixture",
        }
        x=tape.to_observation(snap,realized_reference=first)
        self.assertAlmostEqual(x["realized_price_reference"]["price_to_realized_ratio"],1.)
        self.assertGreater(tape.multipliers(x)["realized110_and_risk050"],0.)
        old,new=tape.add_observation([],x)
        self.assertTrue(new)
        revised=tape.to_observation(snap,realized_reference=dict(first,realized_price_usd=50000.))
        rows,added=tape.add_observation(old,revised)
        self.assertFalse(added)
        self.assertEqual(rows[0]["realized_price_reference"]["realized_price_usd"],54000.)

    def test_missing_onchain_source_does_not_change_preexisting_paper_buy(self):
        row={"risk":.05,"btc_usd_to_200wma":.92}
        before=tape.multipliers(row)
        after=tape.multipliers({**row,"realized_price_reference":{
            "status":"STALE_OR_DELAYED","usable_for_forward":False,
            "price_to_realized_ratio":.60}})
        self.assertEqual(before,after)
        self.assertEqual(before["realized110_and_risk050"],0.)


    def test_fresh_explore21_csv_is_preferred_with_original_response_hash(self):
        sample_dates=[DAY-timedelta(days=500-i) for i in range(500)]
        content="date,realized_price_usd,sth_realized_price_usd,btc_close_usd\n"
        content+="".join(f"{d.isoformat()},53900,70000,74000\n" for d in sample_dates)
        class Response:
            text=content
            content=content.encode()
            def raise_for_status(self):pass
        with patch.object(rp.requests,"get",return_value=Response()) as get:
            out=rp.capture_reference(closed_signal_date=DAY,captured_at_utc=NOW)
        self.assertEqual(get.call_count,1)
        self.assertEqual(out["provider"],rp.EXPLORE21_SOURCE)
        self.assertTrue(out["usable_for_forward"])
        self.assertEqual(out["provider_observation_date"],"2026-11-11")
        self.assertEqual(out["provider_csv_rows"],500)
        self.assertEqual(len(out["raw_response_sha256"]),64)
        self.assertAlmostEqual(out["realized_price_usd"],53900.)

    def test_bad_csv_with_delayed_backup_never_becomes_live_paper_buy(self):
        class BadCSV:
            text="oops,bad\n"
            content=text.encode()
            def raise_for_status(self):pass
        class Delayed:
            def raise_for_status(self):pass
            def json(self):return {
                "d":"2026-11-05","realizedPrice":53947.12,"delayed":True}
        with patch.object(rp.requests,"get",side_effect=[BadCSV(),Delayed()]) as get:
            out=rp.capture_reference(closed_signal_date=DAY,captured_at_utc=NOW)
        self.assertEqual(get.call_count,2)
        self.assertEqual(out["status"],"STALE_OR_DELAYED")
        self.assertEqual(out["provider_observation_date"],"2026-11-05")
        self.assertFalse(out["usable_for_forward"])


if __name__=="__main__":
    unittest.main()
