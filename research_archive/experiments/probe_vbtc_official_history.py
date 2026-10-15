"""Diagnostic only: inspect official VanEck VBTC daily NAV/market-history workbook.

No scraping bypass, no fund orders and no writes to Production.
Only prints column names, dimensions, row samples and provenance.
"""
import io,json
import requests
import pandas as pd
URL="https://www.vaneck.com.au/etf/alternatives/vbtc/downloads/fundhistoprices/"
def main():
    with requests.get(URL,timeout=35,stream=True,headers={"Accept":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}) as res:
        print("source_url",URL)
        print("http_status",res.status_code)
        print("content_type",res.headers.get("Content-Type"))
        res.raise_for_status()
        data=bytearray()
        for chunk in res.iter_content(65536):
            data+=chunk
            if len(data)>12_000_000:raise ValueError("VBTC file too large")
    print("bytes",len(data),"signature",bytes(data[:4]).hex())
    if bytes(data[:2])!=b"PK":raise ValueError("Expected xlsx ZIP signature; fail closed")
    book=pd.ExcelFile(io.BytesIO(data))
    print("sheets",json.dumps(book.sheet_names))
    for sh in book.sheet_names[:3]:
        df=pd.read_excel(book,sheet_name=sh,header=None,nrows=12)
        print("sheet",sh,"preview",json.dumps(df.fillna("").astype(str).values.tolist(),ensure_ascii=False)[:4500])
if __name__=="__main__":main()
