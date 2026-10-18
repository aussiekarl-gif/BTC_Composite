# Frozen BTC buy-side hybrid — small weekly starters and 200WMA recovery

18 October 2026. Research only; **never modify Streamlit, V5.8.2 Production, V5.9 Research, ntfy, broker, Google Sheets or actual portfolio** based on this experiment.

## The explicit question

Could a **small regular purchase before a confirmed 200WMA crossing** reduce the cash drag in maturing Bitcoin regimes with shorter drawdowns/higher lows, without surrendering too much dry powder if Bitcoin subsequently falls far below 200WMA?

Previously completed studies rejected a 10% above-WMA starter only after day56 and price ratio <=1.5, and a 10% INITIAL BUY at the WMA crossing in deliberate deep-bottom shock scenarios. Those are different hypotheses; neither validates the current variant.

## One predeclared strategy (no parameter tuning after examining outcomes)

- Start with A$400,000 **entirely fresh cash** at preselected halving-relative day+650,+750,+850,+900; do NOT fabricate any pre-existing BTC lot or top-sale proceeds.
- On every 7th calendar day beginning **start+1**, invest **1% of original starting AUD cash** only UNTIL the **FIRST strictly completed prior-day BTC close below the strict exact 200-week MA**. Cap aggregate pre-gate gross purchases at **10% of original cash** permanently. This can make at most 10 pre-gate starter purchases. There is no guessed BTC floor and no future data deciding buys.
- At the initial WMA signal, terminate the starter immediately and buy with the unchanged original `adaptive_recovery` 200WMA weekly schedule at gate date and each 7 days thereafter. All later 2.5/15/4.5/1% allocations reference **original fixed AUD cash**, constrained by true cash remaining. The 10% starter cap is **NOT** a permanent risk or post-gate exposure limit: original weekly rules may deploy all remaining funds while BTC continues falling.
- If **no** post-start below-WMA signal occurs, starter is capped at 10% and leaves >=90% AUD cash; fixed-gate comparators hold 100% cash, fixed 52-week DCA and lump sum provide opportunity cost context.
- Compare at identical BTC/USD daily close (not executable ASX:IBIT), dated STRICTLY PRIOR AUD FX, A$3/trade, self-financing cash and FIFO illustrative accumulation SMSF CGT after terminal liquidation. No price slippage/IBIT tracking/real CGT tax-phase changes.
- Show aftertax AUD terminal differences, BTC held, cash remaining, drawdown, fee tally and retrospectively scored buy price vs observed low. Avoid treating 20% buy-VWAP error as a return guarantee.
- Calendar windows 2017/2021 through halving+1150 **complete** (but already seen in research); 2025/26 right-censored at 2026-10-05.
- Frozen deliberate negative counterfactual delayed-bottom paths use 2017 cash+900 shock+990, 2017 cash+750 shock+960, 2021 cash+650 shock+900, drop 50% or 70% to halving+1060 and then terminal 55%/105% of pre-shock price. Preserve every actual historical price before the shock. Count actual starter purchases *before* shock; when none are exposed, don't call the test successful.
- Synthetic **shallow-no-cross-rising** and **abrupt last-day crash-before-next-signal** tests deliberately check opposite outcomes. These are falsification cases, not probabilities.
- Reject for live promotion if downside is materially worse in stress, wins rely on one cohort, or the only improvement is cash exposure purchased at the cost of substantial downside risk. Two completed modern Bitcoin cycles cannot prove structural non-stationarity.

Expected artifacts: full dated JSON order ledgers, historical and stress CSVs. CI unit tests check no gate, 10% starter cap, original WMA gate date, original post-gate sizing, no lookahead, no invented history, and bad historical price/FX fail closed.

Live existing 200WMA recommendations and notices remain unchanged regardless of research outcome.
