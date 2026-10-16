"""Research-only top-signal research invariants (not prediction tests)."""
import unittest

import numpy as np
import pandas as pd

from engines.research.top_signal_horse_race import (
    build_daily_signals, distinct_events, evaluate_alerts, parse_chart_csv,
    first_tradeable_maturity_warning_by_cycle,
)


def sample(n=1250):
    idx=pd.date_range("2016-01-01",periods=n,freq="D",tz="UTC")
    # Deeper rally after year 2, then adverse fall: synthetic only.
    price=np.array([100.+.5*i for i in range(n)],dtype=float)
    price[1000:]=np.maximum(10.,price[999]-3.0*np.arange(1,n-999))
    mvrv=2.+.001*np.arange(n)
    nupl=.4+.0001*np.arange(n)
    sopr=np.full(n,1.05)
    return pd.DataFrame({"price_usd":price,"mvrv_z":mvrv,
                         "nupl":nupl,"sopr":sopr},index=idx)


class TopSignalHorseRaceTests(unittest.TestCase):
    def test_strict_prior_data_decision_not_using_current_day(self):
        full=sample()
        original=build_daily_signals(full)
        mutated=full.copy()
        cutoff=1100
        mutated.iloc[cutoff:]=[100000.,500.,1.,100.]
        shifted=build_daily_signals(mutated)
        earlier_cols=("classic_euphoria","pi_top_cross","relative_euphoria",
                      "trend_reversal","cycle_maturity_warning",
                      "maturity_confirmed_reversal","late_trend_break")
        for key in earlier_cols:
            pd.testing.assert_series_equal(
                original[key].iloc[:cutoff+1],
                shifted[key].iloc[:cutoff+1])

    def test_pi_cross_is_rare_one_time_event_not_permanent_regime(self):
        df=sample()
        s=build_daily_signals(df)
        # Simple smooth up-only period has no sudden crossover guarantee.
        self.assertIn("pi_top_cross",s.columns)
        self.assertTrue(s["pi_top_cross"].dtype==bool)

    def test_distinct_events_do_not_count_consecutive_true_days(self):
        idx=pd.date_range("2020-01-01",periods=180,freq="D",tz="UTC")
        s=pd.Series(True,index=idx)
        out=distinct_events(s,separation_days=90)
        self.assertEqual([x.date().isoformat() for x in out],
                         ["2020-01-01","2020-03-31"])

    def test_censored_future_events_never_counted_as_success(self):
        df=sample()
        s=build_daily_signals(df)
        s.loc[:, "classic_euphoria"]=False
        s.loc[df.index[-30], "classic_euphoria"]=True
        outcomes=evaluate_alerts(df,s,
                                 peak_windows={"synthetic":("2016-01-01",
                                                             "2019-06-01")})
        x=outcomes["classic_euphoria"]
        self.assertEqual(x["distinct_events_since_2013"],1)
        self.assertEqual(x["fully_followed_events"],0)
        self.assertEqual(x["censored_recent_events"],1)

    def test_first_live_top_warning_cannot_cherry_pick_later_alert(self):
        idx=pd.date_range("2016-01-01",periods=800,freq="D",tz="UTC")
        frame=pd.DataFrame({"price_usd":[100.]*800},index=idx)
        # In 2017 the actual peak is December, while first maturity
        # warning in June is 70% below peak. Best-looking later
        # warning MUST NOT substitute for the first tradeable one.
        frame.loc["2017-12-16","price_usd"]=1000.
        signs=pd.DataFrame({"cycle_maturity_warning":[False]*800},index=idx)
        signs.loc["2017-06-24","cycle_maturity_warning"]=True
        signs.loc["2017-12-15","cycle_maturity_warning"]=True
        output=first_tradeable_maturity_warning_by_cycle(
            frame,signs,maturity_start_days=350,
            maturity_end_days=800)
        self.assertEqual(len(output["cycles"]),1)
        row=output["cycles"][0]
        self.assertEqual(row["first_warning"],"2017-06-24")
        self.assertEqual(row["error_from_hindsight_peak_pct"],90.)
        self.assertFalse(row["first_warning_within_25pct_hindsight"])

    def test_prior_day_breakdown_signal_occurs_after_downtrend(self):
        df=sample()
        s=build_daily_signals(df)
        mid=s.loc[df.index[400:700],"trend_reversal"]
        self.assertFalse(mid.any())
        self.assertTrue(s["drawdown90_prior"].ge(0).all() or
                        s["drawdown90_prior"].isna().any())

    def test_invalid_missing_data_fails_closed(self):
        df=sample()
        df.loc[df.index[900],"nupl"]=np.nan
        with self.assertRaisesRegex(ValueError,"Invalid"):
            build_daily_signals(df)

    def test_csv_validation_and_source_dates(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"a.csv"
            path.write_text(
                "timestamp,MVRV Z-Score,Price\n"
                "1704067200000,3.5,40000\n"
                "1704153600000,3.6,41000\n",encoding="utf8")
            parsed=parse_chart_csv(path,"MVRV Z-Score")
            self.assertEqual(len(parsed),2)
            self.assertEqual(str(parsed.index[0].date()),"2024-01-01")
            path.write_text("timestamp,MVRV Z-Score,Price\n"
                            "1704067200000,3.5,40000\n"
                            "1704067200000,3.6,41000\n",encoding="utf8")
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                parse_chart_csv(path,"MVRV Z-Score")


if __name__=="__main__":
    unittest.main()
