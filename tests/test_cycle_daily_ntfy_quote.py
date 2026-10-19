import datetime as dt
import unittest
from unittest.mock import patch,Mock
from engines.research.ibit_quote import parse_ibit_quote,fetch_ibit_quote
from cycle_trading_daily_ntfy import daily_message,send_ntfy,format_mobile_notification

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
        with patch("cycle_trading_daily_ntfy.read_exported_history",side_effect=RuntimeError("offline")):
            day,message=daily_message(now=NOW,quote=quote,market=None)
        self.assertEqual(day,"2026-10-17")
        self.assertIn("ASX:IBIT A$22.42",message)
        self.assertIn("Cycle signal: DATA UNAVAILABLE",message)
        self.assertIn("Production: no data",message)
        self.assertIn("Research: no data",message)
        self.assertNotIn("A$500,000",message)
        self.assertNotIn("V5.9",message)
    def test_ntfy_http_headers_are_latin1_safe(self):
        # Requests encodes HTTP header values as Latin-1. A Unicode em dash
        # in Title previously prevented *every* daily notification.
        response=Mock()
        with patch("cycle_trading_daily_ntfy.requests.post",return_value=response) as send:
            send_ntfy("One requested test",topic="unit-test-channel")
        response.raise_for_status.assert_called_once()
        args=send.call_args
        self.assertEqual(args.args[0],"https://ntfy.sh/unit-test-channel")
        self.assertEqual(args.kwargs["data"],b"One requested test")
        for value in args.kwargs["headers"].values():
            value.encode("latin-1")
        self.assertEqual(args.kwargs["headers"]["Title"],"BTC Cycle Trading - Daily")
        self.assertEqual(args.kwargs["headers"]["Markdown"],"yes")

    def test_mobile_markdown_hold_layout_is_action_first(self):
        lines=[
            "Cycle Trading daily | 2026-10-17 Brisbane",
            "ASX:IBIT A$22.41 (indicative, delayed)",
            "ETF quote dated 2026-10-16 UTC",
            "BTC close US$81,567 (2026-10-15)",
            "Prior 200WMA US$66,909",
            "Cycle signal: HOLD",
            "BUY allocation: 0.00% of available AUD cash",
            "SELL allocation: 0.00% of current BTC/IBIT holdings",
            "Reason: No eligible Cycle Trading research signal.",
            "Halving day: 908 (since 2024-04-20)",
            "Production: no trade to compare (risk 0.27)",
            "Research: no trade to compare (risk 0.00; near Power Law floor, not zero investment risk)",
            "Market-only % per eligible tranche; no Google Sheets/broker access; not a broker order.",
            "Research only: verify broker holdings, quote and SMSF tax before trading.",
        ]
        rendered=format_mobile_notification(lines)
        self.assertIn("## ⏸️ Cycle signal: HOLD",rendered)
        self.assertIn("**BUY allocation: 0.00%**",rendered)
        self.assertIn("**SELL allocation: 0.00%**",rendered)
        self.assertLess(rendered.index("Cycle signal: HOLD"),rendered.index("BTC close US$"))
        self.assertIn("**📈 MARKET SNAPSHOT**",rendered)
        self.assertIn("**🧭 OTHER MODELS**",rendered)
        self.assertIn("Production: no trade to compare (risk 0.27)",rendered)
        self.assertIn("Research: no trade to compare (risk 0.00;",rendered)
        self.assertIn("Market-only % per eligible tranche",rendered)
        self.assertNotIn("Reason: No eligible Cycle Trading",rendered)

    def test_mobile_markdown_buy_and_major_red_flag_are_emphasized(self):
        lines=[
            "Cycle Trading daily | 2026-10-17 Brisbane",
            "Cycle signal: BUY WATCH",
            "BUY allocation: 2.50% of available AUD cash",
            "SELL allocation: 0.00% of current BTC/IBIT holdings",
            "Reason: BTC below strict 200WMA.",
            "⚠ MAJOR RED FLAG — Both references at extreme risk",
            "BTC close US$81,567 (2026-10-15)",
            "Production: disagrees (risk 0.90)",
            "Research: disagrees (risk 0.93)",
        ]
        body=format_mobile_notification(lines)
        self.assertIn("## 🟢 Cycle signal: BUY WATCH",body)
        self.assertIn("**BUY allocation: 2.50%**",body)
        self.assertIn("**🚨 REVIEW BEFORE TRADING**",body)
        self.assertEqual(body.count("MAJOR RED FLAG"),1)
        self.assertLess(body.index("REVIEW BEFORE TRADING"),body.index("BUY allocation:"))
        self.assertIn("Reason: BTC below strict 200WMA.",body)

    def test_mobile_markdown_keeps_unavailable_data_and_unknown_notes(self):
        body=format_mobile_notification([
            "Cycle Trading daily | 2026-10-17 Brisbane",
            "ASX:IBIT quote: unavailable/stale — check broker",
            "Cycle signal: DATA UNAVAILABLE — no trade recommendation",
            "BUY allocation: unavailable | SELL allocation: unavailable",
            "Production: no data",
            "Research: no data",
            "Extra model metadata not recognized",
        ])
        self.assertIn("Cycle signal: DATA UNAVAILABLE",body)
        self.assertIn("ASX:IBIT quote: unavailable",body)
        self.assertIn("SELL allocation: unavailable",body)
        self.assertIn("Extra model metadata not recognized",body)

    def test_ntfy_push_title_is_short_and_major_warnings_are_prominent(self):
        response=Mock()
        bodies=[
            ("## ⏸️ Cycle signal: HOLD", "BTC Cycle - HOLD", "default", "chart_with_upwards_trend"),
            ("## 🟢 Cycle signal: BUY WATCH", "BTC Cycle - BUY WATCH", "default", "chart_with_upwards_trend"),
            ("## 🟠 Cycle signal: SELL WATCH", "BTC Cycle - SELL WATCH", "default", "chart_with_upwards_trend"),
            ("> MAJOR RED FLAG\\n## 🟢 Cycle signal: BUY WATCH","BTC Cycle - MAJOR WARNING","high","warning"),
        ]
        with patch("cycle_trading_daily_ntfy.requests.post",return_value=response) as post:
            for body,title,priority,tags in bodies:
                send_ntfy(body,topic="unit-test-channel")
                headers=post.call_args.kwargs["headers"]
                self.assertEqual(headers["Title"],title)
                self.assertEqual(headers["Priority"],priority)
                self.assertEqual(headers["Tags"],tags)
                self.assertEqual(headers["Markdown"],"yes")
                for field in headers.values():
                    field.encode("latin-1")
        self.assertEqual(post.call_count,len(bodies))

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
        self.assertEqual(daily.count("cron:"),3)
        self.assertEqual(daily.count("cron: '0 0 * * *'"),1)
        self.assertEqual(daily.count("cron: '15 0 * * *'"),1)
        self.assertEqual(daily.count("cron: '35 0 * * *'"),1)
        self.assertNotIn("cron: '0 22 * * *'",daily)
        # Brisbane never changes clocks; both UTC times are Brisbane-local
        # 10:00 and 10:15 respectively, including in southern summer.
        from zoneinfo import ZoneInfo
        for date in (dt.date(2026,1,17),dt.date(2026,10,17)):
            primary=dt.datetime.combine(date,dt.time(0),tzinfo=dt.timezone.utc)
            backup=primary+dt.timedelta(minutes=15)
            later=primary+dt.timedelta(minutes=35)
            self.assertEqual(primary.astimezone(ZoneInfo("Australia/Brisbane")).strftime("%H:%M"),"10:00")
            self.assertEqual(backup.astimezone(ZoneInfo("Australia/Brisbane")).strftime("%H:%M"),"10:15")
            self.assertEqual(later.astimezone(ZoneInfo("Australia/Brisbane")).strftime("%H:%M"),"10:35")
        self.assertIn("last_cycle_ntfy_date.txt",daily)
        self.assertIn("group: btc-cycle-daily-notify-global",daily)
        self.assertIn('if [[ "$previous" == "$today" ]]',daily)
        self.assertIn('SEND_NTFY=no',daily)
        self.assertIn('SEND_NTFY=yes',daily)
        self.assertIn('id: delivery_precheck',daily)
        self.assertIn("TZ=Australia/Brisbane date +%F",daily)
        self.assertEqual(daily.count("if: steps.delivery_precheck.outputs.already_reserved != 'true'"),4)
        self.assertIn("already_reserved=true",daily)
        self.assertIn("group: btc-cycle-daily-notify-global",daily)
        self.assertNotIn("  workflow_dispatch:",daily.split("jobs:")[0])


    def test_repository_has_only_one_ntfy_sender_and_daily_schedule(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        workflows=root/".github"/"workflows"
        candidates=[]
        for path in workflows.glob("*.yml"):
            content=path.read_text(encoding="utf-8")
            if "secrets.NTFY_TOPIC" in content:
                candidates.append(path.name)
        self.assertEqual(candidates,["cycle_trading_daily_ntfy.yml"])
        retired=(root/"dca_model_compare_notify.py").read_text(encoding="utf-8")
        self.assertNotIn("requests.post(",retired)
        self.assertNotIn("def send_ntfy(",retired)
        self.assertIn("Retired: dual-model ntfy",retired)

    def test_cycle_trading_is_first_and_fresh_session_default(self):
        from pathlib import Path
        app=(Path(__file__).resolve().parents[1]/"app.py").read_text(encoding="utf-8")
        self.assertIn(
            '["Cycle Trading — Research", "Production", "Research", '
            '"Bottom Signal Timeline"]',app)
        self.assertIn('index=0,',app)
        self.assertIn('"Production": Path(__file__).parent',app)
        self.assertIn('"Research": Path(__file__).parent',app)


if __name__=="__main__":
    unittest.main()
