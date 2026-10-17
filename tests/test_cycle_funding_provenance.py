"""Optional funding labels must not change a single executed trade or tax lot."""
import copy
import unittest
import pandas as pd

from engines.research.cycle_funding_provenance import (
    classify_executed_buy,classify_with_stale_guard,
    UNREVIEWED,INDEPENDENT,CYCLE_SALE,
)
from engines.research.cycle_real_sale_budget import original_sale_cash_reconciliation
from engines.shared.portfolio_transactions import (
    portfolio_positions,merge_legacy_purchase_editor,
)

H="2024-04-20"
ASOF="2026-10-15"


def buy(date,qty,spent,fee=3):
    return {
        "Date":date,"Asset":"ASX:IBIT",
        "Units / BTC Received":qty,"AUD Spent":spent,
        "Brokerage / Fee AUD":fee,"BTC AUD Price":100000.,
        "Notes":"Order explicitly executed",
    }


def portfolio():
    return {
        "starting_capital_aud":500000.,
        "rows":[
            buy("01/05/24",100,10000,20),
            buy("11/05/26",3,1000,3),
            buy("18/05/26",5,2000,5),
        ],
        "sales":[{
            "Date":"02/09/25","Asset":"ASX:IBIT",
            "Units Sold":50,"AUD Proceeds":20000,
            "Brokerage / Fee AUD":10,
        }],
    }


class OriginalSaleFundingProvenanceTests(unittest.TestCase):
    def test_existing_ledger_remains_unchanged_except_confirmed_metadata(self):
        p=portfolio()
        original=copy.deepcopy(p)
        before=portfolio_positions(p)
        after=classify_executed_buy(
            p,row_index=1,funding_source=INDEPENDENT,confirmed=True)
        self.assertEqual(p,original)
        self.assertEqual(before,portfolio_positions(after))
        self.assertEqual(p["sales"],after["sales"])
        self.assertEqual(after["rows"][1]["Funding Source"],INDEPENDENT)
        self.assertNotIn("Funding Source",after["rows"][0])

    def test_legacy_unknown_buys_still_debit_original_budget(self):
        p=portfolio()
        legacy=original_sale_cash_reconciliation(p,H,asof=ASOF)
        self.assertEqual(legacy["all_later_buys_including_fees_aud"],3008.)
        self.assertEqual(legacy["unreviewed_buys_including_fees_aud"],3008.)
        self.assertEqual(legacy["user_labeled_independent_buys_aud"],0.)
        self.assertFalse(legacy["ledger_buyback_tagging_verified"])

    def test_independent_label_excludes_only_attested_row(self):
        p=portfolio()
        tagged=classify_executed_buy(
            p,row_index=1,funding_source=INDEPENDENT,confirmed=True)
        audit=original_sale_cash_reconciliation(tagged,H,asof=ASOF)
        self.assertEqual(audit["all_later_buys_including_fees_aud"],2005.)
        self.assertEqual(audit["unreviewed_buys_including_fees_aud"],2005.)
        self.assertEqual(audit["user_labeled_independent_buys_aud"],1003.)
        self.assertEqual(audit["funding_labels_reviewed_count"],1)
        self.assertEqual(audit["total_later_buy_count"],2)
        self.assertEqual(audit["recorded_cash_before_tax_reserve_aud"],
                         original_sale_cash_reconciliation(
                             p,H,asof=ASOF)["recorded_cash_before_tax_reserve_aud"])

    def test_cycle_sale_label_is_debited_and_requires_actual_original_sale(self):
        p=portfolio()
        tagged=classify_executed_buy(
            p,row_index=1,funding_source=CYCLE_SALE,
            halving=H,confirmed=True)
        audit=original_sale_cash_reconciliation(tagged,H,asof=ASOF)
        self.assertEqual(audit["cycle_tagged_buys_including_fees_aud"],1003.)
        self.assertEqual(audit["all_later_buys_including_fees_aud"],3008.)
        self.assertEqual(tagged["rows"][1]["Funding Cycle Halving"],H)
        no_sale=portfolio()
        no_sale["sales"]=[]
        with self.assertRaisesRegex(ValueError,"No original BTC/IBIT sale proceeds"):
            classify_executed_buy(
                no_sale,row_index=1,funding_source=CYCLE_SALE,
                halving=H,confirmed=True)

    def test_cannot_backdate_original_2025_cycle_for_early_2026_purchase(self):
        p=portfolio()
        p["rows"].append(buy("01/01/26",2,800,3))
        with self.assertRaisesRegex(ValueError,"predates this cycle"):
            classify_executed_buy(
                p,row_index=3,funding_source=CYCLE_SALE,
                halving=H,confirmed=True)

    def test_reject_unconfirmed_unknown_index_and_corrupt_tags(self):
        p=portfolio()
        with self.assertRaisesRegex(ValueError,"confirmation"):
            classify_executed_buy(
                p,row_index=1,funding_source=INDEPENDENT,confirmed=False)
        with self.assertRaisesRegex(ValueError,"Unknown funding source"):
            classify_executed_buy(
                p,row_index=1,funding_source="Never traded",confirmed=True)
        with self.assertRaisesRegex(ValueError,"valid existing"):
            classify_executed_buy(
                p,row_index=10,funding_source=INDEPENDENT,confirmed=True)
        with self.assertRaisesRegex(ValueError,"required"):
            classify_executed_buy(
                p,row_index=1,funding_source=CYCLE_SALE,confirmed=True)
        p["rows"][1]["Funding Source"]="Fake broker verified"
        with self.assertRaisesRegex(ValueError,"Unknown BUY Funding Source"):
            original_sale_cash_reconciliation(p,H,asof=ASOF)

    def test_restoring_unreviewed_reinstates_conservative_debit(self):
        p=portfolio()
        p=classify_executed_buy(
            p,row_index=1,funding_source=INDEPENDENT,confirmed=True)
        p=classify_executed_buy(
            p,row_index=1,funding_source=UNREVIEWED,confirmed=True)
        self.assertNotIn("Funding Source",p["rows"][1])
        self.assertEqual(original_sale_cash_reconciliation(
            p,H,asof=ASOF)["all_later_buys_including_fees_aud"],3008.)

    def test_stale_guard_rejects_purchase_or_sale_changed_elsewhere(self):
        original=portfolio()
        fresh=copy.deepcopy(original)
        fresh["rows"][1]["Notes"]="Edited in another Streamlit session"
        with self.assertRaisesRegex(ValueError,"changed since page load"):
            classify_with_stale_guard(
                original,fresh,row_index=1,
                funding_source=INDEPENDENT,confirmed=True)
        fresh=copy.deepcopy(original)
        fresh["sales"][0]["AUD Proceeds"]=20100
        with self.assertRaisesRegex(ValueError,"changed since page load"):
            classify_with_stale_guard(
                original,fresh,row_index=1,
                funding_source=INDEPENDENT,confirmed=True)

    def test_legacy_editor_preserves_funding_meta_for_identical_execution(self):
        original=classify_executed_buy(
            portfolio(),row_index=1,funding_source=CYCLE_SALE,
            halving=H,confirmed=True)
        stripped=copy.deepcopy(original["rows"])
        for row in stripped:
            row.pop("Funding Source",None)
            row.pop("Funding Cycle Halving",None)
        updated=merge_legacy_purchase_editor(
            original,copy.deepcopy(original),edited_buys=stripped,
            starting_capital_aud=500000.)
        self.assertEqual(updated["rows"][1]["Funding Source"],CYCLE_SALE)
        self.assertEqual(updated["rows"][1]["Funding Cycle Halving"],H)
        self.assertEqual(portfolio_positions(updated),
                         portfolio_positions(original))


if __name__=="__main__":
    unittest.main()
