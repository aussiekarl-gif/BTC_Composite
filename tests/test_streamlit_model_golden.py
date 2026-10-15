"""Frozen Streamlit model outputs: never silently alter live financial maths.

A checked-in baseline was generated ONCE from untouched Production V5.8.2
and Research V5.9 using synthetic BTC inputs. The baseline is not refreshed
automatically. It can only change as a consciously reviewed source change.
"""
import json
import math
import unittest
from pathlib import Path

from streamlit_model_golden_input import make_fixture,synthetic_btc_history,GOLDEN


def compare(test,expected,observed,path):
    if isinstance(expected,dict):
        test.assertIsInstance(observed,dict,path)
        test.assertEqual(set(expected),set(observed),path)
        for key in expected:
            compare(test,expected[key],observed[key],path+"."+key)
    elif isinstance(expected,list):
        test.assertIsInstance(observed,list,path)
        test.assertEqual(len(expected),len(observed),path)
        for i,(a,b) in enumerate(zip(expected,observed)):
            compare(test,a,b,path+f"[{i}]")
    elif isinstance(expected,float):
        test.assertIsInstance(observed,(int,float),path)
        test.assertTrue(math.isclose(expected,observed,rel_tol=1e-9,abs_tol=1e-8),
                        f"{path}: expected {expected!r}, got {observed!r}")
    else:
        test.assertEqual(expected,observed,path)


class GoldenStreamlitModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected=json.loads(GOLDEN.read_text())
        cls.current=make_fixture()

    def test_production_is_frozen(self):
        compare(self,self.expected["production"],self.current["production"],"Production V5.8.2")

    def test_research_is_frozen_independently(self):
        compare(self,self.expected["research"],self.current["research"],"Research V5.9")

    def test_research_active_wf_power_law_is_frozen(self):
        # This is the default calculation path used by research_app.py.
        expected=self.expected["research_active_power_law"]
        actual=self.current["research_active_power_law"]
        compare(self,expected,actual,"Research Streamlit WF Power Law")
        self.assertIsNone(actual["2020-07-19"]["fair_value"])
        self.assertGreater(actual["2021-04-04"]["risk_score"],0.)
        self.assertLess(actual["2021-04-04"]["risk_score"],1.)

    def test_only_expected_snapshot_versions(self):
        self.assertEqual(self.expected["schema"],"streamlit-model-golden-v1")
        self.assertEqual(self.current["schema"],self.expected["schema"])
        self.assertEqual(self.current["production_sha_policy"],"frozen Production V5.8.2")

    def test_synthetic_inputs_have_no_live_data_dependency(self):
        df=synthetic_btc_history()
        self.assertEqual(len(df),460)
        self.assertEqual(df.index[0].strftime("%Y-%m-%d"),"2020-01-01")
        self.assertTrue(df[["price","mvrv_z","fear_greed","regime_score"]].notna().all().all())
        self.assertTrue((df["price"]>0).all())

    def test_budget_conservation_both_engines(self):
        for name in ("production","research"):
            allocation=self.current[name]["allocator"]
            amounts=allocation["contributions"]
            self.assertAlmostEqual(sum(amounts),500000.,places=4)
            self.assertAlmostEqual(allocation["summary"]["total_invested_aud"],500000.,places=4)
            self.assertAlmostEqual(allocation["summary"]["fees_aud"],1000.,places=4)

    def test_shared_fx_alignment_matches_frozen_production(self):
        import pandas as pd
        from engines.production import production_model as production
        from engines.research import research_model as research
        dates=pd.date_range("2026-01-01",periods=6,freq="D",tz="UTC")
        frame=pd.DataFrame({"price":[10,11,12,13,14,15]},index=dates)
        rates=pd.Series([.65,.70],index=dates[[1,4]])
        a=production.align_fx_to_dates(frame,rates)
        b=research.align_fx_to_dates(frame,rates)
        pd.testing.assert_frame_equal(a,b,check_exact=True)
        self.assertEqual(list(b["usd_per_aud"]),[.65,.65,.65,.65,.70,.70])
        pd.testing.assert_frame_equal(frame,
            pd.DataFrame({"price":[10,11,12,13,14,15]},index=dates))
        # Missing FX preserves the original fallback without modifying source.
        missing=research.align_fx_to_dates(frame,None,fallback=.72)
        self.assertEqual(list(missing["usd_per_aud"]),[.72]*6)

    def test_risk_bucket_distribution_matches_frozen_production(self):
        import pandas as pd
        from engines.production import production_model as production
        from engines.research import research_model as research
        example=pd.Series([0.,.01,.015,.3,.8,1.,float("nan")])
        old=production.risk_occurrence_table(example)
        new=research.risk_occurrence_table(example)
        pd.testing.assert_frame_equal(old,new,check_exact=True)
        self.assertEqual(int(new["Weeks"].sum()),6)
        self.assertAlmostEqual(float(new["Percent"].sum()),100.)
        self.assertEqual(list(new.loc[new["Weeks"]>0,"Weeks"]),[1,2,1,2])

    def test_shared_allocator_empty_input_preserves_behavior(self):
        import pandas as pd
        from engines.production import production_model as production
        from engines.research import research_model as research
        zero=pd.DataFrame({"actual_buy_aud":[0.,0.],
                           "btc_price_aud":[90000.,100000.]})
        for model in (production,research):
            table,summary=model.apply_equal_capital_allocator(zero,500000.,fee_pct=.001)
            self.assertTrue(table.empty)
            self.assertEqual(summary,{})

    def test_distinct_engines_not_automatically_made_identical(self):
        # This scenario exercises their common calculation path; the two
        # models may diverge for other strategies, which is *intentional*.
        self.assertEqual(self.current["production"]["allocator"],self.current["research"]["allocator"])


if __name__=="__main__":
    unittest.main()
