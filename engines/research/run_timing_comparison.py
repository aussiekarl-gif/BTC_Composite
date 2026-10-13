#!/usr/bin/env python3
"""Research-only, same-window BTC entry-timing comparison.

Compares fixed DCA, buy-and-hold, and risk-triggered accumulation without selling.
All strategies use the same valid risk-score observation dates and AUD budget.
This is a diagnostic, not a promise of future returns; risk scores must be
point-in-time and the score's publication/execution lag must be independently checked.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.shared.central_data import load_master

CAPITAL = 500_000.0
FEE = 0.001


def summary(name, data, allocations, cash):
    prices = data["btc_price_aud"].to_numpy(float)
    spent = float(np.sum(allocations))
    fees = spent * FEE
    btc = float(
        np.sum(
            np.divide(
                allocations * (1 - FEE),
                prices,
                out=np.zeros_like(prices),
                where=prices > 0,
            )
        )
    )
    final_price = float(prices[-1])
    ending_equity = float(cash + btc * final_price)
    return {
        "strategy": name,
        "starting_capital_aud": CAPITAL,
        "cash_remaining_aud": float(cash),
        "gross_spent_aud": spent,
        "fees_aud": fees,
        "btc_held": btc,
        "ending_equity_aud": ending_equity,
        "return_pct": ending_equity / CAPITAL * 100 - 100,
        "btc_equivalent_if_all_in_at_start": CAPITAL * (1 - FEE) / prices[0],
        "btc_accumulation_vs_fixed_dca_pct": None,
    }


def main():
    raw = load_master(columns=["btc_price_aud", "risk_score"])
    raw["btc_price_aud"] = pd.to_numeric(raw["btc_price_aud"], errors="coerce")
    raw["risk_score"] = pd.to_numeric(raw["risk_score"], errors="coerce")
    raw = raw.sort_index()

    # The central master is a daily/date-indexed table but risk_score is sparse.
    # Filter to valid joint price/risk observations FIRST, then lag by one valid
    # risk observation. Shifting before filtering loses the signal because the
    # immediately preceding calendar row usually has no risk score.
    valid = raw[
        np.isfinite(raw["btc_price_aud"])
        & (raw["btc_price_aud"] > 0)
        & np.isfinite(raw["risk_score"])
        & raw["risk_score"].between(0, 1)
    ].copy()
    valid["decision_risk"] = valid["risk_score"].shift(1)
    data = valid[np.isfinite(valid["decision_risk"])].copy()

    if len(data) < 20:
        raise RuntimeError(
            f"Only {len(data)} valid lagged price/risk rows "
            f"from {len(valid)} joint valid observations"
        )

    prices = data["btc_price_aud"].to_numpy(float)
    risk = data["decision_risk"].to_numpy(float)
    n = len(data)
    rows = []

    # Fixed DCA spends one scheduled installment at every valid observation.
    # Signal strategies can only spend that observation's scheduled installment
    # when eligible; skipped installments remain cash. This avoids using the
    # total number of future eligible signals to size purchases (lookahead).
    installment = CAPITAL / n
    allocations = np.full(n, installment)
    rows.append(
        summary(
            "fixed_DCA_equal_installment_each_valid_observation",
            data,
            allocations,
            CAPITAL - float(allocations.sum()),
        )
    )
    rows.append(
        summary(
            "buy_and_hold_at_first_valid_observation",
            data,
            np.r_[CAPITAL, np.zeros(n - 1)],
            0.0,
        )
    )

    for threshold in (0.15, 0.25, 0.35, 0.45, 0.55):
        eligible = risk < threshold
        allocations = np.zeros(n)
        allocations[eligible] = installment
        rows.append(
            summary(
                f"risk_DCA_threshold_{threshold:.2f}",
                data,
                allocations,
                CAPITAL - float(allocations.sum()),
            )
        )

    # Opportunistic sizing: use the current scheduled installment times a
    # score-based multiplier, capped at available cash. No future signal count.
    # Multiplier ranges from 0 to 3x as score moves from threshold to zero.
    for threshold in (0.15, 0.25, 0.35, 0.45):
        allocations = np.zeros(n)
        cash = CAPITAL
        for i, score in enumerate(risk):
            if score < threshold and cash > 0:
                strength = (threshold - score) / threshold
                spend = min(cash, installment * 3.0 * strength)
                if spend >= 100:
                    allocations[i] = spend
                    cash -= spend
        rows.append(
            summary(
                f"capped_risk_accumulation_{threshold:.2f}",
                data,
                allocations,
                cash,
            )
        )

    output = pd.DataFrame(rows)
    fixed_btc = float(
        output.loc[
            output.strategy == "fixed_DCA_equal_installment_each_valid_observation",
            "btc_held",
        ].iloc[0]
    )
    output["btc_accumulation_vs_fixed_dca_pct"] = (
        output["btc_held"] / fixed_btc - 1
    ) * 100

    result = {
        "dataset": {
            "rows": int(n),
            "joint_valid_price_risk_rows": int(len(valid)),
            "start": data.index.min().isoformat(),
            "end": data.index.max().isoformat(),
            "price_start_aud": float(prices[0]),
            "price_end_aud": float(prices[-1]),
            "decision_risk_min": float(risk.min()),
            "decision_risk_max": float(risk.max()),
            "capital_aud": CAPITAL,
            "fee_per_side_pct": FEE * 100,
        },
        "results": output.replace({np.nan: None}).to_dict(orient="records"),
        "caveats": [
            "Risk score is lagged one valid joint price/risk observation before execution; actual publication timestamps and upstream lookahead still require audit.",
            "DCA schedule uses valid lagged price/risk observations; sparse risk-score coverage may not represent a true weekly schedule.",
            "Threshold strategies spend at most one scheduled installment per eligible observation; opportunistic strategy scales that installment by a signal multiplier, with no future eligible-count sizing.",
            "Fees included; spread, slippage, tax and terminal liquidation costs excluded.",
            "Threshold strategies are descriptive comparisons, not selected or validated trading rules.",
        ],
    }
    print("BTC TIMING COMPARISON")
    print(json.dumps(result, indent=2, allow_nan=False, default=str))


if __name__ == "__main__":
    main()
