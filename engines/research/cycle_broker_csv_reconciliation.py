"""Read-only comparison of independent broker statements to saved executed trades.

CSV files exist ONLY in Streamlit process memory; never save uploaded CSV
or rewrite the user's Google Sheets portfolio. The broker-neutral expected
format is a documented import TEMPLATE, not a guess at the varying Stake,
IBKR, Webull or other broker export formats.

An exported statement covers an explicitly stated date window. 'Unmatched
portfolio' means missing only IF the imported statement is complete for
that range and account; otherwise treat it as review-only. Ambiguous repeated
economically identical fills are NEVER silently paired by row number.

A broker CASH balance can contain unsettled funds/tax provisions and
therefore is NOT automatically an available-after-liabilities BUY amount.
"""
from __future__ import annotations

import copy
import csv
import datetime as dt
import io
import math
from collections import Counter

from engines.shared.portfolio_transactions import (
    ASSETS,parse_date,portfolio_positions,
)

MAX_BYTES=512*1024
MAX_ROWS=1500
TRANSACTION_COLUMNS=("Date","Side","Asset","Units","Gross AUD","Fee AUD","Reference")
BALANCE_COLUMNS=("As Of","Asset","Quantity")
TRANSACTION_TEMPLATE=(
    "Date,Side,Asset,Units,Gross AUD,Fee AUD,Reference\n"
    "2026-10-15,BUY,ASX:IBIT,10,250.00,3.00,ORDER-123\n"
    "2026-10-16,SELL,Direct BTC,0.00500000,600.00,0.00,ORDER-124\n"
)
BALANCE_TEMPLATE=(
    "As Of,Asset,Quantity\n"
    "2026-10-17,ASX:IBIT,100\n"
    "2026-10-17,Direct BTC,0.12500000\n"
    "2026-10-17,AUD Cash,50000.00\n"
)
EPS=1e-8
AUD_TOL=.02


def _finite(v,label,*,positive=True):
    if v is None or str(v).strip()=="":
        raise ValueError(f"Missing {label}")
    try:
        n=float(v)
    except (ValueError,TypeError):
        raise ValueError(f"Invalid {label}; use a plain decimal point")
    if not math.isfinite(n) or n<0 or (positive and n==0):
        raise ValueError(f"Invalid {label}; positive finite number required")
    return n


def _asset(value,*,allow_cash=False):
    x=str(value).strip().upper()
    mapping={
        "ASX:IBIT":"ASX:IBIT","IBIT.AX":"ASX:IBIT",
        "IBIT.AU":"ASX:IBIT","DIRECT BTC":"Direct BTC",
        "BTC":"Direct BTC","AUD CASH":"AUD Cash",
        "AUD":"AUD Cash",
    }
    if x not in mapping or (mapping[x]=="AUD Cash" and not allow_cash):
        raise ValueError(
            "Unrecognised asset. Use ASX:IBIT, Direct BTC, "
            "or AUD Cash (balances only); never interpret US IBIT as ASX:IBIT"
        )
    return mapping[x]


def _date(value,label):
    try:
        result=parse_date(value)
    except (ValueError,TypeError):
        raise ValueError(f"{label}: use YYYY-MM-DD or DD/MM/YYYY")
    return result


def _csv(data,required,kind):
    if not isinstance(data,bytes) or not data or len(data)>MAX_BYTES:
        raise ValueError(f"{kind} CSV must be 1 byte to {MAX_BYTES:,} bytes")
    if b"\x00" in data:
        raise ValueError("Binary file supplied instead of text CSV")
    try:
        txt=data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("CSV must use UTF-8 (Excel CSV UTF-8 supported)")
    try:
        reader=csv.DictReader(io.StringIO(txt,newline=""),strict=True)
        names=reader.fieldnames
        if not names or len(names)!=len(set(names)):
            raise ValueError("CSV headers are missing or duplicated")
        names=[n.strip() for n in names]
        if len(set(names))!=len(names) or not all(n in names for n in required):
            raise ValueError(
                f"{kind} CSV requires exact columns: "+", ".join(required))
        extra=[n for n in names if n not in required]
        if extra:
            raise ValueError(
                f"Unsupported {kind} columns: "+", ".join(extra)+
                ". Convert to the safe template; no hidden broker fields are guessed"
            )
        records=[]
        for i,row in enumerate(reader,start=2):
            if i>MAX_ROWS+1:
                raise ValueError(f"{kind} CSV exceeds {MAX_ROWS} data rows")
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"{kind} CSV row {i} has extra/missing fields")
            records.append({k.strip():v.strip() for k,v in row.items()})
    except csv.Error as exc:
        raise ValueError(f"{kind} CSV formatting error: {exc}")
    if not records:
        raise ValueError(f"{kind} CSV contains no records")
    return records


def parse_broker_executions_csv(data,*,today):
    rows=_csv(data,TRANSACTION_COLUMNS,"Transaction")
    cutoff=_date(today,"Current date")
    output=[]
    seen_refs=set()
    for i,row in enumerate(rows,start=2):
        day=_date(row["Date"],f"Broker trade date row {i}")
        if day>cutoff:raise ValueError(f"Broker trade row {i} is future dated")
        side=row["Side"].upper()
        if side not in ("BUY","SELL"):
            raise ValueError(f"Transaction row {i}: Side must be BUY or SELL")
        asset=_asset(row["Asset"])
        qty=_finite(row["Units"],f"Units row {i}")
        if asset=="ASX:IBIT" and abs(qty-round(qty))>EPS:
            raise ValueError(f"IBIT row {i} must use whole ASX units")
        if asset=="Direct BTC" and abs(qty-round(qty,8))>EPS/100:
            raise ValueError(f"Direct BTC row {i} exceeds eight decimal places")
        gross=_finite(row["Gross AUD"],f"Gross AUD row {i}")
        fee=_finite(row["Fee AUD"],f"Fee AUD row {i}",positive=False)
        if gross<=fee:raise ValueError(f"Row {i}: gross consideration must exceed fee")
        ref=row["Reference"].strip()
        if ref:
            ref_id=(side,asset,ref.casefold())
            if ref_id in seen_refs:
                raise ValueError(f"Repeated broker execution Reference on row {i}")
            seen_refs.add(ref_id)
        output.append(dict(
            date=day,side=side,asset=asset,
            qty=round(qty,8) if asset=="Direct BTC" else int(round(qty)),
            gross=round(gross,2),fee=round(fee,2),reference=ref,
            broker_row=i,
        ))
    return output


def parse_broker_balances_csv(data,*,today):
    rows=_csv(data,BALANCE_COLUMNS,"Balances")
    cutoff=_date(today,"Current date")
    positions={}
    observed=set()
    for i,row in enumerate(rows,start=2):
        day=_date(row["As Of"],f"Balance row {i}")
        if day>cutoff:raise ValueError("Broker balance statement is future dated")
        observed.add(day)
        asset=_asset(row["Asset"],allow_cash=True)
        qty=_finite(row["Quantity"],f"Balance quantity row {i}",positive=False)
        if asset=="ASX:IBIT" and abs(qty-round(qty))>EPS:
            raise ValueError("IBIT broker balance must contain whole ETF units")
        if asset in positions:
            raise ValueError("Repeated asset in broker balance statement")
        positions[asset]=qty
    if len(observed)!=1:
        raise ValueError("All broker balances must have one identical As Of date")
    if not any(a in positions for a in ASSETS):
        raise ValueError("Balance statement must include IBIT or Direct BTC")
    return {"date":next(iter(observed)),"positions":positions}


def _ledger_as_of(saved,day):
    if not isinstance(saved,dict):
        raise ValueError("Existing saved My Portfolio is unavailable")
    rows,sales=saved.get("rows",[]),saved.get("sales",[])
    if not isinstance(rows,list) or not isinstance(sales,list):
        raise ValueError("Portfolio trade lists must be valid")
    # Validate entire saved portfolio before comparing a dated subset.
    portfolio_positions(saved)
    view={k:copy.deepcopy(v) for k,v in saved.items()
          if k not in ("rows","sales")}
    view["rows"]=[copy.deepcopy(v) for v in rows
                  if parse_date(v.get("Date"))<=day]
    view["sales"]=[copy.deepcopy(v) for v in sales
                   if parse_date(v.get("Date"))<=day]
    return view,portfolio_positions(view)


def compare_broker_balances(saved,parsed_balances):
    """Compare recorded holdings as of broker snapshot; never imply tax-free cash."""
    asof=parsed_balances["date"]
    _,positions=_ledger_as_of(saved,asof)
    ledger={"ASX:IBIT":positions["ibit_units"],
            "Direct BTC":positions["direct_btc"],
            "AUD Cash":positions["cash_remaining_aud"]}
    comparisons=[]
    for asset,reported in parsed_balances["positions"].items():
        amount=float(ledger[asset])
        discrepancy=round(reported-amount,8 if asset=="Direct BTC" else 2)
        tolerance=1e-8 if asset=="Direct BTC" else (
            .01 if asset=="ASX:IBIT" else AUD_TOL)
        comparisons.append({
            "asset":asset,
            "broker_reported":reported,
            "portfolio_recorded":amount,
            "broker_minus_portfolio":discrepancy,
            "matches":abs(discrepancy)<=tolerance,
        })
    return {
        "as_of":str(asof),
        "read_only":True,
        "broker_cash_after_tax_verified":False,
        "rows":comparisons,
        "discrepancy_count":sum(not x["matches"] for x in comparisons),
        "missing_assets_not_assumed_zero":[
            a for a in ("ASX:IBIT","Direct BTC","AUD Cash")
            if a not in parsed_balances["positions"]],
        "cash_note":(
            "AUD cash on a broker statement may be gross, unsettled or "
            "reserved. The difference could reflect deposits, withdrawals, "
            "tax, fees, interest or missing fills. It is NOT verified money "
            "free after SMSF tax; never feed into DCA trade sizing automatically."
        ),
    }


def _ledger_executions(saved,start,end):
    view,_=_ledger_as_of(saved,end)
    rows=[]
    for side,source in (("BUY",view["rows"]),("SELL",view["sales"])):
        for i,row in enumerate(source):
            day=parse_date(row.get("Date"))
            if day<start:continue
            asset=_asset(row.get("Asset"))
            qty=_finite(
                row.get("Units / BTC Received" if side=="BUY" else "Units Sold"),
                "Recorded units")
            gross=_finite(row.get("AUD Spent" if side=="BUY" else "AUD Proceeds"),
                          "Recorded AUD consideration")
            fee=_finite(row.get("Brokerage / Fee AUD",0),"Recorded fee",positive=False)
            notes=str(row.get("Notes","")).strip()
            trans_id=str(row.get("Transaction ID","")).strip()
            rows.append(dict(
                date=day,side=side,asset=asset,qty=qty,
                gross=gross,fee=fee,
                reference=notes or trans_id,
                row=i+1,
            ))
    return rows


def compare_broker_transactions(saved,broker_rows,*,start_date,end_date,
                                complete_statement_confirmed=False):
    """Unique 1-to-1 comparison: ambiguous repeated executions stay AMBIGUOUS.

    Requires a user-supplied statement coverage interval, checked against
    each imported trade. Without a complete statement declaration, unmatched
    saved trades are explicitly NOT evidence the broker is missing them.
    """
    start=_date(start_date,"Statement start")
    end=_date(end_date,"Statement end")
    if start>end or (end-start).days>366*6:
        raise ValueError("Statement period must be ordered and at most 6 years")
    if not isinstance(broker_rows,list) or not broker_rows:
        raise ValueError("No valid broker executions")
    for row in broker_rows:
        if not start<=row["date"]<=end:
            raise ValueError(
                f"Broker trade row {row['broker_row']} lies outside declared statement period")
    ledgers=_ledger_executions(saved,start,end)
    used_broker=set()
    used_ledger=set()
    matched=[]
    def economic(a,b):
        tolerance=1e-8 if a["asset"]=="Direct BTC" else .001
        return (a["date"]==b["date"] and a["side"]==b["side"]
                and a["asset"]==b["asset"]
                and abs(float(a["qty"])-float(b["qty"]))<=tolerance
                and abs(float(a["gross"])-float(b["gross"]))<=AUD_TOL
                and abs(float(a["fee"])-float(b["fee"]))<=AUD_TOL)
    # Match unique execution references, but NEVER override mismatching
    # cash or quantity just because two note/reference strings coincide.
    for i,broker in enumerate(broker_rows):
        if not broker["reference"]:
            continue
        candidates=[
            j for j,entry in enumerate(ledgers)
            if j not in used_ledger and entry["reference"]
            and entry["reference"].casefold()==broker["reference"].casefold()
            and entry["side"]==broker["side"] and entry["asset"]==broker["asset"]]
        if len(candidates)!=1:continue
        j=candidates[0]
        competitors=[
            k for k,b in enumerate(broker_rows)
            if k not in used_broker and b["reference"]
            and b["reference"].casefold()==broker["reference"].casefold()
            and b["side"]==broker["side"] and b["asset"]==broker["asset"]]
        if len(competitors)==1 and economic(broker,ledgers[j]):
            used_broker.add(i)
            used_ledger.add(j)
            matched.append((i,j))
    # Unreferenced or nonmatching-reference fills may be compared
    # economically ONLY when exactly one row matches on each side.
    progress=True
    while progress:
        progress=False
        for i,broker in enumerate(broker_rows):
            if i in used_broker:continue
            options=[j for j,entry in enumerate(ledgers)
                     if j not in used_ledger and economic(broker,entry)]
            if len(options)!=1:continue
            j=options[0]
            peers=[k for k,b in enumerate(broker_rows)
                   if k not in used_broker and economic(b,ledgers[j])]
            if len(peers)!=1:continue
            matched.append((i,j))
            used_broker.add(i)
            used_ledger.add(j)
            progress=True
    ambiguous_broker=set()
    ambiguous_ledger=set()
    for i,broker in enumerate(broker_rows):
        if i in used_broker:continue
        options=[j for j,entry in enumerate(ledgers)
                 if j not in used_ledger and economic(broker,entry)]
        if options:
            ambiguous_broker.add(i)
            ambiguous_ledger.update(options)
    details=[]
    for i,j in matched:
        broker=broker_rows[i]
        details.append(dict(status="MATCHED",broker_row=broker["broker_row"],
                            saved_row=ledgers[j]["row"],side=broker["side"],
                            asset=broker["asset"],date=str(broker["date"]),
                            units=broker["qty"],gross_aud=broker["gross"],
                            fee_aud=broker["fee"]))
    for i,broker in enumerate(broker_rows):
        if i in used_broker:continue
        details.append(dict(
            status="AMBIGUOUS_DUPLICATE" if i in ambiguous_broker
            else "BROKER_ONLY_REVIEW",
            broker_row=broker["broker_row"],saved_row=None,
            side=broker["side"],asset=broker["asset"],
            date=str(broker["date"]),units=broker["qty"],
            gross_aud=broker["gross"],fee_aud=broker["fee"]))
    for j,entry in enumerate(ledgers):
        if j in used_ledger:continue
        details.append(dict(
            status="AMBIGUOUS_DUPLICATE" if j in ambiguous_ledger
            else "PORTFOLIO_ONLY_REVIEW",
            broker_row=None,saved_row=entry["row"],
            side=entry["side"],asset=entry["asset"],
            date=str(entry["date"]),units=entry["qty"],
            gross_aud=round(entry["gross"],2),
            fee_aud=round(entry["fee"],2)))
    counts=dict(Counter(x["status"] for x in details))
    return {
        "read_only":True,
        "from_date":str(start),"to_date":str(end),
        "complete_statement_user_attested":bool(complete_statement_confirmed),
        "broker_entries":len(broker_rows),"recorded_entries_in_period":len(ledgers),
        "matched_executions":len(matched),
        "broker_only":counts.get("BROKER_ONLY_REVIEW",0),
        "portfolio_only":counts.get("PORTFOLIO_ONLY_REVIEW",0),
        "ambiguous_rows":counts.get("AMBIGUOUS_DUPLICATE",0),
        "all_rows_accounted_for":(
            len(matched)==len(broker_rows)==len(ledgers)),
        "details":sorted(details,key=lambda x:(x["date"],x["status"],x["side"])),
        "warning":(
            "Exact economics may coincide for two genuine separate fills. "
            "Ambiguous repeated rows require distinct broker references "
            "and manual review; no execution is saved automatically. "
            "A statement is only assumed complete for this date range "
            "when the user explicitly confirms account coverage. "
            "Balances and unsettled transactions may be dated differently."
        ),
    }
