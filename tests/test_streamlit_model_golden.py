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

    def test_distinct_engines_not_automatically_made_identical(self):
        # This scenario exercises their common calculation path; the two
        # models may diverge for other strategies, which is *intentional*.
        self.assertEqual(self.current["production"]["allocator"],self.current["research"]["allocator"])


if __name__=="__main__":
    unittest.main()
