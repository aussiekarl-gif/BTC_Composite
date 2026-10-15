# 200WMA BTC ETF-like SMSF cost/tax stress — 2026-10-15

**Research only; Production V5.8.2 unchanged.** Source scripts: `engines/research/test_200wma_smsf_costs.py` and `engines/research/smsf_cgt_ledger.py`.

Validated GitHub Actions:
- [AUD run 38810383990](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38810383990), `200wma-smsf-costs-aud`.
- [USD regression run 38810383986](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38810383986), `200wma-smsf-costs-usd`. Includes deterministic FIFO discount, loss carryforward and tax-funded sale tests.

## Assumed research portfolio
- Initial A$500,000; hypothetical 20% BTC ETF / 80% cash.
- 12 weeks risk-weighted initial investment; 12-week bell rebuy and 16-week bell sell jobs on upward deviations of the *completed prior weekly USD BTC price* over the trailing 200WMA.
- Same-tier overlap blocked; no reverse cancellation. Historical BTC/AUD reference prices; ETF returns approximated with deterministic annual expense drag, **not actual ETF historical prices**.
- 0.1% fee and 0.5% slippage each purchase/sale. Base sensitivity adds A$20 per fill and 0.45% annual management-fee drag, **both hypothetical**.
- Comparison is otherwise identical cash-first DCA which does **not** sell holdings.
- Tax ledger identifies FIFO acquisition parcels, nets capital losses across Australian July–June tax years, applies one-third discount only for parcels held *more than* 12 months, then 15% SMSF accumulation tax to remaining net taxable gains. Annual tax is charged in July after the previous tax year, earlier than ordinary SMSF return-payment dates; reserve cash is used first, otherwise the model sells ETF units and records any resulting taxable gains.
- **Alternative scenario:** all income is eligible for exempt current pension income (ECPI), modelled at 0% CGT; no claim that a mixed or partly-pension fund has this status.

## Results — Australian dollars
| Simulated holding period | 2 years, 89 overlapping starts | 4 years, 63 overlapping starts |
|:--|--:|--:|
| Gross advantage vs same DCA, A$20/fill, 0.45% MER | +4.567% median | +48.984% median |
| Terminal-only 15% accumulation CGT estimate | +2.402% median | +38.470% median |
| **CGT charged annually from cash, A$20/fill, 0.45% MER** | **+2.402% median** | **+33.099% median** |
| Winning starts with annual CGT | 48/89 | 53/63 |
| Worst historical result with annual CGT | **−59.482%** | **−30.502%** |
| Median total modelled accumulation CGT liability | A$39,041 | A$168,372 |
| Cohorts needing ETF liquidation specifically to fund CGT | 0/89 | 0/63 |

**Cost controls:** 0 brokerage, 0 management fee, 0% CGT gives median +5.406% (2 years) and +49.200% (4 years) versus DCA, so the apparent strategy edge is highly regime-dependent, and CGT eats into it.

## Comparative USD costs (same parameters)
The 4-year USD median falls from +66.962% before CGT to +58.149% with terminal-only CGT, then **+50.887%** when tax payments reduce trading cash each year (A$20-equivalent brokerage / 0.45% annual MER proxy; tax calculated in the simulation currency).

## Critical caveats / blocking gates
- Historical **overlapping** start dates and already-explored parameters; results are **not** independent out-of-sample evidence.
- Simulated ETF share value is a BTC price proxy with hypothetical fee drag, **not exchange-traded VBTC/IBTC/QBTC daily NAV and market spreads**. The model ignores distributions, tracking differences, ETF tax attribution, tax effects on loss adjustments outside the asset ledger, SMSF administration costs, membership, contributions/withdrawals, net exempt pension proportions and retirement caps.
- It assumes all taxable accumulated gains receive standard compliant SMSF treatment; actual annual income may be higher/lower, and trustees can identify actual acquisition parcels subject to recordkeeping. The tax payment convention is a conservative stress, **not an actual ATO lodgement timetable**.
- The implied two-year worst-case advantage versus simple DCA is sharply negative. **Do not promote into Production or deploy real capital on the basis of these numbers.**

Official tax background:
- ATO, [SMSF capital gains and discount](https://www.ato.gov.au/api/public/content/0-42064e26-5e71-4fce-8ca5-a244fc3c6d69).
- ATO, [Current pension exemptions, CGT and carried losses](https://www.ato.gov.au/api/public/content/fd1b39492bff4825b4acdf5920001ecc).
