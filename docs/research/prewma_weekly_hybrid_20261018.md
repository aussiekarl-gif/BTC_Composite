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


## Completed numerical verdict — REJECT LIVE PROMOTION (18 October 2026)

The frozen candidate and all independent comparative accounts passed [GitHub Actions run 39105863929](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39105863929): 8 new hybrid tests, 8 reference cash-only 200WMA tests and 9 existing earlier fallback tests **all pass**. [Detailed run ledger, cohort CSVs and shock paths](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39105863929/artifacts/12127813010). Historical period is already modelled/inspected, so no out-of-sample evidence.

| Historical BTC cycle | Fresh cash start, halving+day | Pre-gate starter share of ORIGINAL AUD | Hybrid vs original 200WMA in illustrative after-tax AUD | Hybrid vs fixed 52-week DCA |
|---|---:|---:|---:|---:|
| 2017 completed | 650 | 10% | **-4.036%** | +27.293% |
| 2017 completed | 750 | 10% | **-3.458%** | +31.324% |
| 2017 completed | 850 | 6% | **-0.458%** | +48.787% |
| 2017 completed | 900 | 10%; original gate never triggers | **+17.330%** | **-25.931%** |
| 2021 completed | 650 | 10% | **-4.950%** | +6.463% |
| 2021 completed | 750 | 2% | **-0.383%** | +6.460% |
| 2021 completed | 850,900 | 0%; immediate WMA gate | 0.000% | +6.191%, +6.327% |
| 2025/26 right-censored | 650 | 10% | +0.837%* | +7.124%* |
| 2025/26 right-censored | 750 | 4% | +0.022%* | +11.535%* |
| 2025/26 right-censored | 850 | 7%; no new gate by Oct 5 | +0.760%* | **-0.697%*** |

*2025/26 current observed low/terminal price may change dramatically after archive cutoff Oct 5; NOT a completed investment period.*

Against immediate lump sum, even the strongest late 2017-relative case (+17.330% over no-buy original) finished **56.923% below lump sum**. The proposed partial starter therefore fails to capture much of the upside in a fast recovery. It may marginally improve recent 2026 observed trajectories but they are right-censored.

### Exposed delayed-bottom stress

**All twelve** synthetic cases bought 10% of original cash before the forced shock, so none of the stress comparisons is vacuous. Ten of 12 ended behind the unchanged original 200WMA strategy (all four 2021+650 shocks and all four 2017+750 shocks, plus two of four 2017+900). The **worst relative after-tax outcome was -12.834%** (2017 +750, 70% delayed drawdown, end 55% of pre-shock price). Two 2017+900 synthetic endings were marginally ahead (+1.377%, +1.142%), but the same cohort lost (-3.701%, -2.744%) on the less favorable terminal recovery outcomes. These **invented paths are not sample outcomes and do not imply a 10/12 loss probability**.

### Decision

- **DO NOT promote** this 1% weekly max-10% starter to Streamlit or ntfy; its worst exposed delay-to-bottom loss, negative 2017/2021 cohorts and poor performance against conventional weekly DCA in a no-WMA rally do not establish a robust improvement.
- The real tradeoff remains unsolved: an unconditional starter reduces cash drag when BTC recovers but adds price exposure before the eventual bottom; simply assuming future higher lows or shorter cycles cannot resolve the tradeoff.
- Preserve strict prior-completed-close 200WMA as the existing baseline, no fabricated 2025 portfolio holdings and no daily trading rule changes. If considering a future candidate, distinguish prospective genuine personal cash-start dates and use a separately frozen forward test with slippage, ETF trading hours and real AUD tax lots.
- Research negative result is recorded here and in GitHub PR #139; keep new research code off `main` by closing the draft unmerged. No production V5.8.2, Research V5.9, Streamlit, daily ntfy, live orders or Google Sheets data were changed.
