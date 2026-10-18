# Price-only breakdown re-timing — frozen research experiment (18 Oct 2026)

**Status: research only. No changes to the live Streamlit decision, portfolio ledger, daily ntfy, Production V5.8.2 or Research V5.9. Do not promote candidate without completed comparative evidence.**

## Predeclared test (one hypothesis)

- Baseline: unchanged chronological hypothetical A$500k BTC purchase at each 2016, 2020 or 2024 halving, original day500..730 original-BTC staged exits, fixed earliest day744 prior-close-below-200WMA weekly after-tax cash buyback. The replayer must reproduce the existing independent baseline.
- Candidate: preserve original day500 5% BTC sale. Observe *only prior 90 daily BTC/USD closes* (same existing `prior_price_regime`) each day from halving+501 through +524. At the FIRST price-only `breakdown` reading (prior price >=15% below prior 90-day high, prior price below 50DMA, 50DMA declining over 14 days), SELL **5% of ORIGINAL BTC** early. On day525, subtract that precise 5% original from the **existing original staged day525 tranche**. If no breakdown in that window, candidate is identical to baseline.
- Existing prior-price BUY gate and subsequent 200WMA adaptive recovery remain unchanged. Both use historical AUD FX strictly before execution, A$3 per order, FIFO illustrative immediate CGT escrow and same archived BTC execution-close proxy.
- No added BTC sale: **cumulative original BTC sold by day525 and by end of sell cycle must match to rounding**. If a day525 order could not fund the offset, fail closed rather than allowing an extra sale.
- Historical price comes from archived provider export crosschecked across the existing three exports, but no MVRV/NUPL/SOPR values are used to generate this signal. Dated price alone cannot establish executable BTC/ETF fills. The history is already known to the researchers and must not be represented as out-of-sample.

## Precommitted interpretation

- Compare dollar and percent difference in hypothetical terminal after-tax AUD, eventual BTC balance, order count, fees and realised tax escrow, with original wallet matched exactly.
- Only **2017 and 2021** have completed original 1150-day replay windows; label 2025/26 as right-censored through 2026-10-05.
- If never triggered, this experiment is non-informative for that cycle. If it increases final after-tax wealth only for one of two cycles, **do not promote**. Even two positive in-sample cycles would be exploratory, not a reliable return estimate.
- Strong negative results or missing realistic timing robustness => reject. No threshold sweep, no hindsight selection among signals.
- Check synthetic tests for next-day price causality, missing data fail-closed, same original sold by day525, strict original simulation parity and identical 200WMA gate.
- Extra warnings: BTC USD close proxy is not an ASX:IBIT transaction price; Australian SMSF CGT assumptions are simplified; a real 2026 IBIT holding cannot retroactively have participated in a 2025 sell.

## Reproduce in GitHub Actions

Workflow: `.github/workflows/price_only_breakdown_advance.yml` and research artifact `price-only-breakdown-retiming-evidence`.

```bash
python -m unittest discover -s tests -p 'test_price_only_breakdown_advance.py' -v
python -m engines.research.price_only_breakdown_advance --out artifacts/price_only_breakdown_advance
```
