"""Native broker CSV mapping: no assumed FX, ticker, side or fee semantics."""
import copy
import unittest

from engines.research.cycle_broker_csv_mapping import (
    read_unmapped_csv,source_column_values,
    map_native_broker_executions,map_native_broker_balances,
)
from engines.research.cycle_broker_csv_reconciliation import (
    compare_broker_transactions,compare_broker_balances,
)
from tests.test_cycle_broker_csv_reconciliation import portfolio

NOW="2026-10-17"


def data(text):
    return text.encode("utf-8-sig")


TRADE=(
    "Trade Date,Action,Ticker,Amount,Consideration,Commission,CCY,Order No\n"
    "2026-10-15,Acquired,IBIT,10,250.00,3.00,AUD,ORDER-123\n"
    "2026-10-16,Disposed,IBIT,2,60.00,3.00,AUD,ORDER-124\n"
)
COLUMNS={
    "Date":"Trade Date","Side":"Action","Asset":"Ticker",
    "Units":"Amount","Gross AUD":"Consideration",
    "Fee AUD":"Commission","Currency":"CCY","Reference":"Order No",
}
SIDE={"Acquired":"BUY","Disposed":"SELL"}
ASSET={"IBIT":"ASX:IBIT"}


def normalize(blob=None,**override):
    kwargs=dict(
        data=data(TRADE) if blob is None else blob,
        columns=COLUMNS,side_values=SIDE,asset_values=ASSET,
        confirmed_aud=True,confirmed_asx=True,today=NOW,
    )
    kwargs.update(override)
    return map_native_broker_executions(**kwargs)


class NativeCsvMappingTests(unittest.TestCase):
    def test_native_trade_columns_require_explicit_asset_aud_and_action(self):
        blob=data(TRADE)
        columns,rows=read_unmapped_csv(blob)
        self.assertEqual(columns[0],"Trade Date")
        self.assertEqual(len(rows),2)
        self.assertEqual(source_column_values(blob,"Action"),
                         ["Acquired","Disposed"])
        normalized=normalize()
        self.assertEqual(len(normalized),2)
        self.assertEqual(normalized[0]["asset"],"ASX:IBIT")
        self.assertEqual(normalized[1]["side"],"SELL")
        self.assertEqual(normalized[0]["reference"],"ORDER-123")
        before=portfolio()
        copy_before=copy.deepcopy(before)
        audit=compare_broker_transactions(
            before,normalized,
            start_date="2026-10-15",end_date=NOW,
            complete_statement_confirmed=True)
        self.assertEqual(audit["matched_executions"],2)
        self.assertEqual(before,copy_before)

    def test_us_dollars_and_unconfirmed_currency_block_mapping(self):
        wrong=data(TRADE.replace(",AUD,",",USD,"))
        with self.assertRaisesRegex(ValueError,"not AUD"):
            normalize(blob=wrong)
        with self.assertRaisesRegex(ValueError,"Confirm all money"):
            normalize(confirmed_aud=False)
        no_currency={k:v for k,v in COLUMNS.items() if k!="Currency"}
        with self.assertRaisesRegex(ValueError,"Confirm all money"):
            normalize(columns=no_currency,confirmed_aud=False)
        valid=normalize(columns=no_currency,confirmed_aud=True)
        self.assertEqual(len(valid),2)

    def test_ambiguous_ibit_needs_explicit_asx_listing_confirmation(self):
        with self.assertRaisesRegex(ValueError,"Australian ASX"):
            normalize(confirmed_asx=False)
        with self.assertRaisesRegex(ValueError,"Unmapped broker Asset"):
            normalize(asset_values={})
        with self.assertRaisesRegex(ValueError,"Invalid broker Asset"):
            normalize(asset_values={"IBIT":"US:IBIT"})
        with self.assertRaisesRegex(ValueError,"Unmapped broker Side"):
            normalize(side_values={"Acquired":"BUY"})

    def test_asset_fixed_mode_requires_asset_confirmation(self):
        columns={k:v for k,v in COLUMNS.items() if k!="Asset"}
        a=normalize(columns=columns,asset_values={},
                    fixed_asset="ASX:IBIT",confirmed_asx=True)
        self.assertEqual(len(a),2)
        with self.assertRaisesRegex(ValueError,"fixed asset"):
            normalize(columns=columns,fixed_asset=None)

    def test_unknown_duplicated_fields_and_bad_native_rows_fail_closed(self):
        duplicate=data("Name, Name,Unit\na,b,10\n")
        with self.assertRaisesRegex(ValueError,"repeated header"):
            read_unmapped_csv(duplicate)
        with self.assertRaisesRegex(ValueError,"two meanings"):
            normalize(columns={**COLUMNS,"Units":"Consideration"})
        with self.assertRaisesRegex(ValueError,"missing"):
            source_column_values(data(TRADE),"Unknown")
        with self.assertRaises(ValueError):
            normalize(blob=data(TRADE.replace("10,250.00","10,not_money")))
        with self.assertRaises(ValueError):
            normalize(blob=data(TRADE.replace("10,250.00","10.5,250.00")))
        with self.assertRaisesRegex(ValueError,"Unsafe spreadsheet formula"):
            normalize(blob=data(TRADE.replace("ORDER-123","=1+1")))

    def test_missing_fee_requires_explicit_zero_fee_confirmation(self):
        columns={k:v for k,v in COLUMNS.items() if k!="Fee AUD"}
        with self.assertRaisesRegex(ValueError,"fee"):
            normalize(columns=columns,confirmed_fee_free=False)
        out=normalize(columns=columns,confirmed_fee_free=True)
        self.assertEqual(out[0]["fee"],0)
        self.assertEqual(len(out),2)

    def test_native_duplicate_fills_are_not_silently_repaired(self):
        duplicate=data(
            "Date,Side,Symbol,Quantity,Gross,Fee,Currency,Ref\n"
            "2026-10-15,B,IBIT,10,250,3,AUD,\n"
            "2026-10-15,B,IBIT,10,250,3,AUD,\n"
        )
        fields=dict(Date="Date",Side="Side",Asset="Symbol",
                    Units="Quantity",**{"Gross AUD":"Gross","Fee AUD":"Fee",
                                        "Currency":"Currency","Reference":"Ref"})
        output=normalize(
            blob=duplicate,columns=fields,side_values={"B":"BUY"})
        p=portfolio()
        audit=compare_broker_transactions(
            p,output,start_date="2026-10-15",end_date=NOW)
        self.assertEqual(audit["matched_executions"],0)
        self.assertGreater(audit["ambiguous_rows"],0)

    def test_native_balance_mapping_with_one_explicit_snapshot(self):
        balances=data(
            "Symbol,Position,Money\n"
            "IBIT.AX,108,AUD\n"
            "BTC,0,BTC\n"
            "Cash,490000,AUD\n"
        )
        fields={"Asset":"Symbol","Quantity":"Position","Currency":"Money"}
        out=map_native_broker_balances(
            balances,columns=fields,
            asset_values={"IBIT.AX":"ASX:IBIT",
                          "BTC":"Direct BTC","Cash":"AUD Cash"},
            fixed_asof=NOW,confirmed_cash_aud=True,
            confirmed_asx=True,today=NOW)
        self.assertEqual(out["positions"]["ASX:IBIT"],108)
        result=compare_broker_balances(portfolio(),out)
        self.assertEqual(result["rows"][0]["asset"],"ASX:IBIT")
        self.assertFalse(result["broker_cash_after_tax_verified"])

    def test_native_balance_cash_currency_and_date_must_be_proven(self):
        balances=data("Symbol,Position,Money\nIBIT.AX,108,AUD\nCash,2,USD\n")
        f={"Asset":"Symbol","Quantity":"Position","Currency":"Money"}
        mappings={"IBIT.AX":"ASX:IBIT","Cash":"AUD Cash"}
        base=dict(columns=f,asset_values=mappings,
                  fixed_asof=NOW,confirmed_asx=True,today=NOW)
        with self.assertRaisesRegex(ValueError,"Non-AUD"):
            map_native_broker_balances(balances,confirmed_cash_aud=True,**base)
        with self.assertRaisesRegex(ValueError,"Confirm cash"):
            map_native_broker_balances(balances,confirmed_cash_aud=False,**base)
        with self.assertRaisesRegex(ValueError,"dated"):
            map_native_broker_balances(
                balances,columns=f,asset_values=mappings,
                confirmed_asx=True,confirmed_cash_aud=True,today=NOW)

    def test_future_source_snapshot_and_missing_currency_block(self):
        blob=data("Date,Asset,Qty\n2026-10-18,IBIT.AX,100\n")
        with self.assertRaisesRegex(ValueError,"future"):
            map_native_broker_balances(
                blob,columns={"As Of":"Date","Asset":"Asset",
                              "Quantity":"Qty"},
                asset_values={"IBIT.AX":"ASX:IBIT"},confirmed_asx=True,
                today=NOW)


if __name__=="__main__":
    unittest.main()
