"""Research-only deterministic tests for signal-based DCA duration and VWAP."""
import unittest

import pandas as pd

from engines.research.adaptive_dca_execution import (
    audit_error_rates, group_trade_legs, report_adaptive,
    simulate_adaptive,
)


def fixture(prices, risks):
    return pd.DataFrame(
        {"btc_price_aud":prices, "risk_score":risks},
        index=pd.date_range("2018-01-01",periods=len(prices),
                            freq="W-MON",tz="UTC"),
    )


class AdaptiveDcaExecutionTests(unittest.TestCase):
    def test_purchase_effective_average_uses_btc_quantity_not_mean_of_prices(self):
        orders=[
            dict(date="2020-01-01",side="BUY",btc_quantity=100/110,
                 gross_notional_aud=100,fee_aud=0),
            dict(date="2020-01-08",side="BUY",btc_quantity=100/140,
                 gross_notional_aud=100,fee_aud=0),
        ]
        group=group_trade_legs(orders)
        self.assertEqual(len(group),1)
        self.assertAlmostEqual(group[0]["vwap_price_aud"],123.2,places=3)
        self.assertAlmostEqual((group[0]["vwap_price_aud"]/100-1)*100,23.2,places=2)

    def test_sale_effective_average_is_quantity_weighted(self):
        orders=[
            dict(date="2020-01-01",side="SELL",btc_quantity=.5,
                 gross_notional_aud=85,fee_aud=0),
            dict(date="2020-01-08",side="SELL",btc_quantity=.5,
                 gross_notional_aud=70,fee_aud=0),
        ]
        result=group_trade_legs(orders)[0]
        self.assertAlmostEqual(result["vwap_price_aud"],155)
        self.assertAlmostEqual((1-result["vwap_price_aud"]/200)*100,22.5)

    def test_flat_fee_exactly_once_per_filled_order(self):
        risks=[0.8]*150
        risks[0:28]=[0.10]*28
        prices=[100.]*150
        result=simulate_adaptive(fixture(prices,risks))
        self.assertGreater(result["buy_orders"],0)
        self.assertAlmostEqual(result["fee_total_aud"],3*result["trade_count"])
        self.assertGreaterEqual(result["cash_aud"],-1e-9)
        self.assertGreaterEqual(result["btc"],-1e-9)
        self.assertAlmostEqual(
            result["ending_equity_aud"],
            result["cash_aud"]+result["btc"]*prices[-1],
        )

    def test_trade_duration_flexible_and_pauses_allowed(self):
        risks=[.5]*200
        risks[0:18]=[.1]*18
        risks[70:86]=[.1]*16
        prices=[100.]*200
        data=fixture(prices,risks)
        r=simulate_adaptive(data)
        buys=[x for x in r["trades"] if x["side"]=="BUY"]
        self.assertGreater(len(buys),18)
        legs=group_trade_legs(r["trades"])
        self.assertEqual(len(legs),1)
        self.assertEqual(legs[0]["side"],"BUY")
        self.assertGreater(
            (pd.Timestamp(legs[0]["end"])-pd.Timestamp(legs[0]["start"])).days,
            40*7,
        )

    def test_prior_week_causality_under_future_price_and_risk_changes(self):
        risks=[.1]*15+[.5]*40+[.8]*30+[.5]*85
        prices=[100.+i*0.3 for i in range(170)]
        data=fixture(prices,risks)
        full=simulate_adaptive(data)
        cutoff=100
        mutated=data.copy()
        mutated.iloc[cutoff:]=[10000.,1.]
        changed=simulate_adaptive(mutated)
        baseline=[t for t in full["trades"]
                  if pd.Timestamp(t["date"]) < data.index[cutoff]]
        revised=[t for t in changed["trades"]
                 if pd.Timestamp(t["date"]) < data.index[cutoff]]
        self.assertEqual(baseline,revised)

    def test_sell_requires_trailing_evidence_and_does_not_sell_early(self):
        prices=[100.+i for i in range(110)]+[210-10*(i-110) for i in range(110,140)]+[100.]*60
        risks=[.1]*32+[.5]*30+[.7]*70+[.5]*68
        data=fixture(prices,risks)
        r=simulate_adaptive(data,confirm_drawdown=.15)
        sell=[t for t in r["trades"] if t["side"]=="SELL"]
        self.assertGreater(len(sell),0)
        self.assertTrue(all(pd.Timestamp(t["date"]) >= data.index[110] for t in sell))
        self.assertTrue(all(t["reason"]=="armed_drawdown_and_trend" for t in sell))

    def test_report_and_censored_scoring(self):
        prices=[100.+(i%30) for i in range(190)]
        risks=[.1]*25+[.5]*50+[.8]*60+[.1]*55
        report=report_adaptive(fixture(prices,risks))
        self.assertEqual(len(report["candidates"]),3)
        self.assertTrue(all(c["fee_total_aud"]==3*c["trade_count"]
                            for c in report["candidates"]))
        self.assertTrue(all("pairs_eligible" in c["accuracy"]
                            for c in report["candidates"]))


if __name__=="__main__":
    unittest.main()
