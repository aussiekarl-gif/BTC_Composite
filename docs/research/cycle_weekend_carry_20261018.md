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

## Verified result — 18 October 2026

[**GitHub Actions run 39118361041 passed 32 tests**](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39118361041) (6 new weekend queued-watch tests, 8 original weekday execution parity/safety, 8 weekly DCA, 10 current live market allocation tests). All 114 dated rows (11 real/cohort x3 assumed cost scenarios x2 buy sizes; 8 shock paths x3 costs x2 buy sizes) and original/carry BTC buy dates, order sizes, posttax AUD accounts in [artifact 12133376916](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39118361041/artifacts/12133376916). All market-level WMA WATCH counts identical between queue and original strict weekday models.

### Pure sizing unchanged: 2.5% remaining AUD cash in BOTH models

| Observed historic BTC cycle cash cohorts | Strict weekday only | Optional weekend pending carry (same 2.5%) | Entire terminal account gain/loss |
|---|---|---|---:|
| 2017 complete starts +650/+750/+850 | Zero purchases: only Sunday signal | **ONE Monday 2018-12-17 BUY** | **+4.590%** no extra cost; **+4.538%** at 25bp/side + 0.39% p.a.; **+4.505%** at 50bp/side |
| 2017 complete +900 | No post-start WMA WATCH | no trade | 0% |
| 2021 complete +650/+750 | 39 purchases | 39 (no extra carried trade) | 0% |
| 2021 complete +850 | 30 | 30 | 0% |
| 2021 complete +900 | 22 | 22 | 0% |
| 2025/26 incomplete +650/+750 | 6 | 6 (Monday 2026-06-08 opportunity changed earlier fill) | **−0.041%** |
| 2025/26 incomplete +850 | none | none | 0% |

**These are entirely retrospective BTC/USD converted AUD returns for a hypothetical AUD400k fresh-cash wallet. ASX:IBIT did NOT trade in December 2018; its first ASX trading day was 14 Nov 2025. Thus the 2018 'Monday BUY' refers to an hypothetical BTC-close-priced *weekday proxy*, NOT an actual IBIT quote or actual owned asset.** Two identical starts are highly overlapping, not independent sample confirmation.

The single extra Monday BUY solved a 2018 missed trigger **in that observed completed market**. The 2025/26 still-unfinished interval instead loses 0.041% terminal account even though there are no extra fills: the pending WATCH advances one weekly purchase timing. This means the rule modifies timing in ways that can be harmful even when the trade count is unchanged.

### Artificial prolonged bear-path sensitivity

| Same candidate 2.5% strict weekday vs carried | Historical-prefix synthetic outcomes of eight paths |
|---|---|
| 2017-based four deeper-bottom paths | **all four worse** when weekend carry adds the single earlier BUY: −0.152% to **−0.955%** under zero-extra-cost assumption |
| 2021-based four paths | identical 0% (no new carried BUY) |
| With 50bp assumed one-side cost and 0.39% NAV drag | four losing of eight; worst **−0.963%**, others unchanged |

These scenarios were deliberately constructed, not probabilities. **The recommendation remains blocked from automatic promotion**: although recovered 4.5–4.6% whole-account historically in one otherwise-missed BUY event, it also costs up to 0.96% in known artificial extended declines. We have **only one completed observed modern cycle where it changes the trade count**. The 3% safe rebound limit and <=3-day maximum age are selected POST HOC and thus not validated.

### Separate technical correctness risk to resolve

The present live market BUY WATCH is calculated on a fully previous BTC close and is valid as a market indication even on weekends, but an ASX instruction must explicitly preserve the **snapshot of the weekend signal and its date**. Merely reading Monday's fresh market model would say HOLD and lose the queued watch. A future live implementation would have to persist a separately dated market signal and de-duplicate it with actual broker order ledger, using an actual exchange session/holiday calendar and actual quote/bid-ask. Otherwise this research weekend carry can be accidentally acted upon twice, after a holiday, or at a wildly different price. This study uses weekdays Mon-Fri, not verified real ASX trading holidays.

**Decision: retain 2.5% original Cycle BUY live; no Production/Streamlit/ntfy/portfolio/broker changes.** Record the historical missed-weekend problem as high priority for real trade-execution design review and future prospective validation; do NOT quietly add an on-Monday BUY exception to a HOLD recommendation before explicit user approval and more robust independent execution tests.

