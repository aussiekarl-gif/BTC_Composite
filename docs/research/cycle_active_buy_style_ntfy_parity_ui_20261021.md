# Cycle Trading active BUY percentages must match daily ntfy — 21 October 2026

**Reliability fix to dashboard presentation only. No market-data/BUY/SELL algorithm change.**

The shared market model supports `buy_style="adaptive_recovery"` (active Cycle Trading: **2.5% of remaining AUD cash** when previous BTC/USD close is strictly below previous exact 200WMA) and `buy_style="adaptive_value"` (an older experimental **3.5% or 10%** below 200WMA). The actual once-daily ntfy explicitly calls the **fixed default `adaptive_recovery`**.

Before this change the **Current trading decision** Streamlit panel had a selector `cycle_decision_buy_style` with BOTH values. Choosing the experimental sizing could create a *current* hypothetical cash/IBIT BUY amount much larger than the current ntfy BUY, while the dashboard itself said that both percentages use the same daily market rules. This was a hidden **recommendation parity bug**, despite both output paths being research-only.

## Fix

- Import the already existing `DEFAULT_BUY_STYLE` from `engines/research/cycle_trade_allocation.py` in `engines/research/cycle_trading_app.py`. Use it as the sole sizing option in **Current trading decision**. The default is unchanged at 2.5% of remaining AUD cash, never 3.5% or 10%.
- Clearly label this as matching the one daily ntfy. The *separate* Historical sell & buyback tab **continues to offer** both `adaptive_recovery` and `adaptive_value` as historical research alternatives; no model or historical comparison behavior is deleted or changed.
- An old Streamlit browser session may still store `cycle_decision_buy_style="adaptive_value"`. The current panel must IGNORE that stale preference, rather than present an alternate as the current BUY amount.
- Do NOT modify the underlying `calculate_allocation_signal`, the daily ntfy, SELL fractions, broker reconciliation, current 2.5% market rule, data tapes, portfolio Sheets, Production 5.8.2, or Research 5.9.

## Tests and rollout

`tests/test_streamlit_offline_ui_smoke.py` runs the **actual Streamlit launcher** with entirely synthetic verified completed BTC, dated FX, isolated unavailable Google Sheets and no executable broker quote. Assert current tab contains no live alternate BUY selector; the historic research alternate remains; a simulated stale session value of `adaptive_value` still produces *BUY 2.50%* at a verified below-WMA price, and it never fabricates a trade when portfolio is absent. The same test verifies HOLD, refresh, stale feed => UNAVAILABLE, and independent Production/Research date persistence. Existing shared allocation and ntfy parity suites must stay green.

This is a narrow usability correctness issue, not a re-fit of investment strategies or evidence of better investment returns. Active BUY/SELL, real portfolio and daily notification remain untouched. No additional GitHub schedule, no new notification or market provider.
