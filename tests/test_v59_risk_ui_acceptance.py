"""Offline acceptance of the actual V5.9 DCA Today Streamlit screen.

Test fixture values are synthetic and NEVER emitted to user portfolio/ntfy.
Confirms missing private Google portfolio does not expose a buy quantity and
the actual Research page renders the opt-in planner, not only source code.
"""
from __future__ import annotations

from contextlib import ExitStack
import datetime as dt
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "engines/research/research_app.py"


def synthetic_history():
    end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    dates = pd.date_range(end=end, periods=800, freq="D", tz="UTC")
    prices = np.linspace(70000., 75000., len(dates))
    return pd.DataFrame({"price": prices}, index=dates)


def synthetic_risk(frame, *args, **kwargs):
    out = frame.copy()
    out["risk_score"] = 0.0
    out["risk_score_source"] = "Walk-forward Power Law"
    out["power_law_score"] = 0.0
    out["continuous_valuation_risk"] = 0.05
    out["fair_value"] = out["price"] * 2
    out["power_law_residual"] = -0.30
    out["power_law_slope"] = 5.2
    out["power_law_intercept"] = -12.0
    out["weekly_ma50"] = 80000.
    out["weekly_ma200"] = 65000.
    out["weekly_bull_confirmed"] = False
    out["bull_age_weeks"] = np.nan
    out["cycle_stage"] = "BEAR / UNCONFIRMED"
    out["bottom_challenger_exceptional_zone"] = False
    out["bottom_challenger_category_votes"] = 0
    out["bottom_challenger_week_event"] = "NONE"
    out["bottom_challenger_week_multiplier"] = np.nan
    return out


class ResearchRealPageAcceptance(unittest.TestCase):
    def tearDown(self):
        st.cache_data.clear()

    def test_no_private_portfolio_still_shows_3x_as_research_only(self):
        prices = synthetic_history()
        fx = pd.Series(.69, index=prices.index)
        def no_writes(*args, **kwargs):
            raise AssertionError("Never save private portfolio or send broker order")

        with ExitStack() as stack:
            for target, replace in [
                ("engines.research.research_model.fetch_btc_history", lambda *a,**k:prices.copy()),
                ("engines.research.research_model.fetch_aud_usd_rates", lambda *a,**k:fx.copy()),
                ("engines.research.research_model.fetch_live_btc_aud", lambda *a,**k:float("nan")),
                ("engines.research.research_model.add_risk_indicators", synthetic_risk),
                ("engines.shared.portfolio_store.load_portfolio", lambda: ({}, "Offline simulated: no private portfolio")),
                ("engines.shared.portfolio_store.save_portfolio", no_writes),
                ("engines.shared.model_settings_store.load_dca_target_date", lambda *_: (None,None)),
                ("engines.shared.model_settings_store.save_dca_target_date", no_writes),
            ]:
                stack.enter_context(patch(target, replace))
            stack.enter_context(patch("engines.research.research_model.LOCAL_STORAGE_AVAILABLE",False))
            st.cache_data.clear()
            page = AppTest.from_file(str(APP), default_timeout=75).run()
            self.assertFalse(page.exception,
                             repr([x.message for x in page.exception]))
            # The live 1x and read-only 3x must remain clearly separated.
            names = [m.label for m in page.metric]
            self.assertIn("Live ordinary multiplier",names)
            self.assertIn("Aggressive research multiplier",names)
            self.assertIn("Actual V5.9 sizing risk",names)
            metrics = {m.label: str(m.value) for m in page.metric}
            self.assertEqual(metrics["Live ordinary multiplier"],"1.00×")
            self.assertEqual(metrics["Aggressive research multiplier"],"3.00×")
            self.assertFalse(any("indicative_whole_ibit_units" in str(m.value)
                                 for m in page.metric))
            # Private portfolio intentionally absent; planner explicitly blocks.
            self.assertTrue(any(
                "saved Google/Streamlit portfolio could not be verified"
                in str(w.message) for w in page.warning
            ), [str(w.message) for w in page.warning])
            self.assertFalse(any(
                "Manual IBIT plan only:" in str(s.message) for s in page.success
            ))


if __name__ == "__main__":
    unittest.main()
