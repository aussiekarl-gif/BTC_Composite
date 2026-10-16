"""Research-only staggered 200WMA trading simulator.

Signals use completed weekly observations; executions occur at the *following*
weekly close. This is not an executable forecast or a live trading system.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def simulate_wma_windows(
    data,
    weeks=12,
    buy_trigger_pct=0.0,
    sell_trigger_pct=100.0,
    buy_fraction=1.0,
    sell_fraction=1.0,
    starting_capital_aud=500_000.0,
    fee_pct=0.001,
    min_trade_aud=100.0,
):
    """Trade a fixed cash/BTC snapshot over 12 or 16 weekly installments.

    Required columns: btc_price_aud and wma_200 (same currency).
    A campaign begins on a signal *crossing*, not every week below/above a
    threshold. A signal at week t starts fills at week t+1; opposite signals
    cancel any unfilled schedule. Campaign allocations are fixed using holdings
    at the first fill; weights sum to 1, without accidental reallocation.
    """
    if weeks not in (12, 16):
        raise ValueError("weeks must be 12 or 16")
    if not (0 <= buy_fraction <= 1 and 0 <= sell_fraction <= 1):
        raise ValueError("fractions must be in [0, 1]")
    if not (buy_trigger_pct < sell_trigger_pct):
        raise ValueError("buy threshold must be below sell threshold")
    if not (0 <= fee_pct < 1) or min_trade_aud < 0 or starting_capital_aud <= 0:
        raise ValueError("invalid fees, minimum trade or capital")
    required = {"btc_price_aud", "wma_200"}
    if not isinstance(data, pd.DataFrame) or not required.issubset(data):
        raise ValueError("data requires btc_price_aud and wma_200")
    data = data.sort_index().copy()
    if not data.index.is_unique:
        raise ValueError("weekly index must be unique")
    # Moderate centre-weighting: nonzero edge weeks, exactly normalized.
    weight = np.arange(1, weeks + 1, dtype=float)
    weight = np.minimum(weight, weight[::-1])
    weight /= weight.sum()
    cash = float(starting_capital_aud)
    btc = 0.0
    fees = 0.0
    previous_dev = None
    pending = None
    campaign = None
    rows = []
    for ts, record in data.iterrows():
        price = float(record["btc_price_aud"])
        wma = float(record["wma_200"])
        valid = np.isfinite(price) and price > 0 and np.isfinite(wma) and wma > 0
        dev = 100 * (price / wma - 1) if valid else np.nan
        action = "HOLD"
        gross = 0.0
        trade_fee = 0.0
        if not valid:
            pending = None
            campaign = None
            previous_dev = None
            rows.append(dict(date=ts, action="SKIP_INVALID", price=price,
                             deviation_pct=dev, cash_aud=cash, btc_held=btc,
                             equity_aud=(cash + btc * price if np.isfinite(price) and price > 0 else np.nan),
                             trade_gross_aud=0.0, fee_aud=0.0))
            continue

        # Execute only last week's known trigger. Never use today's signal
        # to open a trade at today's closing price.
        if pending is not None:
            direction = pending
            pending = None
            campaign = dict(direction=direction, step=0,
                            budget=(cash * buy_fraction if direction == "BUY"
                                    else btc * sell_fraction))
        if campaign is not None:
            step = campaign["step"]
            portion = campaign["budget"] * weight[step]
            if campaign["direction"] == "BUY":
                gross = min(cash, portion)
                if gross >= min_trade_aud:
                    trade_fee = gross * fee_pct
                    btc += (gross - trade_fee) / price
                    cash -= gross
                    action = "BUY"
            else:
                quantity = min(btc, portion)
                gross = quantity * price
                if gross >= min_trade_aud:
                    trade_fee = gross * fee_pct
                    btc -= quantity
                    cash += gross - trade_fee
                    action = "SELL"
            fees += trade_fee
            campaign["step"] += 1
            if campaign["step"] == weeks:
                campaign = None

        # Threshold crossings schedule the next week's campaign. On an
        # opposite crossing, cancel the unfinished campaign immediately.
        if previous_dev is not None:
            next_direction = None
            if previous_dev > buy_trigger_pct >= dev:
                next_direction = "BUY"
            elif previous_dev < sell_trigger_pct <= dev:
                next_direction = "SELL"
            if next_direction:
                if campaign is None or campaign["direction"] != next_direction:
                    campaign = None
                    pending = next_direction
        previous_dev = dev
        rows.append(dict(date=ts, action=action, price=price,
                         deviation_pct=dev, cash_aud=cash, btc_held=btc,
                         equity_aud=cash + btc * price,
                         trade_gross_aud=gross if action != "HOLD" else 0.0,
                         fee_aud=trade_fee))
    history = pd.DataFrame(rows)
    ending = history["equity_aud"].dropna()
    summary = dict(ending_equity_aud=float(ending.iloc[-1]) if len(ending) else np.nan,
                   btc_held=btc, cash_aud=cash, fees_aud=fees,
                   buy_count=int((history.action == "BUY").sum()) if len(history) else 0,
                   sell_count=int((history.action == "SELL").sum()) if len(history) else 0)
    return history, summary


def prepare_weekly_wma(daily_prices_aud):
    """200 *prior completed* weekly closes; earliest output at week 201."""
    prices = pd.to_numeric(daily_prices_aud, errors="coerce")
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise TypeError("prices must have a DatetimeIndex")
    weekly = prices.sort_index().resample("W-MON").last()
    wma = weekly.shift(1).rolling(200, min_periods=200).mean()
    return pd.DataFrame({"btc_price_aud": weekly, "wma_200": wma}).dropna()
