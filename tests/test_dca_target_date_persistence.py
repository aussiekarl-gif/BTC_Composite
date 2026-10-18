"""Production V5.8.2 / Research V5.9 durable date persistence regression.

Protect real BTC/IBIT portfolios by storing independent preference keys,
never editing the 'shared' portfolio row. Tests use temporary SQLite and
isolated fake Google worksheet; no user's connected Google data accessed.
"""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engines.shared import model_settings_store as settings
from engines.shared.portfolio_store import (
    load_portfolio,save_portfolio,
)

TODAY=dt.date(2026,10,19)
DEFAULT=dt.date(2029,10,18)
MIN=dt.date(2026,10,26)


class FakeWorksheet:
    def __init__(self):
        self.records=[{
            "portfolio_key":"shared",
            "payload_json":json.dumps({
                "rows":[{"Asset":"ASX:IBIT","Units / BTC Received":20.}],
                "sales":[{"Date":"2026-10-13","Units Sold":3.}],
                "starting_capital_aud":500000,
            }),
            "updated_at_utc":"2026-10-18T00:00:00+00:00",
        }]
    def get_all_records(self):
        return [dict(x) for x in self.records]
    def append_row(self,values,*,value_input_option):
        self.records.append(dict(zip(
            ("portfolio_key","payload_json","updated_at_utc"),values)))
    def update(self,values,range_name,*,value_input_option):
        row=int(range_name.split(":")[0][1:])
        self.records[row-2]=dict(zip(
            ("portfolio_key","payload_json","updated_at_utc"),values[0]))


class DurableDcaTargetTests(unittest.TestCase):
    def test_prod_date_persists_over_sqlite_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"investment.sqlite3"
            self.assertEqual(settings.load_dca_target_date("production",db),
                             (None,None))
            self.assertEqual(settings.save_dca_target_date(
                "production","2026-12-31",db),(True,None))
            self.assertEqual(settings.load_dca_target_date(
                "production",db),("2026-12-31",None))
            self.assertEqual(settings.save_dca_target_date(
                "production",dt.date(2027,1,10),db),(True,None))
            self.assertEqual(settings.load_dca_target_date(
                "production",db),("2027-01-10",None))

    def test_research_independent_and_real_portfolio_rows_unaffected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"investment.sqlite3"
            ledger={
                "rows":[{"Asset":"ASX:IBIT","Date":"2026-10-12",
                         "Units / BTC Received":1982.}],
                "sales":[{"Asset":"ASX:IBIT","Date":"2026-10-18",
                          "Units Sold":15.}],
                "starting_capital_aud":500000.,
                "capital_remaining_aud":335628.,
            }
            self.assertEqual(save_portfolio(ledger,db),(True,None))
            self.assertEqual(settings.save_dca_target_date(
                "production",dt.date(2026,12,31),db),(True,None))
            self.assertEqual(settings.save_dca_target_date(
                "research",dt.date(2027,3,31),db),(True,None))
            self.assertEqual(settings.load_dca_target_date(
                "research",db),("2027-03-31",None))
            self.assertEqual(settings.load_dca_target_date(
                "production",db),("2026-12-31",None))
            self.assertEqual(load_portfolio(db),(ledger,None))
            self.assertEqual(settings.save_dca_target_date(
                "production",dt.date(2027,12,1),db),(True,None))
            self.assertEqual(load_portfolio(db),(ledger,None))
            self.assertEqual(settings.load_dca_target_date(
                "research",db),("2027-03-31",None))

    def test_google_sheet_uses_isolated_settings_rows_not_shared(self):
        worksheet=FakeWorksheet()
        unchanged=worksheet.records[0].copy()
        with patch.object(settings._store,"_use_sqlite",return_value=False),(
             patch.object(settings._store,"_google_worksheet",
                          return_value=worksheet)):
            self.assertEqual(settings.load_dca_target_date(
                "production"),(None,None))
            self.assertEqual(settings.save_dca_target_date(
                "production",dt.date(2026,12,31)),(True,None))
            self.assertEqual(settings.save_dca_target_date(
                "research",dt.date(2027,4,15)),(True,None))
            self.assertEqual(settings.save_dca_target_date(
                "production",dt.date(2026,11,30)),(True,None))
            self.assertEqual(settings.load_dca_target_date(
                "production"),("2026-11-30",None))
            self.assertEqual(settings.load_dca_target_date(
                "research"),("2027-04-15",None))
            self.assertEqual(len(worksheet.records),3)
            self.assertEqual(worksheet.records[0],unchanged)
            self.assertEqual({r["portfolio_key"] for r in worksheet.records},{
                "shared","setting:production_dca_today_target_date",
                "setting:research_strategy_review_target_date"})

    def test_loaded_server_preferred_to_stale_browser_fallback(self):
        value,existing=settings.choose_target_date(
            server_date="2026-12-31",
            browser_date="2029-10-18",
            default_date=DEFAULT,min_date=MIN)
        self.assertEqual(value,dt.date(2026,12,31))
        self.assertTrue(existing)

    def test_existing_browser_date_migrates_when_backend_empty(self):
        date,chosen=settings.choose_target_date(
            server_date=None,browser_date="2027-02-08",
            default_date=DEFAULT,min_date=MIN)
        self.assertEqual(date,dt.date(2027,2,8))
        self.assertTrue(chosen)

    def test_no_prior_choice_does_not_claim_generated_default_user_selection(self):
        date,chosen=settings.choose_target_date(
            server_date=None,browser_date=None,
            default_date=DEFAULT,min_date=MIN)
        self.assertEqual(date,DEFAULT)
        self.assertFalse(chosen)

    def test_expired_user_selection_does_not_reset_three_years(self):
        date,chosen=settings.choose_target_date(
            server_date="2026-10-25",browser_date="2029-10-18",
            default_date=DEFAULT,min_date=MIN)
        self.assertEqual(date,MIN)
        self.assertTrue(chosen)

    def test_bad_date_records_and_unknown_models_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"budget.sqlite3"
            self.assertFalse(settings.save_dca_target_date(
                "production","not-a-date",db)[0])
            self.assertFalse(settings.save_dca_target_date(
                "bad_model","2026-12-31",db)[0])
            self.assertEqual(settings.load_dca_target_date(
                "bad_model",db)[0],None)
            self.assertFalse(settings.save_dca_target_date(
                "production",dt.datetime.now(),db)[0])

    def test_failed_google_write_is_reported_not_fake_success(self):
        sheet=FakeWorksheet()
        with patch.object(settings._store,"_use_sqlite",return_value=False):
            with patch.object(settings._store,"_google_worksheet",
                              side_effect=RuntimeError("permission denied")):
                self.assertEqual(settings.load_dca_target_date("production"),
                                 (None,"RuntimeError: permission denied"))
                ok,error=settings.save_dca_target_date(
                    "production",dt.date(2026,12,31))
                self.assertFalse(ok)
                self.assertIn("permission denied",error)
        self.assertEqual(len(sheet.records),1)

    def test_both_streamlit_widgets_persist_unique_settings(self):
        root=Path(__file__).resolve().parents[1]
        prod=(root/"engines/production/production_app.py").read_text()
        research=(root/"engines/research/research_app.py").read_text()
        self.assertIn('key="production_today_target_date"',prod)
        self.assertIn('key="research_today_target_date"',research)
        self.assertIn('load_dca_target_date("production")',prod)
        self.assertIn('load_dca_target_date("research")',research)
        self.assertIn('save_dca_target_date(\n                "production"',prod)
        self.assertIn('save_dca_target_date(\n                "research"',research)
        # Keep original risk formula, and do not begin automatically
        # saving default date just because no preference exists.
        for app in (prod,research):
            self.assertIn("if (has_user_target or target_deployment_date != default_target)",app)
            self.assertIn('dt.timedelta(days=7)',app)
            self.assertIn('_save_browser_state(browser_state)',app)


if __name__=="__main__":
    unittest.main()
