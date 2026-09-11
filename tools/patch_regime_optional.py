from pathlib import Path

p = Path('engines/shared/parity_app.py')
s = p.read_text()
s = s.replace('def add_or_gap(label, current_series, central_col, current_source):', 'def add_or_gap(label, current_series, central_col, current_source, role="Production-critical"):\n')
s = s.replace('            "Input": label,\n            "Current source": current_source,', '            "Input": label,\n            "Role": role,\n            "Current source": current_source,')
s = s.replace('        row["Central observations"] = central_obs\n        rows.append(row)', '        row["Role"] = role\n        row["Central observations"] = central_obs\n        rows.append(row)')
s = s.replace('    "BGeometrics regime-score",\n)', '    "BGeometrics regime-score",\n    role="Optional context — not used in Risk Score/DCA sizing",\n)')
s = s.replace('parity[["Input","Current source","Central candidate","Central observations"', 'parity[["Input","Role","Current source","Central candidate","Central observations"')
old = '''measured = int((parity["Status"] == "MEASURED").sum())
present_unvalidated = int(parity["Status"].str.startswith("CENTRAL PRESENT", na=False).sum())
gaps = int(parity["Status"].str.contains("GAP", regex=True, na=False).sum())
st.metric("Inputs with measured central parity", measured)
st.metric("Central inputs present but awaiting live validation", present_unvalidated)
st.metric("True central-source gaps", gaps)

if gaps:
'''
new = '''critical = parity[parity["Role"].eq("Production-critical")].copy()
measured = int((critical["Status"] == "MEASURED").sum())
present_unvalidated = int(critical["Status"].str.startswith("CENTRAL PRESENT", na=False).sum())
gaps = int(critical["Status"].str.contains("GAP", regex=True, na=False).sum())
optional_gaps = int((~parity["Role"].eq("Production-critical") & parity["Status"].str.contains("GAP", regex=True, na=False)).sum())
st.metric("Production-critical inputs with measured central parity", measured)
st.metric("Production-critical inputs present but awaiting live validation", present_unvalidated)
st.metric("True Production-critical central-source gaps", gaps)
if optional_gaps:
    st.caption(f"Optional/context-only source gaps: {optional_gaps}. These do not block Production input centralization because they are not used in the active Risk Score/DCA sizing path.")

if gaps:
'''
if old not in s:
    raise SystemExit('migration block not found')
s = s.replace(old, new, 1)
s = s.replace('"Centralization is not ready for Production yet. Some exact-source inputs are genuinely missing from the central master. "', '"Centralization is not ready for Production yet. Some Production-critical exact-source inputs are genuinely missing from the central master. "')
p.write_text(s)
