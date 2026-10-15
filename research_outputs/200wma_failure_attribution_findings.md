# Cash-drag root cause: 2019 and 2023 BTC cohort failures

**Research only — do not change Production V5.8.2.**

Verified [GitHub Actions run 38815941285](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38815941285), artifact `200wma-aud-failure-attribution`.

## Conditions and comparison
A$500,000 notional portfolio starts 20% BTC and 80% cash, fully deploys remaining cash across 12 weeks with causal 200WMA weights. Tier trading uses 12-week bell purchases and 16-week bell sells, same-tier overlap blocked, 0.1% dealing fee, 0.5% slippage, A$20 per fill, 0.45% annual simulated ETF fee drag, and simplified 15% SMSF accumulation CGT with yearly cash settlement. The comparison is identical risk-weighted DCA **without any subsequent sells**. This is a synthetic BTC/AUD ETF proxy, not an actual historical ASX fund before its 2024 inception.

Results are over **13 overlapping starting dates per year** and a 104-week horizon.

| Start year | Wins vs DCA | Median net advantage | Median sell-tier fills | Median rebuy-tier fills | Median final cash |
|:--|--:|--:|--:|--:|--:|
| 2019 | 0 / 13 | **−32.690%** | 180 | 84 | A$1,904,097 |
| 2021 control | 13 / 13 | **+96.852%** | 134 | 192 | A$104,222 |
| 2023 | 2 / 13 | **−12.872%** | 97 | **0** | A$893,511 |

### Exposure diagnosis
- **2019:** median cash weight across the post-funding weeks **41.36%**, with 37 of the 92 post-funding weeks above 50% cash. The worst 2019 starting cohort (25 March 2019) had a two-year return **59.48% below DCA**, spent **47 weeks above 50% cash**, and had mean post-funding cash weight **61.57%**.
- **2023:** although median cash weight across post-funding weeks was only **20.35%**, median tier-rebuy count was **zero** and the strategy ended with about **A$894k uninvested cash**. At the worst 2023 starting date (30 October 2023), it ended with **A$1.07m cash** and was **19.18% below DCA**.
- **2021 control:** strong outperformance corresponds to 192 median tier-rebuy fills and lower median ending cash, not just a good initial buy price.
- The 26-week partial idle-cash recycling guard modestly reduced loss (2019 median −28.607%; 2023 median −11.050%), but did **not** produce a positive median or win any 2019/2023 cohorts that had previously been losing.

## Diagnosis and next controlled experiment
A sell trigger can become profitable only if re-entry occurs at a sufficiently favourable price. The fixed 10-tier +100% to +280% sell ladder can create large unspent cash balances when BTC stays above its prior 200WMA buying thresholds. This is a measurable structural failure, **not just trading fees**.

Test a *prior-specified exposure cap* that prevents free cash resulting from tier selling from exceeding fixed percentages of current marked portfolio value, e.g. **25%, 40%, 60%**, against the uncapped baseline. Use matched AUD after-tax 2-year and 4-year starts, including 2021 controls and all available cohorts. These thresholds are selected **after studying history**, so any apparent gain is *in-sample* and cannot justify Production promotion.

## Implications
- Do not select a 26-week idle-cash safeguard merely because it improves four-year median results.
- Do not conclude a strategy is robust from 2018–2024 overlapping starts.
- Prefer *prospective* data from the frozen VBTC paper test starting 19 October 2026, real execution spreads when available, and fixed strategy constraints before allocating capital.
