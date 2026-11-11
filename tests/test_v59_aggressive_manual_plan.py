"""Deterministic broker-cash and manual IBIT quantity safety tests."""
import copy
from datetime import datetime, timedelta, timezone, date
import unittest
from engines.research.v59_aggressive_manual_plan import (
    manual_ibit_plan, broker_fields_fingerprint,
)

NOW = datetime(2026,11,9,1,0,tzinfo=timezone.utc) # noon Sydney, Monday
PORTFOLIO = {"starting_capital_aud":500000.0, "rows":[], "sales":[]}
RISK = {
    "risk_and_fx_fresh": True, "risk_signal_ready": True,
    "risk_score_source": "Walk-forward Power Law", "r2_sizing_risk": 0.0,
    "ready_for_live_aggressive_orders": False,
    "closed_risk_observation_utc": "2026-11-08T00:00:00+00:00",
    "closed_risk_age_days": 1,
    "captured_at_utc": NOW.isoformat(),
    "fx_observation_date_utc": "2026-11-06",
    "status": "RESEARCH_SIGNAL_SNAPSHOT_READY",
    "risk_model": "Research WF Power Law",
}


def plan(ledger=None, risk=None, cash=500000, units=0, ask=20, reserve=0,
         verified_at=NOW, attested=True, now=NOW):
    ledger = copy.deepcopy(PORTFOLIO if ledger is None else ledger)
    risk = copy.deepcopy(RISK if risk is None else risk)
    review = date(2027,12,31)
    expected = broker_fields_fingerprint(
        ledger=ledger, cash=cash, ibit_units=units, ibit_ask=ask,
        brokerage_fee=3., protected_aud=reserve, target=review,
    ) if attested else None
    return manual_ibit_plan(
        saved_portfolio=ledger, risk_snapshot=risk, now_utc=now,
        verified_at_utc=verified_at, broker_cash_aud=cash,
        broker_ibit_units=units, broker_ask_aud=ask,
        protected_cash_aud=reserve, review_date=review,
        brokerage_fee_aud=3.0, expected_fields_hash=expected,
    )


class ManualAggressivePlanTests(unittest.TestCase):
    def test_risk_zero_is_3x_with_5pct_original_cap(self):
        p = plan()
        self.assertTrue(p["ready"], p["blockers"])
        self.assertEqual(p["multiplier"], 3.0)
        self.assertEqual(p["weekly_cap_aud"], 25000)
        self.assertEqual(p["proposed_max_spend_aud"], 25000)
        self.assertEqual(p["indicative_whole_ibit_units"], 1249)
        self.assertLessEqual(p["indicative_order_total_inc_fee_aud"], p["proposed_max_spend_aud"])
        self.assertFalse(p["order_sent"])

    def test_no_buy_above_point_five(self):
        risk = dict(RISK, r2_sizing_risk=.500001)
        p = plan(risk=risk)
        self.assertFalse(p["ready"])
        self.assertIn("RISK_ABOVE_0_50_NO_BUY", p["blockers"])
        self.assertIsNone(p["proposed_max_spend_aud"])

    def test_cash_reserve_and_broker_cash_reduce_allowance(self):
        p = plan(cash=8000, reserve=2000)
        self.assertTrue(p["ready"])
        self.assertLess(p["proposed_max_spend_aud"], 6000)
        self.assertEqual(p["spendable_aud"], 6000)

    def test_missing_or_unconfirmed_reconciled_ledger_fails_closed(self):
        self.assertFalse(plan(ledger={"rows":[]})["ready"])
        self.assertIn("BROKER_CONFIRMATION_DOES_NOT_MATCH_CURRENT_FIELDS",
                      plan(attested=False)["blockers"])
        self.assertIn("BROKER_IBIT_UNITS_DISAGREE_WITH_SAVED_LEDGER",
                      plan(units=1)["blockers"])

    def test_stale_or_missing_risk_and_broker_confirmation_blocks(self):
        self.assertIn("STAKE_BROKER_FIELDS_NOT_RECENTLY_CONFIRMED",
                      plan(verified_at=NOW - timedelta(minutes=16))["blockers"])
        r = dict(RISK, risk_and_fx_fresh=False)
        self.assertIn("RISK_AND_AUD_FX_NOT_VERIFIED_FRESH", plan(risk=r)["blockers"])
        r = dict(RISK, risk_score_source="Neutral fallback", r2_sizing_risk=0)
        self.assertIn("RISK_IS_NOT_ACTUAL_V59_MODEL", plan(risk=r)["blockers"])

    def test_normal_exchange_session_only(self):
        self.assertIn("ASX_MARKET_NOT_IN_NORMAL_DAY_SESSION",
                      plan(now=NOW+timedelta(hours=7))["blockers"])
        self.assertIn("ASX_MARKET_NOT_IN_NORMAL_DAY_SESSION",
                      plan(now=NOW+timedelta(days=5))["blockers"])

    def test_existing_monday_buy_prevents_duplicate_allocation(self):
        ledger = copy.deepcopy(PORTFOLIO)
        ledger["rows"] = [{
            "Date": "09/11/2026", "Asset": "ASX:IBIT",
            "Units / BTC Received": 10, "AUD Spent": 200,
            "Brokerage / Fee AUD": 3, "BTC AUD Price": 100_000,
        }]
        p = plan(ledger=ledger, cash=499797, units=10)
        self.assertIn("BUY_ALREADY_RECORDED_THIS_WEEK", p["blockers"])
        self.assertFalse(p["ready"])

    def test_old_risk_date_cannot_reuse_a_true_freshness_flag(self):
        prior = dict(RISK, closed_risk_observation_utc="2026-10-20T00:00:00+00:00",
                     closed_risk_age_days=20)
        p = plan(risk=prior)
        self.assertFalse(p["ready"])
        self.assertIn("R2_COMPLETED_DAILY_OBSERVATION_STALE_OR_FUTURE", p["blockers"])
        self.assertIsNone(p["indicative_whole_ibit_units"])

    def test_dated_signal_and_age_must_agree(self):
        prior = dict(RISK, closed_risk_age_days=0)
        p = plan(risk=prior)
        self.assertFalse(p["ready"])
        self.assertIn("R2_OBSERVATION_DATE_AGE_MISMATCH", p["blockers"])

    def test_partial_current_utc_day_is_not_a_closed_r2_signal(self):
        risk = dict(RISK, closed_risk_observation_utc="2026-11-09T00:00:00+00:00",
                    closed_risk_age_days=0)
        p = plan(risk=risk)
        self.assertFalse(p["ready"])
        self.assertIn("R2_COMPLETED_DAILY_OBSERVATION_STALE_OR_FUTURE", p["blockers"])

    def test_cached_snapshot_without_recent_capture_is_blocked(self):
        r = dict(RISK, captured_at_utc=(NOW - timedelta(hours=2)).isoformat())
        self.assertIn("R2_SNAPSHOT_CAPTURE_NOT_RECENT", plan(risk=r)["blockers"])
        r = dict(RISK, captured_at_utc="2026-11-09T01:00:00")
        self.assertIn("R2_SNAPSHOT_CAPTURE_TIMESTAMP_UNVERIFIED", plan(risk=r)["blockers"])

    def test_status_model_and_fx_date_are_enforced(self):
        for updates, error in (
            ({"risk_model": "Composite V3.6"}, "RISK_MODEL_NOT_LIVE_V59_R2"),
            ({"status": "BLOCKED_SOURCE_OR_FRESHNESS"}, "RISK_SOURCE_ACCEPTANCE_NOT_READY"),
            ({"fx_observation_date_utc": "2026-10-30"}, "AUD_FX_OBSERVATION_DATE_STALE_OR_FUTURE"),
        ):
            with self.subTest(updates=updates):
                p = plan(risk=dict(RISK, **updates))
                self.assertFalse(p["ready"])
                self.assertIn(error, p["blockers"])

    def test_quote_larger_than_budget_no_whole_units(self):
        p = plan(ask=30000)
        self.assertIn("NO_AFFORDABLE_WHOLE_IBIT_SHARES_WITHIN_WEEKLY_BUDGET", p["blockers"])


if __name__ == "__main__":
    unittest.main()
