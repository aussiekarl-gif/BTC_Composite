"""Prospective, append-only VBTC research paper journal.

No Production access or live trades. Each prospective weekly snapshot is
recorded only AFTER a completed W-MON BTC signal and an issuer-published
ASX ETF traded-price reference. Missing weeks are blocked rather than
retroactively filled. Replay is deterministic from the frozen observations.
"""
import argparse,hashlib,json,sys
from datetime import timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import requests

from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_exact_10x10 import CAP
from engines.research.smsf_cgt_ledger import FifoCgtLedger,AnnualSmsfTaxPayment
from engines.research.vbtc_official_history import download_history

ROOT=Path("research_forward/200wma_v1")
CONFIG=ROOT/"config_frozen.json"
EVENTS=ROOT/"weekly_observations.jsonl"
SCORE=ROOT/"scoreboard.json"
BLOCKCHAIN="https://api.blockchain.info/charts/market-price"


def iso(x):
    return pd.Timestamp(x).strftime("%Y-%m-%d")

def stable(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)

def config_read():
    config=json.loads(CONFIG.read_text())
    if config["capital_aud"]!=CAP or config["schema"]!="btc-200wma-paper-v1":
        raise ValueError("Unexpected changed frozen portfolio configuration")
    digest=hashlib.sha256(stable(config).encode()).hexdigest()
    return config,digest

def last_completed_monday(now):
    today=pd.Timestamp(now).normalize()
    monday=today-pd.Timedelta(days=today.weekday())
    if today.weekday()==0:monday-=pd.Timedelta(days=7)
    return monday

def btc_usd_history():
    response=requests.get(BLOCKCHAIN,params={"timespan":"all","format":"json","sampled":"false"},timeout=45)
    response.raise_for_status()
    values=response.json().get("values",[])
    s=pd.Series({pd.Timestamp(int(p["x"]),unit="s",tz="UTC"):float(p["y"])
                 for p in values if float(p["y"])>0}).sort_index()
    if len(s)<1500 or s.index.has_duplicates:
        raise ValueError("Invalid or insufficient BTC/USD source observations")
    weekly=s.resample("W-MON").last()
    if weekly.iloc[-215:].isna().any():
        raise ValueError("BTC USD history has gaps inside the 200WMA lookback")
    ma=weekly.shift(1).rolling(200,min_periods=200).mean()
    return weekly,ma,s.index.max()

def recorded():
    if not EVENTS.exists():return []
    rows=[json.loads(t) for t in EVENTS.read_text().splitlines() if t.strip()]
    dates=[pd.Timestamp(e["week_end"],tz="UTC") for e in rows]
    if dates!=sorted(set(dates)):raise ValueError("Paper observations aren't unique and increasing")
    return rows

def observation(week,usd,ma,last_usd_source,official,official_meta,capture):
    if week not in usd.index or week not in ma.index:
        raise ValueError("BTC weekly signal not available")
    if last_usd_source<week:
        raise ValueError("BTC provider has not yet published full target weekly close")
    px=float(usd.loc[week]);average=float(ma.loc[week])
    if not np.isfinite(px) or not np.isfinite(average) or min(px,average)<=0:
        raise ValueError("BTC USD / 200WMA missing or invalid")
    eligible=official.loc[official["date"]<=week]
    if eligible.empty:raise ValueError("No official ASX price on/before week")
    row=eligible.iloc[-1]
    report_date=pd.Timestamp(row["date"])
    if (week-report_date).days>3 or float(row["volume"])<=0:
        raise ValueError("No valid VBTC last-traded-price within 3 calendar days of week")
    return {
        "week_end":iso(week),
        "observed_at_utc":capture.isoformat(),
        "btc_usd_close":round(px,8),
        "btc_200wma_usd":round(average,8),
        "btc_deviation_pct":round(100*(px/average-1),8),
        "vbtc_trade_reference_aud":round(float(row["last_traded_aud"]),6),
        "vbtc_nav_aud":round(float(row["nav_aud"]),6),
        "vbtc_market_date":iso(report_date),
        "vbtc_volume":int(row["volume"]),
        "vbtc_premium_pct":round(float(row["premium_pct_calculated"]),6),
        "vbtc_issuer_workbook_sha256":official_meta["sha256"],
        "data_treatment":"Issuer last traded quote, not guaranteed executable bid/ask",
        "btc_price_provider":BLOCKCHAIN
    }

def check_history(rows,usd,ma,official):
    # Do not overwrite or reprice historical observations on provider restatements.
    market={iso(x):x for x in official["date"]}
    prices=official.set_index("date")["last_traded_aud"]
    for old in rows:
        day=pd.Timestamp(old["week_end"],tz="UTC")
        if day in usd.index and day in ma.index:
            if abs(float(usd.loc[day])-old["btc_usd_close"])/old["btc_usd_close"]>1e-7:
                raise ValueError("Past BTC historical snapshot revised; stop, don't restate")
            if abs(float(ma.loc[day])-old["btc_200wma_usd"])/old["btc_200wma_usd"]>1e-7:
                raise ValueError("Past 200WMA baseline revised; stop, don't restate")
        market_date=pd.Timestamp(old["vbtc_market_date"],tz="UTC")
        if market_date in prices.index:
            if abs(float(prices.loc[market_date])-old["vbtc_trade_reference_aud"])>1e-4:
                raise ValueError("Issuer retrospectively revised recorded ETF market quote")

def load_price_arrays(events):
    # Observations contain one explicit bootstrap week followed by prospective weeks.
    if len(events)<2:raise ValueError("Need bootstrap and first forward observation")
    dates=pd.DatetimeIndex(pd.to_datetime([r["week_end"] for r in events],utc=True))
    if any((dates[k]-dates[k-1]).days!=7 for k in range(1,len(dates))):
        raise ValueError("Missing W-MON observations; cannot paper-fill across gap")
    s=pd.Series([float(r["vbtc_trade_reference_aud"]) for r in events],index=dates)
    signals=pd.Series([float(r["btc_usd_close"]) for r in events],index=dates)
    ma=pd.Series([float(r["btc_200wma_usd"]) for r in events],index=dates)
    return s,signals,ma

def simulate_history(events,config,config_hash):
    if len(events)<2:return {"status":"not_started","config_sha256":config_hash,"weeks":{}}
    s,signals,ma=load_price_arrays(events)
    weeks={}
    variants={"baseline_dca":{"sell_levels":[],"buy_levels":[],"cash_recycle_idle_weeks":0},
              "tier_12buy_16sell":{"cash_recycle_idle_weeks":0},
              "tier_12buy_16sell_recycle26":{"cash_recycle_idle_weeks":26}}
    for n in range(1,len(events)):
        outcomes={}
        for label,spec in variants.items():
            trade_events=[]
            ledger=FifoCgtLedger()
            def cb(evt):
                ledger(evt)
                trade_events.append({"date":iso(evt["date"]),"side":evt["side"],"kind":evt["kind"],
                     "units":round(float(evt["units"]),8),"cash_aud":round(float(evt["cash"]),2)})
            tax=AnnualSmsfTaxPayment(ledger,config["brokerage_aud_per_fill"],
                                    config["fee_fraction_per_fill"],
                                    config["slippage_assumption_per_fill"])
            opts={k:v for k,v in spec.items()}
            state=staged(s,ma,0,shape="bell",buy_weeks=config["buy_execution_weeks"],
                sell_weeks=config["sell_execution_weeks"],block_overlap=True,
                reverse_cancel=False,initial_btc_fraction=config["initial_btc_etf_fraction"],
                funding_weeks=config["initial_funding_weeks"],funding_weighted=True,
                btc_core_fraction=0.,signal_price=signals,
                fee=config["fee_fraction_per_fill"],
                slippage=config["slippage_assumption_per_fill"],
                brokerage_fixed=config["brokerage_aud_per_fill"],end_index=n,
                trade_callback=cb,weekly_hook=tax,
                cash_recycle_fraction=config["cash_recycle"]["allocation_fraction"],
                cash_recycle_min_share=config["cash_recycle"]["min_cash_weight"],
                **opts)
            ledger_state=ledger.tax_summary()
            if abs(ledger_state["net_units"]-state["btc_held"])>1e-5:
                raise ValueError("Paper tax ledger and simulated ETF inventory differ")
            mark=float(state["value_usd"])
            net=round(mark-ledger_state["tax_outstanding"],2)
            if net<0:raise ValueError("Negative tax-adjusted paper NAV")
            current_week=events[n]["week_end"]
            today_fills=[t for t in trade_events if t["date"]==current_week]
            outcomes[label]={"portfolio_gross_aud":round(mark,2),
                    "portfolio_less_modelled_tax_aud":net,
                    "free_cash_aud":round(float(state["cash_usd"]),2),
                    "etf_units":round(float(state["btc_held"]),8),
                    "tax_paid_to_date_aud":ledger_state["tax_cash_paid"],
                    "tax_outstanding_aud":ledger_state["tax_outstanding"],
                    "historical_fill_count":len(trade_events),
                    "week_fills":today_fills,
                    "pending_tier_jobs":state["pending_jobs"]}
        base=outcomes["baseline_dca"]["portfolio_less_modelled_tax_aud"]
        for name,v in outcomes.items():
            v["excess_vs_identical_dca_pct"]=round(100*(v["portfolio_less_modelled_tax_aud"]/base-1),5)
        weeks[events[n]["week_end"]]={"market":{"vbtc_traded_aud":events[n]["vbtc_trade_reference_aud"],
           "vbtc_nav_aud":events[n]["vbtc_nav_aud"],
           "vbtc_premium_pct":events[n]["vbtc_premium_pct"],
           "btc_usd_deviation_vs_200wma_pct":events[n]["btc_deviation_pct"]},
           "portfolios":outcomes}
    return {"schema":"btc-200wma-forward-scoreboard-v1",
            "config_sha256":config_hash,
            "status":"paper_running",
            "completed_weeks":len(events)-1,
            "last_week":events[-1]["week_end"],"weeks":weeks,
            "source_type":"Official VBTC traded market quote; neither executable bid nor ask",
            "model_tax_note":"Illustrative tax payment at first July weekly settlement; not a real SMSF return"}

def check_prior_scoreboard(current):
    if not SCORE.exists():return
    prior=json.loads(SCORE.read_text())
    if prior.get("config_sha256")!=current["config_sha256"]:
        raise ValueError("Frozen config fingerprint changed")
    for week,old in prior.get("weeks",{}).items():
        if week not in current["weeks"] or stable(old)!=stable(current["weeks"][week]):
            raise ValueError(f"Existing paper result {week} would be restated; refusing write")

def collect(config,existing,capture):
    latest_complete=last_completed_monday(capture)
    first=pd.Timestamp(config["earliest_first_completed_week_utc"],tz="UTC")
    if latest_complete<first:return existing,{"status":"awaiting_first_complete_week","first_week":iso(first)}
    next_week=first if not existing else pd.Timestamp(existing[-1]["week_end"],tz="UTC")+pd.Timedelta(days=7)
    if next_week>latest_complete:return existing,{"status":"up_to_date","last_week":existing[-1]["week_end"]}
    if (capture-next_week).days>7:
        raise ValueError(f"Missed prospective paper snapshot {iso(next_week)}; no retroactive entry")
    usd,ma,last_usd=btc_usd_history()
    official,meta=download_history()
    if existing:check_history(existing,usd,ma,official)
    new=list(existing)
    if not new:
        prior=first-pd.Timedelta(days=7)
        b=observation(prior,usd,ma,last_usd,official,meta,capture)
        b["bootstrap_only"]=True
        new.append(b)
    while next_week<=latest_complete:
        new.append(observation(next_week,usd,ma,last_usd,official,meta,capture))
        next_week+=pd.Timedelta(days=7)
    return new,{"status":"prospective_observation_ready","new_weeks":len(new)-len(existing)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--save",action="store_true",
        help="Write append-only research-only observation and scoreboard")
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    config,digest=config_read()
    if args.self_test:
        test_records=[]
        for j in range(4):
            date=pd.Timestamp("2026-10-12",tz="UTC")+pd.Timedelta(days=7*j)
            test_records.append({"week_end":iso(date),"vbtc_trade_reference_aud":20.+j,
              "vbtc_nav_aud":19.7+j,"vbtc_premium_pct":1.0,
              "btc_usd_close":70000+j*5000,"btc_200wma_usd":45000+j*100,
              "btc_deviation_pct":50.,"vbtc_market_date":iso(date)})
        one=simulate_history(test_records[:2],config,digest)
        many=simulate_history(test_records,config,digest)
        week=test_records[1]["week_end"]
        if stable(one["weeks"][week])!=stable(many["weeks"][week]):
            raise AssertionError("Future observations changed prior paper results")
        assert len(many["weeks"])==3 and "baseline_dca" in many["weeks"][week]["portfolios"]
        print(json.dumps({"self_test":"PASS","first":week,"future_lookahead_guard":"PASS"}))
        return
    capture=pd.Timestamp.now(tz="UTC")
    existing=recorded()
    new,status=collect(config,existing,capture)
    score=simulate_history(new,config,digest)
    check_prior_scoreboard(score)
    print(json.dumps({**status,"config_sha256":digest,"paper_record_count":len(new),
                       "last_snapshot_week":score.get("last_week"),
                       "reference_quote_type":"VBTC issuer last traded, not executable bid/ask"},indent=2))
    if args.save and len(new)>len(existing):
        ROOT.mkdir(parents=True,exist_ok=True)
        EVENTS.write_text("".join(stable(x)+"\n" for x in new))
        SCORE.write_text(json.dumps(score,indent=2)+"\n")
        print("RESEARCH_FILES_UPDATED",str(EVENTS),str(SCORE))
    elif args.save:
        print("NO_CHANGE: no new completed week; no trading or portfolio files written")

if __name__=="__main__":main()
