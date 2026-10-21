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

    def test_actual_cycle_launcher_missing_portfolio_still_shows_market_hold_and_refresh(self):
        history,fx=frozen_synthetic_history()
        counts={"public":0,"portfolio":0}
        # Capture the ACTUAL buy style passed by the real Streamlit
        # launcher to the unchanged allocation engine. Captions are
        # stored differently by Streamlit versions, so don't infer
        # recommendation parity from a markdown display collection.
        from engines.research.cycle_trade_decision import (
            make_current_decision as original_decision,
        )
        seen_current_styles=[]
        def capture_decision(*args,**kwargs):
            result=original_decision(*args,**kwargs)
            seen_current_styles.append((
                kwargs.get("buy_style"),result["market_signal"],
                result["buy_pct_total_cash"],result["action_aud"],
            ))
            return result
        def public_prices(*args,**kwargs):
            counts["public"]+=1
            return history["price_usd"],fx,history["price_usd"]
        def portfolio():
            counts["portfolio"]+=1
            return {}, "Simulated offline Google Sheets connection; no account access"
        health={"verified":True}
        def verified_merge(*args,**kwargs):
            return history["price_usd"],{
                "strict_close_date_verified":health["verified"],
                "overlap_days":5,"max_overlap_difference_pct":0.02,
            }
        def quote(*args,**kwargs):
            now=dt.datetime.now(dt.timezone.utc)
            return {
                "symbol":"ASX:IBIT","price_aud":22.30,
                "provider":"SYNTHETIC UNITTEST ONLY",
                "timestamp_utc":now.isoformat(),
                "age_hours":0.0,
            }
        with ExitStack() as stack:
            patches=[
                ("engines.research.top_signal_horse_race.read_exported_history",
                 lambda:history),
                ("engines.research.cycle_live_completed_utc_prices.fetch_cycle_live_sources",
                 public_prices),
                ("engines.research.cycle_live_completed_utc_prices.merge_verified_live_cycle_prices",
                 verified_merge),
                ("engines.shared.portfolio_store.load_portfolio",portfolio),
                ("engines.research.cycle_trade_decision.make_current_decision",
                 capture_decision),
                ("engines.shared.portfolio_store.save_portfolio",
                 lambda *a,**k:(_ for _ in ()).throw(AssertionError(
                     "Smoke test must never write user portfolio"))),
                ("engines.research.ibit_quote.fetch_ibit_quote",quote),
                ("engines.research.cycle_halving_countdown.fetch_halving_countdown",
                 lambda *a,**k:fake_halving()),
                ("engines.research.day500_aftertax_reinvestment.fetch_fx_for_cycle",
                 lambda *a,**k:fx),
                ("engines.research.cycle_model_redflags.fetch_reference_model_risks",
                 lambda *a,**k:{}),
            ]
            for target,replacement in patches:
                stack.enter_context(patch(target,replacement))
            stack.enter_context(patch.dict(os.environ,{
                "BTC_PORTFOLIO_BACKEND":"sqlite",
                "BTC_PORTFOLIO_DB_PATH":"/tmp/btc_streamlit_smoke_must_not_touch.sqlite3",
            }))
            st.cache_data.clear()
            page=AppTest.from_file(str(APP),default_timeout=35).run()
            self.assertFalse(page.exception,repr([x.message for x in page.exception]))
            widgets=[(x.label,str(x.value)) for x in page.metric]
            self.assertIn(("Current research market signal","HOLD"),widgets)
            self.assertIn(("Spendable trade amount","Not verified"),widgets)
            self.assertFalse(any(
                x.key=="cycle_decision_buy_style" for x in page.selectbox
            ),"Current live panel must not provide different BUY % than ntfy")
            self.assertTrue(any(
                x.key=="cycle_research_buyer" for x in page.selectbox
            ),"Existing historical research alternatives remain accessible")
            self.assertTrue(any(x.label=="Recorded portfolio" and x.value=="Unavailable"
                                for x in page.metric))
            self.assertTrue(any(b.key=="cycle_research_refresh" for b in page.button))
            previous=counts.copy()
            refresh=next(b for b in page.button if b.key=="cycle_research_refresh")
            page=refresh.click().run()
            self.assertFalse(page.exception,repr([x.message for x in page.exception]))
            self.assertGreater(counts["portfolio"],previous["portfolio"])
            self.assertGreater(counts["public"],previous["public"])
            self.assertIn(("Current research market signal","HOLD"),
                          [(x.label,str(x.value)) for x in page.metric])
            self.assertFalse(any("Verified BUY research budget"==x.label
                                 or "Verified SELL research units"==x.label
                                 for x in page.metric))
            # Reuse the SAME actual launcher, not a simulated helper page:
            # a new verified price discount should change MARKET WATCH,
            # but NO holdings/cash means absolutely no executable BUY.
            history["price_usd"].iloc[-35:]=30000.0
            # A saved old browser session value selecting the RESEARCH
            # 10% value-weighted style cannot override current ntfy's
            # only approved 2.5%-remaining-cash market sizing.
            page.session_state["cycle_decision_buy_style"]="adaptive_value"
            page=next(b for b in page.button
                      if b.key=="cycle_research_refresh").click().run()
            self.assertFalse(page.exception,repr([x.message for x in page.exception]))
            self.assertIn(("Current research market signal","BUY WATCH"),
                          [(x.label,str(x.value)) for x in page.metric])
            self.assertTrue(seen_current_styles)
            self.assertEqual(
                seen_current_styles[-1],
                ("adaptive_recovery","BUY WATCH",2.5,0.),
                "Stale adaptive_value browser key cannot change the REAL current BUY %",
            )
            self.assertIn(("Spendable trade amount","Not verified"),
                          [(x.label,str(x.value)) for x in page.metric])
            self.assertFalse(any(x.label=="Verified BUY research budget"
                                 for x in page.metric))
            # If independent public-close verification fails, a new
            # BUY WATCH must immediately become UNAVAILABLE, not be
            # cached as a fresh tradeable market recommendation.
            health["verified"]=False
            page=next(b for b in page.button
                      if b.key=="cycle_research_refresh").click().run()
            self.assertFalse(page.exception,repr([x.message for x in page.exception]))
            self.assertIn(("Current research market signal","UNAVAILABLE"),
                          [(x.label,str(x.value)) for x in page.metric])
            self.assertFalse(any(x.label=="Verified BUY research budget"
                                 for x in page.metric))

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
