"""
Cowen Risk Matrix — Benjamin Cowen's On-Chain Metrics Historical Risk
composite (Into The Cryptoverse) — launched as the "Cowen Risk Matrix" menu
point in the BTC Dynamic DCA dashboard.

Pipeline: nine metrics -> per-metric 0–1 risk score (historical percentile of
the current value) -> weighted composite "Total On-Chain Risk" (0–1) ->
dynamic-DCA risk matrix.

Data sources:
  1. LIVE (default): BGeometrics (bitcoin-data.com) — anonymous, free plan
     (no registration needed; 10 requests/hour; last ~4 years of data).
     See engines/cowen_risk_fetchers.py.  Optional: CryptoQuant free-account
     community endpoints via the CQ_API_KEY env var; token fills via
     CRYPTOQUANT_API_KEY / COINGLASS_API_KEY / COINGECKO_API /
     BGEOMETRICS_TOKEN; MANUAL_REALISED_PRICE_USD.
  2. CSV import: raw series as columns (see the cowen-risk-matrix repo:
     https://github.com/aussiekarl-gif/cowen-risk-matrix).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

try:
    from engines.cowen_risk_fetchers import fetch_live_df
except ImportError:  # standalone cowen-risk-matrix layout
    from fetchers import fetch_live_df

# ---------------------------------------------------------------------------
# Metric registry
# ---------------------------------------------------------------------------
# All nine metrics are "risk-up": a higher raw value means higher risk.
# (Cowen's private 0–1 mapping is approximated by the historical percentile
# recipe — see risk_score() below.)

METRICS: dict[str, dict] = {
    "PuellMultiple": {
        "label": "Puell Multiple",
        "formula": "issuance_usd / rolling(365).mean(issuance_usd)",
        "default_weight": 1.0,
    },
    "MVRV": {
        "label": "MVRV",
        "formula": "market_cap / realized_cap",
        "default_weight": 1.0,
    },
    "MVRVZScore": {
        "label": "MVRV Z-Score",
        "formula": "(market_cap − realized_cap) / std(market_cap)",
        "default_weight": 1.0,
    },
    "TransactionFees": {
        "label": "Transaction Fees",
        "formula": "transaction_fees_usd  (fee spikes vs historical norms)",
        "default_weight": 1.0,
    },
    "TerminalPrice": {
        "label": "Terminal Price",
        "formula": "terminal_price | (cdd_cumulative_usd / (supply × age)) × 21e6",
        "default_weight": 1.0,
    },
    "MCTC": {
        "label": "MCTC",
        "formula": "market_cap / thermo_cap",
        "default_weight": 1.0,
    },
    "mCTC": {
        "label": "mCTC",
        "formula": "miner_cap_usd / thermo_cap",
        "default_weight": 1.0,
    },
    "RHODL": {
        "label": "RHODL Ratio",
        "formula": "rhodl_ratio  (realized value of 1-week coins ÷ 1y–2y coins × market age)",
        "default_weight": 0.0,   # Cowen: 0 weight (less reliable signal)
    },
    "SupplyP/L": {
        "label": "Supply P/L",
        "formula": "supply_in_profit_pct",
        "default_weight": 0.0,   # Cowen: 0 weight (less reliable signal)
    },
}

# Interpretation notes — one per metric (direction: higher raw value = higher risk, all nine).
METRIC_NOTES: dict[str, str] = {
    "PuellMultiple": (
        "Miner-profitability oscillator: daily issuance value (USD) ÷ 365-day moving average. "
        "High (≥ ~2× normal) = miners' revenue running above yearly average — historically precedes macro tops; "
        "Low (< ~1) = miners losing money — bottoms."
    ),
    "MVRV": (
        "Market Cap ÷ Realized Cap — valuation gap above the supply's average entry basis. "
        "High (> ~2.5) = late-cycle stretch; low (~1–1.2) = near bottoms."
    ),
    "MVRVZScore": (
        "(Market Cap − Realized Cap) ÷ σ(Market Cap) — same gap in standardized dollar terms; "
        "sharper regime-boundary signal than the ratio."
    ),
    "TransactionFees": (
        "Average fee pressure (USD value of fees per day, or sat/vB) vs historical norms; "
        "spikes during bull phases raise risk (fees are part of miner revenue)."
    ),
    "TerminalPrice": (
        "Terminal Price = Transferred Price × 21,000,000 (Transferred Price = CDD ÷ (supply × market age)). "
        "When terminal price ≈ spot price, tops have formed."
    ),
    "MCTC": (
        "Market Cap ÷ Thermocap (cumulative miner revenue). Historically > ~10 is top-like; "
        "dropping below ~2 can mark bottoms (CoinMetrics)."
    ),
    "mCTC": (
        "Miner Cap ÷ Thermocap — value of coins held by miners vs total thermocap. "
        "High = miners hold unusually large value; low = distributed/sold."
    ),
    "RHODL": (
        "Realized Value of 1-week coins ÷ 1y–2y coins × market age; late-cycle heat = recent "
        "turnover dominating mature held value. Cowen sets weight 0 (less reliable signal)."
    ),
    "SupplyP/L": (
        "% of circulating supply priced above last-moved price; high = most coins above cost basis "
        "(late cycle). Cowen sets weight 0."
    ),
}

# Risk tiers: risk band → DCA multiplier → note (Cowen method, CryptoGates/Cryptonews).
RISK_TIERS: list[tuple[str, str, str]] = [
    ("0 – 0.1", "3x", "Floor / accumulation zone — most aggressive DCA (Cowen: bottoms often form once risk < 0.1)"),
    ("0.1 – 0.2", "2x", "Accumulation — DCA 2x"),
    ("0.2 – 0.3", "1x", "Early-cycle — DCA base level"),
    ("> 0.3", "0 (skip)", "Late-cycle — no new buys; keep cash"),
    ("> 0.5", "SELL", "High risk — sell or slow down"),
]


# ---------------------------------------------------------------------------
# Series derivation — transcribed from public sources (see README.md)
# ---------------------------------------------------------------------------

def _col(df: pd.DataFrame, *names: str) -> Optional[pd.Series]:
    """First column present in df with at least one non-NaN value."""
    for n in names:
        if n in df and df[n].notna().any():
            return df[n]
    return None


def derive_series(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Compute the 9 risk metrics' raw series from an input DataFrame.

    Accepts both CSV columns (Glassnode/CoinMetrics/Coinglass/CoreCharts
    exports) and the canonical live columns from
    engines.cowen_risk_fetchers.fetch_live_df()
    (BGeometrics free API: 'mvrv', 'mvrv_zscore', 'puell_multiple',
    'terminal_price', 'thermo_cap', 'market_cap', 'rhodl_ratio', ...).
    """
    s: dict[str, pd.Series] = {}

    mc = _col(df, "market_cap")
    rc = _col(df, "realized_cap")
    tc = _col(df, "thermo_cap", "thermocap_usd")

    # 1–2) MVRV and MVRV Z-Score
    #    MVRV = Market Cap / Realized Cap
    #    MVRVZScore = (Market Cap − Realized Cap) / σ(Market Cap)
    if (m := _col(df, "mvrv", "mvrv_ratio")) is not None:
        s["MVRV"] = m
    elif mc is not None and rc is not None:
        s["MVRV"] = mc / rc
    if (z := _col(df, "mvrz", "mvrv_zscore", "mvrv_z", "mvrv_zScore")) is not None:
        s["MVRVZScore"] = z
    elif mc is not None and rc is not None:
        sd = mc.std()
        if sd is not None and sd > 0:
            s["MVRVZScore"] = (mc - rc) / sd

    # Realized price (live fill / CSV column): derive Realized Cap = price ×
    # supply → MVRV when there is no direct mvrv / realized_cap series.
    if (rp := _col(df, "realized_price_usd", "realised_price_usd")) is not None:
        if rc is None:
            supply_rp = _col(df, "circulating_supply", "supply_current")
            if supply_rp is not None:
                rc = rp * supply_rp
        if rc is not None and mc is not None and "MVRV" not in s:
            s["MVRV"] = mc / rc

    # 3) Puell Multiple: Daily issuance value (USD) ÷ 365-day MA of it.
    if (p := _col(df, "puell_multiple")) is not None:
        s["PuellMultiple"] = p
    elif (v := _col(df, "daily_issuance_usd")) is not None:
        s["PuellMultiple"] = v / v.rolling(365, min_periods=365).mean()

    # 4) Transaction Fees: average fee pressure (USD value of fees per day).
    if (f := _col(df, "transaction_fees_usd", "average_fee_usd")) is not None:
        s["TransactionFees"] = f

    # 5) Terminal Price (Checkmate/BlockHorizon):
    #    Transferred Price = CDD / (Existing Supply × Market Age)
    #    Terminal Price    = Transferred Price × 21,000,000
    if (tp := _col(df, "terminal_price")) is not None:
        s["TerminalPrice"] = tp
    elif (
        (cdd := _col(df, "cdd_cumulative_usd")) is not None
        and (age := _col(df, "market_age_days")) is not None
        and mc is not None
        and (supply := _col(df, "circulating_supply")) is not None
    ):
        s["TerminalPrice"] = (cdd / (supply * age)) * 21_000_000

    # 6) MCTC: Market Cap ÷ Thermocap (Cointelegraph/CoinMetrics RevAllTimeUSD).
    if mc is not None and tc is not None:
        s["MCTC"] = mc / tc

    # 7) mCTC: Miner Cap ÷ Thermocap. Miner Cap = value of coins held by miners
    #    (CoinMetrics SplyMiner0HopAllUSD + SplyMiner1HopAllUSD).
    if (mcap := _col(df, "miner_cap_usd")) is not None and tc is not None:
        s["mCTC"] = mcap / tc

    # 8) RHODL Ratio: (Realized Value of 1-week coins ÷ 1y–2y coins) × market age (days).
    if (r := _col(df, "rhodl_ratio")) is not None:
        s["RHODL"] = r

    # 9) Supply P/L: % of circulating supply whose current price > last-moved price.
    if (p := _col(df, "supply_in_profit_pct")) is not None:
        s["SupplyP/L"] = p

    return s


# ---------------------------------------------------------------------------
# Risk scoring and compositing
# ---------------------------------------------------------------------------

def risk_score(series: pd.Series) -> float:
    """0–1 risk for a risk-up metric: the historical percentile of the
    current value (fraction of all history at/below it)."""
    s = series.dropna()
    if s.size < 2:
        return 0.5
    return float((s <= s.iloc[-1]).mean())


def band_label(risk: float) -> str:
    if risk < 0.1:
        return "Floor — best accumulation zone (Cowen: bottoms often sit below 0.1)"
    if risk < 0.2:
        return "Accumulation"
    if risk < 0.3:
        return "Early-cycle — continue DCA at base"
    if risk < 0.5:
        return "Late-cycle — slow DCA, build cash"
    return "High risk — sell or slow down"


def dca_action(risk: float) -> tuple[str, str]:
    """Dynamic-DCA tiers (Cowen method, CryptoGates example)."""
    if risk > 0.5:
        return "Sell / slow down", "risk > 0.5 — trim or halt buys, take profits."
    if risk > 0.3:
        return "Skip buys", "risk > 0.3 — no new DCA this period; keep cash."
    if risk > 0.2:
        return "Buy 1x", "risk in (0.2, 0.3] — base DCA amount."
    if risk > 0.1:
        return "Buy 2x", "risk in (0.1, 0.2] — double the buy."
    return "Buy 3x", "risk ≤ 0.1 — triple the buy (accumulation zone)."


def dca_matrix_table() -> pd.DataFrame:
    rows = [
        ("0 – 0.1", "3x", "floor/accumulation — most aggressive buying (Cowen: bottoms often form once risk < 0.1)"),
        ("0.1 – 0.2", "2x", "risk 0.1–0.2: DCA 2x (cryptogates example)"),
        ("0.2 – 0.3", "1x", "risk 0.2–0.3: DCA 1x — base amount"),
        ("> 0.3", "0", "risk > 0.3: skip buys — keep cash"),
        ("> 0.5", "SELL", "risk above 0.5: 'area to sell or slow down' (CryptoGates)"),
    ]
    return pd.DataFrame(
        rows,
        columns=["risk band", "DCA multiplier", "note"],
    )


def fmt(x) -> str:
    if pd.isna(x):
        return "n/a"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:.4f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Streamlit app
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CSV data loaders — BTC_Composite repo data + Research7 risk series
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Walk up from this file to the repo root (has data/risk_history.csv or .git)."""
    p = Path(__file__).resolve()
    for cand in p.parents:
        if (cand / "data" / "risk_history.csv").exists() or (cand / ".git").exists():
            return cand
    return p.parent


def _load_btc_composite_mvrz_series() -> Optional[pd.Series]:
    """BTC_Composite/data/mvrv_z_score_*.csv — MVRZ series starting ~Nov 2010
    (risk_history.csv itself starts 2026)."""
    data_dir = _repo_root() / "data"
    if not data_dir.exists():
        return None
    frames = []
    for f in sorted(data_dir.glob("mvrv_z_score_*.csv")):
        df = pd.read_csv(f)
        if "timestamp" not in df.columns or "MVRV Z-Score" not in df.columns:
            continue
        frames.append(pd.DataFrame({
            "date": pd.to_datetime(df["timestamp"], unit="ms", errors="coerce"),
            "mvrz": pd.to_numeric(df["MVRV Z-Score"], errors="coerce"),
        }).dropna(subset=["date", "mvrz"]).sort_values("date"))
    if not frames:
        return None
    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["date"]).sort_values("date")
    return out.set_index("date")["mvrz"]


def _load_btc_composite_data() -> Optional[pd.DataFrame]:
    """BTC_Composite/data/risk_history.csv — the user's own risk-ladder CSV.

    Also merges the earlier MVRZ series from BTC_Composite/data/mvrv_z_score_*.csv
    so the risk line can span back to ~2010."""
    f = _repo_root() / "data" / "risk_history.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    if "date_utc" in df.columns:
        df = df.rename(columns={"date_utc": "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    # risk_history.csv contains duplicate dates — keep one row per date.
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    extra = _load_btc_composite_mvrz_series()
    if extra is not None:
        df = pd.concat([df.set_index("date"), extra.to_frame("mvrz")], axis=1, join="outer").reset_index()
    return df


def _load_research7_series() -> Optional[pd.DataFrame]:
    """Research7/data/indicators/risk_history_*.csv — merged into app columns."""
    base = _repo_root().parent / "Research7" / "data" / "indicators"
    if not base.exists():
        return None
    maps = {
        "risk_history_mvrv_z.csv": "mvrz",
        "risk_history_puell_multiple.csv": "puell_multiple",
        "risk_history_realised_price_usd.csv": "realized_price_usd",
        "risk_history_price_usd.csv": "price_usd",
        "risk_history_composite_risk.csv": "composite_risk",
        "risk_history_ahr999.csv": "ahr999",
    }
    frames = []
    for fn, col in maps.items():
        f = base / fn
        if not f.exists():
            continue
        df = pd.read_csv(f)
        if "value" not in df.columns or "date" not in df.columns:
            continue
        df = df[["date", "value"]].rename(columns={"value": col})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", col]).sort_values("date")
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        return None
    out = frames[0]
    for df in frames[1:]:
        out = out.merge(df, on="date", how="outer")
    return out


def _risk_history_line(df: Optional[pd.DataFrame], series: dict, weights: dict) -> Optional[pd.Series]:
    """Historical risk line for the risk-gauge chart: the weighted mean of each
    metric's historical percentile (spans ~2010 via the merged MVRZ data);
    falls back to the CSV 'composite_risk' column when no weighted line is available."""
    frames = []
    for k, w in weights.items():
        if w <= 0 or k not in series:
            continue
        s = series[k].dropna()
        if s.size < 2:
            continue
        s_sorted = np.sort(s.to_numpy())
        # percentile of each value within the series: fraction ≤ value
        pct = pd.Series(
            np.searchsorted(s_sorted, s.to_numpy(), side="right") / s_sorted.size,
            index=s.index,
        )
        frames.append(pct * w)
    if frames:
        out = pd.concat(frames, axis=1).sum(axis=1)
        wsum = sum(weights[k] for k, w in weights.items() if w > 0 and k in series)
        if wsum > 0:
            return (out / wsum).rename("risk")
    if df is not None and "composite_risk" in df.columns:
        s = pd.to_numeric(df["composite_risk"], errors="coerce")
        if s.notna().any():
            return s.dropna().rename("risk")
    return None


def main() -> None:
    st.set_page_config(page_title="Cowen Risk Matrix", page_icon="₿")
    st.title("Cowen Risk Matrix")
    st.caption("Cowen On-Chain Metrics Historical Risk — open-source replica — formulas & sources in README.md")

    st.subheader("Data sources")
    cb_btc = st.checkbox(
        "Load BTC_Composite data (BTC_Composite/data/risk_history.csv)",
        key="cb_cowen_btc_composite",
    )
    cb_r7 = st.checkbox(
        "Load Research7 risk series (Research7/data/indicators/risk_history_*.csv)",
        key="cb_cowen_research7",
    )
    uploaded = st.file_uploader(
        "Import raw series as CSV (optional — overrides the checkboxes; live free data used by default)",
        type=["csv"],
    )

    df = None
    source_label = None
    if cb_btc:
        df = _load_btc_composite_data()
        if df is not None and len(df) > 0:
            source_label = f"BTC_Composite data/risk_history.csv ({len(df)} rows)"
        else:
            st.warning("BTC_Composite/data/risk_history.csv not found — nothing loaded.")
    if df is None and cb_r7:
        df = _load_research7_series()
        if df is not None and len(df) > 0:
            source_label = f"Research7 risk series ({len(df)} rows)"
        else:
            st.warning("Research7 risk series not found — nothing loaded.")
    if df is None and uploaded is not None:
        df = pd.read_csv(uploaded)
        if "date" in df:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").sort_values()
            df = df.set_index("date")
        source_label = "CSV import"
    if df is None:
        df = fetch_live_df()
        if df is None or df.empty:
            st.info(
                "No live data available — the BGeometrics fetch returned nothing "
                "(hourly limit 10 req/hour, or network hiccup). Import a CSV of raw "
                "series (see README) or try again after the cache expires."
            )
            return
        source_label = "live free data — BGeometrics bitcoin-data.com (anonymous, cached 30 min)"
    st.success("Source: " + source_label)

    series = derive_series(df)
    available = [k for k, s in series.items() if s.dropna().size >= 2]
    if not available:
        st.warning(
            "None of the expected columns/series were found. Expected at least one of: "
            "mvrv|market_cap+realized_cap, puell_multiple|daily_issuance_usd, rhodl_ratio, ..."
        )
        return

    st.success(
        "Computed: " + ", ".join(METRICS[k]["label"] for k in available)
    )
    missing = [METRICS[k]["label"] for k in ("TransactionFees", "mCTC") if k not in series]
    if missing:
        st.caption(
            "No live/CSV source for: " + ", ".join(missing)
            + " — provide via CSV import (README) or use Cowen's dashboard."
        )

    # ---- weights: Cowen's sliders (weight 0 = excluded) ------------------
    st.subheader("Weights (screenshot sliders — 0 = excluded)")
    weights: dict[str, float] = {}
    for k in available:
        weights[k] = st.slider(
            METRICS[k]["label"], 0.0, 1.0, METRICS[k]["default_weight"],
            step=0.05, key=f"w_{k}",
        )
    for k in METRICS:
        if k not in weights:
            weights[k] = 0.0

    # ---- per-metric risk -------------------------------------------------
    risks = {k: risk_score(series[k]) for k in available}
    active = [k for k in available if weights[k] > 0]
    if not active:
        st.warning("All weights are 0 — drag at least one slider above 0 to compute risk.")
        return
    den = sum(weights[k] for k in active)
    total = sum(weights[k] * risks[k] for k in active) / den

    st.subheader("Per-metric risk (historical percentile of the current value)")
    rows = []
    for k in available:
        s_k = series[k].dropna()
        cur = s_k.iloc[-1]
        rows.append({
            "metric": METRICS[k]["label"],
            "formula": METRICS[k]["formula"],
            "current": fmt(cur),
            "risk": f"{risks[k]:.4f}",
            "points": int(s_k.size),
            "weight": f"{weights[k]:.2f}",
            "contribution": (
                f"{weights[k] * risks[k] / den:.4f}" if k in active else "—"
            ),
        })
    st.table(pd.DataFrame(rows))

    # ---- total risk -------------------------------------------------------
    st.subheader("Total On-Chain Risk")
    st.metric("Total Risk (0 = floor, 1 = top)", f"{total:.3f}")
    st.caption(band_label(total))

    # ---- historical risk chart (Cowen-style risk gauge) -------------------
    st.subheader("Total On-Chain Risk (historical)")
    risk_line = _risk_history_line(df, series, weights)
    if risk_line is None:
        st.caption("No historical risk series available — load data above or wait for live data.")
    else:
        st.line_chart(risk_line.to_frame("risk"))
        span = (f"{pd.to_datetime(risk_line.index.min()).date()} → "
                f"{pd.to_datetime(risk_line.index.max()).date()} ({risk_line.size} points)")
        st.caption(f"Risk line span: {span}")
        st.caption(
            "0 = floor/accumulation zone · 0.2–0.3 = early-cycle · "
            "0.3–0.5 = late-cycle warning · > 0.5 = high risk (sell / slow down)."
        )

    # ---- dynamic DCA matrix + interpretation ------------------------------
    st.subheader("Dynamic DCA (risk matrix)")
    amount, note = dca_action(total)
    st.markdown(f"**Current risk: {total:.3f} → {amount}** — {note}")
    st.table(dca_matrix_table())

    st.subheader("Risk interpretation & per-metric notes")
    st.markdown(f"**Current tier:** {band_label(total)}")
    st.table(pd.DataFrame(RISK_TIERS, columns=["risk band", "DCA multiplier", "meaning"]))
    with st.expander("Per-metric notes (all 9)"):
        st.table(pd.DataFrame(
            [{"metric": METRICS[k]["label"], "note": METRIC_NOTES[k]} for k in METRICS],
            columns=["metric", "note"],
        ))


if __name__ == "__main__":
    main()
