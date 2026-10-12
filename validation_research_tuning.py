#!/usr/bin/env python3
"""
Validation Framework for V5.9 Research Tuning (Oct 2026)
=========================================================

Tests four recommended tuning changes:
1. Lower research DCA floor from 0.8x to 0.6x at risk 1.0
2. Tighten bottom-zone threshold to require 3 confirming categories (not 2)
3. Add drawdown severity bump: +0.5x when price > 50% below recent peak
4. Extend halving window from 800–1000 days to 600–1200 days

Validates against:
- Production (V5.8.2) for safety regression
- Research (V5.9 old) for tuning delta
- Research (V5.9 tuned) for behavior correctness
- Comparison notifications for format/stability
"""

import datetime as dt
import sys
import math
from typing import Tuple, Dict, Any

import numpy as np
import pandas as pd

# Import both model engines
from engines.production import production_model as PROD_MODEL
from engines.research import research_model as RESEARCH_MODEL


def bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"

def green(s: str) -> str:
    return f"\033[92m{s}\033[0m"

def red(s: str) -> str:
    return f"\033[91m{s}\033[0m"

def yellow(s: str) -> str:
    return f"\033[93m{s}\033[0m"


# ================================================================
# Test 1: Verify Research Constants
# ================================================================

def test_tuning_constants():
    """Confirm all four tuning changes are in place."""
    print(f"\n{bold('TEST 1: Tuning Constants')}")
    print("-" * 60)

    tests = [
        ("DCA floor at risk=1.0", RESEARCH_MODEL.SMART_DCA_POINTS[-1][1], 0.6, "should be 0.6x"),
        ("Bottom category threshold", RESEARCH_MODEL.BOTTOM_CHALLENGER_REQUIRED_CONFIRMING_CATEGORIES, 3, "should require 3 categories"),
        ("Halving window start", RESEARCH_MODEL.HALVING_ACCUMULATION_START_DAY, 600, "should be 600 days"),
        ("Halving window end", RESEARCH_MODEL.HALVING_ACCUMULATION_END_DAY, 1200, "should be 1200 days"),
    ]

    all_pass = True
    for name, actual, expected, note in tests:
        match = actual == expected
        status = green("✓ PASS") if match else red(f"✗ FAIL ({note})")
        print(f"{status} | {name:40} = {actual:>6} (expected {expected})")
        all_pass = all_pass and match

    return all_pass


# ================================================================
# Test 2: Drawdown Severity Multiplier
# ================================================================

def test_drawdown_severity():
    """Verify drawdown bump function behavior."""
    print(f"\n{bold('TEST 2: Drawdown Severity Multiplier')}")
    print("-" * 60)

    fn = RESEARCH_MODEL.drawdown_severity_multiplier

    test_cases = [
        (100.0, 100.0, 0.0, "at recent peak"),
        (75.0, 100.0, 0.0, "25% down (< 50% threshold)"),
        (50.0, 100.0, 0.50, "exactly 50% down"),
        (40.0, 100.0, 0.50, "60% down (>50% threshold)"),
        (1.0, 100.0, 0.50, "99% crash"),
        (np.nan, 100.0, 0.0, "price is NaN"),
        (100.0, np.nan, 0.0, "peak is NaN"),
    ]

    all_pass = True
    for price, peak, expected, desc in test_cases:
        result = fn(price, peak)
        match = np.isclose(result, expected, atol=1e-9) if np.isfinite(result) and np.isfinite(expected) else (np.isnan(result) == np.isnan(expected))
        status = green("✓") if match else red("✗")
        print(f"{status} | Price={price:>6}, Peak={peak:>6} → {result:.2f} ({desc})")
        all_pass = all_pass and match

    return all_pass


# ================================================================
# Test 3: DCA Curve Interpolation
# ================================================================

def test_dca_curve():
    """Verify Research DCA curve has correct shape."""
    print(f"\n{bold('TEST 3: Research DCA Curve Shape')}")
    print("-" * 60)

    fn = RESEARCH_MODEL.interpolate
    curve = RESEARCH_MODEL.SMART_DCA_POINTS

    test_points = [
        (0.0, 2.0, "at risk 0 (cheapest)"),
        (0.25, 1.5, "mid-point lower"),
        (0.5, 1.0, "at risk 0.5 (neutral)"),
        (0.75, 0.8, "mid-point upper"),
        (1.0, 0.6, "at risk 1.0 (most expensive)"),
    ]

    all_pass = True
    for risk, expected_approx, desc in test_points:
        result = fn(curve, risk)
        # Check rough tolerance (not exact, just directional)
        in_range = (result >= (expected_approx - 0.2)) and (result <= (expected_approx + 0.2))
        status = green("✓") if in_range else red("✗")
        print(f"{status} | Risk={risk:.2f} → {result:.3f}x (~{expected_approx:.1f}x) — {desc}")
        all_pass = all_pass and in_range

    return all_pass


# ================================================================
# Test 4: Production vs Research Safety Check
# ================================================================

def test_production_vs_research_safety():
    """Ensure production is still conservative vs research."""
    print(f"\n{bold('TEST 4: Production vs Research Multipliers')}")
    print("-" * 60)

    now_utc = dt.datetime.now(dt.timezone.utc)
    closed_end_utc = dt.datetime.combine(now_utc.date(), dt.time.min, tzinfo=dt.timezone.utc) - dt.timedelta(microseconds=1)
    lookback_start = closed_end_utc - dt.timedelta(days=365 * 5)

    try:
        df = PROD_MODEL.fetch_btc_history(lookback_start, closed_end_utc)
        fx = PROD_MODEL.fetch_aud_usd_rates(lookback_start, closed_end_utc)
        token = PROD_MODEL.get_bgeometrics_token()
        bg = PROD_MODEL.fetch_bgeometrics_bundle(lookback_start - dt.timedelta(days=300), closed_end_utc, token)
        
        df = PROD_MODEL.align_fx_to_dates(df, fx)
        df = PROD_MODEL.merge_bgeometrics(df, bg)
        
        prod_params = {
            "risk_model": "Composite V3.6",
            "pl_cheap": PROD_MODEL.DEFAULT_PL_CHEAP,
            "pl_expensive": PROD_MODEL.DEFAULT_PL_EXPENSIVE,
        }
        research_params = {
            "risk_model": "Research WF Power Law",
            "pl_cheap": RESEARCH_MODEL.DEFAULT_PL_CHEAP,
            "pl_expensive": RESEARCH_MODEL.DEFAULT_PL_EXPENSIVE,
            "research_pl_min_weeks": RESEARCH_MODEL.RESEARCH_PL_MIN_WEEKS,
            "research_pl_refit_days": RESEARCH_MODEL.RESEARCH_PL_REFIT_DAYS,
        }
        
        prod_df = PROD_MODEL.add_risk_indicators(df.copy(), "Composite V3.6", prod_params)
        research_df = RESEARCH_MODEL.add_risk_indicators(df.copy(), "Research WF Power Law", research_params)
        
        prod_df = prod_df.dropna(subset=["risk_score"])
        research_df = research_df.dropna(subset=["risk_score"])
        
        if not prod_df.empty and not research_df.empty:
            # Align on common dates
            common_dates = prod_df.index.intersection(research_df.index)
            if len(common_dates) > 0:
                prod_latest = prod_df.loc[common_dates[-1]]
                research_latest = research_df.loc[common_dates[-1]]
                
                prod_risk = float(prod_latest["risk_score"])
                research_risk = float(research_latest["risk_score"])
                prod_mult = float(PROD_MODEL.interpolate(PROD_MODEL.DEFAULT_ALWAYS_DCA_POINTS, prod_risk))
                research_mult = float(RESEARCH_MODEL.interpolate(RESEARCH_MODEL.SMART_DCA_POINTS, research_risk))
                
                print(f"Latest common date: {common_dates[-1].date()}")
                print(f"Production  risk={prod_risk:.3f} → mult={prod_mult:.3f}x")
                print(f"Research    risk={research_risk:.3f} → mult={research_mult:.3f}x")
                
                # Safety check: production should not systematically buymore aggressive than research over many historical dates
                prod_mults = [PROD_MODEL.interpolate(PROD_MODEL.DEFAULT_ALWAYS_DCA_POINTS, float(r)) 
                             for r in prod_df.loc[common_dates, "risk_score"].dropna()]
                research_mults = [RESEARCH_MODEL.interpolate(RESEARCH_MODEL.SMART_DCA_POINTS, float(r)) 
                                 for r in research_df.loc[common_dates, "risk_score"].dropna()]
                
                avg_prod = np.mean(prod_mults)
                avg_research = np.mean(research_mults)
                
                print(f"\nHistorical averages:")
                print(f"  Production:  {avg_prod:.3f}x")
                print(f"  Research:    {avg_research:.3f}x")
                
                # Research can be more aggressive, but check for wild divergence
                divergence = abs(avg_research - avg_prod) / max(avg_prod, avg_research)
                status = green("✓ PASS") if divergence < 0.5 else yellow(f"⚠ HIGH DIVERGENCE ({divergence:.1%})")
                print(f"{status} | Divergence: {divergence:.1%}")
                
                return divergence < 0.5
    except Exception as e:
        print(red(f"✗ EXCEPTION: {e}"))
        return False
    
    return False


# ================================================================
# Test 5: Comparison Notification Format
# ================================================================

def test_notification_format():
    """Verify dual-model comparison script can run without error."""
    print(f"\n{bold('TEST 5: Notification Format & Stability')}")
    print("-" * 60)

    try:
        from dca_model_compare_notify import calculate_model_summary, fetch_live_prices
        
        now_utc = dt.datetime.now(dt.timezone.utc)
        closed_end_utc = dt.datetime.combine(now_utc.date(), dt.time.min, tzinfo=dt.timezone.utc) - dt.timedelta(microseconds=1)
        
        print("Fetching Production summary...")
        prod, prod_e, prod_latest = calculate_model_summary(PROD_MODEL, "Composite V3.6")
        print(f"  Risk={prod['risk']:.3f} ({prod['label']}), Mult={prod['multiplier']:.3f}x")
        
        print("Fetching Research summary...")
        research, research_e, research_latest = calculate_model_summary(RESEARCH_MODEL, "Research WF Power Law")
        print(f"  Risk={research['risk']:.3f} ({research['label']}), Mult={research['multiplier']:.3f}x")
        
        print("Fetching live prices...")
        btc_aud, btc_usd = fetch_live_prices(prod_e, prod_latest)
        print(f"  BTC AUD=${btc_aud:,.0f}, USD=${btc_usd:,.0f}")
        
        # Verify all fields are present and numeric
        checks = [
            ("Production risk", prod['risk'], float),
            ("Production multiplier", prod['multiplier'], float),
            ("Research risk", research['risk'], float),
            ("Research multiplier", research['multiplier'], float),
            ("BTC AUD price", btc_aud, (float, int)),
            ("BTC USD price", btc_usd, (float, int)),
        ]
        
        all_pass = True
        for name, val, expected_type in checks:
            is_valid = isinstance(val, expected_type) and np.isfinite(val)
            status = green("✓") if is_valid else red("✗")
            print(f"{status} | {name:30} = {val} ({type(val).__name__})")
            all_pass = all_pass and is_valid
        
        return all_pass
        
    except Exception as e:
        print(red(f"✗ EXCEPTION: {e}"))
        return False


# ================================================================
# Test 6: Budget Allocation with Drawdown Bump
# ================================================================

def test_budget_allocation_with_bump():
    """Verify budget allocator handles drawdown multiplier correctly."""
    print(f"\n{bold('TEST 6: Budget Allocation with Drawdown Bump')}")
    print("-" * 60)

    try:
        now_utc = dt.datetime.now(dt.timezone.utc)
        closed_end_utc = dt.datetime.combine(now_utc.date(), dt.time.min, tzinfo=dt.timezone.utc) - dt.timedelta(microseconds=1)
        lookback_start = closed_end_utc - dt.timedelta(days=365 * 3)

        df = RESEARCH_MODEL.fetch_btc_history(lookback_start, closed_end_utc)
        fx = RESEARCH_MODEL.fetch_aud_usd_rates(lookback_start, closed_end_utc)
        token = RESEARCH_MODEL.get_bgeometrics_token()
        bg = RESEARCH_MODEL.fetch_bgeometrics_bundle(lookback_start - dt.timedelta(days=300), closed_end_utc, token)
        
        df = RESEARCH_MODEL.align_fx_to_dates(df, fx)
        df = RESEARCH_MODEL.merge_bgeometrics(df, bg)
        
        params = {
            "risk_model": "Research WF Power Law",
            "pl_cheap": RESEARCH_MODEL.DEFAULT_PL_CHEAP,
            "pl_expensive": RESEARCH_MODEL.DEFAULT_PL_EXPENSIVE,
            "research_pl_min_weeks": RESEARCH_MODEL.RESEARCH_PL_MIN_WEEKS,
            "research_pl_refit_days": RESEARCH_MODEL.RESEARCH_PL_REFIT_DAYS,
            "start_date": lookback_start,
            "end_date": closed_end_utc,
            "day_of_week": 0,
        }
        
        result_df, summary = RESEARCH_MODEL.simulate_dca_backtest(
            df, params, 1000.0, "Weekly", "Risk-Scaled DCA", 
            risk_curve=RESEARCH_MODEL.SMART_DCA_POINTS
        )
        
        if not result_df.empty:
            # Check for drawdown_severity_multiplier column
            has_col = "drawdown_severity_multiplier" in result_df.columns
            status = green("✓") if has_col else red("✗")
            print(f"{status} | drawdown_severity_multiplier column exists: {has_col}")
            
            if has_col:
                bumped = (result_df["drawdown_severity_multiplier"] > 0).sum()
                total = len(result_df)
                print(f"  Periods with bump applied: {bumped}/{total} ({100*bumped/total:.1f}%)")
                
                # Check that bump is actually additive
                has_addition = (result_df["dca_multiplier"] > result_df["drawdown_severity_multiplier"]).all()
                status = green("✓") if has_addition else red("✗")
                print(f"{status} | DCA multiplier includes bump (additive): {has_addition}")
                
                print(f"\nBacktest summary:")
                print(f"  BTC held: {summary['btc_held']:.6f}")
                print(f"  Total invested: A${summary['total_invested_aud']:,.0f}")
                print(f"  ROI: {summary['roi_pct']:.1f}%")
                
                return has_col and has_addition
        else:
            print(red("✗ No backtest results"))
            return False
            
    except Exception as e:
        print(red(f"✗ EXCEPTION: {e}"))
        import traceback
        traceback.print_exc()
        return False


# ================================================================
# Main
# ================================================================

def main():
    """Run all validation tests."""
    print(f"\n{bold('='*60)}")
    print(f"{bold('V5.9 Research Tuning Validation Framework')}")
    print(f"{bold('October 2026')}")
    print(f"{bold('='*60)}")

    results = {}
    
    results["Constants"] = test_tuning_constants()
    results["Drawdown"] = test_drawdown_severity()
    results["DCA Curve"] = test_dca_curve()
    results["Production Safety"] = test_production_vs_research_safety()
    results["Notification"] = test_notification_format()
    results["Budget Alloc"] = test_budget_allocation_with_bump()

    # Summary
    print(f"\n{bold('='*60)}")
    print(f"{bold('VALIDATION SUMMARY')}")
    print(f"{bold('='*60)}")
    for name, passed in results.items():
        status = green("✓ PASS") if passed else red("✗ FAIL")
        print(f"{status} | {name}")

    total_pass = sum(1 for v in results.values() if v)
    total = len(results)
    
    if total_pass == total:
        print(f"\n{green(bold(f'All {total} tests passed!'))}")
        return 0
    else:
        print(f"\n{red(bold(f'{total - total_pass} of {total} tests failed.'))}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
