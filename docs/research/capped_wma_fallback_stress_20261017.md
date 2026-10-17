# BTC fresh-cash 200WMA fallback — frozen 10% starter audit
17 October 2026 | Research only | PR #127

## Verdict: retain original live BUY rule; DO NOT promote 10% starter

A *small starter allocation* can reduce the opportunity cost of waiting for a NEW 200WMA crossing, but the first exposed crash scenarios show genuine additional downside. The capped fallback improved one real retrospective late-2018 no-cross entry from A$400,000 to **A$462,553.75**, yet it still finished **57.54% below an immediate BTC lump sum** in that same rising market. In deliberate delayed-crash paths where the 10% starter had already executed, it finished as much as **4.12% below the original fixed-budget BUY** and **18.81% below the daily remaining-cash BUY** on the matched hypothetical after-tax AUD metric.

The current 2.5%-of-remaining-cash Streamlit/ntfy policy and original day500/200WMA historical model remain **unchanged**. None of this establishes a 20/25% future trough error guarantee, a prospective annual gain, or a genuinely out-of-sample win rate.

## ONE predeclared starter rule, not a broad parameter search

A new A$400,000 *hypothetical fresh-cash only* portfolio, with no BTC originally held at the halving and no fabricated September 2025 sale:

1. Original strict prior-close below prior **200WMA** (200 exactly prior seven-day spaced daily closes) remains primary activation.
2. If there has been **no** post-enrolment below-200WMA activation, first wait **56 days**. Only at start+56/+63/+70/+77 may the experiment invest **2.5% of ORIGINAL AUD400k**, each date, when the prior close is in the range **1.0–1.5× the prior 200WMA**. Hard limit **10% in total** of original cash for these starter fills. Do not chase >1.5×200WMA, do not force a missed fill later.
3. If the below-WMA entry activates earlier or later, terminate the starter and use the **unmodified original weekly adaptive-recovery** 2.5/15/4.5/1% of original cash budget. Those later regular BUYs **can use more than the starter's 10% cap**. The 10% limit is NOT a permanent portfolio BTC exposure ceiling.
4. Each execution uses daily BTC/USD close (optimistic proxy), an actually *prior dated* USD/AUD FX observation, A$3 per executed fill and simplified FIFO SMSF capital-gains tax on hypothetical terminal liquidation. Both benchmark accounts use the identical starting cash, date, price/FX source, end date, and simplified tax approach.

The starter thresholds were frozen in code before seeing this experiment's results. They are research hypotheses, **not empirically optimal values** or an untouched out-of-sample trial. The original historical 200WMA/day500 rules have already been heavily studied.

## Completed historical observation windows

Each item is ending hypothetical AFTER-liquidation-tax AUD from the **same original A$400k**, compared to the original fixed-budget 200WMA BUY policy from PR #126.

| Previously inspected period | New cash starts | Starter capital used | End A$ with capped fallback | Relative benefit vs original 200WMA-only |
|---|---|---:|---:|---:|
| 2017-based | 20 Apr 2018 (+650d) | 0% | 1,048,234.76 | 0% |
| 2017-based | 29 Jul 2018 (+750d) | 0% | 1,048,234.76 | 0% |
| 2017-based | 6 Nov 2018 (+850d) | 0% | 1,048,234.76 | 0% |
| **2017-based** | **26 Dec 2018 (+900d)** | **10%** | **462,553.75** | **+15.64%** |
| 2021-based | 20 Feb 2022 (+650d) | 0% | 584,507.80 | 0% |
| 2021-based | 31 May 2022 (+750d) | 0% | 584,507.80 | 0% |
| 2021-based | 8 Sep 2022 (+850d) | 0% | 541,440.34 | 0% |
| 2021-based | 28 Oct 2022 (+900d) | 0% | 517,279.73 | 0% |

For the **26 Dec 2018** starting case, the original prior-200WMA BUY rule **never made a post-start trade** and remained A$400k cash. The capped starter spent precisely **10%**, ended with **90% original cash remaining** and ended at A$462,553.75 (+15.64% relative to cash/current strict rule). The same starter finished **27.0% below fixed 52-week DCA** and **57.54% below immediate lump-sum BTC acquisition**. These are relative ending wealth differences, **not** opportunity-return forecasts.

Where the original below-200WMA gate occurred early, the starter never activated. Thus it generated **no improvement in 7 of 8 completed historical entry cohorts**. That is descriptive of these already-studied dates, **not a future win rate**.

## Recent observation — censored 2025/26 cycle

All terminal prices through the archived **5 October 2026** close only. The bottom and future outcomes remain unknown.

| Fresh cash starts | Fallback original-budget starter | End A$ fallback | Relative vs original fixed-budget BUY | Relative vs simplified daily BUY |
|---|---:|---:|---:|---:|
| 30 Jan 2026 (+650d) | 10% | 486,748.75* | +0.65%* | +4.42%* |
| 10 May 2026 (+750d) | 0% | 483,584.32* | 0%* | +3.74%* |
| 18 Aug 2026 (+850d) | 0% | 400,000* | 0%* | 0%* |

*Incomplete observation.* In the final August example, only **48 days** of future close data exist through 5 October; the eight-week fallback does **not** have time to execute. Both 200WMA-gated strategies hold all A$400k cash, and no outcome beyond 5 October 2026 is implied.

## Delayed 50/70% downside — important corrected design

Historical BTC closes **BEFORE each designated shock date remain exactly unchanged**. At historical halving-relative day900, day960 or day990, artificially force the BTC price down 50% or 70% to a **day1060 trough**, then set a day1150 terminal close to 55% or 105% of pre-shock price with smooth geometric interpolation. **Those post-shock prices are fabricated counterfactuals**, not Bitcoin history, projections or probabilities. Dated historical AUD FX remains identical across variants even though real FX could react differently in a crisis.

The first audit used only +750/+900 and +850/+960 windows. In those windows the fallback generally **did not buy before the crash**, making the test misleadingly benign; comparing two identical policies could not prove safety. We correctly added **day900 new-cash start → 10% starter executes by day977 → delayed day990 shock → day1060 trough**, with a dedicated synthetic unit test that insists the previously executed starter can materially hurt terminal AUD relative to original strict waiting. Full stress outcomes below use **12 fixed cases per historic pre-shock cycle**, including four exposed candidate scenarios in the 2017-based period.

| Synthetic history source | Total deliberately chosen stress cases | Scenarios actually exposing starter to crash | Worst fallback vs original strict fixed-budget BUY | Worst fallback vs current daily remaining-cash BUY | Best fallback vs current daily BUY |
|---|---:|---:|---:|---:|---:|
| 2017-based prefix | 12 | **4** | **−4.12%** | **−18.81%** | +20.92% |
| 2021-based prefix | 12 | **0** | 0% | +2.25% | +91.26% |

The 2021 stress group **does not validate fallback downside**: every replay activated original 200WMA buying first, so the fallback stayed off. Its sometimes favorable comparison with the current daily rule measures the **original fixed-budget weekly model's results**, not any demonstrated benefit of buying above WMA.

The maximum fraction spent **before** the artificial trough was **86.5% of starting cash** in the 2017 stress family, and **100% in the 2021 family**, because once the real prior-below-200WMA rule starts, the existing weekly recovery rule can still deploy almost all remaining capital. That is unrelated to the strict 10% *pre-trigger* starter cap; the overall policy is NOT capped at 10% risk exposure.

These stress-case counts are **neither statistical win rates nor probability estimates**. They are adversarial causal diagnostics using already-inspected cycle prefixes and scenario assumptions selected to expose risk.

## Decision and development priority

**Do not promote this candidate to Streamlit or ntfy.** It demonstrates a mechanically useful way to limit *some* missed-upside cost, but the improvement is concentrated in one complete historical entry period, requires eight weeks before acting, fails to solve the full opportunity gap, and can reduce after-tax portfolio value when crashes follow the starter. An eligible above-WMA range does not distinguish a durable recovery from a false rally.

If further exploration is warranted, stop modifying production and evaluate risk budget and drawdown tolerances against the user's *actual verified 2026 cash, BTC and ASX:IBIT positions*, and separate accumulation goals from potentially taxable SMSF events. Any future challenger should be judged on many dated starts, unchanged cohort rules, difficult negative scenarios and forward evidence before replacing the live model.

## Audit and reproducibility

- Research code: `engines/research/capped_wma_fallback_stress.py`
- Tests: `tests/test_capped_wma_fallback_stress.py` (9 tests), plus existing PR #126 tests (8)
- CI: `.github/workflows/capped_wma_fallback_stress.yml`
- Complete historical and synthetic daily-price-driven trade ledgers: GitHub Actions artifact `capped-10pct-wma-starter-stress`
- All historical result and math percentages are AUD-based, from identical hypothetical cash starts, simulated BTC USD closes/FX, fee and simplified SMSF liquidation CGT assumptions. NOT actual ETF or personal investment performance.
- **Production V5.8.2, Research V5.9, existing Cycle Trading Streamlit/ntfy recommendations and schedules, real Google Sheets portfolio, user holdings and broker orders unchanged.**
