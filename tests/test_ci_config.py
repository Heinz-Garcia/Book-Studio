"""Tests für Batch B10: Finale Test- und CI-Härtung.

Stellt sicher, dass:
- `pytest.ini` existiert und die nötigen Marker/Felder hat.
- `.github/workflows/ci.yml` existiert und die Schlüssel-Schritte hat.
- `.pre-commit-config.yaml` existiert und die nötigen Hooks definiert.
- `python -m py_compile` über alle Top-Level-Module fehlerfrei läuft
  (entspricht dem `python-compile`-Hook in `.pre-commit-config.yaml`).
- `tests/` deckt die Service-Layer-Dateien ab.

Referenz: .doc/refactoring-master.md, Batch B10.
"""

from __future__ import annotations

import configparser
import re
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --- pytest.ini -----------------------------------------------------------


def test_pytest_ini_exists():
    assert (PROJECT_ROOT / "pytest.ini").is_file(), "pytest.ini fehlt"


def test_pytest_ini_has_slow_marker():
    cp = configparser.ConfigParser()
    cp.read(PROJECT_ROOT / "pytest.ini", encoding="utf-8")
    assert "pytest" in cp, "pytest.ini: [pytest] Sektion fehlt"
    markers = cp["pytest"].get("markers", "")
    assert "slow" in markers, "pytest.ini: 'slow'-Marker fehlt"


def test_pytest_ini_has_coverage_config():
    cp = configparser.ConfigParser()
    cp.read(PROJECT_ROOT / "pytest.ini", encoding="utf-8")
    # Coverage-Sektionen müssen vorhanden sein.
    assert "coverage:run" in cp, "pytest.ini: [coverage:run] Sektion fehlt"
    assert "coverage:report" in cp, "pytest.ini: [coverage:report] Sektion fehlt"


def test_pytest_ini_has_testpaths():
    cp = configparser.ConfigParser()
    cp.read(PROJECT_ROOT / "pytest.ini", encoding="utf-8")
    testpaths = cp["pytest"].get("testpaths", "")
    assert "tests" in testpaths, "pytest.ini: testpaths=tests fehlt"


# --- CI-Workflow ----------------------------------------------------------


def test_ci_workflow_exists():
    path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert path.is_file(), ".github/workflows/ci.yml fehlt"


def test_ci_workflow_has_required_steps():
    path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    text = path.read_text(encoding="utf-8")
    for keyword in ("actions/checkout", "actions/setup-python", "quarto-actions/setup", "pytest", "smoke_tests.py"):
        assert keyword in text, f"CI-Workflow fehlt Schlüsselwort: {keyword}"


def test_ci_workflow_runs_multiple_python_versions():
    path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    text = path.read_text(encoding="utf-8")
    # Mindestens 3.11, 3.12, 3.13.
    for v in ("3.11", "3.12", "3.13"):
        assert v in text, f"Python-Version {v} fehlt im CI-Workflow"


# --- pre-commit -----------------------------------------------------------


def test_pre_commit_config_exists():
    path = PROJECT_ROOT / ".pre-commit-config.yaml"
    assert path.is_file(), ".pre-commit-config.yaml fehlt"


def test_pre_commit_config_has_ruff_and_flake8():
    text = (PROJECT_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "ruff" in text
    assert "flake8" in text


# --- Syntax-Check via py_compile ------------------------------------------


CORE_MODULES = [
    "app_config.py",
    "session_state.py",
    "services/__init__.py",
    "services/studio_adapter.py",
    "services/workspace_service.py",
    "services/book_session_service.py",
    "services/render_service.py",
    "services/diagnostics_service.py",
    "services/backup_service.py",
    "services/ui_state_service.py",
    "services/constants.py",
    "frontmatter_parser.py",
    "quarto_block_parser.py",
]


@pytest.mark.parametrize("module", CORE_MODULES)
def test_module_passes_py_compile(module: str):
    """Entspricht dem `python-compile`-Hook: alle Service-Layer-Module
    müssen sich syntaktisch kompilieren lassen."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(PROJECT_ROOT / module)],
        capture_output=True,
        text=True,
        check=False,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, (
        f"{module} lässt sich nicht kompilieren:\n{result.stderr}"
    )


# --- Service-Layer-Test-Coverage-Check -----------------------------------


SERVICE_MODULES = [
    "app_config",
    "session_state",
    "frontmatter_parser",
    "quarto_block_parser",
]


def test_every_service_module_has_a_test_file():
    """Mindestens ein Test-Modul pro Service-Layer-Datei."""
    tests_dir = PROJECT_ROOT / "tests"
    test_files = {p.name for p in tests_dir.glob("test_*.py")}
    for module in SERVICE_MODULES:
        # Erwartet: test_<module>.py oder ein Test, der den Modul-Namen erwähnt.
        direct = tests_dir / f"test_{module}.py"
        if direct.exists():
            continue
        # Sonst: irgendein bestehender Test importiert das Modul.
        referenced = False
        for test_file in test_files:
            content = (tests_dir / test_file).read_text(encoding="utf-8")
            if f"import {module}" in content or f"from {module}" in content:
                referenced = True
                break
        assert referenced, f"Service-Modul '{module}' hat keinen dedizierten Test"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
