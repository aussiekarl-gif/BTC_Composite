"""Reconstruct distribution ORIGINAL holdings from an immutable trade ledger."""
import unittest
from engines.research.cycle_position_anchor import original_cycle_inventory


def row(side,date,asset,qty,price=20):
    if side=="BUY":
        return {"Date":date,"Asset":asset,
            "Units / BTC Received":qty,"AUD Spent":qty*price,
            "Brokerage / Fee AUD":0.,"BTC AUD Price":100000.}
    return {"Date":date,"Asset":asset,"Units Sold":qty,
            "AUD Proceeds":qty*price,"Brokerage / Fee AUD":0.}


class CyclePositionAnchorTests(unittest.TestCase):
    def test_real_2026_initial_funding_has_no_2025_legacy_position(self):
        saved={"starting_capital_aud":500000.,"rows":[
            row("BUY","01/01/26","ASX:IBIT",1000)
        ]}
        result=original_cycle_inventory(saved,"2024-04-20",asof="2026-10-16")
        self.assertFalse(result["eligible"])
        self.assertEqual(result["day500"],"2025-09-02")
        self.assertEqual(result["original_holdings"]["ASX:IBIT"],0.)
        self.assertIn("cannot apply legacy",result["reason"])

    def test_original_position_remains_constant_after_more_buying(self):
        saved={"starting_capital_aud":500000.,"rows":[
            row("BUY","01/06/25","ASX:IBIT",1000),
            row("BUY","01/10/25","ASX:IBIT",300),
            row("BUY","01/06/25","Direct BTC",.1,10000),
        ],"sales":[
            row("SELL","25/08/25","ASX:IBIT",100),
            row("SELL","04/09/25","ASX:IBIT",200),
            row("SELL","25/09/25","ASX:IBIT",350),
            row("SELL","25/09/25","Direct BTC",.03,10000)
        ]}
        result=original_cycle_inventory(saved,"2024-04-20",asof="2025-10-01")
        self.assertEqual(result["original_holdings"]["ASX:IBIT"],900)
        self.assertEqual(result["sold_from_original"]["ASX:IBIT"],550)
        self.assertEqual(result["remaining_original"]["ASX:IBIT"],350)
        self.assertAlmostEqual(result["original_sold_fraction"]["ASX:IBIT"],550/900)
        self.assertAlmostEqual(result["original_holdings"]["Direct BTC"],.1)
        self.assertAlmostEqual(result["remaining_original"]["Direct BTC"],.07)
        self.assertTrue(result["eligible"])

    def test_sales_cannot_count_as_original_beyond_original_inventory(self):
        saved={"starting_capital_aud":500000.,"rows":[
            row("BUY","01/06/25","ASX:IBIT",10),
            row("BUY","05/09/25","ASX:IBIT",100),
        ],"sales":[
            row("SELL","10/09/25","ASX:IBIT",50),
        ]}
        result=original_cycle_inventory(saved,"2024-04-20",asof="2025-10-01")
        self.assertEqual(result["original_holdings"]["ASX:IBIT"],10)
        self.assertEqual(result["sold_from_original"]["ASX:IBIT"],10)
        self.assertEqual(result["remaining_original"]["ASX:IBIT"],0)

    def test_asof_dates_do_not_read_future_recorded_sales(self):
        saved={"starting_capital_aud":500000.,"rows":[
            row("BUY","01/06/25","ASX:IBIT",10)
        ],"sales":[row("SELL","31/12/25","ASX:IBIT",5)]}
        a=original_cycle_inventory(saved,"2024-04-20",asof="2025-09-02")
        b=original_cycle_inventory(saved,"2024-04-20",asof="2026-01-01")
        self.assertEqual(a["sold_from_original"]["ASX:IBIT"],0)
        self.assertEqual(b["sold_from_original"]["ASX:IBIT"],5)

    def test_invalid_oversold_ledger_fails_closed(self):
        saved={"starting_capital_aud":500000.,
            "rows":[row("BUY","01/06/25","ASX:IBIT",5)],
            "sales":[row("SELL","01/07/25","ASX:IBIT",6)]}
        with self.assertRaises(ValueError):
            original_cycle_inventory(saved,"2024-04-20",asof="2026-01-01")


if __name__=="__main__":
    unittest.main()
