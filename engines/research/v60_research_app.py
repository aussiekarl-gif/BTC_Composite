"""Streamlit dashboard for the isolated V6.0 200WMA research programme.

No portfolio, broker, order, notification or Production integration.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from engines.research.v60_200wma_policy import (
    CANDIDATE_LADDERS,
)

st.title("Bitcoin Dynamic DCA V6.0 — 200WMA Research")
st.caption("Independent Research • 200-week valuation • Percentage-based accumulation")

st.warning(
    "Research only — V6.0 is not approved for live investing. "
    "This screen does not issue a buy/sell recommendation, read your portfolio, "
    "or connect to a broker."
)

st.subheader("Research design")
st.write(
    "The 200-week moving average is the primary valuation reference. "
    "A normal 2.5% base DCA remains active above and around the average; "
    "the model does not wait for BTC to fall below the 200WMA before buying. "
    "Deeper discounts increase the percentage of deployable cash used."
)

rows = []
for name, ladder in CANDIDATE_LADDERS.items():
    rows.append({
        "Candidate": name.replace("_", " ").title(),
        "Normal": f"{ladder[0]:.1f}%",
        "20% below": f"{ladder[1]:.1f}%",
        "25% below": f"{ladder[2]:.1f}%",
        "30% below": f"{ladder[3]:.1f}%",
    })
st.subheader("Candidate allocation ladders")
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
st.caption(
    "Percentages apply to deployable cash, not fixed AUD amounts. "
    "These are research hypotheses, not selected settings."
)

st.subheader("Cash protection")
st.write(
    "Protected-cash floors of 0%, 10%, 20% and 30% of initial cash are "
    "tested separately from the allocation ladder. A separate weekly hard "
    "cap of 5% of original capital remains in the replay."
)

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "research_forward_validation"
    / "v60_dashboard_snapshot_2026-11-19.json"
)
snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
historical = snapshot["historical_replay"]
stress = snapshot["synthetic_stress"]
paper = snapshot["prospective_paper_tape"]
PACING_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "research_forward_validation"
    / "v60_historical_pacing_summary_2026-11-19.json"
)
pacing = json.loads(PACING_PATH.read_text(encoding="utf-8"))

st.subheader("Historical holdout snapshot")
st.caption(
    f"BTC data cutoff {historical['btc_last_observation_date']} • "
    f"{historical['holdout_cohort_count']} overlapping 104-week holdout windows • "
    f"{historical['cash_yield_gross_annual_pct']:.0f}% gross cash-yield scenario • "
    "no protected-cash floor"
)
pacing_rows = {
    (row["reserve_pct_initial_cash"], row["cumulative_spend_cap"]): row
    for row in pacing["historical_holdout"]
}
reference_pacing = pacing_rows.get((0, "uncapped"), {})
comparison_rows = [
    {
        "Policy": "Reference 20/25/30",
        "Median final AUD uplift vs fixed DCA": f"{historical['measured_ladder_holdout']['median_final_equity_uplift_vs_fixed_pct']:+.2f}%",
        "Median BTC-unit uplift vs fixed DCA": f"{historical['measured_ladder_holdout']['median_btc_units_uplift_vs_fixed_pct']:+.2f}%",
        "Cohort wins": f"{historical['measured_ladder_holdout']['cohort_win_rate_final_equity_pct']:.1f}%",
        "P10 uplift vs fixed DCA": f"{reference_pacing.get('p10_equity_uplift_pct', 0.0):+.2f}%",
        "Worst uplift vs fixed DCA": f"{reference_pacing.get('worst_equity_uplift_pct', 0.0):+.2f}%",
        "Max drawdown difference (pp)": f"{reference_pacing.get('median_max_drawdown_difference_pp', 0.0):+.2f}",
        "Overlapping windows": pacing["holdout_cohort_count"],
    },
    {
        "Policy": "Sensitivity 10/15/20",
        "Median final AUD uplift vs fixed DCA": f"{historical['measured_ladder_10_15_20_holdout']['median_final_equity_uplift_vs_fixed_pct']:+.2f}%",
        "Median BTC-unit uplift vs fixed DCA": f"{historical['measured_ladder_10_15_20_holdout']['median_btc_units_uplift_vs_fixed_pct']:+.2f}%",
        "Cohort wins": f"{historical['measured_ladder_10_15_20_holdout']['cohort_win_rate_final_equity_pct']:.1f}%",
        "P10 uplift vs fixed DCA": "n/a",
        "Worst uplift vs fixed DCA": "n/a",
        "Max drawdown difference (pp)": "n/a",
        "Overlapping windows": pacing["holdout_cohort_count"],
    },
]
st.dataframe(pd.DataFrame(comparison_rows), hide_index=True, width="stretch")
st.caption(
    "Sample: the holdout windows appear in the matched-budget table below. "
    "Retrospective, not prospective proof; the rolling cohorts overlap and are not "
    "independent tests. The sensitivity set has no matched-budget downside metrics "
    "published; see the prolonged-bear and slower-allocation sections for downside "
    "evidence."
)
st.warning(
    "The discount tiers did not activate at all during 2017–2021. "
    "In the 2022-onward holdout they activated only 24 / 16 / 9 weeks at "
    "10% / 15% / 20% discounts. The 20% and 25% thresholds were reached "
    "on the same nine weeks; all observed tier activations were in 2022–2023. "
    "The rolling cohorts overlap and are not independent tests."
)

st.subheader("Severe-bear stress warning")
st.write(
    "In a synthetic 104-week 70% decline, the measured 20/25/30 policy "
    f"returned {stress['measured_20_25_30']['no_reserve_return_pct']:.1f}% "
    "with no reserve, versus "
    f"{stress['fixed_weekly']['no_reserve_return_pct']:.1f}% for fixed weekly DCA. "
    "With a 30% protected-cash floor, the outcomes were "
    f"{stress['measured_20_25_30']['reserve_30_pct_return_pct']:.1f}% and "
    f"{stress['fixed_weekly']['reserve_30_pct_return_pct']:.1f}% respectively."
)
st.caption(
    "A 40% cumulative-spend cap nearly matched fixed DCA in the synthetic bear "
    "but reduced the measured policy's rapid-V recovery result. No reserve or "
    "cumulative cap has been selected."
)


st.subheader("Historical cash-pacing holdout — matched budgets")
st.caption(
    f"{pacing['holdout_cohort_count']} overlapping 104-week holdout windows • "
    f"{pacing['cash_yield_gross_annual_pct']:.0f}% gross cash-yield scenario • "
    "measured 20/25/30 ladder • same cap and reserve applied to fixed weekly DCA"
)
pacing_frame = pd.DataFrame(pacing["historical_holdout"])
pacing_frame = pacing_frame.rename(columns={
    "reserve_pct_initial_cash": "Protected cash reserve",
    "cumulative_spend_cap": "Cumulative spend cap",
    "median_equity_uplift_pct": "Median final equity uplift",
    "p10_equity_uplift_pct": "10th-percentile equity uplift",
    "worst_equity_uplift_pct": "Worst equity uplift",
    "median_btc_uplift_pct": "Median BTC-unit uplift",
    "win_rate_pct": "Cohort wins",
    "median_spend_difference_pct": "Median spend difference",
    "median_max_drawdown_difference_pp": "Max drawdown difference (pp)",
})
pacing_frame["Overlapping windows"] = pacing["holdout_cohort_count"]
for column in (
    "Median final equity uplift", "10th-percentile equity uplift",
    "Worst equity uplift", "Median BTC-unit uplift", "Cohort wins",
    "Median spend difference",
):
    pacing_frame[column] = pacing_frame[column].map(lambda x: f"{x:+.2f}%")
pacing_frame["Protected cash reserve"] = pacing_frame["Protected cash reserve"].map(lambda x: f"{x:.0f}%")
pacing_frame["Max drawdown difference (pp)"] = pacing_frame["Max drawdown difference (pp)"].map(lambda x: f"{x:+.2f}")
st.dataframe(pacing_frame, hide_index=True, width="stretch")
st.caption(
    "The matched fixed-DCA comparator has the same starting capital, reserve, "
    "cash-yield assumption and cumulative spend cap. Actual spend can still differ; "
    "that difference is shown. Negative drawdown differences mean the dynamic "
    "policy had a deeper maximum drawdown."
)

st.subheader("Synthetic prolonged-bear stress — 30% cash reserve")
bear_rows = [
    row for row in pacing["synthetic_stress"]
    if row["scenario"] == "prolonged_bear_70pct"
]
bear_frame = pd.DataFrame(bear_rows).rename(columns={
    "cumulative_spend_cap": "Cumulative spend cap",
    "fixed_return_pct": "Fixed weekly DCA return",
    "measured_return_pct": "Measured 20/25/30 return",
    "measured_minus_fixed_pp": "Measured minus fixed (pp)",
})
for column in ("Fixed weekly DCA return", "Measured 20/25/30 return"):
    bear_frame[column] = bear_frame[column].map(lambda x: f"{x:+.2f}%")
bear_frame["Measured minus fixed (pp)"] = bear_frame["Measured minus fixed (pp)"].map(lambda x: f"{x:+.2f}")
st.dataframe(
    bear_frame[["Cumulative spend cap", "Fixed weekly DCA return",
                "Measured 20/25/30 return", "Measured minus fixed (pp)"]],
    hide_index=True, width="stretch",
)
st.warning(
    "The measured policy still underperformed fixed DCA in every synthetic "
    "prolonged-bear cap tested. It did better in false-bottom and rapid-V recovery "
    "scenarios. This path dependence is why no spending cap or reserve is selected."
)
st.caption(
    "The historical results are retrospective, not prospective proof: the BTC "
    "export ends 2026-10-05, and the 146 holdout windows overlap heavily with "
    "discount-tier activations concentrated in 2022–2023."
)


SCALE_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "research_forward_validation"
    / "v60_allocation_scale_summary_2026-11-19.json"
)
scale_evidence = json.loads(SCALE_EVIDENCE_PATH.read_text(encoding="utf-8"))

st.subheader("Slower allocation sensitivity — 0% and 5% cash yield")
st.caption(
    "Measured 20/25/30 ladder scaled to 0.5x, 0.75x and 1.0x; "
    "30% protected-cash reserve; 50% cumulative-spend cap; "
    "fixed weekly DCA matched by cohort, yield, reserve and cap."
)
scale_frame = pd.DataFrame(scale_evidence["historical_scale_comparison"]).rename(columns={
    "split": "Period",
    "cash_yield_pct": "Gross cash yield",
    "scale": "Ladder scale",
    "base_buy_pct": "Base allocation",
    "top_tier_buy_pct": "30%-discount allocation",
    "median_equity_uplift_pct": "Median equity uplift",
    "p10_equity_uplift_pct": "10th-percentile uplift",
    "worst_equity_uplift_pct": "Worst cohort",
    "median_btc_uplift_pct": "Median BTC-unit uplift",
    "win_rate_pct": "Cohort wins",
    "median_drawdown_difference_pp": "Drawdown difference (pp)",
    "cohorts": "Cohorts",
})
for column in (
    "Gross cash yield", "Base allocation", "30%-discount allocation",
    "Median equity uplift", "10th-percentile uplift", "Worst cohort",
    "Median BTC-unit uplift", "Cohort wins",
):
    scale_frame[column] = scale_frame[column].map(lambda x: f"{x:+.2f}%")
scale_frame["Ladder scale"] = scale_frame["Ladder scale"].map(lambda x: f"{x:.2f}x")
scale_frame["Drawdown difference (pp)"] = scale_frame["Drawdown difference (pp)"].map(lambda x: f"{x:+.2f}")
st.dataframe(scale_frame, hide_index=True, width="stretch")
st.warning(
    "The 0.5x ladder is more conservative, not proven superior. In the 2017–2021 "
    "training split its median uplift was close to zero and the win rate was only "
    "39.9% at 0% yield / 52.5% at 5% yield. The stronger holdout result is "
    "concentrated in a later market regime; all rolling cohorts overlap."
)

st.subheader("Synthetic path comparison — 50% cap, 30% reserve")
stress_frame = pd.DataFrame(scale_evidence["synthetic_stress_cap_50"]).rename(columns={
    "scenario": "Synthetic path",
    "scale": "Ladder scale",
    "base_buy_pct": "Base allocation",
    "measured_minus_fixed_return_pp": "Return difference vs fixed (pp)",
    "measured_btc_uplift_vs_fixed_pct": "BTC-unit difference vs fixed",
})
stress_frame["Ladder scale"] = stress_frame["Ladder scale"].map(lambda x: f"{x:.2f}x")
stress_frame["Base allocation"] = stress_frame["Base allocation"].map(lambda x: f"{x:.2f}%")
stress_frame["Return difference vs fixed (pp)"] = stress_frame["Return difference vs fixed (pp)"].map(lambda x: f"{x:+.2f}")
stress_frame["BTC-unit difference vs fixed"] = stress_frame["BTC-unit difference vs fixed"].map(lambda x: f"{x:+.2f}%")
st.dataframe(stress_frame, hide_index=True, width="stretch")
st.caption(
    "The slower ladder reduces losses in the prolonged-bear and extended-bear paths, "
    "but gives up some rapid-recovery upside. These are synthetic paths, not forecasts."
)

st.subheader("Validation status")
st.info(
    "Historical replay and synthetic stress testing are complete. "
    "The V6.0 prospective paper tape is initialized on a separate research branch; "
    f"its first eligible Sunday close is {paper['first_eligible_sunday_close_utc']}. "
    f"It is schema v{paper['signal_schema_version']} and records allocation scales "
    f"{paper['allocation_scale_candidates']}. It currently contains {paper['signal_rows']} signal and "
    f"{paper['asx_observation_rows']} ASX observation rows. "
    "Cumulative deployment pacing remains under research. No candidate is approved "
    "for live investing."
)
st.caption(
    "The replay uses a next-Monday BTC/AUD spot proxy, not an ASX:IBIT fill. "
    "Cash yield is gross and not tax-adjusted; actual ASX spreads, brokerage, "
    "tax and personal cash flows are not fully modelled. "
    "V5.9 remains archived with its code, reports and paper tapes preserved. "
    "Production V5.8.2 remains frozen."
)

# A deliberate machine-readable label for navigation/safety regression tests.
trade_executable = False
st.caption(f"Trade executable: {trade_executable}")
