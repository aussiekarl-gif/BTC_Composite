# Weekend 200WMA signal carry — newly discovered candidate, 18 October 2026

**Research-only, deliberately chosen AFTER seeing earlier PR #147 outcomes. Nothing in Production, current Cycle Trading BUY/SELL, Streamlit, ntfy or portfolio has been changed.**

## Background and precise reason

Existing Cycle Trading shared `calculate_allocation_signal` gives BUY WATCH only if previous BTC/USD daily close was strictly below prior 200 spaced weekly BTC daily closes. Existing active execution also requires a ≥7-calendar-day cooldown since the previous **executed** BUY or SELL. A BTC/USD price can reach the strict 200WMA during Sat/Sun, when ASX:IBIT is not tradable, then rally before Monday. The current market WATCH can show HOLD on Monday; a user following weekday-only HOLD never gets to BUY at all.

Completed 2017 after halving+650,+750,+850 gave **ONE** eligible fresh below-WMA BUY event under the BTC-close all-day proxy on **Sunday 16 December 2018**; weekday-only proxy gave zero BUYs, leaving 100% cash. This is structural timing, not a weak 2.5% multiplier. Based on observing this anomaly, we freeze the following **separate future-only hypothesis**, without pretending it is validated on independent historical data.

## Frozen rule for experiment — NOT live

Use all current exact original shared BUY market WATCH triggers on BTC completed T−1 data; a pending weekend WATCH can be remembered only on Saturday/Sunday and must expire the moment its **first subsequent weekday** is reviewed. For that review, the pending BUY may be executed on that weekday only if:
1. No executed BUY/SELL in prior seven calendar days; actual research simulated wallet exactly limits 7-day BUYs.
2. Weekend market WATCH was <=3 **calendar** days earlier and no earlier weekday review consumed it.
3. Latest strictly prior-day BTC close **has not rebounded more than 3% ABOVE the then-prior strict 200WMA**.
4. The simulated execution occurs at the weekday reference BTC/AUD T close, **not backdated to the weekend low**. No unverified price as an executable IBIT quote; holiday exclusions NOT implemented, so weekday may still not be a real ASX open session.

The 3% price cap and maximum 3 days are fixed candidate safeguards selected after identifying 2017 Sunday gap. They are **not validated thresholds**; permit a BUY when the unmodified current model would have HOLD, and risk chasing a rebound. This is why explicit user approval after thorough independent research is required before any live adoption.

## Matched comparison

Original weekly 2.5% remaining cash and additional exploratory 3.0% residual cash, each **with and without weekend carry**. Both start AUD400k fresh cash (not past user's personal portfolio). Calculate aftertax terminal AUD, BTC units, purchase dates, cash left, and number of *actually carried Monday* orders for 2017/2021 complete through halving+1150, 2025/26 incomplete through Oct5 2026, starts halving +650/750/850/900. Independent prior-only BTC/USD close and dated USD/AUD FX; flat A$3 per fill; illustrative immediate SMSF FIFO CGT. Three cost sensitivities: no extra spread/no fund fee; weekday 25bps each side + 0.39% annual hypothetical NAV drag; weekday 50bps each side + 0.39% drag. Actual iShares Australia IBIT launched November 2025, so earlier histories remain counterfactual BTC proxies.

Eight previously used 2017/2021 historic-prefix synthetic deeper 50/70% bear paths, terminal at 55% or 105% previous shock level; these are **not probabilities**. Score whether the added exposure from preserving weekend BUY opportunity improves actual historic terminal account relative to unmodified weekday strict rule AND whether it makes losses worse in adverse plausible counterfactual paths. Separately compare 3.0% vs 2.5% within same carried policy. No optimization based on these results.

Test safeguards: weekend Sunday signal can buy Monday if historical T−1 no more than +3% above strict WMA; cannot carry through +6% next-day rebound; original market WATCH unchanged; no weekends actual fills; missing price/FX fails closed; cooldown remains exact; no duplicate carry after Monday; if no signal, no invented BUY.

**Do not deploy weekend carry automatically.** Continue daily forward validation and independent IBIT price/exchange-calendar provenance work.

CI numerical outcomes: Pending.
