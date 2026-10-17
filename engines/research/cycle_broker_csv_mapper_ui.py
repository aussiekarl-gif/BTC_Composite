"""Guided broker export column mapping controls for optional Streamlit audits.

All choices are user-confirmed per source-file fingerprint. Uploaded
content stays in the app process and is not persisted to Google Sheets.
"""
from __future__ import annotations

import hashlib

import streamlit as st

from engines.research.cycle_broker_csv_mapping import (
    read_unmapped_csv,source_column_values,
    map_native_broker_executions,map_native_broker_balances,
)
from engines.research.cycle_broker_csv_reconciliation import (
    parse_broker_executions_csv,parse_broker_balances_csv,
)


def _file_key(kind,raw):
    return "cycle_broker_mapping_"+kind+"_"+hashlib.sha256(raw).hexdigest()[:16]


def _field(key,display,headers,*,required=True):
    options=["(not provided)"]+list(headers)
    chosen=st.selectbox(
        display,options,key=key,
        help=("Select the exact existing broker CSV source column. "
              "Do not use net settlement cash in place of gross AUD consideration."))
    if chosen=="(not provided)":
        return None
    return chosen


def _field_group(headers,key,spec):
    fields={}
    # Each field must be manually identified, never guessed from header words.
    for target,label,required in spec:
        fields[target]=_field(key+"_"+target,label,headers,required=required)
    missing=[label for target,label,required in spec
             if required and fields[target] is None]
    if missing:
        raise ValueError("Select required broker columns: "+", ".join(missing))
    return fields


def _map_values(raw,key,column,*,choices,description):
    values=source_column_values(raw,column)
    mapping={}
    st.caption(description)
    for i,v in enumerate(values):
        chosen=st.selectbox(
            f"Value from broker: {v!r}",["(unmapped)"]+list(choices),
            key=f"{key}_{i}")
        if chosen!="(unmapped)":
            mapping[v]=chosen
    return mapping


def _source_display(raw):
    headers,rows=read_unmapped_csv(raw)
    st.caption(
        f"Received {len(rows)} broker CSV records with "
        f"{len(headers)} source columns. These remain in memory."
    )
    st.caption("Source headings: "+", ".join(headers))
    return headers


def broker_executions_from_upload(upload,*,today):
    raw=upload.getvalue()
    key=_file_key("executions",raw)
    mode=st.radio(
        "Execution CSV format",
        ["Already matches standard template","Map source broker columns"],
        key=key+"_mode",horizontal=True)
    if mode=="Already matches standard template":
        return parse_broker_executions_csv(raw,today=today)
    headers=_source_display(raw)
    st.caption(
        "Map BUY/SELL transaction EXECUTION records only, not cash transfers, "
        "pending orders, settlement rows or hypothetical confirmations. "
        "Gross must be AUD before brokerage. Use a matching original broker "
        "account and keep your exported source file for independent review."
    )
    fields=_field_group(headers,key,[
        ("Date","Execution date column",True),
        ("Side","BUY/SELL action column",True),
        ("Units","Executed shares/BTC quantity column",True),
        ("Gross AUD","GROSS executed consideration in AUD",True),
        ("Fee AUD","Brokerage fee in AUD (if any)",False),
        ("Reference","Unique broker order/reference column (optional)",False),
        ("Currency","Currency column for consideration/fees (optional)",False),
    ])
    asset_source=st.selectbox(
        "Asset source",["Single confirmed asset for all rows","Asset/symbol column"],
        key=key+"_asset_mode")
    fields["Asset"]=None
    fixed_asset=None
    if asset_source=="Asset/symbol column":
        fields["Asset"]=_field(key+"_asset","Broker ticker/asset column",headers)
    else:
        fixed_asset=st.selectbox(
            "Confirmed exchange-traded asset",
            ["(not selected)","ASX:IBIT","Direct BTC"],
            key=key+"_fixed_asset")
        if fixed_asset=="(not selected)":
            fixed_asset=None
    if not fields["Side"]:
        raise ValueError("Select executed action column before mapping labels")
    side=_map_values(
        raw,key+"_side",fields["Side"],choices=("BUY","SELL"),
        description="Identify every raw broker action; none are inferred.")
    assets={}
    if fields["Asset"]:
        assets=_map_values(
            raw,key+"_asset_value",fields["Asset"],
            choices=("ASX:IBIT","Direct BTC"),
            description=(
                "Classify EACH original broker symbol. 'IBIT' on a "
                "US exchange is not ASX:IBIT; check custody/exchange first."
            ))
    fee_free=st.checkbox(
        "My execution report is genuinely fee-free; use A$0 fees "
        "(only if no fee source column was selected)",
        value=False,key=key+"_no_fee")
    audited_aud=st.checkbox(
        "I checked that Gross and Fee figures are in AUD, not USD, "
        "and Gross means consideration BEFORE brokerage",
        value=False,key=key+"_aud")
    asx=st.checkbox(
        "I checked that every row classified ASX:IBIT is the "
        "AUSTRALIAN-listed ETF, not the US-listed IBIT",
        value=False,key=key+"_asx")
    return map_native_broker_executions(
        raw,columns=fields,side_values=side,asset_values=assets,
        fixed_asset=fixed_asset,confirmed_aud=audited_aud,
        confirmed_asx=asx,confirmed_fee_free=fee_free,today=today)


def broker_balances_from_upload(upload,*,today):
    raw=upload.getvalue()
    key=_file_key("balances",raw)
    mode=st.radio(
        "Balance CSV format",
        ["Already matches standard template","Map source broker columns"],
        key=key+"_mode",horizontal=True)
    if mode=="Already matches standard template":
        return parse_broker_balances_csv(raw,today=today)
    headers=_source_display(raw)
    st.caption(
        "For holdings ONLY (not pending orders), map each broker balance "
        "asset to Australian IBIT units, direct BTC or AUD cash. "
        "Do not map a foreign-market ETF or foreign-currency cash as Australian."
    )
    fields=_field_group(headers,key,[
        ("As Of","Balance as-of date column (optional if single snapshot)",False),
        ("Asset","Ticker or cash asset column",True),
        ("Quantity","Held units or cash quantity column",True),
        ("Currency","Cash balance currency column (optional)",False),
    ])
    if not fields["Asset"]:
        raise ValueError("Select balance asset column before mapping labels")
    fixed_asof=None
    if not fields["As Of"]:
        fixed_asof=st.date_input(
            "Explicit dated broker snapshot (not today's assumed balance)",
            value=today,max_value=today,key=key+"_asof")
        asof_ack=st.checkbox(
            "I checked the original broker statement as-of date above",
            value=False,key=key+"_asof_confirm")
        if not asof_ack:
            raise ValueError("Confirm actual dated broker statement snapshot")
    assets=_map_values(
        raw,key+"_asset",fields["Asset"],
        choices=("ASX:IBIT","Direct BTC","AUD Cash"),
        description="Map all source asset labels; no unrecognised row is discarded.")
    aud=st.checkbox(
        "I checked any cash amounts are in AUD; balance is NOT assumed "
        "free after SMSF taxes and liabilities",
        value=False,key=key+"_aud_cash")
    asx=st.checkbox(
        "I checked ASX:IBIT means Australian-listed IBIT ETF, "
        "not US IBIT",
        value=False,key=key+"_asx")
    return map_native_broker_balances(
        raw,columns=fields,asset_values=assets,
        fixed_asof=fixed_asof,confirmed_cash_aud=aud,
        confirmed_asx=asx,today=today)
