"""Research-only Coinbase/Kraken daily-close adapter safety tests."""
import unittest
import pandas as pd
from engines.research.cycle_coinbase_daily_reference import (
    parse_completed_coinbase_daily,compare_coinbase_kraken,
)

TODAY="2026-11-06"
def payload():
    start=pd.Timestamp("2026-10-30",tz="UTC")
    rows=[]
    for i in range(8):
        date=start+pd.Timedelta(days=i)
        rows.append([int(date.timestamp()),90.,110.,99.,100.,10.])
    return rows

class CoinbaseCompletedDailyTests(unittest.TestCase):
    def test_excludes_unfinished_today_and_sorts_descending_provider_rows(self):
        result=parse_completed_coinbase_daily(payload()[::-1],utc_today=TODAY)
        self.assertEqual(str(result.index[-1].date()),"2026-11-05")
        self.assertEqual(len(result),7)

    def test_duplicate_dates_rejected(self):
        rows=payload()
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            parse_completed_coinbase_daily(rows+[rows[0]],utc_today=TODAY)

    def test_malformed_and_nonmidnight_rejected(self):
        rows=payload()
        rows[0][0]+=3600
        with self.assertRaisesRegex(ValueError,"midnight"):
            parse_completed_coinbase_daily(rows,utc_today=TODAY)

    def test_same_date_agreement_is_research_only(self):
        c=parse_completed_coinbase_daily(payload(),utc_today=TODAY)
        k=c.copy(deep=True)
        report=compare_coinbase_kraken(c,k,utc_today=TODAY)
        self.assertEqual(report["status"],"RESEARCH_ONLY_VERIFIED")
        self.assertFalse(report["trading_enabled"])
        self.assertEqual(report["completed_close_utc"],"2026-11-05")

    def test_exchange_disagreement_fails_closed(self):
        c=parse_completed_coinbase_daily(payload(),utc_today=TODAY)
        k=c.copy(deep=True)
        k.iloc[-1,0]=105.
        with self.assertRaisesRegex(ValueError,"disagree"):
            compare_coinbase_kraken(c,k,utc_today=TODAY)

    def test_missing_yesterday_fails_closed(self):
        c=parse_completed_coinbase_daily(payload(),utc_today=TODAY)
        k=c.iloc[:-1].copy()
        with self.assertRaisesRegex(ValueError,"yesterday"):
            compare_coinbase_kraken(c,k,utc_today=TODAY)

if __name__=="__main__":
    unittest.main()
