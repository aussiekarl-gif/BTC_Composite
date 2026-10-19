# Bitcoin capital deployment objective — clarified 20 October 2026

## User decision (supersedes earlier deadline assumption)

**The user's BTC deployment deadline is flexible into 2027 if signals remain unattractive.** November 2026 is no longer a hard requirement to invest remaining AUD capital. Do **not** hard-code a compulsory buy, catch-up tranche, final all-cash sweep, or target cash-exhaustion date into Cycle Trading, Production V5.8.2, Research V5.9 or the trading dashboard.

A prolonged HOLD / 100% uninvested remaining AUD cash can be a legitimate conditional research outcome, not an error requiring an automatic purchase. Cash drag / missed upside must still be measured so we do not always reward being uninvested.

## What is NOT being changed

- The actual Streamlit Cycle Trading BUY recommendation remains **2.5% of available remaining AUD cash**, *only* upon an eligible previous BTC close below previous 200WMA and *subject to the actual account's 7-calendar-day trade cooldown*. Neither this amount nor SELL logic is changed.
- The **original preregistered 20-week fixed DCA** and initial buy-and-hold in the A$100k prospective ASX benchmark are frozen **CONTROL POLICIES**, not a deadline imposed on the user's uninvested capital. Retaining them preserves a clean evaluation of the opportunity cost of waiting.
- The earlier A$500k fresh-cash scenarios are hypothetical *reference accounts*, not a verified picture of the actual user's current unspent cash, brokerage holdings, pension tax phase or available funding.
- No broker orders, SMSF tax assumptions, portfolio/Google Sheets changes, extra ntfy messages, historical source tape rewrites or new scheduled CI job.

## Next economically relevant optimisation question

Under which *pre-registered, point-in-time* valuation and cycle regimes can we increase weekly BUY percentages (e.g. 3.0%, 3.5%, 5.0% of **remaining** AUD cash), while improving expected terminal **after-cost AUD equity** without unacceptable worst-case drawdown if Bitcoin's decline extends into 2027?

Use the already available exact-live seven-day-cooldown research, and avoid attributing better returns merely to more BTC exposure.

Essential testing requirements:
1. Keep the 2.5% actual current BUY baseline and the predeclared fixed weekly DCA / buy-and-hold matched-capital controls intact.
2. Test conditional deployment with no required terminal cash spend, distinct October 2026–2027 checkpoints used only for *measurement*, and hypothetical eligibility varying from zero to every possible seven-day-spaced window.
3. Quantify cash remaining, cash invested, BTC/IBIT market exposure and opportunity cost versus fixed DCA/buy-and-hold, not just average price or total BTC.
4. Measure 2021/2017 historical window sensitivity and 2026/27 future outcomes with no vintage revisions, no extra fitting after viewing the future, price drawdowns, a second lower low and recovery without buying; label 2017/2021 as retrospective, NOT prospectively validated.
5. Include real AUD IBIT spread/slippage, observed ASX trading hours, fees, FX, and parcel-specific tax sensitivity before any live model or fund decisions.
6. Do not add an artificial year-end 'safety buy', 2027 mandatory buy, or automatic strategy promotion. If value signals remain poor, wait without a deadline. If the source is stale/unverified, the model must HOLD.

## Illustrative cash-deployment envelope — no market forecasts or trades

Research module: `engines/research/flexible_2027_cash_deployment_envelope.py`

The script shows only **conditional** percentage-of-remaining-cash arithmetic using illustrative A$500,000 and eligible BUY opportunity counts, *not* predicted 200WMA signals, a personal portfolio or actual BTC purchases.

Checkpoints Nov 2026, Mar/Jun/Dec 2027 are **measurement dates, not deadlines**. An upper bound assumes buying can be eligible every seven days. The scenarios include **ZERO eligible BUY opportunities** (all cash remains) and 25%/50%/100% of the maximum opportunity count. Buying 2.5%, 3%, 3.5% or 5% of remaining cash only on those counterfactual opportunities is shown alongside untouched residual cash.

This module cannot establish price return, future bear-bottom probabilities, tax, broker execution, sufficient exposure, genuine performance or statistical alpha. More aggressive weekly purchases mechanically reduce available cash but can worsen subsequent losses. A cash-only hypothetical envelope helps assess sizing, **not optimise model parameters**.

Run offline:
`python -m unittest discover -s tests -p 'test_flexible_2027_cash_deployment_envelope.py' -v`

One manual/PR GitHub test workflow (no cron) validates the code and produces an optional research artifact. The pending real BTC/ASX forward samples remain the ultimate evidence gate; no live strategy changes are authorized by this decision alone.
