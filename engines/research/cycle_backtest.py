"""Research-only, causal full-cycle BTC strategy simulator.

Separate from Production and the accumulation-only DCA backtest. Models a fixed initial
AUD cash pool, risk-triggered buys and sells, fees, FIFO realised P&L, cash, and equity.

Input risk scores must be point-in-time/causally scored. Each row is treated as executable
at its own close; account for execution slippage and signal publication timing before use.
"""
from collections import deque

import numpy as np
import pandas as pd


def simulate_cycle_strategy(
    data,
    starting_capital_aud=500_000.0,
    buy_threshold=0.25,
    sell_threshold=0.75,
    max_buy_pct_period=0.05,
    max_sell_pct_period=0.20,
    fee_pct=0.001,
    min_trade_aud=100.0,
):
    """Simulate risk-triggered buys and sells using AUD prices and causal risk scores.

    Required columns: btc_price_aud and risk_score. Low risk means cheaper; high risk
    means more expensive. Buys deploy at most max_buy_pct_period of initial capital,
    scaled linearly from full size at risk=0 to zero at buy_threshold. Sells liquidate
    at most max_sell_pct_period of current BTC, scaled from zero at sell_threshold to
    full size at risk=1. Unused cash remains cash; no forced final sale occurs.
    Fees apply to gross buy contributions and gross sale proceeds.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    required = {"btc_price_aud", "risk_score"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if not np.isfinite(starting_capital_aud) or starting_capital_aud <= 0:
        raise ValueError("starting_capital_aud must be finite and positive")
    if not (0 <= buy_threshold < sell_threshold <= 1):
        raise ValueError("Require 0 <= buy_threshold < sell_threshold <= 1")
    if not (0 < max_buy_pct_period <= 1 and 0 < max_sell_pct_period <= 1):
        raise ValueError("Buy/sell per-period limits must be in (0, 1]")
    if not (0 <= fee_pct < 1):
        raise ValueError("fee_pct must be in [0, 1)")
    if min_trade_aud < 0:
        raise ValueError("min_trade_aud cannot be negative")
    if data.empty:
        return pd.DataFrame(), {}

    out = data.copy().sort_index()
    cash = float(starting_capital_aud)
    btc = 0.0
    cumulative_buy_gross = cumulative_sell_gross = cumulative_fees = 0.0
    realized_pnl = 0.0
    lots = deque()
    rows = []

    for timestamp, row in out.iterrows():
        price = pd.to_numeric(pd.Series([row["btc_price_aud"]]), errors="coerce").iloc[0]
        risk = pd.to_numeric(pd.Series([row["risk_score"]]), errors="coerce").iloc[0]
        action = "HOLD"
        buy_gross = sell_gross = fee = bought = sold = 0.0
        realized_this_period = 0.0

        if not np.isfinite(price) or price <= 0 or not np.isfinite(risk) or not (0 <= risk <= 1):
            equity = cash + btc * price if np.isfinite(price) and price > 0 else np.nan
            remaining_cost_basis = sum(lot[1] for lot in lots)
            btc_value = btc * price if np.isfinite(price) and price > 0 else np.nan
            unrealized = btc_value - remaining_cost_basis if np.isfinite(btc_value) else np.nan
            rows.append({
                "date": timestamp, "btc_price_aud": price, "risk_score": risk,
                "action": "SKIP_INVALID_INPUT", "buy_gross_aud": 0.0,
                "sell_gross_aud": 0.0, "fees_aud": 0.0, "btc_bought": 0.0,
                "btc_sold": 0.0, "btc_held": btc, "cash_aud": cash,
                "btc_value_aud": btc_value,
                "equity_aud": equity, "realized_pnl_aud": realized_pnl,
                "realized_pnl_period_aud": 0.0,
                "unrealized_pnl_aud": unrealized,
                "total_pnl_aud": equity - starting_capital_aud if np.isfinite(equity) else np.nan,
                "cumulative_buy_gross_aud": cumulative_buy_gross,
                "cumulative_sell_gross_aud": cumulative_sell_gross,
                "cumulative_fees_aud": cumulative_fees,
            })
            continue

        if risk < buy_threshold and cash >= min_trade_aud:
            strength = (buy_threshold - risk) / max(buy_threshold, 1e-12)
            buy_gross = min(cash, starting_capital_aud * max_buy_pct_period * strength)
            if buy_gross < min_trade_aud:
                buy_gross = 0.0
            if buy_gross > 0:
                fee = buy_gross * fee_pct
                bought = (buy_gross - fee) / price
                cash -= buy_gross
                btc += bought
                cumulative_buy_gross += buy_gross
                cumulative_fees += fee
                lots.append([bought, buy_gross])
                action = "BUY"

        elif risk > sell_threshold and btc > 0:
            strength = (risk - sell_threshold) / max(1.0 - sell_threshold, 1e-12)
            fraction = max_sell_pct_period * strength
            sold = btc * fraction
            sell_gross = sold * price
            fee = sell_gross * fee_pct
            net_proceeds = sell_gross - fee
            cash += net_proceeds
            btc -= sold
            cumulative_sell_gross += sell_gross
            cumulative_fees += fee

            remaining_to_match = sold
            while remaining_to_match > 1e-14 and lots:
                lot_btc, lot_cost = lots[0]
                matched = min(remaining_to_match, lot_btc)
                matched_cost = lot_cost * (matched / lot_btc)
                matched_proceeds = net_proceeds * (matched / sold) if sold > 0 else 0.0
                realized_this_period += matched_proceeds - matched_cost
                lot_btc -= matched
                lot_cost -= matched_cost
                remaining_to_match -= matched
                if lot_btc <= 1e-14:
                    lots.popleft()
                else:
                    lots[0] = [lot_btc, lot_cost]
            realized_pnl += realized_this_period
            action = "SELL"

        btc_value = btc * price
        equity = cash + btc_value
        remaining_cost_basis = sum(lot[1] for lot in lots)
        unrealized = btc_value - remaining_cost_basis
        rows.append({
            "date": timestamp, "btc_price_aud": price, "risk_score": risk,
            "action": action, "buy_gross_aud": buy_gross, "sell_gross_aud": sell_gross,
            "fees_aud": fee, "btc_bought": bought, "btc_sold": sold, "btc_held": btc,
            "cash_aud": cash, "btc_value_aud": btc_value, "equity_aud": equity,
            "realized_pnl_aud": realized_pnl,
            "realized_pnl_period_aud": realized_this_period,
            "unrealized_pnl_aud": unrealized,
            "total_pnl_aud": equity - starting_capital_aud,
            "cumulative_buy_gross_aud": cumulative_buy_gross,
            "cumulative_sell_gross_aud": cumulative_sell_gross,
            "cumulative_fees_aud": cumulative_fees,
        })

    result = pd.DataFrame(rows)
    valid = result.dropna(subset=["equity_aud"])
    if valid.empty:
        return result, {}
    final = valid.iloc[-1]
    summary = {
        "starting_capital_aud": float(starting_capital_aud),
        "ending_equity_aud": float(final["equity_aud"]),
        "total_pnl_aud": float(final["equity_aud"] - starting_capital_aud),
        "total_return_pct": float((final["equity_aud"] / starting_capital_aud - 1) * 100),
        "realized_pnl_aud": float(final["realized_pnl_aud"]),
        "unrealized_pnl_aud": float(final["unrealized_pnl_aud"]),
        "cash_remaining_aud": float(final["cash_aud"]),
        "btc_held": float(final["btc_held"]),
        "btc_value_aud": float(final["btc_value_aud"]),
        "fees_aud": float(result["fees_aud"].fillna(0).sum()),
        "buy_count": int((result["action"] == "BUY").sum()),
        "sell_count": int((result["action"] == "SELL").sum()),
        "observations": int(len(result)),
    }
    return result, summary



def simulate_next_observation_strategy(data, **kwargs):
    """Trade at this observation's price using only the previous observation's risk score.

    The first row has no prior signal and is deliberately skipped. This is a more
    conservative execution-timing check than trading at the same close that generated
    the signal. It does not model intraperiod fills, spreads, or market impact.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    required = {"btc_price_aud", "risk_score"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    shifted = data.copy().sort_index()
    shifted["risk_score"] = pd.to_numeric(
        shifted["risk_score"], errors="coerce"
    ).shift(1)
    return simulate_cycle_strategy(shifted, **kwargs)

def simulate_buy_and_hold_benchmark(data, starting_capital_aud=500_000.0, fee_pct=0.001):
    """Buy BTC once at the first valid observation and hold to the last valid price."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    required = {"btc_price_aud"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if not np.isfinite(starting_capital_aud) or starting_capital_aud <= 0:
        raise ValueError("starting_capital_aud must be finite and positive")
    if not (0 <= fee_pct < 1):
        raise ValueError("fee_pct must be in [0, 1)")
    prices = pd.to_numeric(data["btc_price_aud"], errors="coerce")
    prices = prices[np.isfinite(prices) & (prices > 0)]
    if prices.empty:
        return {}
    first_price = float(prices.iloc[0])
    final_price = float(prices.iloc[-1])
    fee = float(starting_capital_aud) * fee_pct
    btc_bought = (float(starting_capital_aud) - fee) / first_price
    ending_value = btc_bought * final_price
    return {
        "starting_capital_aud": float(starting_capital_aud),
        "entry_price_aud": first_price,
        "exit_mark_price_aud": final_price,
        "btc_held": float(btc_bought),
        "fees_aud": float(fee),
        "ending_equity_aud": float(ending_value),
        "total_pnl_aud": float(ending_value - starting_capital_aud),
        "total_return_pct": float((ending_value / starting_capital_aud - 1) * 100),
        "observations": int(len(prices)),
    }


def walk_forward_parameter_sweep(
    data,
    starting_capital_aud=500_000.0,
    fee_pct=0.001,
    split_fraction=0.70,
    buy_thresholds=(0.15, 0.25, 0.35),
    sell_thresholds=(0.65, 0.75, 0.85),
    max_buy_pct_periods=(0.02, 0.05, 0.10),
    max_sell_pct_periods=(0.10, 0.20, 0.25),
    min_trade_aud=100.0,
):
    """Select parameters on the first chronological segment and evaluate once on the later segment.

    The later segment is a fresh-capital, independent test window: it does not carry BTC
    acquired during training. This avoids pretending the training and test results are one
    continuous portfolio, and tests whether the selected rule transfers to unseen dates.
    Parameters are ranked only on training total return. No test-period result is used
    to select the winning parameters.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    required = {"btc_price_aud", "risk_score"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if not (0.50 <= split_fraction <= 0.90):
        raise ValueError("split_fraction must be between 0.50 and 0.90")
    if data.empty:
        return pd.DataFrame(), {}, pd.DataFrame(), {}, {}
    clean = data.copy().sort_index()
    clean["btc_price_aud"] = pd.to_numeric(clean["btc_price_aud"], errors="coerce")
    clean["risk_score"] = pd.to_numeric(clean["risk_score"], errors="coerce")
    clean = clean[
        np.isfinite(clean["btc_price_aud"]) & (clean["btc_price_aud"] > 0)
        & np.isfinite(clean["risk_score"]) & clean["risk_score"].between(0, 1)
    ]
    split_at = int(len(clean) * split_fraction)
    if split_at < 2 or len(clean) - split_at < 2:
        return pd.DataFrame(), {}, pd.DataFrame(), {}, {}
    train = clean.iloc[:split_at].copy()
    test = clean.iloc[split_at:].copy()
    results = []
    for buy_threshold in buy_thresholds:
        for sell_threshold in sell_thresholds:
            if not (0 <= buy_threshold < sell_threshold <= 1):
                continue
            for max_buy in max_buy_pct_periods:
                for max_sell in max_sell_pct_periods:
                    _, summary = simulate_cycle_strategy(
                        train,
                        starting_capital_aud=starting_capital_aud,
                        buy_threshold=float(buy_threshold),
                        sell_threshold=float(sell_threshold),
                        max_buy_pct_period=float(max_buy),
                        max_sell_pct_period=float(max_sell),
                        fee_pct=fee_pct,
                        min_trade_aud=min_trade_aud,
                    )
                    if summary:
                        results.append({
                            "buy_threshold": float(buy_threshold),
                            "sell_threshold": float(sell_threshold),
                            "max_buy_pct_period": float(max_buy),
                            "max_sell_pct_period": float(max_sell),
                            "train_ending_equity_aud": summary["ending_equity_aud"],
                            "train_total_pnl_aud": summary["total_pnl_aud"],
                            "train_return_pct": summary["total_return_pct"],
                            "train_realized_pnl_aud": summary["realized_pnl_aud"],
                            "train_fees_aud": summary["fees_aud"],
                            "train_buy_count": summary["buy_count"],
                            "train_sell_count": summary["sell_count"],
                        })
    leaderboard = pd.DataFrame(results)
    if leaderboard.empty:
        return leaderboard, {}, pd.DataFrame(), {}, {}
    leaderboard = leaderboard.sort_values(
        ["train_return_pct", "train_realized_pnl_aud"],
        ascending=False,
        kind="stable",
    ).reset_index(drop=True)
    winner = leaderboard.iloc[0]
    test_df, test_summary = simulate_cycle_strategy(
        test,
        starting_capital_aud=starting_capital_aud,
        buy_threshold=float(winner["buy_threshold"]),
        sell_threshold=float(winner["sell_threshold"]),
        max_buy_pct_period=float(winner["max_buy_pct_period"]),
        max_sell_pct_period=float(winner["max_sell_pct_period"]),
        fee_pct=fee_pct,
        min_trade_aud=min_trade_aud,
    )
    benchmark = simulate_buy_and_hold_benchmark(
        test[["btc_price_aud"]],
        starting_capital_aud=starting_capital_aud,
        fee_pct=fee_pct,
    )
    test_df.attrs["test_start"] = str(test.index[0])
    test_df.attrs["test_end"] = str(test.index[-1])
    test_df.attrs["train_start"] = str(train.index[0])
    test_df.attrs["train_end"] = str(train.index[-1])
    return leaderboard, winner.to_dict(), test_df, test_summary, benchmark
