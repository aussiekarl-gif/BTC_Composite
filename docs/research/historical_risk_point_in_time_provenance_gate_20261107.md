# Historical risk-score provenance and point-in-time release gate — 2026-11-07

Research-only; no live changes.

## Evidence verified directly from btc-audit-data main

- `data_contract.json` names `btc_audit_backup.csv` as the research master and states that Production must not read it directly.
- `validated/production_input_manifest.json` (2026-09-11) records **PASS_EXACT** historical shadow-engine parity across 5,779 overlapping dates and all six V5.8.2 component outputs; it explicitly labels the candidate **NOT PROMOTED**.
- The candidate's mapped source columns are `src__blockchain_btc_usd`, `src__frankfurter_usd_per_aud`, `src__bgeometrics_mvrv_z`, and `src__bgeometrics_fear_greed`.
- Fresh live MVRV-Z and Fear & Greed parity is still listed as pending, and the manifest prohibits switching Production.

## Distinguish four separate validation questions

1. **Arithmetic parity**: does replaying the captured historical series reproduce V5.8.2 outputs? **YES**, for the documented overlap.
2. **Observation-date fidelity**: does each historical row's date mean the information was known and publishable then? **NOT PROVEN**.
3. **Revision fidelity**: would the provider have supplied the same number at the original historical decision time, rather than a later backfill or revised value? **NOT PROVEN**.
4. **Execution fidelity**: could the resulting signal be acted upon at the modeled next-observation price, accounting for release lag, spread and fees? **NOT PROVEN**.

The research master risk_score is not thereby a historically tradable, independently timestamped Production signal. The reconstructed Power Law series is a separate price-only approximation, not a reconstruction of all six Production components.

## Required independent evidence

For each risk input and source: provider identifier, observation timestamp and timezone, earliest known publication/ingestion timestamp, historical revision policy, gap/backfill policy, snapshot version/hash, and proof that model decisions lag publication. Rebuild weekly historical decisions using only snapshots available before each simulated order. Fail closed on unknown release times rather than assuming same-day availability.

**Release gate:** until those proofs exist, label historical threshold studies `PROVENANCE_UNVERIFIED`, keep #76/#89/#238 draft and research-only, and do not promote a sell threshold or migrate Production data.
