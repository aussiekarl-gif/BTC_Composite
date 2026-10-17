"""Explicit in-memory mapping of an unfamiliar broker CSV to our neutral schema.

No broker-specific interpretation, FX conversion, persisted credentials,
portfolio writes or automatic orders. Every side, asset and currency must
be explicitly understood. In particular, the string "IBIT" on a US broker
report does not imply ASX:IBIT.

A native broker export might contain net cash, settlement amounts or USD,
none of which is safely interchangeable with gross AUD consideration.
Users must identify the GROSS AUD field and separately the fee field;
do not subtract or add fees implicitly.
"""
from __future__ import annotations

import csv
import io

from engines.research.cycle_broker_csv_reconciliation import (
    MAX_BYTES,MAX_ROWS,
    TRANSACTION_COLUMNS,BALANCE_COLUMNS,
    parse_broker_executions_csv,parse_broker_balances_csv,
)

NO_COLUMN="(not provided)"
MAX_UNIQUE_CODES=20


def read_unmapped_csv(data):
    """Bounded UTF-8 CSV with intact arbitrary broker columns."""
    if not isinstance(data,bytes) or not 0<len(data)<=MAX_BYTES:
        raise ValueError("Broker CSV must be nonempty and at most 512 KiB")
    if b"\x00" in data:
        raise ValueError("Binary/non-CSV input is unsupported")
    try:
        raw=data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Upload a UTF-8 CSV export") from exc
    try:
        reader=csv.DictReader(io.StringIO(raw,newline=""),strict=True)
        columns=reader.fieldnames
        if not columns or any(n is None or not n.strip() for n in columns):
            raise ValueError("Broker CSV requires nonempty header names")
        columns=[v.strip() for v in columns]
        if len(set(columns))!=len(columns):
            raise ValueError("Broker CSV contains repeated header names")
        rows=[]
        for i,row in enumerate(reader,start=2):
            if i>MAX_ROWS+1:
                raise ValueError("Broker CSV exceeds 1,500 records")
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Broker CSV line {i} has extra or missing columns")
            rows.append({k.strip():v.strip() for k,v in row.items()})
    except csv.Error as exc:
        raise ValueError(f"Broker CSV parsing error: {exc}") from exc
    if not rows:
        raise ValueError("Broker CSV contains no transactions or balances")
    return columns,rows


def source_column_values(data,column):
    """Observed source labels, not guessed meaning; max 20 unique codes."""
    columns,rows=read_unmapped_csv(data)
    if column not in columns:
        raise ValueError("Selected source field is missing")
    labels=sorted({row[column].strip() for row in rows})
    if any(not k for k in labels):
        raise ValueError("Source classification column contains an empty label")
    if len(labels)>MAX_UNIQUE_CODES:
        raise ValueError("More than 20 distinct broker labels; split/check export")
    return labels


def _mapped_field(row,fields,target,*,required=True):
    source=fields.get(target)
    if not source:
        if required:
            raise ValueError(f"Map the broker column for {target} explicitly")
        return ""
    if source not in row:
        raise ValueError(f"Mapped column for {target} is not in this broker CSV")
    return row[source]


def _map_code(raw,mapping,label,choices):
    if not isinstance(mapping,dict) or raw not in mapping:
        raise ValueError(f"Unmapped broker {label}: {raw!r}")
    value=mapping[raw]
    if value not in choices:
        raise ValueError(f"Invalid broker {label} mapping for {raw!r}")
    return value


def _as_csv(records,headers):
    buff=io.StringIO(newline="")
    writer=csv.DictWriter(buff,fieldnames=headers,lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return buff.getvalue().encode("utf-8")


def _currency_ok(row,fields,confirmed_aud):
    if confirmed_aud is not True:
        raise ValueError(
            "Confirm all money columns are actual AUD amounts, NOT USD "
            "or net settlement/total amounts")
    raw=_mapped_field(row,fields,"Currency",required=False)
    if fields.get("Currency") and raw.strip().upper()!="AUD":
        raise ValueError(
            f"Broker currency {raw!r} is not AUD. Convert/reconcile "
            "from original broker FX externally; no silent conversion"
        )


def map_native_broker_executions(data,*,columns,side_values,asset_values,
                                 fixed_asset=None,confirmed_aud=False,
                                 confirmed_asx=False,
                                 confirmed_fee_free=False,today):
    """Only explicitly user-mapped source rows; final neutral parser decides.

    Fields Date/Side/Units/Gross AUD and the real fee column are mandatory,
    except fees may be 0 if user separately confirms genuinely fee-free.
    The reference is optional, resulting in possible ambiguous duplicates.
    """
    headers,rows=read_unmapped_csv(data)
    if not isinstance(columns,dict):
        raise ValueError("Explicit source-column map required")
    selected=[v for v in columns.values() if v]
    if any(v not in headers for v in selected):
        raise ValueError("Source-column mapping refers to missing fields")
    if len(selected)!=len(set(selected)):
        raise ValueError("One source column cannot be used for two meanings")
    if not columns.get("Fee AUD") and confirmed_fee_free is not True:
        raise ValueError(
            "Map actual broker fees or explicitly certify there were none")
    if not columns.get("Asset") and fixed_asset not in (
            "ASX:IBIT","Direct BTC"):
        raise ValueError("Select a confirmed fixed asset or map asset column")
    generated=[]
    for row in rows:
        _currency_ok(row,columns,confirmed_aud)
        side=_map_code(_mapped_field(row,columns,"Side"),
                       side_values,"Side",("BUY","SELL"))
        if columns.get("Asset"):
            asset=_map_code(_mapped_field(row,columns,"Asset"),
                            asset_values,"Asset",("ASX:IBIT","Direct BTC"))
        else:
            asset=fixed_asset
        if asset=="ASX:IBIT" and confirmed_asx is not True:
            raise ValueError(
                "Confirm ETF is the Australian ASX-listed IBIT, not US IBIT")
        ref=_mapped_field(row,columns,"Reference",required=False)
        if ref.lstrip().startswith(("=","+","-","@")):
            raise ValueError("Unsafe spreadsheet formula in broker Reference")
        generated.append({
            "Date":_mapped_field(row,columns,"Date"),
            "Side":side,
            "Asset":asset,
            "Units":_mapped_field(row,columns,"Units"),
            "Gross AUD":_mapped_field(row,columns,"Gross AUD"),
            "Fee AUD":(_mapped_field(row,columns,"Fee AUD")
                       if columns.get("Fee AUD") else "0.00"),
            "Reference":ref,
        })
    payload=_as_csv(generated,TRANSACTION_COLUMNS)
    return parse_broker_executions_csv(payload,today=today)


def map_native_broker_balances(data,*,columns,asset_values,
                               fixed_asof=None,confirmed_cash_aud=False,
                               confirmed_asx=False,today):
    """Map native balance statement, never claim cash is tax-reserved."""
    headers,rows=read_unmapped_csv(data)
    if not isinstance(columns,dict):
        raise ValueError("Explicit broker balance field mapping required")
    selected=[v for v in columns.values() if v]
    if any(v not in headers for v in selected):
        raise ValueError("Balance mapping refers to missing source columns")
    if len(set(selected))!=len(selected):
        raise ValueError("Cannot reuse a source column for different meanings")
    if not columns.get("As Of") and fixed_asof is None:
        raise ValueError("Confirm dated broker balance snapshot")
    generated=[]
    for row in rows:
        label=_mapped_field(row,columns,"Asset")
        asset=_map_code(label,asset_values,"balance asset",
                        ("ASX:IBIT","Direct BTC","AUD Cash"))
        if asset=="ASX:IBIT" and confirmed_asx is not True:
            raise ValueError("Confirm ASX-listed ETF, not US IBIT")
        if asset=="AUD Cash":
            if confirmed_cash_aud is not True:
                raise ValueError(
                    "Confirm cash quantity is AUD; not USD or a reserve-free amount")
            if columns.get("Currency") and _mapped_field(
                    row,columns,"Currency").upper()!="AUD":
                raise ValueError("Non-AUD cash balance cannot be silently converted")
        generated.append({
            "As Of":(_mapped_field(row,columns,"As Of")
                     if columns.get("As Of") else str(fixed_asof)),
            "Asset":asset,
            "Quantity":_mapped_field(row,columns,"Quantity"),
        })
    payload=_as_csv(generated,BALANCE_COLUMNS)
    return parse_broker_balances_csv(payload,today=today)
