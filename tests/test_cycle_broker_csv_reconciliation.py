"""CSV statement reconciliation tests: one-to-one, no writes or false cash."""
import copy
import unittest

from engines.research.cycle_broker_csv_reconciliation import (
    parse_broker_executions_csv,parse_broker_balances_csv,
    compare_broker_transactions,compare_broker_balances,
    TRANSACTION_TEMPLATE,BALANCE_TEMPLATE,MAX_BYTES,
)
from engines.shared.portfolio_transactions import portfolio_positions

TODAY="2026-10-17"


def purchase(date,units,gross,fee=3,ref="ONE",asset="ASX:IBIT"):
    return {
        "Date":date,"Asset":asset,"Units / BTC Received":units,
        "AUD Spent":gross,"Brokerage / Fee AUD":fee,
        "BTC AUD Price":100000.,"Notes":ref,
    }


def sale(date,units,gross,fee=3,ref="SELL-1",asset="ASX:IBIT"):
    return {
        "Date":date,"Asset":asset,"Units Sold":units,
        "AUD Proceeds":gross,"Brokerage / Fee AUD":fee,
        "Notes":ref,
    }


def portfolio():
    return {
        "starting_capital_aud":500000.,
        "rows":[purchase("01/05/24",100,10000,20,ref="2024-BUY"),
                purchase("15/10/26",10,250,3,ref="ORDER-123")],
        "sales":[sale("16/10/26",2,60,3,ref="ORDER-124")],
    }


def statement(rows):
    return ("Date,Side,Asset,Units,Gross AUD,Fee AUD,Reference\n"+
            "\n".join(rows)+"\n").encode("utf8")


def parse(rows):
    return parse_broker_executions_csv(statement(rows),today=TODAY)


class CsvBrokerAuditTests(unittest.TestCase):
    def test_templates_are_valid_utf8_csv_and_distinguish_assets(self):
        records=parse_broker_executions_csv(
            TRANSACTION_TEMPLATE.encode("utf8"),today=TODAY)
        self.assertEqual(len(records),2)
        self.assertEqual(records[0]["asset"],"ASX:IBIT")
        self.assertEqual(records[1]["asset"],"Direct BTC")
        self.assertEqual(records[1]["qty"],.005)
        balances=parse_broker_balances_csv(
            BALANCE_TEMPLATE.encode("utf8"),today=TODAY)
        self.assertEqual(balances["date"].isoformat(),TODAY)
        self.assertEqual(balances["positions"]["Direct BTC"],.125)

    def test_exact_one_to_one_with_same_reference_matches(self):
        saved=portfolio()
        before=copy.deepcopy(saved)
        x=parse(["2026-10-15,BUY,IBIT.AX,10,250,3,ORDER-123",
                 "2026-10-16,SELL,ASX:IBIT,2,60,3,ORDER-124"])
        a=compare_broker_transactions(saved,x,start_date="2026-10-15",
                                      end_date="2026-10-17",
                                      complete_statement_confirmed=True)
        self.assertEqual(a["matched_executions"],2)
        self.assertTrue(a["all_rows_accounted_for"])
        self.assertEqual(a["broker_only"],0)
        self.assertEqual(a["portfolio_only"],0)
        self.assertEqual(a["ambiguous_rows"],0)
        self.assertTrue(a["complete_statement_user_attested"])
        self.assertEqual(saved,before)

    def test_import_is_read_only_never_updates_google_sheets_or_portfolio(self):
        saved=portfolio()
        old=portfolio_positions(saved)
        mismatch=compare_broker_transactions(
            saved,parse(["2026-10-15,BUY,IBIT.AX,10,275,3,ORDER-123"]),
            start_date="2026-10-15",end_date="2026-10-17")
        self.assertEqual(mismatch["matched_executions"],0)
        self.assertEqual(mismatch["broker_only"],1)
        self.assertEqual(mismatch["portfolio_only"],2)
        self.assertFalse(mismatch["complete_statement_user_attested"])
        self.assertEqual(old,portfolio_positions(saved))
        self.assertTrue(mismatch["read_only"])

    def test_duplicate_identical_broker_fills_stay_ambiguous(self):
        p=portfolio()
        p["rows"].append(purchase("15/10/26",10,250,3,ref="ORDER-456"))
        b=parse(["2026-10-15,BUY,IBIT.AX,10,250,3,",
                 "2026-10-15,BUY,IBIT.AX,10,250,3,"])
        a=compare_broker_transactions(p,b,start_date="2026-10-15",
                                      end_date="2026-10-15")
        self.assertEqual(a["matched_executions"],0)
        self.assertEqual(a["ambiguous_rows"],4)
        self.assertFalse(a["all_rows_accounted_for"])

    def test_separate_distinct_ref_disambiguates_same_economics(self):
        p=portfolio()
        p["rows"].append(purchase("15/10/26",10,250,3,ref="ORDER-456"))
        b=parse(["2026-10-15,BUY,IBIT.AX,10,250,3,ORDER-123",
                 "2026-10-15,BUY,IBIT.AX,10,250,3,ORDER-456"])
        a=compare_broker_transactions(p,b,start_date="2026-10-15",
                                      end_date="2026-10-15")
        self.assertEqual(a["matched_executions"],2)
        self.assertEqual(a["ambiguous_rows"],0)

    def test_wrong_broker_ref_with_unique_identical_economics_still_matches(self):
        p=portfolio()
        b=parse(["2026-10-15,BUY,IBIT.AX,10,250,3,EXTERNAL-ID"])
        a=compare_broker_transactions(p,b,start_date="2026-10-15",
                                      end_date="2026-10-15")
        self.assertEqual(a["matched_executions"],1)

    def test_balance_audit_flags_quantity_and_cash_mismatch_without_trading(self):
        p=portfolio()
        b=parse_broker_balances_csv((
            "As Of,Asset,Quantity\n"
            "2026-10-17,IBIT.AX,109\n"
            "2026-10-17,BTC,0\n"
            "2026-10-17,AUD Cash,10000\n"
        ).encode(),today=TODAY)
        result=compare_broker_balances(p,b)
        self.assertEqual(result["discrepancy_count"],2)
        table={x["asset"]:x for x in result["rows"]}
        self.assertEqual(table["ASX:IBIT"]["portfolio_recorded"],108.)
        self.assertFalse(table["ASX:IBIT"]["matches"])
        self.assertTrue(table["Direct BTC"]["matches"])
        self.assertFalse(table["AUD Cash"]["matches"])
        self.assertFalse(result["broker_cash_after_tax_verified"])
        self.assertIn("NOT verified",result["cash_note"])

    def test_past_dated_balance_excludes_future_ledger_fills(self):
        p=portfolio()
        b=parse_broker_balances_csv((
            "As Of,Asset,Quantity\n"
            "2026-10-14,ASX:IBIT,100\n"
            "2026-10-14,AUD Cash,489980\n"
        ).encode(),today=TODAY)
        x=compare_broker_balances(p,b)
        self.assertEqual(x["discrepancy_count"],0)
        self.assertIn("Direct BTC",x["missing_assets_not_assumed_zero"])

    def test_other_broker_asset_and_us_ibit_not_silently_mapped(self):
        for raw in (
            "2026-10-15,BUY,IBIT,10,250,3,1",
            "2026-10-15,BUY,NASDAQ:IBIT,10,250,3,1",
            "2026-10-15,BUY,SHARES,10,250,3,1",
        ):
            with self.assertRaisesRegex(ValueError,"Unrecognised asset"):
                parse([raw])

    def test_missing_headers_unknown_fields_and_large_input_fail_closed(self):
        for raw in (
            b"Date,Side,Asset,Units,Gross AUD,Fee AUD\n2026-10-15,BUY,ASX:IBIT,1,20,3",
            b"Date,Side,Asset,Units,Gross AUD,Fee AUD,Reference,Secret\n"
            b"2026-10-15,BUY,ASX:IBIT,1,20,3,abc,xxx",
            b"bad input",
        ):
            with self.assertRaises(ValueError):
                parse_broker_executions_csv(raw,today=TODAY)
        with self.assertRaisesRegex(ValueError,"bytes"):
            parse_broker_executions_csv(
                b"X"*(MAX_BYTES+1),today=TODAY)

    def test_bad_date_fractional_ibit_negative_fee_and_repeated_ref_rejected(self):
        bad=[
            "2026-10-18,BUY,ASX:IBIT,1,50,3,FUTURE",
            "2026-10-15,BUY,ASX:IBIT,1.2,50,3,FRACTION",
            "2026-10-15,BUY,ASX:IBIT,1,50,-3,NEG",
            "2026-10-15,BUY,ASX:IBIT,1,50,60,TOOBIG",
        ]
        for raw in bad:
            with self.assertRaises(ValueError):
                parse([raw])
        with self.assertRaisesRegex(ValueError,"Repeated"):
            parse(["2026-10-15,BUY,ASX:IBIT,1,50,3,REF",
                   "2026-10-15,BUY,ASX:IBIT,1,50,3,REF"])

    def test_bad_balance_duplicate_or_inconsistent_asof_fails_closed(self):
        for rows in (
            "2026-10-17,ASX:IBIT,10\n2026-10-17,IBIT.AX,10",
            "2026-10-17,ASX:IBIT,10\n2026-10-16,Direct BTC,1",
            "2026-10-17,AUD Cash,10",
            "2026-10-17,ASX:IBIT,10.8",
        ):
            with self.assertRaises(ValueError):
                parse_broker_balances_csv((
                    "As Of,Asset,Quantity\n"+rows+"\n").encode(),
                    today=TODAY)

    def test_statement_period_and_asof_validation(self):
        p=portfolio()
        b=parse(["2026-10-15,BUY,ASX:IBIT,10,250,3,ORDER-123"])
        with self.assertRaisesRegex(ValueError,"outside"):
            compare_broker_transactions(p,b,start_date="2026-10-16",
                                        end_date="2026-10-17")
        with self.assertRaisesRegex(ValueError,"period"):
            compare_broker_transactions(p,b,start_date="2026-10-17",
                                        end_date="2026-10-15")
        p["sales"][0]["Units Sold"]=1000
        with self.assertRaisesRegex(ValueError,"exceeds"):
            compare_broker_transactions(p,b,start_date="2026-10-15",
                                        end_date="2026-10-17")


if __name__=="__main__":
    unittest.main()
