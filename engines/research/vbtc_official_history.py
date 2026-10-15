"""Official VanEck Australia VBTC daily NAV and ASX last-traded-price history.

Issuer-hosted XLSX, not Yahoo's unofficial APIs. This is a public issuer
price reference, NOT an executable bid or ask; never label last trade as
a guaranteed fill. Workbook may change format: fail closed on drift.
"""
import hashlib,io
import pandas as pd
import requests

URL="https://www.vaneck.com.au/etf/alternatives/vbtc/downloads/fundhistoprices/"
HEADERS=["Date","NAV","Change","% Change","Last traded price","Volume*","Premium/Discount","% Premium/Discount"]

def read_history(content,observed_at=None):
    if len(content)>12_000_000 or content[:2]!=b"PK":
        raise ValueError("Issuer workbook must be a small XLSX ZIP")
    book=pd.ExcelFile(io.BytesIO(content))
    if len(book.sheet_names)!=1 or not book.sheet_names[0].startswith("VBTC_asat_"):
        raise ValueError("Issuer workbook tab changed; manual provenance check needed")
    raw=pd.read_excel(book,sheet_name=book.sheet_names[0],header=1)
    if list(raw.columns)[:len(HEADERS)]!=HEADERS:
        raise ValueError(f"VBTC workbook headings unexpectedly changed: {list(raw.columns)}")
    if raw.shape[0]<100:
        raise ValueError("Issuer history unexpectedly short")
    frame=pd.DataFrame({
      "date":pd.to_datetime(raw["Date"],format="%d/%m/%Y",errors="coerce",utc=True),
      "nav_aud":pd.to_numeric(raw["NAV"],errors="coerce"),
      "last_traded_aud":pd.to_numeric(raw["Last traded price"],errors="coerce"),
      "premium_pct_issuer":pd.to_numeric(raw["% Premium/Discount"],errors="coerce"),
      "volume":pd.to_numeric(raw["Volume*"].astype(str).str.replace(",","",regex=False),errors="coerce")
    })
    frame=frame.dropna(subset=["date","nav_aud","last_traded_aud","volume"])
    if len(frame)<100:raise ValueError("Insufficient complete issuer NAV/trade-price rows")
    if frame["date"].duplicated().any():raise ValueError("Duplicate issuer prices")
    frame=frame.sort_values("date").reset_index(drop=True)
    if (frame["nav_aud"]<=0).any() or (frame["last_traded_aud"]<=0).any() or (frame["volume"]<0).any():
        raise ValueError("Nonpositive NAV/trade price, or negative volume")
    if observed_at is not None:
        now=pd.Timestamp(observed_at)
        if now.tz is None:now=now.tz_localize("UTC")
        if frame["date"].iloc[-1]>now.normalize():
            raise ValueError("Provider dates are in the future")
    reported=(frame["last_traded_aud"]/frame["nav_aud"]-1)*100
    complete=frame["premium_pct_issuer"].notna()
    error=(reported[complete]-frame.loc[complete,"premium_pct_issuer"]).abs()
    if len(error) and error.max()>0.08:
        raise ValueError(f"Premium to NAV cannot be reconciled (max error {error.max():.3f}pp)")
    frame["premium_pct_calculated"]=reported
    return frame,{"publisher":"VanEck Australia","url":URL,
      "sha256":hashlib.sha256(content).hexdigest(),
      "tab":book.sheet_names[0],"rows":len(frame),
      "first":str(frame["date"].iloc[0].date()),
      "last":str(frame["date"].iloc[-1].date()),
      "premium_reconciliation_max_pp":float(error.max()) if len(error) else None}

def download_history(timeout=45):
    response=requests.get(URL,timeout=timeout,headers={"Accept":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
    response.raise_for_status()
    if "spreadsheet" not in response.headers.get("content-type","") and response.content[:2]!=b"PK":
        raise ValueError("Issuer did not return XLSX")
    return read_history(response.content,observed_at=pd.Timestamp.now(tz="UTC"))

if __name__=="__main__":
    frame,meta=download_history()
    import json
    print(json.dumps({"metadata":meta,"latest":frame.tail(5).assign(date=lambda d:d.date.dt.strftime("%Y-%m-%d")).to_dict("records")},indent=2))
