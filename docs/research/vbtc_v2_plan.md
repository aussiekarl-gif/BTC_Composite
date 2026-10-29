# VBTC v2 prospective restart

This is a research-only proposal. Preserve the v1 frozen configuration and missed-week evidence unchanged.

Implement a separate v2 configuration, collector, observation journal and scoreboard. The first eligible observation must be a completed future UTC week after deployment, with verified BTC and issuer VBTC source dates. Reject missing, stale, inconsistent or revised historical observations; never backfill a missed week. Keep all journal writes append-only and scoreboards deterministic.

Before scheduling, require tests for date alignment, no lookahead, duplicates, missing observations, revisions and network errors. Start with manual test-only execution, then obtain explicit approval to activate any new schedule. Never modify live Cycle Trading, Production, Streamlit portfolio, Google Sheets or ntfy as part of this experiment.
