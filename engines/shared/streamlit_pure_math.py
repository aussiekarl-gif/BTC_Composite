"""Stable, side-effect-free BTC Streamlit math/allocator helpers.

These functions are copied without changing algorithmic behavior from
Research V5.9 on 2026-10-16. Production V5.8.2 deliberately retains its
frozen internal copies until separate promotion and parity sign-off.

Do not add Streamlit UI, network calls, portfolio storage or live data here.
"""
import pandas as pd

DEFAULT_INTELLIGENT_DCA_BUDGET_AUD=500000.0

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


def risk_occurrence_table(risk_series):
    """Return simple weekly risk buckets for the DCA Today visibility chart."""
    s = pd.to_numeric(pd.Series(risk_series), errors="coerce").dropna()
    bins = [
        (0.00, 0.01, "0.00–0.01"),
        (0.01, 0.02, "0.01–0.02"),
        (0.02, 0.05, "0.02–0.05"),
        (0.05, 0.10, "0.05–0.10"),
        (0.10, 0.20, "0.10–0.20"),
        (0.20, 0.40, "0.20–0.40"),
        (0.40, 0.60, "0.40–0.60"),
        (0.60, 0.80, "0.60–0.80"),
        (0.80, 1.000001, "0.80–1.00"),
    ]
    rows = []
    total = max(len(s), 1)
    for lo, hi, label in bins:
        count = int(((s >= lo) & (s < hi)).sum())
        rows.append({"Risk range": label, "Weeks": count, "Percent": 100.0 * count / total})
    return pd.DataFrame(rows)


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


def apply_equal_capital_allocator(
    result_df,
    total_budget_aud=DEFAULT_INTELLIGENT_DCA_BUDGET_AUD,
    fee_pct=0.0,
):
    """
    Allocate a hard fixed lifetime budget across the already-selected historical
    execution dates using the strategy's relative DCA weights.

    Unlike post-hoc comparison normalization, this produces an explicit
    contribution schedule whose total contributions equal the chosen budget.
    The timing weights are preserved, but the strategy cannot invest more than
    the fixed budget.

    This is a historical research allocator, not a future-price forecast.
    """
    if result_df.empty or total_budget_aud <= 0:
        return pd.DataFrame(), {}

    out = result_df.copy().reset_index(drop=True)

    weights = pd.to_numeric(
        out["actual_buy_aud"], errors="coerce"
    ).fillna(0.0).clip(lower=0.0)

    total_weight = float(weights.sum())
    if total_weight <= 0:
        return pd.DataFrame(), {}

    contributions = weights / total_weight * float(total_budget_aud)

    # Force exact budget equality despite floating-point accumulation.
    if len(contributions) > 0:
        contributions.iloc[-1] += float(total_budget_aud) - float(contributions.sum())

    btc = 0.0
    cumulative = 0.0
    fees = 0.0
    replay_rows = []

    for i, row in out.iterrows():
        contribution = float(contributions.iloc[i])
        fee = contribution * float(fee_pct)
        net = max(0.0, contribution - fee)
        price_aud = float(row["btc_price_aud"])
        btc_bought = net / price_aud if price_aud > 0 else 0.0

        btc += btc_bought
        cumulative += contribution
        fees += fee
        btc_value = btc * price_aud

        replay = row.to_dict()
        replay.update(
            {
                "actual_buy_aud": contribution,
                "btc_bought": btc_bought,
                "btc_held": btc,
                "cumulative_invested_aud": cumulative,
                "cumulative_fees_aud": fees,
                "btc_value_aud": btc_value,
                "pnl_aud": btc_value - cumulative,
                "roi_pct": (
                    (btc_value / cumulative - 1.0) * 100.0
                    if cumulative > 0 else 0.0
                ),
                "avg_cost_aud": cumulative / btc if btc > 0 else 0.0,
            }
        )
        replay_rows.append(replay)

    replay_df = pd.DataFrame(replay_rows)
    final = replay_df.iloc[-1]

    summary = {
        "budget_aud": float(total_budget_aud),
        "total_invested_aud": float(final["cumulative_invested_aud"]),
        "btc_held": float(final["btc_held"]),
        "btc_value_aud": float(final["btc_value_aud"]),
        "avg_cost_aud": float(final["avg_cost_aud"]),
        "roi_pct": float(final["roi_pct"]),
        "fees_aud": float(final["cumulative_fees_aud"]),
    }
    return replay_df, summary
