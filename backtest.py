#!/usr/bin/env python3
"""
Backtest Simulator for BTC Composite DCA
========================================
Simulates the strategy over the last 3 years using historical BTC prices.
Requires: requests, numpy (install via pip)
"""

import csv
import math
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import numpy as np
import requests

# Parameters (match your config)
PRICE_MAX_DCA = 45000
PRICE_MIN_DCA = 65000
SPREAD_WEEKS = 12
TOTAL_CAPITAL_AUD = 500000
TARGET_WEEKS = 16
BASELINE_WEEKLY_AUD = TOTAL_CAPITAL_AUD / (TARGET_WEEKS * 0.04375)  # 714,285

def fetch_btc_history() -> List[Tuple[datetime, float]]:
    """Fetch daily BTC prices from blockchain.com"""
    url = "https://api.blockchain.info/charts/market-price?timespan=all&format=json&sampled=false"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()["values"]
    
    prices = []
    for point in data:
        dt = datetime.fromtimestamp(point["x"], tz=timezone.utc)
        price = float(point["y"])
        if price > 0 and dt > datetime(2021, 1, 1, tzinfo=timezone.utc):
            prices.append((dt, price))
    return prices

def price_penalty_factor(price: float) -> float:
    if price <= PRICE_MAX_DCA:
        return 1.0
    if price >= PRICE_MIN_DCA:
        return 0.0
    return (PRICE_MIN_DCA - price) / (PRICE_MIN_DCA - PRICE_MAX_DCA)

def fundamental_proxy(price: float, sma_200: float) -> float:
    """
    Proxy for your 5-indicator composite.
    Uses Price vs 200-day SMA as a stand-in for "how expensive" it is.
    When price = SMA, score = 1.0 (cheap).
    When price is 50% above SMA, score = 0.0 (expensive).
    """
    if sma_200 <= 0:
        return 0.5
    ratio = price / sma_200
    # Map 1.0 -> 1.0, 1.5 -> 0.0, clamp between 0 and 1
    score = max(0.0, min(1.0, (1.5 - ratio) / 0.5))
    return score

def compute_sma(prices: List[float], window: int) -> float:
    if len(prices) < window:
        return prices[-1] if prices else 0
    return np.mean(prices[-window:])

def run_backtest():
    print("Fetching BTC price history...")
    historical = fetch_btc_history()
    print(f"Loaded {len(historical)} daily data points.")
    
    # Filter to only Mondays (weekly DCA)
    mondays = []
    for dt, price in historical:
        if dt.weekday() == 0:  # Monday
            mondays.append((dt, price))
    
    print(f"Found {len(mondays)} Mondays for DCA simulation.")
    
    cash_remaining = TOTAL_CAPITAL_AUD
    total_btc = 0.0
    total_invested = 0.0
    history_log = []
    prices_used_for_sma = []
    
    # We need a running 200-day SMA
    # Pre-fill with first 200 days (we'll just compute from scratch as we go)
    all_prices = [p for _, p in historical]
    
    for i, (dt, price) in enumerate(mondays):
        # Compute 200-day SMA up to this point
        # Find all prices up to this date
        idx = next((j for j, (d, _) in enumerate(historical) if d >= dt), len(historical))
        sma_window = [p for _, p in historical[max(0, idx-200):idx]]
        sma_200 = np.mean(sma_window) if sma_window else price
        
        # 1. Price Penalty
        p_factor = price_penalty_factor(price)
        
        # 2. Proxy Fundamental (uses SMA)
        f_score = fundamental_proxy(price, sma_200)
        
        # 3. Final Composite (your model uses 5 indicators, we use 1 proxy + price)
        # To match your weights, let's treat this proxy as the "fundamental" part,
        # but also blend in the price penalty separately.
        # In your model, the composite already includes price/realised.
        # For the backtest, we simulate a composite score directly:
        # We'll use price penalty as a multiplier to the fundamental.
        composite = f_score * p_factor  # This mimics your "soft price override" applied to your fundamental.
        
        # If fundamental is 0, we don't buy
        if f_score <= 0.01 or price >= PRICE_MIN_DCA:
            weekly_slice_pct = 0.0
        else:
            weekly_slice_pct = (composite * 100) / SPREAD_WEEKS
        
        # AUD buy
        weekly_aud_buy = BASELINE_WEEKLY_AUD * (weekly_slice_pct / 100)
        weekly_aud_buy = min(weekly_aud_buy, cash_remaining)  # Can't spend more than we have
        
        if weekly_aud_buy > 10:  # Ignore tiny dust buys
            btc_bought = weekly_aud_buy / price
            total_btc += btc_bought
            total_invested += weekly_aud_buy
            cash_remaining -= weekly_aud_buy
        else:
            btc_bought = 0.0
        
        history_log.append({
            "date": dt.strftime("%Y-%m-%d"),
            "price": round(price, 2),
            "sma_200": round(sma_200, 2),
            "f_score": round(f_score, 4),
            "p_factor": round(p_factor, 4),
            "composite": round(composite, 4),
            "slice_pct": round(weekly_slice_pct, 4),
            "aud_buy": round(weekly_aud_buy, 2),
            "btc_bought": round(btc_bought, 8),
            "cash_left": round(cash_remaining, 2),
            "total_btc": round(total_btc, 8),
        })
    
    # Write CSV report
    with open("backtest_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=history_log[0].keys())
        writer.writeheader()
        writer.writerows(history_log)
    
    # Summary
    avg_buy_price = total_invested / total_btc if total_btc > 0 else 0
    current_price = mondays[-1][1]
    portfolio_value = total_btc * current_price
    total_return = ((portfolio_value / total_invested) - 1) * 100 if total_invested > 0 else 0
    
    print("\n" + "="*50)
    print("BACKTEST SUMMARY (Last 3 Years)")
    print("="*50)
    print(f"Total Capital:        ${TOTAL_CAPITAL_AUD:,.0f} AUD")
    print(f"Total Invested:       ${total_invested:,.0f} AUD")
    print(f"Cash Remaining:       ${cash_remaining:,.0f} AUD")
    print(f"BTC Accumulated:      {total_btc:.4f} BTC")
    print(f"Avg Buy Price:        ${avg_buy_price:,.0f} USD")
    print(f"Current BTC Price:    ${current_price:,.0f} USD")
    print(f"Portfolio Value:      ${portfolio_value:,.0f} USD")
    print(f"Total Return:         {total_return:+.1f}%")
    print(f"Weeks simulated:      {len(history_log)}")
    print("="*50)
    print("\nDetailed weekly log saved to: backtest_results.csv")
    print("Run this to see all weekly trades.")

if __name__ == "__main__":
    run_backtest()
