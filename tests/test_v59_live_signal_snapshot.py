"""Live-source provenance gate: synthetic acceptance, no network or portfolio access."""
from datetime import datetime, timezone
import unittest
import pandas as pd

from engines.research.v59_live_signal_snapshot import snapshot_from_scored, live_risk_params

NOW = datetime(2026, 11, 11, 10, 45, tzinfo=timezone.utc)


def frame(stamp, *, risk=.06, label="Walk-forward Power Law", price=75_000, fx=.69):
    return pd.DataFrame(
        {"price": [price], "risk_score": [risk],
         "risk_score_source": [label], "usd_per_aud": [fx],
         "continuous_valuation_risk": [.075]},
        index=pd.DatetimeIndex([stamp], tz="UTC"),
    )


def snap(data, fx_date="2026-11-10"):
    return snapshot_from_scored(data, now_utc=NOW, params=live_risk_params(), fx_latest_date=fx_date)


class ProspectiveRiskCaptureAcceptance(unittest.TestCase):
    def test_valid_closed_score_has_3x_but_not_live_order_approval(self):
        s = snap(frame("2026-11-10"))
        self.assertEqual(s["status"], "RESEARCH_SIGNAL_SNAPSHOT_READY")
        self.assertEqual(s["r2_sizing_risk"], .06)
        self.assertEqual(s["continuous_valuation_risk"], .075)
        self.assertEqual(s["research_aggressive_risk_band_multiplier"], 3.)
        self.assertFalse(s["ready_for_live_aggressive_orders"])
        self.assertFalse(s["personal_portfolio_loaded"])

    def test_full_streamlit_params_include_datetime_and_fingerprint_is_stable(self):
        """The DCA Today UI passes aware start/end datetimes, not JSON strings."""
        params = live_risk_params()
        params["start_date"] = datetime(2015, 11, 14, tzinfo=timezone.utc)
        params["end_date"] = datetime(2026, 11, 11, tzinfo=timezone.utc)
        snapshot = snapshot_from_scored(frame("2026-11-10"), now_utc=NOW,
                                        params=params, fx_latest_date="2026-11-10")
        replay = snapshot_from_scored(frame("2026-11-10"), now_utc=NOW,
                                      params=params, fx_latest_date="2026-11-10")
        self.assertEqual(snapshot["status"], "RESEARCH_SIGNAL_SNAPSHOT_READY")
        self.assertEqual(snapshot["fingerprint"], replay["fingerprint"])
        self.assertEqual(snapshot["research_aggressive_risk_band_multiplier"], 3.)

    def test_daily_future_row_never_replaces_latest_closed(self):
        a = frame("2026-11-10", risk=.4)
        b = frame("2026-11-11", risk=0.)
        s = snap(pd.concat([a, b]))
        self.assertEqual(s["r2_sizing_risk"], .4)
        self.assertEqual(s["research_aggressive_risk_band_multiplier"], 1.5)

    def test_neutral_fallback_not_treated_as_valid_trade_signal(self):
        s = snap(frame("2026-11-10", label="Neutral fallback", risk=.5))
        self.assertFalse(s["risk_signal_ready"])
        self.assertIsNone(s["research_aggressive_risk_band_multiplier"])
        self.assertIn("R2_SCORE_NOT_ACTUAL_WALK_FORWARD_FIT", s["issues"])

    def test_missing_latest_closed_score_blocks_instead_of_using_older_row(self):
        a = frame("2026-11-09", risk=.02)
        b = frame("2026-11-10", risk=float("nan"))
        s = snap(pd.concat([a, b]))
        self.assertFalse(s["risk_signal_ready"])
        self.assertIsNone(s["research_aggressive_risk_band_multiplier"])

    def test_stale_risk_or_fx_blocks_market_readiness(self):
        self.assertFalse(snap(frame("2026-11-01"))["risk_signal_ready"])
        self.assertFalse(snap(frame("2026-11-10"), fx_date="2026-10-01")["risk_and_fx_fresh"])

    def test_future_only_and_naive_clock_refused(self):
        with self.assertRaises(ValueError):
            snap(frame("2026-11-11"))
        with self.assertRaises(ValueError):
            snapshot_from_scored(frame("2026-11-10"),
                 now_utc=datetime(2026,11,11), params=live_risk_params())

    def test_risk_above_half_gives_no_buy_even_on_valid_snapshot(self):
        s = snap(frame("2026-11-10", risk=.501))
        self.assertEqual(s["research_aggressive_risk_band_multiplier"], 0.)


    def test_fx_fixing_must_be_no_later_than_closed_btc_day(self):
        from engines.research.v59_live_signal_snapshot import (
            last_fx_fixing_on_or_before_closed_btc,
        )
        closed = pd.DataFrame(
            {"price":[70000.,71000.]},
            index=pd.to_datetime(["2026-11-10","2026-11-11"],utc=True),
        )
        fx = pd.Series(
            [.70,.71,.72],
            index=pd.to_datetime(["2026-11-10","2026-11-11","2026-11-12"],
                                  utc=True),
        )
        selected = last_fx_fixing_on_or_before_closed_btc(
            closed,fx,datetime(2026,11,12,21,tzinfo=timezone.utc))
        self.assertEqual(selected.date().isoformat(),"2026-11-11")
        self.assertNotEqual(selected.date().isoformat(),"2026-11-12")


if __name__ == "__main__":
    unittest.main()
