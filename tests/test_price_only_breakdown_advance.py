"""Frozen price-only 5%-original re-timing, zero additional BTC test suite."""
import unittest
import numpy as np
import pandas as pd

from engines.research.cycle_chronological_wallet import replay_chronological_wallet
from engines.research.price_only_breakdown_advance import (
    ADVANCE_FRACTION_ORIGINAL, OFFSET_DAY, TRIGGER_FIRST_DAY,
    TRIGGER_LAST_DAY, replay_price_breakdown_advance,
)

H = pd.Timestamp("2020-05-11", tz="UTC")
START = H - pd.Timedelta(days=1500)
END = H + pd.Timedelta(days=940)
IDX = pd.date_range(START, END, freq="D", tz="UTC")


def synthetic_prices(*, breakdown):
    elapsed = (IDX - H).days
    if breakdown:
        # No sell trigger before the day501 eligibility floor. An
        # unequivocally falling 90d high/50DMA regime exists by day501.
        numbers = np.where(
            elapsed < 410, 200.,
            np.where(elapsed < 590, 200. - 0.72 * (elapsed - 410),
                     np.where(elapsed < 710, 70., 76.)))
    else:
        numbers = np.full(len(IDX), 200.)
    return pd.Series(numbers.astype(float), index=IDX)


def synthetic_fx():
    return pd.DataFrame(
        {"aud_per_usd": 1.5},
        index=pd.date_range(START - pd.Timedelta(days=7),
                            END, freq="D", tz="UTC"))


class PriceOnlyBreakdownAdvanceTest(unittest.TestCase):
    def test_original_wallet_parity_flat_history(self):
        price, fx = synthetic_prices(breakdown=False), synthetic_fx()
        baseline = replay_price_breakdown_advance(price, fx, H, END)
        orig = replay_chronological_wallet(price, fx, H, END)
        self.assertEqual(baseline["ending_aftertax_liquidation_aud"],
                         orig["after_hypothetical_liquidation_cgt_aud"])
        self.assertEqual(baseline["btc_end"], orig["btc_held"])
        self.assertEqual(baseline["cash_end_aud"], orig["cash_remaining_aud"])
        self.assertEqual(baseline["sell_count"], orig["sell_count"])
        self.assertEqual(baseline["buy_count"], orig["buyback_count"])

    def test_no_warning_means_exact_original(self):
        price, fx = synthetic_prices(breakdown=False), synthetic_fx()
        original = replay_price_breakdown_advance(
            price, fx, H, END, candidate=False)
        candidate = replay_price_breakdown_advance(
            price, fx, H, END, candidate=True)
        self.assertIsNone(candidate["advanced_sell_date"])
        for k in ("ending_aftertax_liquidation_aud", "btc_end",
                  "cash_end_aud", "sell_count", "buy_count",
                  "fraction_original_sold_total"):
            self.assertEqual(original[k], candidate[k])

    def test_first_prior_price_breakdown_advances_only_five_percent(self):
        price, fx = synthetic_prices(breakdown=True), synthetic_fx()
        original = replay_price_breakdown_advance(price, fx, H, END)
        candidate = replay_price_breakdown_advance(
            price, fx, H, END, candidate=True)
        self.assertIsNotNone(candidate["advanced_sell_date"])
        triggered = pd.Timestamp(candidate["advanced_sell_date"], tz="UTC")
        self.assertGreaterEqual((triggered - H).days, TRIGGER_FIRST_DAY)
        self.assertLessEqual((triggered - H).days, TRIGGER_LAST_DAY)
        self.assertEqual(candidate["advanced_fraction_original_pct"],
                         100 * ADVANCE_FRACTION_ORIGINAL)
        self.assertAlmostEqual(original["fraction_original_sold_by_day525"],
                               candidate["fraction_original_sold_by_day525"],
                               places=7)
        self.assertAlmostEqual(original["fraction_original_sold_total"],
                               candidate["fraction_original_sold_total"],
                               places=7)
        self.assertEqual(original["first_200wma_rebuy"],
                         candidate["first_200wma_rebuy"])
        self.assertTrue(candidate["research_only"])
        self.assertFalse(candidate["live_execution_parity_verified"])

    def test_no_hindsight_repainting_for_first_breakdown_trade(self):
        price, fx = synthetic_prices(breakdown=True), synthetic_fx()
        first = replay_price_breakdown_advance(
            price, fx, H, END, candidate=True)
        d = pd.Timestamp(first["advanced_sell_date"], tz="UTC")
        changed = price.copy()
        changed.loc[d + pd.Timedelta(days=1):] *= 1.8
        second = replay_price_breakdown_advance(
            changed, fx, H, END, candidate=True)
        self.assertEqual(first["advanced_sell_date"],
                         second["advanced_sell_date"])
        ea = next(x for x in first["executions"]
                  if x["advance_on_this_day"])
        eb = next(x for x in second["executions"]
                  if x["advance_on_this_day"])
        self.assertEqual(ea, eb)

    def test_exact_five_percent_is_shifted_not_added(self):
        price, fx = synthetic_prices(breakdown=True), synthetic_fx()
        orig = replay_price_breakdown_advance(price, fx, H, END)
        retimed = replay_price_breakdown_advance(
            price, fx, H, END, candidate=True)
        d525 = str((H + pd.Timedelta(days=OFFSET_DAY)).date())
        a = next(e for e in orig["executions"]
                 if e["date"] == d525 and e["side"] == "SELL")
        b = next(e for e in retimed["executions"]
                 if e["date"] == d525 and e["side"] == "SELL")
        self.assertAlmostEqual(
            a["original_btc_fraction"] - b["original_btc_fraction"],
            ADVANCE_FRACTION_ORIGINAL, places=7)
        self.assertAlmostEqual(
            retimed["fraction_original_sold_total"],
            orig["fraction_original_sold_total"], places=7)

    def test_reject_missing_days_negative_price_and_future_end(self):
        price, fx = synthetic_prices(breakdown=True), synthetic_fx()
        for bad in (
            price.drop(price.index[100]),
            price.mask(price.index == H + pd.Timedelta(days=200), np.nan),
            price.mask(price.index == H + pd.Timedelta(days=200), -1.),
        ):
            with self.assertRaises(ValueError):
                replay_price_breakdown_advance(
                    bad, fx, H, END, candidate=True)
        with self.assertRaises(ValueError):
            replay_price_breakdown_advance(
                price, fx, H, H + pd.Timedelta(days=1200),
                candidate=True)


if __name__ == "__main__":
    unittest.main()
