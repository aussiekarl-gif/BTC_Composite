"""Paper-only, strictly future-dated BTC microstructure scorecard tests."""
import datetime as dt
import unittest

from engines.research.btc_microstructure_forward_scorecard import (
    FROZEN_AFTER, build_report, policy_sha256,
)

UTC = dt.timezone.utc
START = dt.datetime(2026, 10, 19, 7, 20, tzinfo=UTC)
ASOF = START + dt.timedelta(days=9)


def depth(at=START, bid=65, mid=82000):
    slot = at.replace(hour=at.hour//6*6, minute=0, second=0, microsecond=0)
    return {
        "slot_utc": slot.isoformat(), "captured_at_utc": at.isoformat(),
        "mid_usd": str(mid), "bid_depth_share_pct_25bps": str(bid),
        "complete_25bps_band": "True", "row_hash": "b"+at.isoformat(),
    }


def trades(at=START+dt.timedelta(minutes=2),buy=68, secs=21,lag=1):
    slot = at.replace(hour=at.hour//6*6, minute=0, second=0, microsecond=0)
    return {
        "slot_utc":slot.isoformat(), "captured_at_utc":at.isoformat(),
        "aggressor_buy_share_pct_sample":str(buy),
        "sample_duration_seconds":str(secs), "last_trade_age_seconds":str(lag),
        "sample_only_not_continuous":"True",
        "observed_trades":"100",
        "row_hash":"c"+at.isoformat(),
    }


class ForwardScorecardTests(unittest.TestCase):
    def test_policy_freeze_is_future_relative_to_first_records(self):
        self.assertLess(dt.datetime(2026,10,18,23,38,tzinfo=UTC),FROZEN_AFTER)
        self.assertGreater(START,FROZEN_AFTER)
        self.assertEqual(len(policy_sha256()),64)

    def test_one_paired_bull_has_no_future_score(self):
        r=build_report([depth()],[trades()],as_of_utc=ASOF)
        self.assertEqual(r["strict_timestamp_paired_observations"],1)
        self.assertEqual(r["observations"][0]["hypothesis"],"PAPER_BULL")
        self.assertEqual(r["horizon_summary"]["6"]["matured_non_neutral_hypotheses"],0)
        self.assertEqual(r["buy_or_sell_recommendation"],"NONE")
        self.assertEqual(r["portfolio_writes"],0)
        self.assertFalse(r["approved_for_live_trading"])

    def test_bear_and_neutral_are_not_buy(self):
        bearish=build_report([depth(bid=39)],[trades(buy=25)],as_of_utc=ASOF)
        self.assertEqual(bearish["observations"][0]["hypothesis"],"PAPER_BEAR")
        neutral=build_report([depth(bid=60)],[trades(buy=41)],as_of_utc=ASOF)
        self.assertEqual(neutral["observations"][0]["hypothesis"],"PAPER_NEUTRAL")

    def test_frozen_exclusion_prevents_hindsight_classification(self):
        early=dt.datetime(2026,10,18,23,30,tzinfo=UTC)
        r=build_report([depth(at=early)],[trades(at=early+dt.timedelta(minutes=2))],
                       as_of_utc=ASOF)
        self.assertEqual(r["strict_timestamp_paired_observations"],0)
        self.assertEqual(r["pair_exclusion_reasons"]["predates_frozen_policy"],1)

    def test_seven_minutes_cannot_match(self):
        r=build_report([depth()],[trades(at=START+dt.timedelta(minutes=7))],as_of_utc=ASOF)
        self.assertEqual(r["strict_timestamp_paired_observations"],0)
        self.assertEqual(r["pair_exclusion_reasons"]["capture_skew_over_5min"],1)

    def test_incomplete_kraken_is_rejected(self):
        b=depth();b["complete_25bps_band"]="False"
        r=build_report([b],[trades()],as_of_utc=ASOF)
        self.assertEqual(r["pair_exclusion_reasons"]["unusable_source_coverage"],1)

    def test_stale_coinbase_sample_rejected(self):
        t=trades(lag=180)
        r=build_report([depth()],[t],as_of_utc=ASOF)
        self.assertEqual(r["pair_exclusion_reasons"]["trade_sample_unusable"],1)

    def test_six_hour_future_matures_from_actual_later_quote(self):
        # Capture time of hypothesis is the LATER Coinbase receipt (07:22),
        # not the earlier Kraken mid-price receipt (07:20).
        after=START+dt.timedelta(hours=6,minutes=20)
        r=build_report([depth(),depth(at=after,mid=83000)],
                       [trades()],as_of_utc=ASOF)
        outcome=r["observations"][0]["horizons"]["6"]
        self.assertEqual(outcome["status"],"OBSERVED_PRICE_RETURN_NOT_EXECUTABLE")
        self.assertGreater(outcome["btc_mid_return_pct"],1)
        self.assertGreater(outcome["hypothesis_signed_move_pct"],1)
        self.assertGreater(outcome["actual_elapsed_hours"],6)
        self.assertEqual(r["horizon_summary"]["6"]["matured_non_neutral_hypotheses"],1)
        self.assertFalse(r["horizon_summary"]["6"]["minimum_evidence_gate_met"])

    def test_future_before_target_never_counts(self):
        pre=START+dt.timedelta(hours=5)
        r=build_report([depth(),depth(at=pre,mid=88000)],[trades()],as_of_utc=ASOF)
        self.assertEqual(r["observations"][0]["horizons"]["6"]["status"],
                         "NO_EXACT_FUTURE_OBSERVATION")

    def test_late_quote_over_90min_not_accepted(self):
        later=START+dt.timedelta(hours=8,minutes=5)
        r=build_report([depth(),depth(at=later,mid=88000)],[trades()],as_of_utc=ASOF)
        self.assertEqual(r["observations"][0]["horizons"]["6"]["status"],
                         "NO_EXACT_FUTURE_OBSERVATION")

    def test_seven_day_matures_only_after_a_real_quote(self):
        later=START+dt.timedelta(days=7,minutes=30)
        r=build_report([depth(),depth(at=later,mid=81000)],[trades()],as_of_utc=ASOF)
        self.assertEqual(r["horizon_summary"]["168"]["matured_non_neutral_hypotheses"],1)
        self.assertLess(r["observations"][0]["horizons"]["168"]["hypothesis_signed_move_pct"],0)

    def test_no_risk_free_arbitrage_claim(self):
        r=build_report([depth()],[trades()],as_of_utc=ASOF)
        self.assertFalse(r["rules"]["executable_IBIT_AUD_quote"])
        self.assertEqual(r["rules"]["independently_verified_agent_votes"],0)
        self.assertFalse(r["rules"]["data_is_full_6h_trade_flow"])
        self.assertFalse(r["horizon_summary"]["24"]["valid_after_fee_trade_outperformance"])

    def test_missing_venue_does_not_create_signal(self):
        r=build_report([depth()],[],as_of_utc=ASOF)
        self.assertEqual(r["strict_timestamp_paired_observations"],0)
        self.assertEqual(r["pair_exclusion_reasons"]["missing_second_venue"],1)

    def test_future_timestamp_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Future tape"):
            build_report([depth(at=ASOF+dt.timedelta(seconds=1))],[],as_of_utc=ASOF)

    def test_duplicate_source_slot_fails(self):
        with self.assertRaisesRegex(ValueError,"Duplicate source slots"):
            build_report([depth(),depth()],[],as_of_utc=ASOF)

    def test_nonfinite_values_rejected(self):
        with self.assertRaisesRegex(ValueError,"Nonfinite"):
            build_report([depth(bid="nan")],[trades()],as_of_utc=ASOF)

    def test_naive_asof_rejected(self):
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            build_report([],[],as_of_utc=ASOF.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
