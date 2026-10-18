"""One-time, read-only *real provider* Cycle UTC close acceptance probe.

Never posts ntfy, touches portfolio, runs Streamlit, writes a CSV or trades.
The live data correctness release can be smoke-tested by GitHub Actions
with the exact shared public BTC provider/FX exchange price assembly.
"""
from __future__ import annotations

import datetime as dt
import json

from engines.research.top_signal_horse_race import read_exported_history
from engines.research.cycle_live_completed_utc_prices import (
    fetch_cycle_live_sources,merge_verified_live_cycle_prices,
)
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.cycle_trade_allocation import (
    calculate_allocation_signal,DEFAULT_BUY_STYLE,
)


def main():
    instant=dt.datetime.now(dt.timezone.utc)
    today=instant.date()
    hist=read_exported_history()
    public,fx,kraken=fetch_cycle_live_sources(asof=today.isoformat())
    prices,verified=merge_verified_live_cycle_prices(
        hist,public,kraken,utc_today=today)
    # 2024-04-20 epoch verified from Bitcoin blocks, dated constant only
    # for THIS October 2026 release check, not new epoch after next halving.
    if today.year!=2026:
        raise ValueError("Epoch check must be updated outside Oct2026")
    market=build_dashboard_market(
        prices,fx,asof=today.isoformat(),
        confirmed_halving_date="2024-04-20")
    signal=calculate_allocation_signal(
        market,buy_style=DEFAULT_BUY_STYLE)
    if str(market["asof_date"]) != str(
        today-dt.timedelta(days=1)):
        raise ValueError("Live smoke date must be prior completed UTC day")
    print(json.dumps({
        "smoke_only":True,
        "external_live_broker_trade_executable":False,
        "utc_date":str(today),
        "verified_btc_utc_complete_close_day":str(market["asof_date"]),
        "BTC_USD_close":round(float(market["btc_price_usd"]),2),
        "strict_prior_BTC_USD_close":round(
            float(market["previous_close_usd"]),2),
        "prior_200wma_USD":round(float(market["prior_200wma_usd"]),2),
        "signal_from_unchanged_market_allocation":signal["signal"],
        "BUY_pct_actual_remaining_cash":signal["buy_pct_cash"],
        "SELL_pct_actual_remaining_holdings":signal["sell_pct_held"],
        "Blockchain_vs_Kraken_max_abs_pct_last_week":verified[
            "recent_kraken_blockchain_max_diff_pct"],
        "corrected_archive_overlap_max_pct":verified[
            "max_overlap_difference_pct"],
        "Kraken_added_completed_dates":verified[
            "kraken_contiguous_completed_day_bridge"],
        "no_streamlit_portfolio_ntfy_or_production_write":True,
    },sort_keys=True))


if __name__=="__main__":
    main()
