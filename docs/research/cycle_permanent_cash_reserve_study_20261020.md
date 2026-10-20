# BTC Cycle Trading: permanently protected uninvested AUD reserve — 20 October 2026

**RESEARCH ONLY. No live model changes, no actual ETF purchase, no extra ntfy.** Remaining AUD may stay uninvested into 2027 if verified BTC signals are unattractive. Never impose a calendar-driven cash sweep.

## Hypothesis (declared after prior stepwise-reserve failure)

The earlier PR #183 simulated cash floors that were progressively UNLOCKED as BTC fell farther below the prior 200-week moving average. In the most severe further-70% synthetic bear, all floors released and final account drawdown and aftertax AUD losses converged to the high-exposure tiered candidate. This is not an effective permanent tail-risk reserve.

Separate post-results question: does locking **15% or 25% of ORIGINAL hypothetical AUD cash at ALL BTC valuations** prevent extreme cash exhaustion while maintaining an acceptable BTC recovery outcome? All candidate values are predeclared before this audit but historical market scenarios are already heavily studied, hence not independent out-of-sample proof.

## Frozen equal cash BUY-only accounts

Original hypothetical A$400,000 cash, ZERO inherited BTC, never real user portfolio. Six matched policies:

| Policy | Conditional BUY amount | Cash floor, based on original A$400k |
|---|---|---|
| Actual unchanged Cycle 2.5% control | 2.5% remaining cash if prior completed BTC close below prior 200WMA, 7d last-executed cooldown | 0% |
| Original tiered alternative control | 2.5% ordinary; 3.5% if previous close <=90% WMA; 5% if <=80% | 0% |
| Existing 2.5% with permanent 15% reserve | Exactly 2.5% | **15% (A$60k) permanently** |
| Existing 2.5% with permanent 25% reserve | Exactly 2.5% | **25% (A$100k) permanently** |
| Tiered 3.5/5% with permanent 15% reserve | As previous tiered control | **15% permanently** |
| Tiered 3.5/5% with permanent 25% reserve | As previous tiered control | **25% permanently** |

For every order, permitted gross AUD is the smaller of the ordinary conditional percentage of remaining cash and the amount above the absolute original-AUD floor. If no permissible order exceeds the existing minimum ticket, HOLD. **No threshold, date, high-conviction signal or deeper BTC low unlocks either floor**. Funds remain protected even at 70% under 200WMA and can remain cash beyond 2027. This is a model sensitivity, NOT an instruction to withhold exactly 15/25% of your actual financial assets or SMSF portfolio.

Replay exact previous prior-date BTC/USD close, previous 200WMA, prior FX, seven-calendar-day last-executed order cooldown, same A$3 fee and hypothetical FIFO SMSF accumulation-phase tax. Old research `replay_reserves` receives an OPTIONAL explicit policy map but defaults remain exactly the same; every old test still runs. This models BTC USD daily closes (including weekends) and cannot show real ASX:IBIT AUD bid/ask, whole shares, tracking, cash interest, true SMSF tax phase, actual FX spreads or existing investor SELL lots. Simulated permanent floor protects *liquid AUD* but does NOT automatically ensure a maximum account drawdown — market price gap risks still exist for invested BTC.

## Required scenarios and evidence

Same four entries per completed 2017/2021 BTC cycle and right-censored 2025/26 period, with historical source cutoff Oct 5 2026, and original paired synthetic further 50/70% drops, trough day +1060 and eventual 55/105% pre-shock recovery endings. Both stress and recovery are examined against identical starting cash and unchanged 2.5% current model.

Record total hypothetical after-tax AUD terminal account, drawdown, remaining AUD original cash %, BTC units, market exposure %, matched watch dates, executed purchase counts and controls. Explicitly check long-persistent cheap regimes actually make the new floor BIND, not merely green-test a never-binding rule. Tests must prove the original baseline AND prior unreserved tiered challenger are byte-equivalent by account to the previous research engine, cannot future-peek or spend floor, and that no BTC BUY is forced on a date.

Do not interpret mechanically smaller BTC exposure as superior alpha. Relative performance differences in overlapping 2017/2021 historical starts are not independent validated economic improvements; none warrant live promotion absent new prospective data, real ASX order fills and tax/cash-return sensitivity.

## Safeguards

New isolated research module `engines/research/cycle_permanent_cash_reserve_audit.py`, standalone companion unit tests `tests/test_cycle_permanent_cash_reserve_audit.py`, test-only manual/PR GitHub Actions workflow `.github/workflows/research_cycle_permanent_cash_floor.yml`. No scheduled new job, ntfy, broker connections, personal holdings, Production V5.8.2, Research V5.9 or existing immutable BTC/ASX source tapes. Full source numerical CSV/JSON retained on GitHub Actions for examination before any merge.
