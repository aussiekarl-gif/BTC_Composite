"""Research-only ASX postclose observational report on actually published sources.

The stable 2026-10-22 -> 2026-10-23 record validates the first genuinely
captured next-session price, with no fill, alpha claim or BUY/SELL.
The same GitHub cron is used; never add an alert or a second scheduling job.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
import unittest

from engines.research.cycle_mid_session_asx_timing_audit import report

ROOT=Path(__file__).resolve().parents[1]
WF=ROOT/".github/workflows/research_btc_paired_microstructure.yml"
DIR=ROOT/"data/research_forward_validation"


class AfterCloseReportingTests(unittest.TestCase):
    def test_actual_immutable_forward_tapes_have_first_completed_close_comparison(self):
        m=(DIR/"cycle_mid_session_market_watch.csv").read_text(encoding="utf-8")
        a=(DIR/"asx_ibit_closes_forward.csv").read_text(encoding="utf-8")
        r=report(m,a,as_of_utc=dt.datetime.now(dt.timezone.utc))
        self.assertGreaterEqual(r["verified_mid_session_events_in_tape"],2)
        self.assertGreaterEqual(r["verified_asx_indicative_closes_in_tape"],4)
        self.assertGreaterEqual(r["paired_same_and_next_actual_ASX_closes"],1)
        rec=next(x for x in r["observations"]
                 if x["research_sydney_date"]=="2026-10-22")
        self.assertEqual(rec["market_watch"],"HOLD")
        self.assertEqual(rec["outcome_status"],"OBSERVED_CLOSE_TO_CLOSE_NOT_EXECUTABLE")
        self.assertEqual(rec["next_real_recorded_session_date"],"2026-10-23")
        self.assertEqual(rec["same_session_asx_indicative_close_aud"],22.389999)
        self.assertEqual(rec["following_session_asx_indicative_close_aud"],22.120001)
        self.assertAlmostEqual(rec["same_vs_next_close_pct"],-1.205887,places=5)
        self.assertIsNone(rec["directional_cost_of_waiting_next_close_pct"])
        self.assertFalse(r["closing_price_trade_fills_demonstrated"])
        self.assertFalse(r["new_strategy_outperformance_or_better_execution_proven"])
        self.assertFalse(r["minimum_30_non_hold_events_met"])
        self.assertEqual(r["paired_non_hold_events"],0)

    def test_postclose_report_is_after_verified_asx_publisher_and_before_artifact_upload(self):
        text=WF.read_text(encoding="utf-8")
        self.assertEqual(text.count("cron:"),1)
        a=text.index("name: Best-effort strictly POSTCLOSE Sydney ASX:IBIT")
        reportpos=text.index("name: Read-only matching of TWO remotely published BTC and ASX research tapes")
        artifact=text.index("name: Save research-only ASX capture attempt diagnostics")
        self.assertLess(a,reportpos)
        self.assertLess(reportpos,artifact)
        snippet=text[reportpos:artifact]
        self.assertIn("git fetch origin main",snippet)
        self.assertIn('git show "origin/main:data/research_forward_validation/$name"',snippet)
        self.assertIn("cycle_mid_session_market_watch.csv asx_ibit_closes_forward.csv",snippet)
        self.assertLess(snippet.index("git fetch origin main"),
                        snippet.index("cycle_mid_session_asx_timing_audit"))
        self.assertIn("capture_status.json",snippet)
        self.assertIn("r.get('status')=='captured'",snippet)
        self.assertIn("r.get('wrote_close') is True",snippet)
        self.assertIn("source.get('observation_date_sydney')",snippet)
        self.assertIn("market_session_date_sydney",snippet)
        self.assertIn("is_confirmed_broker_fill",snippet)
        self.assertIn("published_mid_session_following_asx_timing.json",snippet)

    def test_report_never_changes_market_tapes_or_sends_notification(self):
        text=WF.read_text(encoding="utf-8")
        reportpos=text.index("name: Read-only matching of TWO remotely published BTC and ASX research tapes")
        artifact=text.index("name: Save research-only ASX capture attempt diagnostics")
        snippet=text[reportpos:artifact]
        self.assertNotIn("git commit",snippet)
        self.assertNotIn("git add",snippet)
        self.assertNotIn("git push",snippet)
        self.assertNotIn("ntfy.sh",snippet)
        self.assertNotIn("cycle_trading_daily_ntfy",snippet)
        self.assertIn("artifacts/asx_ibit_postclose_paired",snippet)
        self.assertIn("github.event_name == 'schedule'",snippet)


if __name__=="__main__":
    unittest.main()
