"""Offline causal quote audit regressions."""
import datetime as dt
import unittest
from engines.research.btc_post_signal_causal_quote_audit import build_audit
UTC=dt.timezone.utc
BASE=dt.datetime(2026,10,19,11,59,tzinfo=UTC)
ASOF=dt.datetime(2026,10,22,tzinfo=UTC)

def depth(at,bid=99.99,ask=100,share=65):
    slot=at.replace(hour=at.hour//6*6,minute=0,second=0,microsecond=0)
    return dict(slot_utc=slot.isoformat(),captured_at_utc=at.isoformat(),
        mid_usd=str((bid+ask)/2),best_bid_usd=str(bid),
        best_ask_usd=str(ask),bid_depth_share_pct_25bps=str(share),
        complete_25bps_band="True",row_hash="k"+at.isoformat())

def sample(at=BASE+dt.timedelta(seconds=20),buy=68):
    slot=at.replace(hour=at.hour//6*6,minute=0,second=0,microsecond=0)
    return dict(slot_utc=slot.isoformat(),captured_at_utc=at.isoformat(),
        aggressor_buy_share_pct_sample=str(buy),
        sample_duration_seconds="20",last_trade_age_seconds="1",
        sample_only_not_continuous="True",observed_trades="100",
        row_hash="c"+at.isoformat())

class CausalAuditTests(unittest.TestCase):
    def check(self,b=None,t=None,asof=ASOF):
        return build_audit([depth(BASE)] if b is None else b,
                           [sample()] if t is None else t,as_of_utc=asof)

    def test_pre_signal_book_is_not_entry(self):
        r=self.check()
        self.assertEqual(r["strict_paired_hypotheses"],1)
        self.assertEqual(r["post_signal_quotes_within_5_minutes"],0)
        self.assertEqual(r["observations"][0]["horizons"]["6"]["status"],
                         "NO_CAUSAL_ENTRY_QUOTE")

    def test_tied_receipt_cannot_establish_order(self):
        self.assertEqual(self.check(t=[sample(at=BASE)])["post_signal_quotes_within_5_minutes"],0)

    def test_later_quote_and_exit_have_cost_scenarios(self):
        entry=dt.datetime(2026,10,19,12,2,tzinfo=UTC)
        exit_=dt.datetime(2026,10,19,18,5,tzinfo=UTC)
        r=self.check(b=[depth(BASE),depth(entry,103.9,104),depth(exit_,105,105.1)])
        o=r["observations"][0]
        self.assertEqual(o["entry_ask_usd"],104)
        net=o["horizons"]["6"]["spot_long_after_hypothetical_fees_pct"]
        self.assertGreater(net["5"],net["10"])
        self.assertGreater(net["10"],net["25"])
        self.assertAlmostEqual(net["10"],100*(105*.999/(104*1.001)-1),places=5)
        self.assertFalse(r["after_cost_ASX_IBIT_outperformance_validated"])

    def test_no_later_exit_no_score(self):
        entry=dt.datetime(2026,10,19,12,2,tzinfo=UTC)
        r=self.check(b=[depth(BASE),depth(entry)])
        self.assertEqual(r["observations"][0]["horizons"]["6"]["status"],
                         "NO_CAUSAL_EXIT_QUOTE")

    def test_late_quote_rejected(self):
        late=BASE+dt.timedelta(minutes=6)
        r=self.check(b=[depth(BASE),depth(late)])
        self.assertEqual(r["post_signal_quotes_within_5_minutes"],0)

    def test_no_future_source(self):
        entry=dt.datetime(2026,10,19,12,2,tzinfo=UTC)
        with self.assertRaisesRegex(ValueError,"Future tape"):
            self.check(b=[depth(BASE),depth(entry)],asof=BASE)

    def test_no_recommendations(self):
        r=self.check()
        self.assertEqual(r["trade_recommendation"],"NONE")
        self.assertEqual(r["ntfy_messages"],0)
        self.assertEqual(r["broker_orders"],0)
