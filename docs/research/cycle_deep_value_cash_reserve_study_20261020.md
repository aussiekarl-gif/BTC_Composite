# BTC 200WMA deep-value buying: original-AUD cash reserve sensitivity — 20 October 2026

**Paper research only. User's AUD deployment deadline is flexible into 2027.** Do not spend cash to meet the calendar, edit Streamlit, the live 2.5% BUY, SELL stages, Production V5.8.2, Research V5.9, current ntfy schedule, real ETF lots, or manually entered balances.

## Why study a reserve rather than simply spending more

The previous separate conditional-value research (PR #182) demonstrated that buying larger fractions when the *prior BTC close was 10–20% under the strictly prior 200-week MA* improved retrospective 2021-cycle after-tax AUD terminal values. But some artificially deeper bear outcomes were much worse, with up to 40–50% marked drawdowns and under 10% initial AUD cash remaining. 2017 and recent 2025/26 partial tests did not trigger sufficiently deep conditional sizing, so those samples neither confirm nor refute a benefit. No independent out-of-sample evidence establishes superior BUY size.

This new, distinct predeclared question asks: **Can we retain a deliberate original-AUD cash reserve until Bitcoin reaches progressively deeper discounts, without paying an unacceptable recovery opportunity cost?**

## Fixed paper rules, no live change

All cases start with equal hypothetical **A$400,000 cash and zero existing BTC**, buy only if original unchanged shared Cycle Trading BUY WATCH is true (strict previous close less than previous 200WMA), observe actual seven-calendar-day last-executed-order cooldown and do not force a terminal cash sweep. Fixed AUD cash floors are measured against **original cash**, not current marked portfolio equity; they protect further optionality without implying the bottom is known. Once the floor is reduced by an actual deeper previous close, released funds remain optional. An increasing floor on a later price recovery cannot undo earlier purchases—it only prevents subsequent spending beneath that floor.

| Research cohort | Eligible BUY size of remaining cash | Never spend below original-AUD reserve until price becomes cheaper |
|---|---|---|
| Live-like control | 2.5% | none |
| Previously studied tiered control | 2.5%; 3.5% if previous close ≤90% of previous 200WMA; 5% if ≤80% | none |
| Reserve-25% | Same tiered BUY sizes | 25% while BTC/WMA >0.80, 10% between 0.70 and 0.80, released below 0.70 |
| Reserve-40% | Same tiered BUY sizes | 40% above 0.90; 25% from 0.80–0.90; 10% from 0.70–0.80; zero at/below 0.70 |
| Reserve-50% | Same tiered BUY sizes | 50% above 0.80; 25% from 0.70–0.80; zero at/below 0.70 |

Note: a floor is a limit for further PURCHASES only; we never sell existing BTC to replenish it. It cannot guarantee a 25–50% cash balance after BTC first passes lower reserve-release thresholds.

## Economic comparability

Research code `engines/research/cycle_deep_value_cash_reserve_audit.py`, direct tests `tests/test_cycle_deep_value_cash_reserve_audit.py`. Requires exact numeric parity for BOTH the previous live 2.5% weekly research engine and the previous unreserved tiered BUY size engine. Then compares full account (cash plus BTC), previous-date-only trade decisions, before-execution historical AUD FX, broker fee A$3, illustrative immediate tax escrow FIFO SMSF accumulation phase, terminal hypothetical after CGT value, BTC units, cash retained %, mean BTC exposure %, account max drawdown and all dated simulated purchases.

Original 2017/2021 completed windows and censored 2025/26 window (historic price cutoff Oct 5 2026) use the prior +650/+750/+850/+900 fresh-AUD enrolment starts. Replicate original PR #182 synthetic additional 50/70% bear drop / eventual 55/105% pre-shock terminal recovery families exactly. **Those dates and stress designs have been inspected repeatedly**, so claims of independent statistical proof or expected future outperformance are prohibited.

Big limitations: BTC/USD calendar closes are not ASX:IBIT weekday fills; no independently observed broker bid/ask, real ETF tracking and FX spread, actual fund holdings or SMSF tax phase, cash yield, continuous investment or pension transfer balance. The cap trades BUY only, no legacy BTC and no user real SELLs. Increasing a paper reserve may appear to reduce losses simply by reducing asset exposure; stress tests and matched exposure must be compared jointly.

## Release and decision gate

No live variant may be promoted by a passing code/test audit or by historical after-tax figures alone. Keep a full source hash of scenario code; require future frozen point-in-time BTC/IBIT data and real trade-cost / SMSF capital control sensitivity, multiple genuinely independent market regimes, before considering a live recommendation change. If research can't find a return/downside improvement, preserve the unchanged 2.5% weekly conditional BUY and user flexibility to hold cash into 2027.

One test-only PR/manual GitHub workflow; no extra scheduled job, ntfy, portfolio, broker or data-master writes.
