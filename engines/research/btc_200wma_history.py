"""Complete-week lookback-safe BTC/USD research series.
W-MON labels its end Monday. Never use a future-labelled partial bar as a
completed weekly signal, trade, or portfolio terminal valuation.
"""
import pandas as pd
FILE="data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv"
def load_completed_200wma_price_history(path=FILE):
    d=pd.read_csv(path)
    d["date"]=pd.to_datetime(d["timestamp"],unit="ms",utc=True)
    raw=pd.Series(pd.to_numeric(d["Price"],errors="coerce").to_numpy(),index=d["date"]).sort_index().dropna()
    if raw.empty or raw.index.has_duplicates or not (raw>0).all():
        raise ValueError("Invalid BTC historical price data")
    weekly=raw.resample("W-MON").last().dropna()
    weekly=weekly.loc[weekly.index<=raw.index.max().normalize()]
    if len(weekly)<202:raise ValueError("Insufficient completed weeks for 200WMA")
    return weekly,weekly.shift(1).rolling(200,min_periods=200).mean()
