"""Deterministic GitHub Markdown dashboard for the frozen VBTC forward paper study.

Source: validated append-only scoreboards, never live broker balances.
No current timestamp, so earlier dashboard contents remain reproducible.
"""
import argparse,json
from pathlib import Path
from engines.research.forward_paper_200wma import ROOT,SCORE,config_read

DASH=ROOT/"DASHBOARD.md"
TITLES={
  "baseline_dca":"Simple DCA control",
  "tier_12buy_16sell":"12-week buys / 16-week sells",
  "tier_12buy_16sell_recycle26":"12/16-week + 26-week cash recycling"
}
RUNS="https://github.com/aussiekarl-gif/BTC_Composite/actions/workflows/research_vbtc_wednesday_scheduler.yml"
SOURCE="https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_forward/200wma_v1/README.md"

def money(v):
    return f"A${float(v):,.2f}"

def percent(v):
    return f"{float(v):+,.2f}%"

def safe_score(config_hash):
    if not SCORE.exists():return None
    data=json.loads(SCORE.read_text())
    if data.get("config_sha256")!=config_hash:
        raise ValueError("Dashboard refuses an unfrozen/different paper configuration")
    if data.get("schema")!="btc-200wma-forward-scoreboard-v1":
        raise ValueError("Invalid or legacy paper scoreboard schema")
    weeks=data.get("weeks",{})
    dates=list(weeks)
    if dates!=sorted(set(dates)):
        raise ValueError("Paper dashboard observations are not strictly increasing")
    if len(weeks)!=data.get("completed_weeks"):
        raise ValueError("Paper scoreboard week count inconsistent")
    if dates and data.get("last_week")!=dates[-1]:
        raise ValueError("Last completed scoreboard week disagrees with history")
    return data

def build(data,config):
    lines=[
        "# BTC 200WMA — Research paper-trading dashboard",
        "",
        "**SIMULATED portfolios, not actual ETF holdings or executable trades.** Research only; Production V5.8.2 is unchanged.",
        "",
        f"**Initial notional capital:** {money(config['capital_aud'])} per strategy. **First eligible completed signal:** {config['earliest_first_completed_week_utc']}.",
        "",
    ]
    if not data or not data.get("weeks"):
        lines.extend([
            "## Current status: awaiting first completed weekly observation",
            "",
            "No forward-test trades or performance results exist yet. The earliest eligible BTC/USD weekly close is **19 October 2026 UTC**; data can be captured after the issuer releases the corresponding official VBTC market price.",
            "",
            "The dashboard will populate only from completed, timestamped, append-only research observations. Historical optimisation results are **not** mixed into this forward test.",
            "",
            "| Frozen portfolio | Status |",
            "|:--|:--|",
            "| Simple DCA control | Awaiting first paper entry |",
            "| 12-week buys / 16-week sells | Awaiting first paper entry |",
            "| 12/16-week + 26-week cash recycling | Awaiting first paper entry |",
            "",
        ])
    else:
        dates=list(data["weeks"])
        latest=data["weeks"][dates[-1]]
        market=latest["market"]
        latest_portfolios=latest["portfolios"]
        if set(latest_portfolios)!=set(TITLES):
            raise ValueError("Paper scoreboard does not contain the exact frozen portfolios")
        lines.extend([
            f"## Latest completed paper week: {dates[-1]}",
            "",
            f"**VBTC official last traded price:** {money(market['vbtc_traded_aud'])} per ETF unit; **NAV:** {money(market['vbtc_nav_aud'])}; **premium/discount:** {percent(market['vbtc_premium_pct'])}.",
            "",
            f"**BTC/USD deviation from completed 200WMA:** {percent(market['btc_usd_deviation_vs_200wma_pct'])}.",
            "",
            "## Side-by-side paper portfolio values",
            "",
            "| Simulated portfolio | Net of *modelled* CGT (AUD) | Return on A$500k | Vs DCA | Free cash (AUD) | Cash weight | ETF units | Simulated fills |",
            "|:--|--:|--:|--:|--:|--:|--:|--:|",
        ])
        for key,title in TITLES.items():
            item=latest_portfolios[key]
            net=float(item["portfolio_less_modelled_tax_aud"])
            gross=float(item["portfolio_gross_aud"])
            cash=float(item["free_cash_aud"])
            if gross<=0:raise ValueError("Invalid marked portfolio value")
            lines.append(f"| {title} | {money(net)} | {percent(100*(net/config['capital_aud']-1))} | "
                f"{percent(item['excess_vs_identical_dca_pct'])} | {money(cash)} | "
                f"{100*cash/gross:.1f}% | {float(item['etf_units']):,.4f} | "
                f"{int(item['historical_fill_count'])} |")
        lines.extend([
            "",
            "**Net of modelled CGT** = mark-to-market paper portfolio less outstanding simulated accumulation-phase CGT. Paid tax is already reflected in cash. No actual SMSF assessment or tax payment is implied.",
            "",
            "## Latest weekly paper fills",
            "",
            "| Portfolio | Side | Kind | Units | Assumed cash flow (AUD) |",
            "|:--|:--|:--|--:|--:|",
        ])
        trades=0
        for key,title in TITLES.items():
            for fill in latest_portfolios[key].get("week_fills",[]):
                trades+=1
                lines.append(f"| {title} | {fill['side']} | {fill['kind']} | "
                             f"{float(fill['units']):,.5f} | {money(fill['cash_aud'])} |")
        if trades==0:
            lines.append("| All three portfolios | No simulated fills this week | — | — | — |")
        lines.extend([
            "",
            "## Historical forward-paper comparison (latest twelve recorded weeks)",
            "",
            "| Completed week | Simple DCA net (AUD) | 12/16 trading vs DCA | 12/16 + cash recycling vs DCA |",
            "|:--|--:|--:|--:|",
        ])
        for day in dates[-12:]:
            portfolios=data["weeks"][day]["portfolios"]
            lines.append(f"| {day} | {money(portfolios['baseline_dca']['portfolio_less_modelled_tax_aud'])} | "
               f"{percent(portfolios['tier_12buy_16sell']['excess_vs_identical_dca_pct'])} | "
               f"{percent(portfolios['tier_12buy_16sell_recycle26']['excess_vs_identical_dca_pct'])} |")
        lines.append("")
    lines.extend([
        "## Data integrity, limits and next run",
        "",
        f"- Frozen research settings: [paper-testing protocol]({SOURCE}).",
        f"- Wednesday 9:17am Brisbane scheduled job: [GitHub Actions]({RUNS}). GitHub may delay scheduled runs.",
        "- The weekly close and VBTC quoted price are **historical reference points**, not executable bid/ask prices. Simulated trading assumes A$20 per fill, 0.1% dealing fees, 0.5% slippage, and illustrative accumulation-phase SMSF tax.",
        "- Existing weekly observations cannot be overwritten; missing or revised data fails closed. Returns over a few paper weeks do **not** establish a statistically reliable edge.",
        "- If you want failure notifications, subscribe to the repository's GitHub Issues/Actions notifications; the workflow raises an issue for scheduler failures.",
        "",
    ])
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--write",action="store_true",help="Write a research-only Markdown dashboard")
    args=p.parse_args()
    config,digest=config_read()
    data=safe_score(digest)
    content=build(data,config)
    if args.write:
        DASH.parent.mkdir(parents=True,exist_ok=True)
        if not DASH.exists() or DASH.read_text()!=content:
            DASH.write_text(content)
            print("DASHBOARD_WRITTEN",DASH)
        else:print("DASHBOARD_UNCHANGED",DASH)
    else:print(content)

if __name__=="__main__":main()
