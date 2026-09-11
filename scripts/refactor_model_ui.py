#!/usr/bin/env python3
"""One-off safe refactor: separate Production/Research model code from Streamlit UI.

The script is intentionally conservative:
- splits each current app at the existing Streamlit UI marker;
- preserves the model prefix and UI suffix byte-for-byte;
- creates small UI wrappers that expose every model global to the unchanged UI;
- changes the root notifier from AST-parsing app files to importing model modules;
- validates syntax/imports and then removes itself + its temporary workflow.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_MARKER = (
    "# ================================================================\n"
    "# Streamlit UI\n"
    "# ================================================================\n"
)

TARGETS = [
    (
        ROOT / "engines" / "production" / "production_app.py",
        ROOT / "engines" / "production" / "production_model.py",
        "production",
        "production_model",
        "V5.8.2 Production",
    ),
    (
        ROOT / "engines" / "research" / "research_app.py",
        ROOT / "engines" / "research" / "research_model.py",
        "research",
        "research_model",
        "V5.9 Research",
    ),
]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_app(app_path: Path, model_path: Path, package: str, module_name: str, label: str):
    original = app_path.read_text(encoding="utf-8")
    count = original.count(UI_MARKER)
    if count != 1:
        raise RuntimeError(f"{app_path}: expected exactly one UI marker, found {count}")

    model_text, ui_text = original.split(UI_MARKER, 1)
    ui_text = UI_MARKER + ui_text

    # This guards the main behavioral risk of moving the model into its own file:
    # model functions should not depend on the old app.py __file__ value.
    if "__file__" in model_text:
        raise RuntimeError(f"{app_path}: model prefix uses __file__; manual review required")

    # Exact preservation proof for both moved sections.
    if model_text + ui_text != original:
        raise RuntimeError(f"{app_path}: split did not reconstruct original byte-for-byte")

    original_hash = sha256(original)
    model_hash = sha256(model_text)
    ui_hash = sha256(ui_text)

    model_path.write_text(model_text, encoding="utf-8")

    wrapper = f'''#!/usr/bin/env python3\n"""Streamlit UI for {label}. Calculation/data logic lives in {module_name}.py."""\nfrom pathlib import Path as _Path\nimport sys as _sys\n\n_REPO_ROOT = _Path(__file__).resolve().parents[2]\nif str(_REPO_ROOT) not in _sys.path:\n    _sys.path.insert(0, str(_REPO_ROOT))\n\nfrom engines.{package} import {module_name} as _model\n\n# Preserve the historical UI namespace so the unchanged Streamlit UI behaves\n# exactly as before, including helpers whose names begin with an underscore.\nglobals().update({{k: v for k, v in vars(_model).items() if not k.startswith("__")}})\n\n'''
    app_path.write_text(wrapper + ui_text, encoding="utf-8")

    # Ensure no model/UI content was edited while moving it.
    if sha256(model_path.read_text(encoding="utf-8")) != model_hash:
        raise RuntimeError(f"{model_path}: model content changed during write")
    new_app = app_path.read_text(encoding="utf-8")
    moved_ui = new_app[new_app.index(UI_MARKER):]
    if sha256(moved_ui) != ui_hash:
        raise RuntimeError(f"{app_path}: UI content changed during write")

    print(
        f"{label}: original={original_hash[:12]} model={model_hash[:12]} "
        f"ui={ui_hash[:12]} model_chars={len(model_text):,} ui_chars={len(ui_text):,}"
    )


def refactor_notifier():
    path = ROOT / "dca_model_compare_notify.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        "- V5.8.2 Production (engines/production/production_app.py)\n"
        "- V5.9 Research (engines/research/research_app.py)",
        "- V5.8.2 Production (engines/production/production_model.py)\n"
        "- V5.9 Research (engines/research/research_model.py)",
    )
    text = text.replace("import ast\n", "")
    text = text.replace("from pathlib import Path\n", "")

    old_constants = '''ROOT = Path(__file__).resolve().parent\nPROD_APP = ROOT / "engines" / "production" / "production_app.py"\nRESEARCH_APP = ROOT / "engines" / "research" / "research_app.py"\nBRISBANE = ZoneInfo("Australia/Brisbane")\n'''
    new_constants = '''from engines.production import production_model as PROD_MODEL\nfrom engines.research import research_model as RESEARCH_MODEL\n\nBRISBANE = ZoneInfo("Australia/Brisbane")\n'''
    if old_constants not in text:
        raise RuntimeError("Notifier constants block no longer matches expected baseline")
    text = text.replace(old_constants, new_constants)

    pattern = re.compile(
        r"\ndef load_app_engine\(app_file: Path\):.*?\n\ndef fixed_engine_params",
        flags=re.S,
    )
    replacement = '''\ndef load_model_engine(engine_module):\n    """Expose the imported calculation module using the notifier's existing dict API."""\n    return vars(engine_module)\n\n\ndef fixed_engine_params'''
    text, n = pattern.subn(replacement, text, count=1)
    if n != 1:
        raise RuntimeError(f"Notifier AST loader replacement count was {n}, expected 1")

    old_calc = '''def calculate_model_summary(app_file: Path, model: str):\n    e = load_app_engine(app_file)'''
    new_calc = '''def calculate_model_summary(engine_module, model: str):\n    e = load_model_engine(engine_module)'''
    if old_calc not in text:
        raise RuntimeError("Notifier calculate_model_summary baseline did not match")
    text = text.replace(old_calc, new_calc)

    text = text.replace(
        'calculate_model_summary(PROD_APP, "Composite V3.6")',
        'calculate_model_summary(PROD_MODEL, "Composite V3.6")',
    )
    text = text.replace(
        'calculate_model_summary(RESEARCH_APP, "Research WF Power Law")',
        'calculate_model_summary(RESEARCH_MODEL, "Research WF Power Law")',
    )

    if "ast." in text or "load_app_engine" in text or "PROD_APP" in text or "RESEARCH_APP" in text:
        raise RuntimeError("Notifier still contains legacy AST/app-path loading references")

    path.write_text(text, encoding="utf-8")


def update_readme():
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "- `engines/production/production_app.py` — frozen V5.8.2 Production control\n"
        "- `engines/research/research_app.py` — V5.9 Research engine\n",
        "- `engines/production/production_model.py` — frozen V5.8.2 Production calculations/data logic\n"
        "- `engines/production/production_app.py` — Production Streamlit UI\n"
        "- `engines/research/research_model.py` — V5.9 Research calculations/data logic\n"
        "- `engines/research/research_app.py` — Research Streamlit UI\n",
    )
    text = text.replace(
        "- `dca_model_compare_notify.py` — temporary daily Production vs Research ntfy comparison\n",
        "- `dca_model_compare_notify.py` — temporary daily Production vs Research ntfy comparison; imports the model modules directly\n",
    )
    path.write_text(text, encoding="utf-8")


def validate():
    files = [
        ROOT / "engines" / "production" / "production_model.py",
        ROOT / "engines" / "production" / "production_app.py",
        ROOT / "engines" / "research" / "research_model.py",
        ROOT / "engines" / "research" / "research_app.py",
        ROOT / "dca_model_compare_notify.py",
        ROOT / "app.py",
    ]
    subprocess.run([sys.executable, "-m", "py_compile", *map(str, files)], check=True)

    # Import calculation modules without running Streamlit UI.
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from engines.production import production_model as p; "
                "from engines.research import research_model as r; "
                "assert callable(p.add_risk_indicators); "
                "assert callable(r.add_risk_indicators); "
                "assert p.SMART_DCA_POINTS; assert r.SMART_DCA_POINTS; "
                "print('model imports OK')"
            ),
        ],
        cwd=ROOT,
        check=True,
    )

    # Model modules must contain no Streamlit startup/UI boundary.
    for p in files[:4:2]:
        text = p.read_text(encoding="utf-8")
        if "st.set_page_config(" in text:
            raise RuntimeError(f"{p}: Streamlit UI startup leaked into model module")

    print("Validation passed: py_compile + direct model imports + UI boundary checks")


def cleanup_one_off_files():
    for rel in [
        "scripts/refactor_model_ui.py",
        ".github/workflows/refactor-model-ui.yml",
    ]:
        p = ROOT / rel
        if p.exists():
            p.unlink()


def main():
    for args in TARGETS:
        split_app(*args)
    refactor_notifier()
    update_readme()
    validate()
    cleanup_one_off_files()


if __name__ == "__main__":
    main()
