"""No forced 2026 deadline; conditional eligible weeks, NOT a price forecast."""
import datetime as dt
from decimal import Decimal
import unittest

from engines.research.flexible_2027_cash_deployment_envelope import (
    build_envelope,
    remaining_cash_after_conditional_buys,
    maximum_possible_seven_day_orders,
    RESEARCH_ENROLMENT_DATE,
    CHECKPOINTS,
    MIN_COOLDOWN_DAYS,
)


class FlexibleDeploymentDecisionTests(unittest.TestCase):
    def test_user_preference_is_no_forced_buy_november_2026(self):
        x=build_envelope()
        self.assertEqual(x["objective_recorded_2026_10_20"],
                         "NOVEMBER_2026_IS_NOT_A_FORCED_DEPLOYMENT_DEADLINE")
        self.assertTrue(x["uninvested_AUD_may_remain_in_2027"])
        self.assertFalse(x["forced_buy_at_any_checkpoint"])
        self.assertTrue(x["live_2_5_percent_weekly_buy_unchanged"])
        self.assertTrue(x["20_week_fixed_DCA_remains_an_independent_benchmark"])

    def test_checkpoints_are_not_broker_buy_dates(self):
        x=build_envelope()
        self.assertTrue(all("not_deployment_deadline" in t
                            for r in x["observations"] for t in r
                            if t.startswith("checkpoint_")))
        self.assertTrue(x["no_live_trading_or_broker_operations"])
        self.assertTrue(x["no_portfolio_reads_or_writes"])
        self.assertTrue(x["no_notifications"])

    def test_november_research_maxopportunity_count_is_six(self):
        self.assertEqual(maximum_possible_seven_day_orders(
            start=RESEARCH_ENROLMENT_DATE,thru=dt.date(2026,11,30)),6)
        self.assertEqual(MIN_COOLDOWN_DAYS,7)

    def test_zero_eligible_signals_keep_all_cash_even_in_2027(self):
        x=build_envelope()
        zero=[t for t in x["observations"]
              if t["hypothetical_fraction_of_weeks_with_eligible_filled_buy"]=="0"]
        self.assertEqual(len(zero),len(CHECKPOINTS)*4)
        for row in zero:
            self.assertEqual(row["cash_remaining_aud_before_prices_costs_tax"],"500000.00")
            self.assertEqual(row["cash_deployed_aud_before_prices_costs_tax"],"0.00")
            self.assertEqual(row["percent_original_cash_deployed"],"0.0000")

    def test_even_all_opportunities_not_a_forced_capital_sweep(self):
        x=build_envelope()
        full=[t for t in x["observations"] if (
            t["checkpoint_calendar_date_not_deployment_deadline"]=="2027-12-31"
            and t["hypothetical_fraction_of_weeks_with_eligible_filled_buy"]=="1"
            and t["candidate_pct_of_remaining_cash_on_eligible_buy_only"]=="2.5")]
        self.assertEqual(len(full),1)
        self.assertGreater(float(full[0]["cash_remaining_aud_before_prices_costs_tax"]),0.0)
        self.assertLess(float(full[0]["cash_deployed_aud_before_prices_costs_tax"]),500000.0)
        self.assertFalse(x["forced_buy_at_any_checkpoint"])

    def test_six_2_5pct_eligible_buys_do_not_equal_six_2_5_original(self):
        end=remaining_cash_after_conditional_buys(Decimal("500000"),Decimal("2.5"),6)
        self.assertEqual(end,Decimal("500000")*(Decimal(".975")**6))
        self.assertGreater(end,Decimal("425000"))  # invested less than 15% original
        self.assertLess(end,Decimal("500000"))

    def test_increasing_pct_increases_exposure_but_proves_no_alpha(self):
        three=remaining_cash_after_conditional_buys(Decimal("500000"),Decimal("3.5"),6)
        five=remaining_cash_after_conditional_buys(Decimal("500000"),Decimal("5.0"),6)
        old=remaining_cash_after_conditional_buys(Decimal("500000"),Decimal("2.5"),6)
        self.assertLess(five,three)
        self.assertLess(three,old)
        self.assertTrue(build_envelope()["no_performance_or_alpha_inferred_from_cash_deployment_speed"])

    def test_more_eligible_signals_lower_cash_without_price_assumption(self):
        x=build_envelope()
        self.assertTrue(x["no_assumed_price_or_spread_or_taxes_or_etf_whole_units"])
        start=Decimal("500000")
        prev=start
        for n in range(18):
            new=remaining_cash_after_conditional_buys(start,Decimal("2.5"),n)
            self.assertLessEqual(new,prev)
            prev=new

    def test_output_has_all_candidates_and_counterfactuals(self):
        x=build_envelope()
        self.assertEqual(len(x["observations"]),64)
        self.assertEqual(
            {r["candidate_pct_of_remaining_cash_on_eligible_buy_only"]
             for r in x["observations"]},
            {"2.5","3.0","3.5","5.0"})
        self.assertTrue(x["all_candidate_percentages_research_only"])
        self.assertTrue(all(not x["is_user_portfolio"]
                            for x in x["observations"]))

    def test_no_pseudo_trading_signal_or_future_market_data(self):
        from engines.research import flexible_2027_cash_deployment_envelope as m
        self.assertNotIn("BTC market WATCH",m.__doc__)
        x=build_envelope()
        self.assertFalse(any("market_signal" in row or "broker_fill" in row
                             for row in x["observations"]))

    def test_invalid_cash_and_percent_rejected(self):
        for amount in (Decimal("0"),Decimal("-1"),Decimal("NaN")):
            with self.assertRaisesRegex(ValueError,"cash"):
                remaining_cash_after_conditional_buys(
                    amount,Decimal("2.5"),1)
        for pct in (Decimal("-1"),Decimal("101"),Decimal("NaN")):
            with self.assertRaisesRegex(ValueError,"percent"):
                remaining_cash_after_conditional_buys(
                    Decimal("100"),pct,1)

    def test_incorrect_triggers_rejected(self):
        for n in (-1,1.25,True):
            with self.assertRaisesRegex(ValueError,"integer"):
                remaining_cash_after_conditional_buys(
                    Decimal("100"),Decimal("2.5"),n)

    def test_no_backwards_or_duplicate_dates(self):
        with self.assertRaisesRegex(ValueError,"precedes"):
            maximum_possible_seven_day_orders(
                start=dt.date(2027,1,1),thru=dt.date(2026,12,31))
        with self.assertRaisesRegex(ValueError,"distinct and ordered"):
            build_envelope(checkpoints=(dt.date(2027,1,1),dt.date(2027,1,1)))

    def test_notional_amount_is_independent_of_users_actual_cash(self):
        x=build_envelope(hypothetical_cash_aud=Decimal("1000"))
        self.assertEqual(x["starting_capital_aud_reference_only"],"1000.00")
        self.assertTrue(x["cash_start_is_illustrative_not_verified_actual_portfolio"])
        self.assertEqual(x["observations"][0]["starting_reference_cash_aud"],"1000.00")


if __name__=="__main__":
    unittest.main()
