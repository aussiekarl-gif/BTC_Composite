"""Readiness means correctly sourced data, not proof of trading profitability."""
import datetime as dt
import unittest
from copy import deepcopy

from engines.research.forward_market_readiness import inspect_forward_tapes
from engines.research.cycle_forward_signal_tape import (
    SIGNAL_COLUMNS,OUTCOME_COLUMNS,GENESIS,_signature,_dump_rows,
    append_snapshot,
)
from engines.research.ibit_asx_forward_close_tape import (
    COLUMNS as ASX_COLUMNS,append_market_observation,
)

UTC=dt.timezone.utc
NOW=dt.datetime(2026,10,20,12,0,tzinfo=UTC)


def btc_record(day,captured,dispersion="6.2900"):
    r={key:"test_fixture" for key in SIGNAL_COLUMNS
       if key not in ("prior_row_hash","row_hash")}
    r.update({
        "observation_date_utc":day,
        "captured_at_utc":captured,
        "signal":"HOLD",
        "source_crosscheck_max_diff_pct":dispersion,
    })
    return r


def ibit_record(day,captured):
    r={key:"test_fixture" for key in ASX_COLUMNS
       if key not in ("prior_row_hash","row_hash")}
    r.update({
        "market_session_date_sydney":day,
        "captured_at_utc":captured,
        "provider_daily_candle_timestamp_utc":captured,
        "symbol":"ASX:IBIT",
        "currency":"AUD",
        "is_confirmed_broker_fill":"False",
    })
    return r


def fixture():
    a,_=append_snapshot("",btc_record(
        "2026-10-15","2026-10-18T07:49:45+00:00"))
    a,_=append_snapshot(a,btc_record(
        "2026-10-17","2026-10-18T08:35:29+00:00"))
    b,_=append_market_observation("",ibit_record(
        "2026-10-19","2026-10-19T07:15:00+00:00"))
    return a,b


class ForwardReadinessTest(unittest.TestCase):
    def test_live_tape_shape_stale_seed_gapped_btc_and_insufficient_asx(self):
        a,b=fixture()
        r=inspect_forward_tapes(a,b,now=NOW)
        self.assertEqual(r["total_frozen_BTC_market_snapshots"],2)
        self.assertEqual(r["genuine_following_day_UTC_BTC_snapshots"],1)
        self.assertEqual(r["historical_not_prospective_BTC_snapshot_dates"],
                         ["2026-10-15"])
        self.assertEqual(r["BTC_snapshot_missing_calendar_days_between_endpoints"],1)
        self.assertEqual(r["latest_observed_BTC_UTC_day"],"2026-10-17")
        self.assertEqual(r["frozen_ASX_IBIT_Sydney_session_quotes"],1)
        self.assertFalse(r["pipeline_sample_counts_met"])
        self.assertFalse(r["can_claim_out_of_sample_trading_edge"])
        self.assertEqual(r["readiness_status"],"NOT_READY_FOR_LIVE_STRATEGY_PROMOTION")
        self.assertTrue(r["public_provider_dispersion_requires_review"])
        self.assertEqual(r["new_ntfy_messages"],0)

    def test_zero_ibit_rows_are_normal_for_weekend_without_fake_bar(self):
        a,_=fixture()
        r=inspect_forward_tapes(
            a,"",now=dt.datetime(2026,10,18,11,0,tzinfo=UTC))
        self.assertEqual(r["frozen_ASX_IBIT_Sydney_session_quotes"],0)
        self.assertIsNone(r["ASX_session_close_age_calendar_days"])
        self.assertFalse(r["eligible_for_automatic_live_rule_promotion"])

    def test_hash_chain_tamper_raises_not_quietly_corrects(self):
        a,b=fixture()
        with self.assertRaisesRegex(ValueError,"Modified"):
            inspect_forward_tapes(a.replace("6.2900","0.0010"),
                                  b,now=NOW)
        with self.assertRaisesRegex(ValueError,"Modified"):
            inspect_forward_tapes(a,b.replace("ASX:IBIT","ASX:IBTT"),now=NOW)

    def test_false_broker_fill_is_blocked_even_with_matching_hash(self):
        a,b=fixture()
        row=ibit_record("2026-10-19","2026-10-19T07:15:00+00:00")
        row["is_confirmed_broker_fill"]="True"
        forged,_=append_market_observation("",row)
        with self.assertRaisesRegex(ValueError,"fabricated broker"):
            inspect_forward_tapes(a,forged,now=NOW)

    def test_non_aus_market_session_refused(self):
        a,b=fixture()
        row=ibit_record("2026-10-18","2026-10-18T05:00:00+00:00")
        forged,_=append_market_observation("",row)
        with self.assertRaisesRegex(ValueError,"Non-prospective"):
            inspect_forward_tapes(a,forged,now=NOW)
        row=ibit_record("2026-10-19","2026-10-19T01:00:00+00:00")
        forged,_=append_market_observation("",row)
        with self.assertRaisesRegex(ValueError,"Non-prospective"):
            inspect_forward_tapes(a,forged,now=NOW)

    def test_outcome_foreign_hash_fails_even_if_outcome_chain_is_valid(self):
        a,b=fixture()
        values={x:"fixture" for x in OUTCOME_COLUMNS
                if x not in ("prior_row_hash","row_hash")}
        values.update({
            "base_observation_date_utc":"2026-10-15",
            "horizon_days":"7",
            "source_base_row_hash":"b"*64,
            "source_future_row_hash":"c"*64,
        })
        values["prior_row_hash"]=GENESIS
        values["row_hash"]=_signature(values,OUTCOME_COLUMNS)
        bogus=_dump_rows([values],OUTCOME_COLUMNS)
        with self.assertRaisesRegex(ValueError,"unobserved"):
            inspect_forward_tapes(a,b,bogus,now=NOW)

    def test_duplicate_future_outcome_horizon_is_rejected(self):
        a,b=fixture()
        from engines.research.cycle_forward_signal_tape import _read_rows
        records=_read_rows(a,SIGNAL_COLUMNS)
        values={x:"fixture" for x in OUTCOME_COLUMNS
                if x not in ("prior_row_hash","row_hash")}
        values.update({
            "base_observation_date_utc":"2026-10-15",
            "horizon_days":"7",
            "source_base_row_hash":records[0]["row_hash"],
            "source_future_row_hash":records[-1]["row_hash"],
        })
        rows=[]
        for i in range(2):
            new=deepcopy(values)
            new["prior_row_hash"]=rows[-1]["row_hash"] if rows else GENESIS
            new["row_hash"]=_signature(new,OUTCOME_COLUMNS)
            rows.append(new)
        with self.assertRaisesRegex(ValueError,"Duplicate forward outcome"):
            inspect_forward_tapes(a,b,_dump_rows(rows,OUTCOME_COLUMNS),now=NOW)

    def test_no_amount_of_pipeline_samples_proves_model_alpha(self):
        a,_=fixture()
        result=inspect_forward_tapes(a,"",now=NOW)
        self.assertFalse(result["can_claim_out_of_sample_trading_edge"])
        self.assertEqual(result["pipeline_smoke_test_targets"],{
            "prospective_BTC_UTC_snapshots":30,
            "distinct_ASX_session_closes":20,
        })
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            inspect_forward_tapes(a,"",now=dt.datetime(2026,10,20,12,0))

    def test_invalid_crosscheck_requires_manual_data_review(self):
        a,b=fixture()
        z,_=append_snapshot("",btc_record(
            "2026-10-17","2026-10-18T08:35:29+00:00",
            dispersion="not-a-number"))
        with self.assertRaisesRegex(ValueError,"Unparseable"):
            inspect_forward_tapes(z,b,now=NOW)


if __name__=="__main__":
    unittest.main()
