"""Deterministic causal and budget parity tests of 17-week WMA episode DCA."""
from datetime import date,timedelta
import unittest

from engines.research import v59_17week_200wma_episode as study
from engines.research import v59_causal_timing_horse_race as base


def mock_rows(n=120,*,cross=1,remain_below=20,price=100000.,risk=.05):
    start=date(2018,1,1)  # Monday
    rows=[]
    for i in range(n):
        monday=start+timedelta(weeks=i)
        ratio=(1.1 if i<cross else (.85 if i<cross+remain_below else 1.08))
        rows.append({"date":monday,
                     "signal_date":monday-timedelta(days=1),
                     "btc_price_aud":price,
                     "risk_score":risk,
                     "risk_score_source":"Walk-forward Power Law",
                     "ratio_to_200wma":ratio,
                     "drawdown_365":-.4,
                     "ratio_to_50dma":1.,"sma50_rising":True})
    return rows


class SeventeenWeekWmaEpisodeTests(unittest.TestCase):
    def test_first_qualifying_crossing_prior_sunday_only(self):
        rows=mock_rows(104)
        events=study.historical_crossings(rows)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["crossing_monday"],date(2018,1,8))
        self.assertEqual(study.consecutive_weeks_below(rows,1),20)
        # A different Monday fill price CANNOT change crossing detection.
        change=[dict(x) for x in rows]
        change[1]["btc_price_aud"]=1.
        self.assertEqual(study.historical_crossings(change),events)

    def test_below_wma_streaks_measure_sunday_closes_not_calendar_crash_duration(self):
        data=mock_rows(104,cross=1,remain_below=20)
        streaks=study.observed_below_wma_streaks(data)
        self.assertEqual(len(streaks),1)
        self.assertEqual(streaks[0]["consecutive_weekly_closes_below_200wma"],20)
        self.assertEqual(streaks[0]["first_monday"],"2018-01-08")

    def test_near_5percent_threshold_may_trigger_without_being_below_wma(self):
        data=mock_rows(105,cross=1,remain_below=20)
        data[1]["ratio_to_200wma"]=1.03
        data[2]["ratio_to_200wma"]=.98
        a=study.historical_crossings(data,threshold=1.05)
        b=study.historical_crossings(data,threshold=1.)
        self.assertEqual(a[0]["crossing_monday"],date(2018,1,8))
        self.assertEqual(b[0]["crossing_monday"],date(2018,1,15))
        # Cohort starts must be distinguishable; near does not imply below.
        self.assertEqual(study.eligible_cohorts(data,threshold=1.05)[0]["start"],"2018-01-08")

    def test_500k_17week_unrestricted_exceeds_user_cap(self):
        rows=mock_rows(104,cross=0,remain_below=104)
        x=study.replay(rows,policy="17_calendar_unrestricted",capital=500000.)
        self.assertEqual(x["number_of_buys"],17)
        self.assertAlmostEqual(x["spent_aud"],500000.,places=5)
        self.assertAlmostEqual(x["biggest_weekly_buy_aud"],500000./17)
        self.assertTrue(x["original_cap_violated"])
        self.assertGreater(x["new_btc_bought_before_drag_104w"],4.9)
        self.assertLess(x["new_btc_bought_before_drag_104w"],5.)

    def test_capped_17week_leaves_uninvested_principal(self):
        rows=mock_rows(104,cross=0,remain_below=104)
        result=study.replay(rows,policy="17_calendar_capped",capital=500000.)
        self.assertEqual(result["number_of_buys"],17)
        self.assertAlmostEqual(result["spent_aud"],433500.,places=5)
        self.assertAlmostEqual(result["biggest_weekly_buy_aud"],25500.,places=5)
        self.assertFalse(result["original_cap_violated"])
        self.assertGreater(result["cash_after_104w_aud"],66500.)

    def test_twenty_weeks_can_fully_deploy_500k_inside_weekly_cap(self):
        rows=mock_rows(104,cross=0,remain_below=104)
        result=study.replay(rows,policy="20_calendar_capped",capital=500000.)
        self.assertEqual(result["number_of_buys"],20)
        self.assertAlmostEqual(result["spent_aud"],500000.,places=5)
        self.assertAlmostEqual(result["biggest_weekly_buy_aud"],25000.)
        self.assertFalse(result["original_cap_violated"])

    def test_only_below_200wma_fails_to_spend_budget_if_early_rebound(self):
        rows=mock_rows(104,cross=0,remain_below=3)
        a=study.replay(rows,policy="17_eligible_below_unrestricted",capital=500000.)
        b=study.replay(rows,policy="17_calendar_unrestricted",capital=500000.)
        self.assertEqual(a["number_of_buys"],3)
        self.assertEqual(b["number_of_buys"],17)
        self.assertGreater(a["cash_after_104w_aud"],b["cash_after_104w_aud"])

    def test_existing_holdings_not_rebought_and_cash_budget_17w_within_cap(self):
        rows=mock_rows(104,cross=0,remain_below=104)
        r=study.replay(rows,policy="17_calendar_unrestricted",capital=510000.,
                       starting_btc_fraction=.41)
        self.assertFalse(r["original_cap_violated"])
        self.assertAlmostEqual(r["spent_aud"],510000*.59,places=4)
        self.assertGreater(r["btc_held_after_104w"],510000*.41/100000.*.98)

    def test_equal_to_frozen_v59_model_budget_and_cash_yield(self):
        rows=mock_rows(104,cross=0,remain_below=104,risk=.05)
        for fraction,capital in ((0.,500000.),(.41,510000.)):
            for policy in study.REFERENCE:
                with self.subTest(policy=policy,fraction=fraction):
                    m=study.replay(rows,policy=policy,capital=capital,
                                   starting_btc_fraction=fraction)
                    b=base.simulate(rows,policy=policy,cash_yield=.05,
                                    reserve_fraction=0.,capital=capital,
                                    max_fraction=study.CAP_AUD/capital,
                                    initial_btc_fraction=fraction)
                    self.assertAlmostEqual(m["btc_held_after_104w"],b["btc_units"],places=7)
                    self.assertAlmostEqual(m["cash_after_104w_aud"],b["cash_aud"],places=5)
                    self.assertAlmostEqual(m["portfolio_after_104w_aud"],b["equity_aud"],places=5)
                    self.assertEqual(m["number_of_buys"],b["buy_count"])

    def test_stale_signal_and_missing_week_not_accepted(self):
        rows=mock_rows(104)
        modified=[dict(x) for x in rows]
        modified[5]["signal_date"]=modified[5]["date"]
        with self.assertRaisesRegex(ValueError,"lag"):
            study.replay(modified,policy="risk_3x",capital=500000.)
        modified=[dict(x) for x in rows]
        modified[5]["date"]+=timedelta(days=2)
        with self.assertRaisesRegex(ValueError,"Missing week"):
            study.replay(modified,policy="risk_3x",capital=500000.)
        modified=[dict(x) for x in rows]
        modified[5]["risk_score_source"]="Neutral fallback"
        with self.assertRaisesRegex(ValueError,"not attested"):
            study.replay(modified,policy="risk_3x",capital=500000.)

    def test_historical_event_selection_no_short_or_missing_future(self):
        rows=mock_rows(104,cross=1)
        self.assertEqual(study.eligible_cohorts(rows),[])
        rows=mock_rows(105,cross=1)
        self.assertEqual(len(study.eligible_cohorts(rows)),1)


if __name__=="__main__":
    unittest.main()
