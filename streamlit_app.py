#!/usr/bin/env python3
"""Single-private-app launcher for BTC Dynamic DCA V5.8.2 Production and V5.9 Research."""
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="BTC Dynamic DCA — Production + Research", layout="wide")

version = st.sidebar.selectbox(
    "App version",
    ["V5.8.2 Production", "V5.9 Research"],
    index=0,
    key="combined_app_version_selector",
    help="Production remains the control. Research uses the simplified causal Power Law sizing engine.",
)

if version == "V5.8.2 Production":
    engine_path = Path(__file__).parent / "engines" / "production" / "app.py"
else:
    engine_path = Path(__file__).parent / "engines" / "research" / "app.py"

# Execute only the selected engine. Keeping the engines in separate folders prevents
# accidental cross-imports or shared calculation globals.
engine_globals = {
    "__name__": "__main__",
    "__file__": str(engine_path),
    "__package__": None,
}
code = compile(engine_path.read_text(encoding="utf-8"), str(engine_path), "exec")
exec(code, engine_globals)
