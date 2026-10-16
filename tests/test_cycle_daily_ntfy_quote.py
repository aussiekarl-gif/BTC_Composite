import datetime as dt
import unittest
from unittest.mock import patch
from engines.research.ibit_quote import parse_ibit_quote,fetch_ibit_quote
from cycle_trading_daily_ntfy import daily_message

NOW=dt.datetime(2026,10,17,2,0,tzinfo=dt.timezone.utc)

def payload(price=22.42,currency="AUD",symbol="IBIT.AX",stamp=None):
    stamp=stamp or int((NOW-dt.timedelta(hours=3)).timestamp())
    return {"chart":{"result":[{"meta":{
        "regularMarketPrice":price,"currency":currency,
        "symbol":symbol,"regularMarketTime":stamp}}]}}


class IBITQuoteAndNotificationTests(unittest.TestCase):
    def test_asx_aud_symbol_only(self):
        a=parse_ibit_quote(payload(),now=NOW)
        self.assertEqual(a["price_aud"],22.42)
        self.assertEqual(a["symbol"],"ASX:IBIT")
        self.assertTrue(a["indicative_only"])
        self.assertIsNone(parse_ibit_quote(payload(symbol="IBIT"),now=NOW))
        self.assertIsNone(parse_ibit_quote(payload(currency="USD"),now=NOW))
        self.assertIsNone(parse_ibit_quote(payload(price=0),now=NOW))
    def test_old_or_future_prices_are_not_substituted(self):
        old=int((NOW-dt.timedelta(days=8)).timestamp())
        future=int((NOW+dt.timedelta(days=1)).timestamp())
        self.assertIsNone(parse_ibit_quote(payload(stamp=old),now=NOW))
        self.assertIsNone(parse_ibit_quote(payload(stamp=future),now=NOW))
        self.assertIsNone(parse_ibit_quote({},now=NOW))
    def test_daily_message_is_one_cycle_summary_without_portfolio_numbers(self):
        quote=parse_ibit_quote(payload(),now=NOW)
        day,message=daily_message(now=NOW,quote=quote,market=None)
        self.assertEqual(day,"2026-10-17")
        self.assertIn("ASX:IBIT A$22.42",message)
        self.assertIn("Cycle signal: DATA UNAVAILABLE",message)
        self.assertNotIn("Production:",message)
        self.assertNotIn("A$500,000",message)
        self.assertNotIn("V5.9",message)
    def test_quote_network_fail_closed(self):
        with patch("engines.research.ibit_quote.requests.get",side_effect=RuntimeError("unavailable")):
            with self.assertRaises(RuntimeError):
                fetch_ibit_quote()
    def test_retired_ntfy_files_have_no_scheduled_legacy_sender(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        retired=(root/".github/workflows/dca_model_compare_notify.yml").read_text()
        self.assertNotIn("cron:",retired)
        self.assertNotIn("NTFY_TOPIC",retired)
        validation=(root/".github/workflows/validation_research_tuning.yml").read_text()
        self.assertNotIn("NTFY_TOPIC",validation)
        daily=(root/".github/workflows/cycle_trading_daily_ntfy.yml").read_text()
        self.assertEqual(daily.count("cron:"),1)
        self.assertIn("last_cycle_ntfy_date.txt",daily)
        self.assertNotIn("  workflow_dispatch:",daily.split("jobs:")[0])


if __name__=="__main__":
    unittest.main()
