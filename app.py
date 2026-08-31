#!/usr/bin/env python3
"""
BTC Dynamic DCA & Tactical Rebalancing Simulator v2
====================================================

Designed for:
- Historical backtesting
- Risk-weighted DCA
- Time-based deployment
- Deployment-pressure / catch-up mechanism
- Smooth risk multipliers
- Portfolio-target rebalancing / profit taking
- Proper BTC cost-basis tracking
- AUD portfolio accounting
- Forward deployment planning (without pretending future prices are known)

Install:
    pip install streamlit pandas requests plotly

Run:
    streamlit run btc_dynamic_dca_v2.py

Important:
- Historical mode uses only data available on each historical date.
- Forward Plan mode does NOT invent future BTC prices or future risk scores.
  It shows a deployment schedule using the current manually supplied risk score.
- This is a research/backtesting tool, not financial advice.
"""

import datetime as dt
import math
from datetime import timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


# ================================================================
# Constants
# ================================================================

GENESIS_DATE = dt.datetime(2009, 1, 3, tzinfo=timezone.utc)

DEFAULT_PL_CHEAP = -0.10
DEFAULT_PL_EXPENSIVE = 0.20

DEFAULT_FUND_CHEAP = 1.00
DEFAULT_FUND_EXPENSIVE = 1.50

# Smooth risk -> DCA multiplier curve.
# Lower risk score = cheaper BTC = larger DCA.
DEFAULT_RISK_POINTS = [
    (0.00, 3.00),
    (0.10, 2.60),
    (0.20, 2.10),
    (0.30, 1.60),
    (0.40, 1.25),
    (0.50, 1.00),
    (0.60, 0.75),
    (0.70, 0.50),
    (0.80, 0.25),
    (0.90, 0.10),
    (1.00, 0.00),
]

# Risk -> desired BTC portfolio weight for profit taking/rebalancing.
DEFAULT_TARGET_BTC_POINTS = [
    (0.00, 1.00),
    (0.10, 0.95),
    (0.20, 0.90),
    (0.30, 0.85),
    (0.40, 0.80),
    (0.50, 0.70),
    (0.60, 0.55),
    (0.70, 0.40),
    (0.80, 0.25),
    (0.90, 0.10),
    (1.00, 0.05),
]

DEFAULT_MAX_PERIOD_PCT = 0.20       # Never invest >20% of initial capital in one period
DEFAULT_MIN_CASH_RESERVE_PCT = 0.00
DEFAULT_PRESSURE_STRENGTH = 0.75
DEFAULT_MAX_RISK_MULTIPLIER = 3.00
DEFAULT_MAX_SELL_PCT_PERIOD = 0.25  # Avoid dumping >25% of BTC in one period
DEFAULT_SELL_THRESHOLD = 0.03       # Rebalance only if target weight differs by 3%+
DEFAULT_FEE_PCT = 0.00

REQUEST_HEADERS = {"User-Agent": "BTC-DCA-Simulator/2.0"}


# ================================================================
# Utility Functions
# ================================================================

def clamp(value, low, high):
    return max(low, min(high, value))


def interpolate(points, x):
    """Piecewise-linear interpolation."""
    points = sorted(points)

    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]

    for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
        if x1 <= x <= x2:
            if x2 == x1:
                return y1
            fraction = (x - x1) / (x2 - x1)
            return y1 + fraction * (y2 - y1)

    return points[-1][1]


def annualized_return(start_value, end_value, years):
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return 0.0
    return (end_value / start_value) ** (1.0 / years) - 1.0


def max_drawdown(values):
    series = pd.Series(values, dtype=float)
    if series.empty:
        return 0.0
    running_max = series.cummax()
    drawdown = series / running_max - 1.0
    return float(drawdown.min())


def format_pct(x):
    return f"{x:+.2f}%"


# ================================================================
# Data Fetchers
# ================================================================

@st.cache_data(ttl=3600)
def fetch_btc_history(start_date, end_date):
    """
    Fetch BTC/USD history from Blockchain.com.

    Extra history before start_date is fetched so the 200-day SMA has
    sufficient lookback data.
    """
    buffer_days = 300
    fetch_start = start_date - timedelta(days=buffer_days)

    url = "https://api.blockchain.info/charts/market-price"
    params = {
        "timespan": "all",
        "format": "json",
        "sampled": "false",
    }

    try:
        resp = requests.get(
            url,
            params=params,
            headers=REQUEST_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        st.error(f"Failed to fetch BTC price data: {exc}")
        return pd.DataFrame()

    values = payload.get("values", [])
    prices = []

    for point in values:
        try:
            timestamp = float(point["x"])
            price = float(point["y"])
            if price > 0:
                timestamp_dt = dt.datetime.fromtimestamp(
                    timestamp, tz=timezone.utc
                )
                prices.append(
                    {"date": timestamp_dt, "price": price}
                )
        except (KeyError, TypeError, ValueError):
            continue

    if not prices:
        return pd.DataFrame()

    df = pd.DataFrame(prices)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # Use requested range plus the lookback needed for indicators.
    df = df[
        (df.index >= fetch_start) &
        (df.index <= end_date)
    ].copy()

    return df


@st.cache_data(ttl=86400)
def fetch_aud_usd_rates(start_date, end_date):
    """
    Returns USD per AUD.

    Frankfurter publishes business-day FX rates, so the series is later
    forward-filled onto BTC dates.
    """
    if end_date < start_date:
        return None

    url = (
        f"https://api.frankfurter.app/"
        f"{start_date.strftime('%Y-%m-%d')}.."
        f"{end_date.strftime('%Y-%m-%d')}"
        f"?from=USD&to=AUD"
    )

    try:
        resp = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()

        rates = payload.get("rates", {})
        if not rates:
            return None

        # API returns AUD per USD. Convert to USD per AUD.
        usd_per_aud = {
            date_string: 1.0 / float(values["AUD"])
            for date_string, values in rates.items()
            if values.get("AUD", 0) > 0
        }

        if not usd_per_aud:
            return None

        series = pd.Series(usd_per_aud, dtype=float)
        series.index = pd.to_datetime(series.index, utc=True)
        series = series.sort_index()
        return series

    except Exception as exc:
        st.warning(
            f"Could not fetch AUD/USD rates: {exc}. "
            f"Using 0.70 USD/AUD as fallback."
        )
        return None


def align_fx_to_dates(data, fx_series, fallback=0.70):
    """Align business-day FX rates to BTC dates."""
    result = data.copy()

    if fx_series is None or fx_series.empty:
        result["usd_per_aud"] = fallback
        return result

    combined_index = result.index.union(fx_series.index).sort_values()
    fx = fx_series.reindex(combined_index).ffill()
    fx = fx.reindex(result.index).ffill().bfill().fillna(fallback)

    result["usd_per_aud"] = fx
    return result


# ================================================================
# Risk Engines
# ================================================================

def power_law_score(date, price, cheap=-0.10, expensive=0.20):
    """
    Power-law residual score.

    residual = log10(actual price) - log10(power-law fair value)

    cheap and expensive are residual thresholds:
      cheap      -> score 0
      expensive  -> score 1
    """
    if price <= 0:
        return 0.5, price

    days = (date - GENESIS_DATE).days
    if days <= 0:
        return 0.5, price

    fair_value_log = 5.84 * math.log10(days) - 17.01
    fair_value = 10 ** fair_value_log

    residual = math.log10(price) - fair_value_log

    denominator = expensive - cheap
    if denominator <= 0:
        return 0.5, fair_value

    score = (residual - cheap) / denominator
    score = clamp(score, 0.0, 1.0)

    return score, fair_value


def sma_score(price, sma, cheap=1.0, expensive=1.5):
    """Score based on BTC / 200-day SMA."""
    if price <= 0 or sma <= 0:
        return 0.5, sma

    ratio = price / sma

    denominator = expensive - cheap
    if denominator <= 0:
        return 0.5, sma

    score = (ratio - cheap) / denominator
    score = clamp(score, 0.0, 1.0)

    return score, sma


def add_risk_indicators(data, risk_model, params):
    result = data.copy()

    # Important: rolling SMA is calculated on the complete available
    # historical series, not only the execution rows.
    result["sma_200"] = (
        result["price"]
        .rolling(window=200, min_periods=1)
        .mean()
    )

    scores = []
    fair_values = []

    for timestamp, row in result.iterrows():
        price = float(row["price"])

        if risk_model == "Power Law Trend":
            score, fair_value = power_law_score(
                timestamp,
                price,
                params["pl_cheap"],
                params["pl_expensive"],
            )
        else:
            score, fair_value = sma_score(
                price,
                float(row["sma_200"]),
                params["fund_cheap"],
                params["fund_expensive"],
            )

        scores.append(score)
        fair_values.append(fair_value)

    result["risk_score"] = scores
    result["fair_value"] = fair_values

    result["price_to_fair"] = (
        result["price"] / result["fair_value"].replace(0, pd.NA)
    )

    result["dca_multiplier"] = result["risk_score"].apply(
        lambda x: interpolate(DEFAULT_RISK_POINTS, x)
    )

    result["target_btc_weight"] = result["risk_score"].apply(
        lambda x: interpolate(DEFAULT_TARGET_BTC_POINTS, x)
    )

    return result


# ================================================================
# Execution Schedule
# ================================================================

def select_execution_dates(df, frequency, day_of_week):
    """Select actual available market data dates."""
    if df.empty:
        return df.copy()

    if frequency == "Daily":
        return df.copy()

    if frequency == "Weekly":
        weekly = df[df.index.dayofweek == day_of_week].copy()

        # If a selected weekday is unavailable, use the first available
        # date in each calendar week.
        if weekly.empty:
            temp = df.copy()
            temp["week"] = temp.index.to_period("W-SUN")
            weekly = (
                temp.groupby("week", group_keys=False)
                .head(1)
                .drop(columns=["week"])
            )

        return weekly

    # Monthly: first available market observation in each month.
    temp = df.copy()
    temp["month"] = temp.index.to_period("M")
    monthly = (
        temp.groupby("month", group_keys=False)
        .head(1)
        .drop(columns=["month"])
    )
    return monthly


# ================================================================
# Portfolio Engine
# ================================================================

def simulate_dynamic_dca(df_full, params):
    """
    Core historical backtest.

    The strategy has three interacting components:

    1. Time target:
       How much capital would normally have been deployed by now?

    2. Risk multiplier:
       Cheap BTC gets a larger DCA allocation.

    3. Deployment pressure:
       If the strategy is behind its time target, purchases increase.
       If it is ahead, purchases decrease.

    Profit-taking is portfolio-target based rather than "sell X% of all BTC"
    because that makes the sell logic respond to the actual BTC/cash mix.
    """
    if df_full.empty:
        return pd.DataFrame(), {}

    start = params["start_date"]
    end = params["end_date"]

    df = df_full[
        (df_full.index >= start) &
        (df_full.index <= end)
    ].copy()

    if df.empty:
        return pd.DataFrame(), {}

    df = add_risk_indicators(
        df,
        params["risk_model"],
        params,
    )

    execution = select_execution_dates(
        df,
        params["frequency"],
        params["day_of_week"],
    )

    if execution.empty:
        return pd.DataFrame(), {}

    total_capital = float(params["total_capital_aud"])
    cash = total_capital
    btc = 0.0

    # Weighted-average BTC acquisition cost in AUD/BTC.
    btc_cost_basis_aud = 0.0

    cumulative_invested = 0.0
    cumulative_sold_proceeds = 0.0
    cumulative_realized_profit = 0.0
    cumulative_fees = 0.0

    trades = []

    n_periods = len(execution)

    for period_number, (timestamp, row) in enumerate(
        execution.iterrows(), start=1
    ):
        price_usd = float(row["price"])
        usd_per_aud = float(row["usd_per_aud"])

        if price_usd <= 0 or usd_per_aud <= 0:
            continue

        btc_price_aud = price_usd / usd_per_aud

        risk = float(row["risk_score"])
        risk_multiplier = float(row["dca_multiplier"])
        target_btc_weight = float(row["target_btc_weight"])

        # ------------------------------------------------------------
        # Time target
        # ------------------------------------------------------------
        time_progress = period_number / n_periods
        target_cumulative_invested = total_capital * time_progress

        deployment_gap = (
            target_cumulative_invested - cumulative_invested
        )

        # Convert the gap into a normalized pressure value.
        # Positive = behind schedule.
        gap_pct = deployment_gap / total_capital

        pressure = 1.0 + (
            clamp(
                gap_pct,
                -0.50,
                1.00,
            ) * params["pressure_strength"]
        )

        pressure = clamp(pressure, 0.50, 1.75)

        # ------------------------------------------------------------
        # Dynamic DCA purchase
        # ------------------------------------------------------------
        base_period_amount = total_capital / n_periods

        desired_buy = (
            base_period_amount
            * risk_multiplier
            * pressure
        )

        # Never exceed configured percentage of original capital in one
        # period.
        max_period_buy = (
            total_capital * params["max_period_pct"]
        )

        desired_buy = min(
            desired_buy,
            max_period_buy,
        )

        # Maintain minimum cash reserve.
        minimum_cash = (
            total_capital * params["min_cash_reserve_pct"]
        )

        available_for_buy = max(
            0.0,
            cash - minimum_cash,
        )

        desired_buy = min(
            desired_buy,
            available_for_buy,
        )

        # ------------------------------------------------------------
        # Portfolio-target rebalancing / profit taking
        # ------------------------------------------------------------
        portfolio_before = (
            cash + btc * btc_price_aud
        )

        current_btc_value = btc * btc_price_aud

        current_btc_weight = (
            current_btc_value / portfolio_before
            if portfolio_before > 0
            else 0.0
        )

        target_difference = (
            current_btc_weight - target_btc_weight
        )

        desired_sell = 0.0

        # Only sell if BTC allocation is materially above target.
        if (
            btc > 0
            and target_difference >= params["sell_threshold"]
        ):
            target_btc_value = (
                portfolio_before * target_btc_weight
            )

            excess_btc_value = max(
                0.0,
                current_btc_value - target_btc_value,
            )

            desired_sell = (
                excess_btc_value
                / btc_price_aud
            )

            max_btc_sell = btc * params["max_sell_pct_period"]

            desired_sell = min(
                desired_sell,
                max_btc_sell,
            )

        # ------------------------------------------------------------
        # Execute SELL first when over target.
        # ------------------------------------------------------------
        sell_proceeds = 0.0
        sell_fee = 0.0
        realized_profit = 0.0

        if desired_sell > 0:
            sell_value_gross = desired_sell * btc_price_aud
            sell_fee = sell_value_gross * params["fee_pct"]
            sell_proceeds = sell_value_gross - sell_fee

            # Weighted average cost basis of BTC sold.
            avg_cost_per_btc = (
                btc_cost_basis_aud / btc
                if btc > 0
                else 0.0
            )

            sold_cost_basis = desired_sell * avg_cost_per_btc
            realized_profit = (
                sell_proceeds - sold_cost_basis
            )

            btc -= desired_sell
            btc_cost_basis_aud -= sold_cost_basis
            btc_cost_basis_aud = max(0.0, btc_cost_basis_aud)

            cash += sell_proceeds

            cumulative_sold_proceeds += sell_proceeds
            cumulative_realized_profit += realized_profit
            cumulative_fees += sell_fee

        # ------------------------------------------------------------
        # Execute BUY.
        # ------------------------------------------------------------
        buy_amount = desired_buy
        buy_fee = buy_amount * params["fee_pct"]
        total_cash_used = buy_amount

        # If fee is charged in AUD, reduce actual BTC purchase amount.
        net_buy_amount = max(
            0.0,
            buy_amount - buy_fee,
        )

        btc_bought = (
            net_buy_amount / btc_price_aud
            if btc_price_aud > 0
            else 0.0
        )

        if btc_bought > 0:
            btc += btc_bought
            btc_cost_basis_aud += net_buy_amount
            cash -= total_cash_used
            cash = max(0.0, cash)

            cumulative_invested += net_buy_amount
            cumulative_fees += buy_fee

        # ------------------------------------------------------------
        # Portfolio after transactions.
        # ------------------------------------------------------------
        btc_value_aud = btc * btc_price_aud
        total_wealth_aud = cash + btc_value_aud

        actual_btc_weight = (
            btc_value_aud / total_wealth_aud
            if total_wealth_aud > 0
            else 0.0
        )

        avg_cost = (
            btc_cost_basis_aud / btc
            if btc > 0
            else 0.0
        )

        unrealized_profit = (
            btc_value_aud - btc_cost_basis_aud
        )

        trades.append(
            {
                "date": timestamp,
                "price_usd": price_usd,
                "btc_price_aud": btc_price_aud,
                "fair_value_usd": float(row["fair_value"]),
                "risk_score": risk,
                "dca_multiplier": risk_multiplier,
                "target_btc_weight": target_btc_weight,
                "actual_btc_weight": actual_btc_weight,
                "time_progress": time_progress,
                "target_cumulative_invested": target_cumulative_invested,
                "cumulative_invested": cumulative_invested,
                "deployment_gap": (
                    target_cumulative_invested
                    - cumulative_invested
                ),
                "pressure": pressure,
                "buy_aud": buy_amount if btc_bought > 0 else 0.0,
                "btc_bought": btc_bought,
                "sell_btc": desired_sell,
                "sell_proceeds_aud": sell_proceeds,
                "realized_profit_aud": realized_profit,
                "fees_aud": buy_fee + sell_fee,
                "btc_held": btc,
                "btc_cost_basis_aud": btc_cost_basis_aud,
                "btc_avg_cost_aud": avg_cost,
                "cash_aud": cash,
                "btc_value_aud": btc_value_aud,
                "total_wealth_aud": total_wealth_aud,
                "unrealized_profit_aud": unrealized_profit,
                "trade": (
                    "BUY+SELL"
                    if btc_bought > 0 and desired_sell > 0
                    else "BUY"
                    if btc_bought > 0
                    else "SELL"
                    if desired_sell > 0
                    else "HOLD"
                ),
            }
        )

    result = pd.DataFrame(trades)

    if result.empty:
        return result, {}

    final = result.iloc[-1]

    first_date = result["date"].iloc[0]
    last_date = result["date"].iloc[-1]

    years = max(
        (last_date - first_date).days / 365.25,
        1 / 365.25,
    )

    starting_capital = total_capital
    ending_wealth = float(final["total_wealth_aud"])

    cagr = annualized_return(
        starting_capital,
        ending_wealth,
        years,
    )

    summary = {
        "starting_capital_aud": starting_capital,
        "ending_wealth_aud": ending_wealth,
        "cash_aud": float(final["cash_aud"]),
        "btc_held": float(final["btc_held"]),
        "btc_value_aud": float(final["btc_value_aud"]),
        "cumulative_invested_aud": float(final["cumulative_invested"]),
        "realized_profit_aud": float(
            result["realized_profit_aud"].sum()
        ),
        "unrealized_profit_aud": float(
            final["unrealized_profit_aud"]
        ),
        "fees_aud": float(result["fees_aud"].sum()),
        "return_pct": (
            ending_wealth / starting_capital - 1.0
        ) * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_drawdown(
            result["total_wealth_aud"]
        ) * 100.0,
        "periods": len(result),
        "final_risk": float(final["risk_score"]),
        "final_btc_weight": float(final["actual_btc_weight"]),
        "final_target_weight": float(final["target_btc_weight"]),
        "final_avg_cost_aud": float(final["btc_avg_cost_aud"]),
    }

    return result, summary


# ================================================================
# Benchmark Strategies
# ================================================================

def simulate_equal_dca(data, total_capital):
    """Equal DCA using the same execution dates as the dynamic strategy."""
    if data.empty or total_capital <= 0:
        return {}, pd.DataFrame()

    periods = len(data)
    amount_per_period = total_capital / periods

    cash = total_capital
    btc = 0.0
    rows = []

    for timestamp, row in data.iterrows():
        price_aud = float(row["price"]) / float(row["usd_per_aud"])

        if price_aud <= 0:
            continue

        buy = min(amount_per_period, cash)
        btc += buy / price_aud
        cash -= buy

        wealth = cash + btc * price_aud

        rows.append(
            {
                "date": timestamp,
                "btc": btc,
                "cash": cash,
                "wealth": wealth,
            }
        )

    if not rows:
        return {}, pd.DataFrame()

    result = pd.DataFrame(rows)
    final = result.iloc[-1]

    summary = {
        "btc": float(final["btc"]),
        "cash": float(final["cash"]),
        "wealth": float(final["wealth"]),
        "return_pct": (
            final["wealth"] / total_capital - 1
        ) * 100,
        "max_drawdown_pct": max_drawdown(
            result["wealth"]
        ) * 100,
    }

    return summary, result


def simulate_lump_sum(data, total_capital):
    """Invest all capital on the first execution date."""
    if data.empty or total_capital <= 0:
        return {}, pd.DataFrame()

    first = data.iloc[0]
    price_aud_first = float(first["price"]) / float(first["usd_per_aud"])

    if price_aud_first <= 0:
        return {}, pd.DataFrame()

    btc = total_capital / price_aud_first
    rows = []

    for timestamp, row in data.iterrows():
        price_aud = float(row["price"]) / float(row["usd_per_aud"])
        wealth = btc * price_aud

        rows.append(
            {
                "date": timestamp,
                "btc": btc,
                "wealth": wealth,
            }
        )

    result = pd.DataFrame(rows)
    final = result.iloc[-1]

    summary = {
        "btc": btc,
        "wealth": float(final["wealth"]),
        "return_pct": (
            final["wealth"] / total_capital - 1
        ) * 100,
        "max_drawdown_pct": max_drawdown(
            result["wealth"]
        ) * 100,
    }

    return summary, result


# ================================================================
# Forward Deployment Planner
# ================================================================

def build_forward_plan(
    capital,
    start_date,
    end_date,
    frequency,
    risk_score,
    btc_price_usd,
    usd_per_aud,
):
    """
    Creates a forward deployment schedule.

    Future BTC price and risk are deliberately NOT forecast.
    The current supplied risk score is used to calculate the planned
    DCA intensity for the schedule.

    This is a planning tool, not a price prediction.
    """
    if end_date <= start_date:
        return pd.DataFrame()

    dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D",
        tz="UTC",
    )

    if frequency == "Weekly":
        dates = dates[dates.dayofweek == 0]

    elif frequency == "Monthly":
        # First day of each month.
        dates = dates[dates.day == 1]

    if len(dates) == 0:
        dates = pd.DatetimeIndex(
            [pd.Timestamp(start_date, tz="UTC")]
        )

    n = len(dates)

    risk_multiplier = interpolate(
        DEFAULT_RISK_POINTS,
        clamp(risk_score, 0, 1),
    )

    base = capital / n

    # Keep the forward schedule conservative and visible.
    max_period = capital * DEFAULT_MAX_PERIOD_PCT

    rows = []
    cumulative = 0.0

    for i, date in enumerate(dates, start=1):
        time_progress = i / n
        target_cumulative = capital * time_progress
        gap = target_cumulative - cumulative

        pressure = 1.0 + (
            clamp(gap / capital, -0.50, 1.00)
            * DEFAULT_PRESSURE_STRENGTH
        )
        pressure = clamp(pressure, 0.50, 1.75)

        planned = min(
            base * risk_multiplier * pressure,
            max_period,
            max(0.0, capital - cumulative),
        )

        cumulative += planned

        rows.append(
            {
                "date": date,
                "risk_score": risk_score,
                "risk_multiplier": risk_multiplier,
                "time_progress_pct": time_progress * 100,
                "target_cumulative_aud": target_cumulative,
                "planned_buy_aud": planned,
                "cumulative_planned_aud": cumulative,
                "capital_remaining_aud": capital - cumulative,
                "btc_price_usd_reference": btc_price_usd,
                "usd_per_aud_reference": usd_per_aud,
                "btc_estimate_at_reference_price": (
                    planned * usd_per_aud / btc_price_usd
                    if btc_price_usd > 0
                    else 0.0
                ),
            }
        )

    return pd.DataFrame(rows)


# ================================================================
# Streamlit UI
# ================================================================

st.set_page_config(
    page_title="BTC Dynamic DCA & Tactical Rebalancer v2",
    layout="wide",
)

st.title("Bitcoin Dynamic DCA & Tactical Rebalancer v2")
st.caption(
    "Risk-weighted DCA + time deployment + deployment pressure + "
    "portfolio-target rebalancing"
)

# ------------------------------------------------
# Sidebar
# ------------------------------------------------

with st.sidebar:
    st.header("Mode")

    mode = st.radio(
        "Analysis Mode",
        [
            "Historical Backtest",
            "Forward Deployment Plan",
        ],
    )

    st.divider()

    st.header("Capital")

    total_capital_aud = st.number_input(
        "Starting Capital (AUD)",
        min_value=1000.0,
        max_value=100_000_000.0,
        value=500_000.0,
        step=10_000.0,
    )

    frequency = st.selectbox(
        "Execution Frequency",
        ["Weekly", "Daily", "Monthly"],
        index=0,
    )

    day_map = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }

    selected_day_name = st.selectbox(
        "Weekly Execution Day",
        list(day_map.keys()),
        index=0,
        disabled=(frequency != "Weekly"),
    )

    selected_day = day_map[selected_day_name]

    st.divider()

    st.header("Risk Model")

    risk_model = st.radio(
        "Risk Metric",
        [
            "Power Law Trend",
            "SMA Ratio (200-day)",
        ],
    )

    st.caption(
        "Risk score: 0 = very cheap / high allocation, "
        "1 = very expensive / low allocation."
    )

    st.divider()

    st.header("Dynamic DCA Controls")

    pressure_strength = st.slider(
        "Deployment Pressure Strength",
        min_value=0.0,
        max_value=1.5,
        value=DEFAULT_PRESSURE_STRENGTH,
        step=0.05,
        help=(
            "Controls how strongly the strategy catches up when it is "
            "behind its time-based deployment target."
        ),
    )

    max_period_pct = st.slider(
        "Maximum Buy Per Period (% of starting capital)",
        min_value=1.0,
        max_value=50.0,
        value=DEFAULT_MAX_PERIOD_PCT * 100,
        step=1.0,
    ) / 100.0

    min_cash_reserve_pct = st.slider(
        "Minimum Cash Reserve (%)",
        min_value=0.0,
        max_value=50.0,
        value=DEFAULT_MIN_CASH_RESERVE_PCT * 100,
        step=1.0,
    ) / 100.0

    st.divider()

    st.header("Rebalancing / Profit Taking")

    sell_threshold = st.slider(
        "Rebalance Threshold",
        min_value=0.0,
        max_value=0.20,
        value=DEFAULT_SELL_THRESHOLD,
        step=0.01,
        help=(
            "The strategy only sells when actual BTC portfolio weight "
            "is this much above its risk-derived target."
        ),
    )

    max_sell_pct_period = st.slider(
        "Maximum BTC Sold Per Period (%)",
        min_value=1.0,
        max_value=100.0,
        value=DEFAULT_MAX_SELL_PCT_PERIOD * 100,
        step=1.0,
    ) / 100.0

    fee_pct = st.number_input(
        "Trading Fee (%)",
        min_value=0.0,
        max_value=5.0,
        value=DEFAULT_FEE_PCT * 100,
        step=0.01,
    ) / 100.0


# ================================================================
# Dates / Parameters
# ================================================================

today = dt.datetime.now(timezone.utc).date()
genesis = dt.date(2009, 1, 3)

if mode == "Historical Backtest":
    start_date = st.sidebar.date_input(
        "Backtest Start Date",
        value=dt.date(2020, 1, 1),
        min_value=genesis,
        max_value=today,
        format="DD/MM/YYYY",
    )

    end_date = st.sidebar.date_input(
        "Backtest End Date",
        value=today,
        min_value=start_date,
        max_value=today,
        format="DD/MM/YYYY",
    )

else:
    start_date = st.sidebar.date_input(
        "Deployment Start Date",
        value=today,
        min_value=today,
        format="DD/MM/YYYY",
    )

    end_date = st.sidebar.date_input(
        "Deployment End Date",
        value=today + timedelta(days=90),
        min_value=start_date + timedelta(days=1),
        format="DD/MM/YYYY",
    )

    st.sidebar.divider()
    st.sidebar.header("Current Market Assumptions")

    forward_risk_score = st.sidebar.slider(
        "Current Risk Score",
        min_value=0.0,
        max_value=1.0,
        value=0.50,
        step=0.01,
    )

    forward_btc_price_usd = st.sidebar.number_input(
        "Current BTC Price (USD)",
        min_value=1.0,
        value=100_000.0,
        step=1_000.0,
    )

    forward_usd_per_aud = st.sidebar.number_input(
        "USD per AUD",
        min_value=0.10,
        max_value=2.00,
        value=0.65,
        step=0.01,
    )


if end_date <= start_date:
    st.error("End date must be after start date.")
    st.stop()


params = {
    "risk_model": risk_model,
    "frequency": frequency,
    "day_of_week": selected_day,
    "fund_cheap": DEFAULT_FUND_CHEAP,
    "fund_expensive": DEFAULT_FUND_EXPENSIVE,
    "pl_cheap": DEFAULT_PL_CHEAP,
    "pl_expensive": DEFAULT_PL_EXPENSIVE,
    "total_capital_aud": total_capital_aud,
    "pressure_strength": pressure_strength,
    "max_period_pct": max_period_pct,
    "min_cash_reserve_pct": min_cash_reserve_pct,
    "sell_threshold": sell_threshold,
    "max_sell_pct_period": max_sell_pct_period,
    "fee_pct": fee_pct,
    "start_date": dt.datetime.combine(
        start_date,
        dt.time.min,
        tzinfo=timezone.utc,
    ),
    "end_date": dt.datetime.combine(
        end_date,
        dt.time.max,
        tzinfo=timezone.utc,
    ),
}


# ================================================================
# Historical Backtest
# ================================================================

if mode == "Historical Backtest":

    with st.spinner("Loading BTC and AUD/USD history..."):
        df_full = fetch_btc_history(
            params["start_date"],
            params["end_date"],
        )

        fx_series = fetch_aud_usd_rates(
            params["start_date"],
            params["end_date"],
        )

    if df_full.empty:
        st.error("No BTC price data was returned.")
        st.stop()

    df_full = align_fx_to_dates(
        df_full,
        fx_series,
    )

    # Run strategy.
    trade_df, summary = simulate_dynamic_dca(
        df_full,
        params,
    )

    if trade_df.empty:
        st.error(
            "The simulation produced no observations. "
            "Try a wider date range."
        )
        st.stop()

    # Benchmarks use same execution dates.
    benchmark_data = df_full[
        (df_full.index >= params["start_date"]) &
        (df_full.index <= params["end_date"])
    ].copy()

    benchmark_data = select_execution_dates(
        benchmark_data,
        frequency,
        selected_day,
    )

    equal_summary, equal_df = simulate_equal_dca(
        benchmark_data,
        total_capital_aud,
    )

    lump_summary, lump_df = simulate_lump_sum(
        benchmark_data,
        total_capital_aud,
    )

    # ------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------

    st.subheader("Dynamic Strategy")

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric(
        "Ending Wealth",
        f"${summary['ending_wealth_aud']:,.0f}",
        format_pct(summary["return_pct"]),
    )

    c2.metric(
        "BTC Held",
        f"{summary['btc_held']:.6f}",
    )

    c3.metric(
        "Cash",
        f"${summary['cash_aud']:,.0f}",
    )

    c4.metric(
        "Invested",
        f"${summary['cumulative_invested_aud']:,.0f}",
    )

    c5.metric(
        "Max Drawdown",
        f"{summary['max_drawdown_pct']:.2f}%",
    )

    c6.metric(
        "CAGR",
        f"{summary['cagr_pct']:.2f}%",
    )

    # ------------------------------------------------------------
    # Benchmark table
    # ------------------------------------------------------------

    st.subheader("Strategy Comparison")

    comparison = pd.DataFrame(
        [
            {
                "Strategy": "Dynamic Risk DCA",
                "Ending Wealth (AUD)": summary["ending_wealth_aud"],
                "Return": summary["return_pct"],
                "Max Drawdown": summary["max_drawdown_pct"],
                "BTC": summary["btc_held"],
            },
            {
                "Strategy": "Equal DCA",
                "Ending Wealth (AUD)": equal_summary.get(
                    "wealth", 0
                ),
                "Return": equal_summary.get(
                    "return_pct", 0
                ),
                "Max Drawdown": equal_summary.get(
                    "max_drawdown_pct", 0
                ),
                "BTC": equal_summary.get(
                    "btc", 0
                ),
            },
            {
                "Strategy": "Lump Sum",
                "Ending Wealth (AUD)": lump_summary.get(
                    "wealth", 0
                ),
                "Return": lump_summary.get(
                    "return_pct", 0
                ),
                "Max Drawdown": lump_summary.get(
                    "max_drawdown_pct", 0
                ),
                "BTC": lump_summary.get(
                    "btc", 0
                ),
            },
        ]
    )

    display_comparison = comparison.copy()
    display_comparison["Ending Wealth (AUD)"] = (
        display_comparison["Ending Wealth (AUD)"]
        .map(lambda x: f"${x:,.0f}")
    )
    display_comparison["Return"] = (
        display_comparison["Return"]
        .map(lambda x: f"{x:+.2f}%")
    )
    display_comparison["Max Drawdown"] = (
        display_comparison["Max Drawdown"]
        .map(lambda x: f"{x:.2f}%")
    )
    display_comparison["BTC"] = (
        display_comparison["BTC"]
        .map(lambda x: f"{x:.6f}")
    )

    st.dataframe(
        display_comparison,
        use_container_width=True,
        hide_index=True,
    )

    # ------------------------------------------------------------
    # Risk chart
    # ------------------------------------------------------------

    st.subheader("Risk Score, BTC Price & Fair Value")

    fig_risk = go.Figure()

    fig_risk.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["risk_score"],
            name="Risk Score",
            line=dict(width=2),
        )
    )

    fig_risk.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["dca_multiplier"],
            name="DCA Multiplier",
            yaxis="y2",
            line=dict(width=2, dash="dash"),
        )
    )

    fig_risk.update_layout(
        height=500,
        template="plotly_dark",
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(
            title="Risk Score",
            range=[0, 1],
        ),
        yaxis2=dict(
            title="DCA Multiplier",
            overlaying="y",
            side="right",
        ),
    )

    st.plotly_chart(
        fig_risk,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # Portfolio chart
    # ------------------------------------------------------------

    st.subheader("Portfolio Wealth & BTC Allocation")

    fig_portfolio = go.Figure()

    fig_portfolio.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["total_wealth_aud"],
            name="Total Wealth (AUD)",
            line=dict(width=3),
        )
    )

    fig_portfolio.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["cash_aud"],
            name="Cash (AUD)",
            line=dict(width=2, dash="dash"),
        )
    )

    fig_portfolio.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["btc_value_aud"],
            name="BTC Value (AUD)",
            line=dict(width=2),
        )
    )

    fig_portfolio.update_layout(
        height=500,
        template="plotly_dark",
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(
            title="AUD",
            tickprefix="$",
        ),
    )

    st.plotly_chart(
        fig_portfolio,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # BTC price and trade markers
    # ------------------------------------------------------------

    st.subheader("BTC Price & Trade Execution")

    fig_trades = go.Figure()

    fig_trades.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["price_usd"],
            name="BTC Price (USD)",
            line=dict(width=2),
        )
    )

    buys = trade_df[trade_df["buy_aud"] > 0]
    sells = trade_df[trade_df["sell_btc"] > 0]

    if not buys.empty:
        fig_trades.add_trace(
            go.Scatter(
                x=buys["date"],
                y=buys["price_usd"],
                mode="markers",
                name="BUY",
                marker=dict(
                    size=8,
                    symbol="triangle-up",
                ),
            )
        )

    if not sells.empty:
        fig_trades.add_trace(
            go.Scatter(
                x=sells["date"],
                y=sells["price_usd"],
                mode="markers",
                name="SELL / REBALANCE",
                marker=dict(
                    size=8,
                    symbol="triangle-down",
                ),
            )
        )

    fig_trades.update_layout(
        height=550,
        template="plotly_dark",
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(
            title="BTC Price (USD)",
            tickprefix="$",
        ),
    )

    st.plotly_chart(
        fig_trades,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # Deployment pressure chart
    # ------------------------------------------------------------

    st.subheader("Deployment Pressure")

    fig_pressure = go.Figure()

    fig_pressure.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["target_cumulative_invested"],
            name="Time Target",
            line=dict(width=2, dash="dash"),
        )
    )

    fig_pressure.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["cumulative_invested"],
            name="Actual Invested",
            line=dict(width=3),
        )
    )

    fig_pressure.update_layout(
        height=450,
        template="plotly_dark",
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(
            title="AUD",
            tickprefix="$",
        ),
    )

    st.plotly_chart(
        fig_pressure,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # Detailed activity
    # ------------------------------------------------------------

    st.subheader("Detailed Activity History")

    display_df = trade_df[
        [
            "date",
            "trade",
            "price_usd",
            "risk_score",
            "dca_multiplier",
            "target_btc_weight",
            "actual_btc_weight",
            "pressure",
            "buy_aud",
            "btc_bought",
            "sell_btc",
            "sell_proceeds_aud",
            "realized_profit_aud",
            "btc_held",
            "cash_aud",
            "total_wealth_aud",
        ]
    ].copy()

    display_df["date"] = display_df["date"].dt.strftime(
        "%d/%m/%Y"
    )

    display_df["price_usd"] = display_df[
        "price_usd"
    ].map(lambda x: f"${x:,.0f}")

    display_df["risk_score"] = display_df[
        "risk_score"
    ].map(lambda x: f"{x:.3f}")

    display_df["dca_multiplier"] = display_df[
        "dca_multiplier"
    ].map(lambda x: f"{x:.2f}x")

    display_df["target_btc_weight"] = display_df[
        "target_btc_weight"
    ].map(lambda x: f"{x:.1%}")

    display_df["actual_btc_weight"] = display_df[
        "actual_btc_weight"
    ].map(lambda x: f"{x:.1%}")

    display_df["pressure"] = display_df[
        "pressure"
    ].map(lambda x: f"{x:.2f}x")

    for col in [
        "buy_aud",
        "sell_proceeds_aud",
        "realized_profit_aud",
        "cash_aud",
        "total_wealth_aud",
    ]:
        display_df[col] = display_df[col].map(
            lambda x: f"${x:,.0f}"
        )

    for col in [
        "btc_bought",
        "sell_btc",
        "btc_held",
    ]:
        display_df[col] = display_df[col].map(
            lambda x: f"{x:.6f}"
        )

    display_df.columns = [
        "Date",
        "Action",
        "BTC USD",
        "Risk",
        "DCA Mult.",
        "Target BTC %",
        "Actual BTC %",
        "Pressure",
        "Buy AUD",
        "BTC Bought",
        "BTC Sold",
        "Sale Proceeds",
        "Realized Profit",
        "BTC Balance",
        "Cash",
        "Total Wealth",
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        height=500,
        hide_index=True,
    )

    # ------------------------------------------------------------
    # CSV download
    # ------------------------------------------------------------

    st.download_button(
        "Download Full Backtest CSV",
        data=trade_df.to_csv(index=False).encode("utf-8"),
        file_name="btc_dynamic_dca_backtest.csv",
        mime="text/csv",
    )


# ================================================================
# Forward Plan
# ================================================================

else:

    risk_multiplier = interpolate(
        DEFAULT_RISK_POINTS,
        forward_risk_score,
    )

    st.subheader("Forward Deployment Plan")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Capital",
        f"${total_capital_aud:,.0f} AUD",
    )

    c2.metric(
        "Current Risk Score",
        f"{forward_risk_score:.2f}",
    )

    c3.metric(
        "DCA Multiplier",
        f"{risk_multiplier:.2f}x",
    )

    c4.metric(
        "Reference BTC Price",
        f"${forward_btc_price_usd:,.0f}",
    )

    plan = build_forward_plan(
        total_capital_aud,
        start_date,
        end_date,
        frequency,
        forward_risk_score,
        forward_btc_price_usd,
        forward_usd_per_aud,
    )

    if plan.empty:
        st.warning("No deployment dates were generated.")
        st.stop()

    final_planned = float(
        plan["cumulative_planned_aud"].iloc[-1]
    )

    remaining = float(
        plan["capital_remaining_aud"].iloc[-1]
    )

    p1, p2, p3 = st.columns(3)

    p1.metric(
        "Planned Deployment",
        f"${final_planned:,.0f}",
    )

    p2.metric(
        "Capital Remaining",
        f"${remaining:,.0f}",
    )

    p3.metric(
        "Number of Purchases",
        f"{len(plan)}",
    )

    st.info(
        "Forward planning warning: future BTC prices and future risk "
        "scores are unknown. This schedule uses the current risk score "
        "and current BTC price only as reference assumptions. It does "
        "not predict future prices."
    )

    # ------------------------------------------------------------
    # Plan chart
    # ------------------------------------------------------------

    fig_plan = go.Figure()

    fig_plan.add_trace(
        go.Scatter(
            x=plan["date"],
            y=plan["target_cumulative_aud"],
            name="Time Target",
            line=dict(width=2, dash="dash"),
        )
    )

    fig_plan.add_trace(
        go.Scatter(
            x=plan["date"],
            y=plan["cumulative_planned_aud"],
            name="Planned Deployment",
            line=dict(width=3),
        )
    )

    fig_plan.update_layout(
        height=450,
        template="plotly_dark",
        xaxis=dict(title="Date"),
        yaxis=dict(
            title="AUD",
            tickprefix="$",
        ),
    )

    st.plotly_chart(
        fig_plan,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # Plan table
    # ------------------------------------------------------------

    display_plan = plan.copy()

    display_plan["date"] = display_plan["date"].dt.strftime(
        "%d/%m/%Y"
    )

    display_plan["risk_score"] = display_plan[
        "risk_score"
    ].map(lambda x: f"{x:.2f}")

    display_plan["risk_multiplier"] = display_plan[
        "risk_multiplier"
    ].map(lambda x: f"{x:.2f}x")

    display_plan["time_progress_pct"] = display_plan[
        "time_progress_pct"
    ].map(lambda x: f"{x:.1f}%")

    for col in [
        "target_cumulative_aud",
        "planned_buy_aud",
        "cumulative_planned_aud",
        "capital_remaining_aud",
    ]:
        display_plan[col] = display_plan[col].map(
            lambda x: f"${x:,.0f}"
        )

    display_plan = display_plan[
        [
            "date",
            "risk_score",
            "risk_multiplier",
            "time_progress_pct",
            "target_cumulative_aud",
            "planned_buy_aud",
            "cumulative_planned_aud",
            "capital_remaining_aud",
        ]
    ]

    display_plan.columns = [
        "Date",
        "Risk",
        "DCA Mult.",
        "Time Progress",
        "Time Target",
        "Planned Buy",
        "Cumulative Planned",
        "Capital Remaining",
    ]

    st.dataframe(
        display_plan,
        use_container_width=True,
        height=500,
        hide_index=True,
    )

    st.download_button(
        "Download Forward Plan CSV",
        data=plan.to_csv(index=False).encode("utf-8"),
        file_name="btc_forward_deployment_plan.csv",
        mime="text/csv",
    )


# ================================================================
# Methodology Notes
# ================================================================

with st.expander("How the new Dynamic DCA engine works"):
    st.markdown(
        """
### 1. Time-based deployment

The model calculates how much of the starting capital would normally
have been deployed by each point in the selected period.

### 2. Risk-weighted DCA

The risk score is converted into a smooth multiplier:

- Low risk / cheap BTC -> larger purchase
- Neutral risk -> approximately normal DCA
- High risk / expensive BTC -> smaller purchase
- Extreme risk -> potentially zero new purchases

### 3. Deployment pressure

The model compares:

**Target cumulative investment**

against

**Actual cumulative investment**

If the strategy is behind schedule, the next purchase is increased.

This prevents the model from simply sitting on cash indefinitely after
a long expensive period.

### 4. Maximum purchase size

A hard per-period maximum prevents one unusually cheap reading from
consuming the entire portfolio.

### 5. Portfolio-target profit taking

Instead of automatically selling a fixed percentage of all BTC, the
model calculates a risk-derived target BTC portfolio weight.

Example:

If the model says the target BTC allocation is 40%, but BTC has risen
until it represents 60% of the portfolio, the strategy sells enough BTC
to move toward the 40% target.

### 6. Cost basis

The model tracks the weighted-average AUD acquisition cost of BTC.
Realized profit is therefore:

**Sale proceeds - cost basis of BTC sold - fees**

rather than incorrectly treating all sale proceeds as profit.

### 7. Forward mode

Forward mode deliberately does not fill future dates with today's BTC
price and pretend that those are future observations. Future prices and
future risk scores are unknown, so the forward planner clearly labels
today's market values as assumptions.
"""
    )
