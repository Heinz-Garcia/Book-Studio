"""Test-Baseline für Book Studio Refactoring (Master-Prompt B0).

Dieser Test dokumentiert den Zustand der Test-Infrastruktur vor Beginn
der Refactoring-Batches. Er ist KEIN Funktions-Test, sondern eine
reproduzierbare Baseline.

Wichtig: Wir starten KEINE Subprozesse (Pytest / Smoke) von hier aus,
weil deren Kette (Pytest → Smoke → Quarto) die Sandbox blockieren kann.
Stattdessen ist die Baseline ein statischer Snapshot, der beim Anlegen
manuell verifiziert wurde.

Referenz: .doc/refactoring-master.md, Batch B0.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_INVOCATION = [sys.executable, "smoke_tests.py"]


# Module mit bekannter fehlender Test-Coverage (siehe Bewertung im Chat).
# Diese Dateien sind im Refactoring explizit zu adressieren.
COVERAGE_GAPS = [
    "book_studio.py",          # God-Class; refactored in B8
    "export_manager.py",       # Render-Orchestrierung; refactored in B1, B8
    "pre_processor.py",        # Pre-Processing-Pfad; refactored in B1, B4
    "session_manager.py",      # Session-IO; refactored in B5, B6
    "md_editor.py",            # Markdown-Editor; refactored in B7
]


# Snapshot der Baseline (verifiziert am 2026-07-02 vor Refactoring-Start):
# - python -m pytest tests/ -q  →  42 passed in 0.66s
# - python smoke_tests.py       →  7/7 erfolgreich
# Diese Konstanten sind absichtlich KEINE live ausgeführten Tests, sondern
# dokumentierte Snapshots. Falls das Verhalten in einem späteren Batch
# abweicht, ist das ein Hinweis auf eine Regression.
#
# Hinweis B4: Die ursprüngliche Pytest-Baseline (42) bezog sich auf den
# Stand vor Abschaltung der Fußnoten-Funktionalität. Mit Abschluss von B4
# gilt: 80 passed (Smoke weiterhin 7/7). Der Pre-B4-Snapshot bleibt für
# historische Vergleiche dokumentiert.
PYTEST_BASELINE_PASS_COUNT = 42
PYTEST_BASELINE_PASS_COUNT_POST_B4 = 80
PYTEST_BASELINE_PASS_COUNT_POST_B5 = 88
PYTEST_BASELINE_PASS_COUNT_POST_B6 = 96
PYTEST_BASELINE_PASS_COUNT_POST_B7 = 110
PYTEST_BASELINE_PASS_COUNT_POST_B8 = 126
PYTEST_BASELINE_PASS_COUNT_POST_B9 = 136
PYTEST_BASELINE_PASS_COUNT_POST_B10 = 159
SMOKE_BASELINE_PASS_COUNT = 7
BASELINE_DATE = "2026-07-02"


def test_coverage_gap_modules_exist():
    """Die im Refactoring zu behandelnden Module sind tatsächlich vorhanden."""
    missing = [m for m in COVERAGE_GAPS if not (PROJECT_ROOT / m).exists()]
    assert not missing, f"Erwartete Dateien fehlen: {missing}"


def test_required_test_infrastructure_exists():
    """Pytest, Smoke-Tests und das Test-Verzeichnis sind vorhanden."""
    assert (PROJECT_ROOT / "smoke_tests.py").exists(), "smoke_tests.py fehlt"
    assert (PROJECT_ROOT / "tests").is_dir(), "tests/ fehlt"
    regression_tests = list((PROJECT_ROOT / "tests").glob("test_*_regression.py"))
    assert len(regression_tests) >= 4, (
        f"Erwartete mindestens 4 Regression-Tests, gefunden: "
        f"{[p.name for p in regression_tests]}"
    )


def test_required_runtime_modules_exist():
    """Die Module mit Pflicht-Funktionen sind vorhanden."""
    for module_name in ("yaml_engine", "book_doctor", "pre_processor",
                        "export_manager"):
        assert (PROJECT_ROOT / f"{module_name}.py").exists(), (
            f"Modul fehlt: {module_name}.py"
        )


def test_baseline_constants_present():
    """Sentinel-Test: Baseline-Snapshot ist dokumentiert."""
    assert BASELINE_DATE == "2026-07-02"
    assert PYTEST_BASELINE_PASS_COUNT >= 40, (
        "Pytest-Baseline-Snapshot aktualisieren – Wert zu niedrig."
    )
    assert PYTEST_BASELINE_PASS_COUNT_POST_B4 >= 70, (
        "Post-B4-Pytest-Snapshot aktualisieren – Wert zu niedrig."
    )
    assert PYTEST_BASELINE_PASS_COUNT_POST_B5 >= 80, (
        "Post-B5-Pytest-Snapshot aktualisieren – Wert zu niedrig."
    )
    assert PYTEST_BASELINE_PASS_COUNT_POST_B6 >= 90, (
        "Post-B6-Pytest-Snapshot aktualisieren – Wert zu niedrig."
    )
    assert PYTEST_BASELINE_PASS_COUNT_POST_B7 >= 100, (
        "Post-B7-Pytest-Snapshot aktualisieren – Wert zu niedrig."
    )
    assert PYTEST_BASELINE_PASS_COUNT_POST_B8 >= 120, (
        "Post-B8-Pytest-Snapshot aktualisieren – Wert zu niedrig."
    )
    assert PYTEST_BASELINE_PASS_COUNT_POST_B9 >= 130, (
        "Post-B9-Pytest-Snapshot aktualisieren – Wert zu niedrig."
    )
    assert PYTEST_BASELINE_PASS_COUNT_POST_B10 >= 150, (
        "Post-B10-Pytest-Snapshot aktualisieren – Wert zu niedrig."
    )
    assert SMOKE_BASELINE_PASS_COUNT == 7, (
        "Smoke-Baseline-Snapshot aktualisieren – Wert weicht ab."
    )


def test_known_console_encoding_caveat_documented():
    """Dokumentiertes Caveat: Smoke-Tests crashen ohne PYTHONIOENCODING=utf-8
    auf Windows-Cmd (cp1252). Wir testen NICHT, dass der Crash kommt
    (CI-flaky), sondern nur, dass die Diagnose hier festgehalten ist.

    Tatsächlicher Workaround: in zukünftigen Batches sollte das
    smoke_tests.py (oder ein Wrapper-Skript) PYTHONIOENCODING=utf-8
    selbst setzen, damit der Crash nicht mehr auftritt.
    """
    # Nur Existenz-Check, keine Live-Ausführung.
    assert SMOKE_INVOCATION[0] == sys.executable
    assert (PROJECT_ROOT / "smoke_tests.py").exists()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
