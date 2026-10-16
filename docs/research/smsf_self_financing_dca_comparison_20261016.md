# Self-financing BTC DCA sizing: FIFO SMSF CGT sensitivity (research only)

**16 October 2026 · not tradeable advice, forecast, or Production code.**

Results validated by [successful GitHub Actions run #38884378158](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38884378158).

* Source and methods: [smsf_self_financing_replay.py](../../engines/research/smsf_self_financing_replay.py).
* Regression checks: [test_smsf_self_financing_replay.py](../../tests/test_smsf_self_financing_replay.py).
* Exact-date reweighting attribution: [dynamic_dca_weighting_attribution_20261016.md](dynamic_dca_weighting_attribution_20261016.md).

## Major scope limitations

The accounts start with **A$500,000 on the earliest tradable January 2016
weekly close**. Terminal values reflect BTC's unprecedented 2016–2026
appreciation and do **NOT** forecast an A$500,000 investment made in 2026.
The historical stored master `risk_score` is still not independently
verified as fully point-in-time. All policies are heavily inspected in sample.

To isolate position sizing rather than detect different tops/bottoms, all
three policies use the **same 322 buy/sell OPPORTUNITY dates** generated
by the research-only 10% drawdown plus trailing AUD 20WMA confirmation
and risk <=0.35 buying. Individual fills can differ when cash/BTC is
too small. Market prices on those dates are independent of the sizing
variant; no future prices enter its fractions.

- **Current adaptive weighting:** original actual fraction of remaining
  BTC/cash available at each opportunity (with minor 7-decimal
  fraction rounding).
- **Constant-rate baseline:** buy with 10% of currently available AUD;
  sell 20% of currently held BTC on each eligible observation. This is
  a constant *fraction*, **not** precisely equal AUD orders.
- **Trend/reserve challenger:** variable fractional buying with last-
  observed 52-week price drawdown and low-risk evidence; variable
  selling with observed relative price rank within the previous
  26-week range. At no time does it know future extrema or plan end.
  It is an exploratory model inspired by known historical failure;
  **not** independent validation.

## Historical terminal outcomes (Aug 31, 2026)

All purchases and sales charge **A$3 brokerage per actual filled order**.
Accounts use AUD cash and BTC and reinvest only actual after-tax cash
from previous sales. SMSF accumulation-phase CGT is approximated
using FIFO purchase lots, 15% on non-discount eligible realised gains,
effective 10% on gains held strictly longer than 12 calendar months,
immediate tax escrow, and capital loss carry-forward. These are not
annual SMSF tax returns and exclude pension-phase exemptions, account
expenses, ETF spreads, or fund management fees.

| Model | BTC remaining | Liquidation value after CGT (A$) | Realised CGT escrow already deducted (A$) | Order brokerage (A$) | Max nominal equity DD |
|---|---:|---:|---:|---:|---:|
| Buy & hold, single initial purchase | 782.40 | 76,436,027 | 0 | 3 buy fee | Not reported |
| Current adaptive sizing | 2,210.63 | 232,206,224 | 18,266,854 | 963 | −60.83% |
| Constant-rate 10%-buy/20%-sell | 2,166.99 | 232,855,885 | 22,036,128 | 966 | −59.20% |
| **Trend/reserve challenger** | **2,289.27** | **242,101,942** | **20,012,566** | 966 | **−61.21%** |

The hypothetical final liquidation value **includes further CGT** on
the remaining unrealised gains, unlike the current equity mark.

For context, before deducting CGT (all models still pay A$3/order),
ending equity was A$305,789,900 (adaptive), A$308,004,451
(constant-rate), and A$319,406,439 (trend/reserve). Comparing
the before-CGT figures with the after-CGT ones is invalid as it
ignores sale-tax drag on reinvestment.

## More important: actual 25%-average-execution accuracy

Using AUD/BTC effective execution prices at each actual order, with
the same ex-post time-ordered cash-feasible peak/low reference and a
26-week extension for judging buy timeliness:

| Model with CGT escrow | Both sides <=15% | <=20% | <=25% | <=35% |
|---|---:|---:|---:|---:|
| Current adaptive | 2/5 | 2/5 | **3/5** | 4/5 |
| Constant-rate | 2/5 | 2/5 | **3/5** | 4/5 |
| Trend/reserve challenger | 2/5 | 2/5 | **3/5** | 4/5 |

The challenger **did not improve the percentage of eligible cycles
that met the 25% target**. Its larger hypothetical AUD value alone
is insufficient evidence to approve it.

### 2021 sale / 2022 rebuy failure persists

| Model | Sell error from feasible reference peak | Buy error above subsequent low |
|---|---:|---:|
| Current adaptive | 46.38% | 41.30% |
| Constant-rate | 45.98% | 33.16% |
| Trend/reserve challenger | **43.05%** | **34.89%** |

All three are far outside the 25% target on BOTH legs. We need
better regime detection / calendar decisions, not just size tweaks.
The final 2025–2026 round-trip is **censored**, not counted.

## Tax treatment is deliberately simplified

- This is NOT annual fiscal-year tax computation. Withholding at each
  sale and reducing next purchase cash immediately is a conservative
  modelling choice; real tax liabilities are calculated through the
  fund annual return, incorporating its other income, losses, and
  eligibility, and may differ materially.
- Tax lot allocation is FIFO, not an optimised identification of
  allowable parcels. Capital losses offset shorter-held gains first.
- Most importantly, 10% is NOT guaranteed on all sales: assets held
  less than 12 months may be taxable at 15%, pension-phase gains can
  be exempt under relevant conditions. Future law may differ.
- Price series uses historic AUD weekly closes, ignores bid-ask
  spreads, actual Bitcoin ETF management charges and market impact.
  No forced asset liquidation happens except the diagnostic
  hypothetical mark-to-liquidate endpoint.

## Decision

**Do not promote any current model.** In-sample, the challenger
has a higher terminal after-tax value but significantly worse maximum
drawdown and **no increase in the number of cycles meeting <=25%
execution error on BOTH sides**.

The next high-impact research activity is verifying point-in-time
`risk_score` inputs and improving BUY/SELL *opportunity detection*
around 2021/2022 using genuinely causal signals, not adjusting
fractional sizes to fit the available history. Test later periods
without re-optimisation, and start prospective paper trading. The
Production Streamlit model, validated data master and portfolio
remain unchanged.
