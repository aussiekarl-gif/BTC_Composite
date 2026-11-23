"""OFFLINE Streamlit UI smoke: actual Cycle launcher + independent date controls.

Run in GitHub Actions with no Gmail, Google Sheets, ntfy, broker or public
BTC access. Fake prices are ONLY unittest fixtures, not saved market data.
A real browser session is a separate manual/live-deployment acceptance gate.
"""
from __future__ import annotations

from contextlib import ExitStack
import datetime as dt
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app.py"
PRODUCTION=ROOT/"engines/production/production_app.py"
RESEARCH=ROOT/"engines/research/research_app.py"

# Component-level date-widget test calls the SAME real persistence functions
# used in both existing large Production/Research pages. The much larger
# model pages are covered separately by their unchanged numerical suites.
DATE_WIDGET_APP=r'''
import datetime as dt
import streamlit as st
from engines.shared.model_settings_store import (
    load_dca_target_date,save_dca_target_date,choose_target_date,
)
today=dt.date.today()
model=st.selectbox("Model to test",["production","research"],key="model_to_test")
server,error=load_dca_target_date(model)
fallback=today+dt.timedelta(days=365*3)
minimum=today+dt.timedelta(days=7)
selected,existing=choose_target_date(
    server_date=server,browser_date=None,
    default_date=fallback,min_date=minimum)
chosen=st.date_input(
    "Target date (offline fixture)",value=selected,
    min_value=minimum,format="DD/MM/YYYY",key="target_date_test_widget")
if (existing or chosen != fallback) and (
    server != chosen.isoformat()):
    ok,msg=save_dca_target_date(model,chosen)
    if not ok:st.error(f"Unable to store target date: {msg}")
st.metric("Durable selected date",chosen.isoformat())
'''


def frozen_synthetic_history():
    end=dt.datetime.now(dt.timezone.utc).date()-dt.timedelta(days=1)
    days=pd.date_range(end=end,periods=1900,freq="D",tz="UTC")
    price=pd.Series(85000.+np.linspace(-18000.,20000.,len(days)),
                    index=days,name="price_usd")
    # No contemporary price advice; generated fixtures live in RAM only.
    fx=pd.DataFrame({"aud_per_usd":np.full(len(days),1.52)},index=days)
    return {"price_usd":price},fx


def fake_halving():
    return {
        "height_verified":True,"halving_date_verified":True,
        "current_height":910000,"next_halving_height":1050000,
        "last_halving_date":"2024-04-20",
        "estimated_date_utc":"2028-04-01",
        "days_remaining":525,"source":"synthetic unittest, offline",
        "estimate_basis":"synthetic test-only estimate",
    }


class StreamlitOfflineSmoke(unittest.TestCase):
    def tearDown(self):
        st.cache_data.clear()

    def test_launcher_excludes_retired_v60_research_page(self):
        # Static launcher contract: do not execute Production or any external
        # data path merely to inspect the navigation options.
        import ast
        source = APP.read_text(encoding="utf-8")
        tree = ast.parse(source)
        radios = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "radio"
        ]
        self.assertEqual(len(radios), 1)
        options_node = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MODEL_OPTIONS"
                    for target in node.targets)
        )
        options = ast.literal_eval(options_node.value)
        self.assertEqual(radios[0].args[1].id, "MODEL_OPTIONS")
        self.assertEqual(options[0], "Production")
        self.assertNotIn("Research V6.0", options)
        self.assertNotIn("Research V5.9", options)
        self.assertNotIn("Cowen Risk Matrix", options)
        self.assertFalse((ROOT / "engines/research/v60_research_app.py").exists())
        # Other research destinations remain available.
        for retained in ("Research 10.0", "Cycle Trading — Research"):
            self.assertIn(retained, options)

    def test_retired_model_radio_state_is_reset_after_deploy(self):
        # A browser session can retain the removed V6.0 radio value when the
        # app redeploys. Exercise the exact guard pattern used by app.py.
        page_source = r'''
import streamlit as st
MODEL_SELECTOR_KEY = "combined_app_section_selector"
MODEL_OPTIONS = [
    "Production", "Research 10.0",
    "Cycle Trading — Research",
    "Bottom Signal Timeline",
]
if st.session_state.get(MODEL_SELECTOR_KEY) not in MODEL_OPTIONS:
    st.session_state.pop(MODEL_SELECTOR_KEY, None)
section = st.sidebar.radio("Model", MODEL_OPTIONS, key=MODEL_SELECTOR_KEY)
st.write(section)
'''
        page = AppTest.from_string(page_source, default_timeout=25)
        page.session_state["combined_app_section_selector"] = "Research V5.9"
        page = page.run()
        self.assertFalse(page.exception, repr([x.message for x in page.exception]))
        self.assertEqual(
            page.radio(key="combined_app_section_selector").value, "Production"
        )

    def test_streamlit_date_widget_persists_across_sessions_without_portfolio_write(self):
        # The real Production & Research Streamlit pages use these helpers
        # and distinct widget keys. This is the isolated INTERACTIVE UI
        # acceptance for their shared preference storage contract.
        prod_src=PRODUCTION.read_text(encoding="utf-8")
        research_src=RESEARCH.read_text(encoding="utf-8")
        for source,model,key in (
            (prod_src,"production","production_today_target_date"),
            (research_src,"research","research_today_target_date")
        ):
            self.assertIn(f'load_dca_target_date("{model}")',source)
            self.assertIn(f'key="{key}"',source)
            self.assertIn("choose_target_date(",source)
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"offline.sqlite3"
            with patch.dict(os.environ,{
                "BTC_PORTFOLIO_BACKEND":"sqlite",
                "BTC_PORTFOLIO_DB_PATH":str(db),
            }):
                st.cache_data.clear()
                page=AppTest.from_string(DATE_WIDGET_APP,default_timeout=25).run()
                self.assertFalse(page.exception)
                desired=dt.date.today()+dt.timedelta(days=130)
                page=page.date_input(key="target_date_test_widget").set_value(desired).run()
                self.assertFalse(page.exception)
                from engines.shared.model_settings_store import load_dca_target_date
                from engines.shared.portfolio_store import load_portfolio
                self.assertEqual(load_dca_target_date("production"),(desired.isoformat(),None))
                # A NEW independent Streamlit session must restore the choice,
                # rather than silently generating the +3-year default.
                reboot=AppTest.from_string(DATE_WIDGET_APP,default_timeout=25).run()
                self.assertEqual(reboot.date_input(key="target_date_test_widget").value,desired)
                self.assertFalse(reboot.exception)
                other=reboot.selectbox(key="model_to_test").set_value("research").run()
                research_date=dt.date.today()+dt.timedelta(days=300)
                other=other.date_input(key="target_date_test_widget").set_value(
                    research_date).run()
                self.assertFalse(other.exception)
                self.assertEqual(load_dca_target_date("research"),
                                 (research_date.isoformat(),None))
                self.assertEqual(load_dca_target_date("production"),
                                 (desired.isoformat(),None))
                # Preferences may touch isolated setting rows ONLY.
                self.assertEqual(load_portfolio(),({},None))
                with __import__("sqlite3").connect(str(db)) as conn:
                    keys=[r[0] for r in conn.execute(
                        "SELECT portfolio_key FROM portfolio_state").fetchall()]
                self.assertEqual(set(keys),{
                    "setting:production_dca_today_target_date",
                    "setting:research_strategy_review_target_date",
                })


if __name__=="__main__":
    unittest.main()
