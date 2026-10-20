# Results: permanent 15%/25% BTC cash reserve — 20 October 2026

**NO LIVE STRATEGY CHANGE.** [GitHub Actions run #39380915065](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39380915065) passed **54 offline regression tests** (11 permanent-floor; 13 preceding staged-floor; 12 preceding deep-value; 8 live weekly BUY; 10 existing shared Cycle trade allocation) and completed the full matched historical/extended-bear numerical replay. Its 6-policy, 11 overlapping historical-start and 8 synthetic-stress account data are archived in `btc-permanent-cash-15-25pct-paper-research`: `full_research.json`, `summary.csv`, `historical.csv`, `extended_bear.csv`. Original staged cash-reserve audit also passed independently in [run #39380915046](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39380915046).

## Cash protection works; total economic improvement NOT established

All accounts start the same hypothetical A$400k **fresh AUD cash** with no existing BTC or personal portfolio. A market BUY can occur ONLY with previous BTC completed close below previous exact 200WMA, after last executed trade's 7-day cooldown. Original live-like 2.5% of remaining cash control and optional 3.5%/5% *deep-value only* tiered control. New floors hold back exactly 15% or 25% of original AUD cash forever, never released even in a BTC -70% further stress or beyond 2027. Historical BTC/USD daily close and strictly prior dated AUD FX are paper proxies, not executable ASX:IBIT orders. A$3 brokerage and simplified FIFO SMSF accumulation phase tax; cash yield, ETF tracking, spreads, tax phase, whole ETF units, existing holdings and SELLs are not modelled.

| Sizing hypothesis | Mean historical whole-account aftertax advantage vs current 2.5% across 11 overlapping starts | Worst 8-stress terminal whole-account disadvantage vs current 2.5% | Worst simulated marked drawdown | Lowest original AUD cash remaining |
|---|---:|---:|---:|---:|
| Unchanged live-like 2.5% no reserve | 0% | 0% (control) | -39.16% | 26.14% |
| Tiered larger BUY, no reserve | +2.6354% | -7.4651% | -49.62% | 9.55% |
| Live-like 2.5%, permanent 15% reserve | 0% | 0% | -39.16% | 26.14% |
| Live-like 2.5%, permanent 25% reserve | 0% | 0% | -39.16% | 26.14% |
| Tiered larger BUY, permanent 15% reserve | +2.6354% | -7.6822% | -49.62% | **15.00%** |
| Tiered larger BUY, permanent 25% reserve | +2.6354% | -13.4779% | -48.65% | **25.00%** |

**Note:** These worst values may be achieved on DIFFERENT synthetic paths; do not infer a single corresponding total return/drawdown path. Historical means are 11 heavily overlapping entry windows in 2017/2021/2025-26, not independent cycles. Historical cases with the earlier 2.5%-only control and the tiered candidate **never reached the 15%/25% floor at all**, so their historical relative equity outcomes are EXACTLY the same as their unreserved controls. Therefore this backtest does NOT independently support a permanent reserve in real markets.

Across 8 deliberately artificial extended bear/recovery paths, baseline 2.5% still retained at least 26.1363% of the original cash. Its added 15%/25% floors NEVER triggered; adding them only increases code complexity. A tiered permanent 25% floor improved the **worst observed maximum drawdown** versus tiered unreserved by roughly 0.97 percentage points (-48.65% vs -49.62%), but made the worst terminal total aftertax return versus current live 2.5% markedly worse (-13.48% versus -7.47%). In some more strongly recovering synthetic paths, fewer cheap purchases blunt recovery. A 15% permanent tiered floor protected at least 15% original cash, but did not eliminate the -49.62% worst observed drawdown. These fixed floors cannot guarantee loss limits on BTC positions already acquired.

## Conclusion and future evidence

**Do NOT promote a permanent cash-reserve rule.** The current live 2.5%-of-remaining AUD BUY, 7d cooldown, SELL schedule, Production 5.8.2, Research 5.9 and one daily ntfy are unchanged. User can still choose to hold cash into 2027 if market attractiveness is poor; this personal deployment flexibility remains independent from coded guarantees.

The results suggest **model parsimony**: separate the original 2.5% baseline's natural dry powder from an extra reserve that did not bind, and do not claim more BTC purchased necessarily means an advantage. The next major evidence gap is authentic ASX:IBIT price/capture and portfolio-specific executable cost and tax parity. Prospective real-world evidence is needed before revisiting live trade percentages; do not repeatedly optimise new threshold combinations on already-observed 2017/2021 windows.

No scheduled job added. Research-only code, PR/manual CI and full source matched-account artifacts. NO broker access, real portfolio edits, ntfy send or BTC/ASX archive rewrite.
