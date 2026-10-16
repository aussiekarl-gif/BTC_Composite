# Streamlit Current Trading Decision — operating guide

**Research-only • 17 October 2026 • No broker orders, no Production changes**

## Open

Use the existing Streamlit app, left sidebar → Model →
**Cycle Trading — Research** → **Current signals**.

A new **Current trading decision — Research** section displays a
single model state (**BUY**, **HOLD**, or **SELL**), illustrative AUD
amount, number of **whole ASX:IBIT ETF units**, explanation of why,
the market data age and any missing inputs. This is an exploratory
model decision, not personal advice, a broker quote or a trade order.

## Daily use

1. Click **Refresh market feed and My Portfolio**. The system
   crosschecks public BTC/USD against archived dated observations,
   uses fully completed prior daily closes and requires a usable
   historical AUD/USD conversion. It displays **HOLD** and proposes
   A$0 if feeds are stale (over 3 days), mismatched or unavailable.
2. Ensure your actual executed 2026 buys are saved in the existing
   **Research → My Portfolio** page, which is the only writer of
   the shared Google Sheets record. The decision page reads it,
   **never updates it**.
3. Check prefilled **Available AUD cash** from your saved starting
   capital, recorded consideration and brokerage. Adjust only
   downward to the cash actually available in the broker. Enter
   your broker's **current ASX:IBIT AUD unit quote** manually.
   Bitcoin/USD is NOT the ETF price. The displayed ETF units
   are rounded down, with A$3 estimated brokerage.
4. For **BUY**: prior completed BTC/USD close must be below the
   strictly trailing 200-week BTC/USD average. Choose the
   exploratory DCA-in style:
   - `adaptive_recovery`: 2.5% of currently available AUD cash;
   - `adaptive_value`: 3.5% or 10% cash according to discount
     to the 200WMA.
   The actual amount never exceeds saved uninvested capital,
   is subject to a A$100 minimum order constraint, and ignores
   unverified trades. At your broker, independently check its
   bid/ask price and decide whether to submit a limit order.
   If filled, save the *executed* buy in My Portfolio.
5. For **SELL**: the sell-top logic is an unvalidated **Research
   hypothesis**, not a certified prediction. It can activate only
   on one of the explicitly reviewed halving days
   **500,525,532,539,546,553,560** while prior BTC price is
   near its prior 90-day high and >1.25× 200WMA, or on a
   separately labeled *EXPERIMENTAL* late-cycle trend breakdown
   (>1.4× 200WMA, 15% off 90-day high and below falling 50DMA).
   A SELL quantity is suppressed unless you check **I have
   verified my currently held ASX:IBIT units in my broker**, enter
   that actual unsold unit quantity and supply the current
   ETF unit quote. The indicated fraction applies to the
   verified remaining holdings and is **not** a reconstructed
   original-BTC position tranche or a backdated 2025 sale.
6. For **HOLD**, the model either has no eligible trigger or
   has insufficient cash, holdings, source data or confirmed
   price. Read the displayed explanation; do not interpret
   HOLD as proof the future price will remain stable.
7. Check **Already executed a BTC/IBIT transaction for this
   signal today** if applicable to suppress a repeated proposal
   during this session. **This flag is NOT a persistent order
   ledger**. Reloading the app clears it.

## Important 2026 timeline

The most recent confirmed Bitcoin halving was
**20 April 2024**, meaning day 500 was **2 September 2025**.
Your real A$500,000 initial deployment began in **2026**. The
backtested selling opportunity cannot be retrospectively
captured by sales of BTC or IBIT acquired later.

The Streamlit account's historical simulator is separate and
still uses hypothetical A$500,000 invested at a historic halving.
Do not confuse those accounts with your real investment.

## Limits / safeguards

- **My Portfolio is a buy-only register** today; the Research
  page does not write transactions. If you SELL, verify your
  broker's current held units at every review. You cannot
  record/synchronise that sale in the current portfolio model
  reliably yet. The page cannot rule out a repeated order
  beyond the manual session checkbox.
- **No automatic transaction** and no connected broker order
  service. The panel returns only a research suggestion.
- **No reliable CGT estimate on a SELL** without SMSF phase,
  parcel cost basis, holding period, carry-forward capital
  losses and actual trading fees. A real SMSF may face 10%,
  15% or 0% effective tax treatment depending on circumstances.
  Consult accounting records before placing a transaction.
- Market signals use **strict prior completed prices**, not
  price moves within the still-forming current daily candle.
  IBIT buys/sells require real ASX market hours, liquidity
  and spread checks.
- The sell-top research is calibrated on **2017, 2021 and 2025
  after the fact** and is not prospectively validated. The
  late-cycle extra safeguard is even less established.
- **No change** to Production V5.8.2, Research V5.9 DCA
  amounts, authoritative provider master or Google Sheets
  Portfolio. This panel is shown separately on the research tab.

## Validation

GitHub Actions:
`research_cycle_trade_decision.yml`
tests BUY/HOLD/SELL arithmetic, verified whole-ETF units, stale
data, missing portfolio, days already traded, no backdating,
no future-price dependencies, cash limits and rollover guard.
`research_cycle_trading_dashboard.yml` preserves existing
portfolio/200WMA research regression checks.
