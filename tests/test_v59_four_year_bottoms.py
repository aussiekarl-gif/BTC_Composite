"""Tests for four-year cycle classification and deliberate hindsight separation."""
from datetime import date,timedelta
import unittest

from engines.research import v59_four_year_bottoms as audit


def rows():
    start=date(2017,12,18)
    out=[]
    for i in range(410):
        d=start+timedelta(weeks=i)
        ratio=1.35
        if d in (date(2018,12,17),date(2022,6,20)):
            ratio=1.03
        if d==date(2020,3,16):
            ratio=.90
        out.append({
            "date":d,"signal_date":d-timedelta(days=1),
            "ratio_to_200wma":ratio,"risk_score":.05,
            "risk_score_source":"Walk-forward Power Law",
            "btc_price_aud":10000*(1+i/410),
            "drawdown_365":-.30,
            "ratio_to_50dma":1.05,
            "sma50_rising":True,
        })
    return out


class CycleBottomTests(unittest.TestCase):
    def test_major_pivots_are_separated_from_covid_shock(self):
        self.assertEqual([c["id"] for c in audit.CYCLES],
                         ["2014_15","2018","2022","2026"])
        self.assertNotIn("2020", [c["id"] for c in audit.CYCLES])
        self.assertIsNone(audit.CYCLES[-1]["retrospective_bottom"])

    def test_first_near_causal_crossing_belongs_to_only_one_major_cycle(self):
        r=rows()
        signals=[audit._causal_prior_peak_signal(r,c)
                 for c in audit.CYCLES[1:3]]
        self.assertEqual([x["first_buy_monday"] for x in signals],
                         ["2018-12-17","2022-06-20"])
        # Ex post Nov 2022 low cannot retroactively replace June 2022 entry.
        self.assertLess(signals[1]["first_buy_monday"],"2022-11-09")

    def test_bottom_oracle_is_noncausal_and_has_fixed_start(self):
        r=audit.evaluate(rows())
        self.assertEqual(r["cycle_count_complete"],2)
        self.assertTrue(r["2020_covid_is_stress_event_not_new_four_year_cycle"])
        self.assertTrue(r["2026_bottom_unconfirmed_and_right_censored"])
        self.assertTrue(r["2015_cycle_not_simulated_with_fabricated_research_R2"])
        c18,c22=r["cycles"][1:3]
        self.assertEqual(c18["oracle_hindsight_bottom_first_monday"],"2018-12-17")
        self.assertEqual(c22["oracle_hindsight_bottom_first_monday"],"2022-11-14")
        self.assertEqual(c22["signal_days_relative_to_hindsight_bottom"],-143)
        self.assertEqual(c18["near_signal_cohort"]["anchor_monday"],"2018-12-17")
        self.assertEqual(c22["hindsight_oracle_cohort"]["anchor_monday"],"2022-11-14")
        self.assertTrue(c22["oracle_hindsight_not_tradeable"])

    def test_shock_price_cannot_invent_new_four_year_cycle(self):
        r=rows()
        out=audit.evaluate(r)
        start=list(x["cycle_id"] for x in out["cycles"])
        price_change=[dict(x) for x in r]
        for x in price_change:
            if x["date"]==date(2020,3,16):
                x["btc_price_aud"]=100.
        comparison=audit.evaluate(price_change)
        self.assertEqual(start,[x["cycle_id"] for x in comparison["cycles"]])
        self.assertEqual(comparison["cycle_count_complete"],2)

    def test_no_fabricated_incomplete_104_week_history(self):
        truncated=[x for x in rows() if x["date"]<=date(2023,1,1)]
        result=audit.evaluate(truncated)
        self.assertEqual(result["cycle_count_complete"],1)
        self.assertIsNone(result["cycles"][2]["hindsight_oracle_cohort"])


if __name__=="__main__":
    unittest.main()
