"""Commit-Sperre: Ohne grüne Test-Suite kein Commit.

Aufgerufen vom pre-commit-Hook (``.pre-commit-config.yaml``, ``language:
system``). Der Hook läuft mit dem Python aus ``PATH`` -- das ist oft nicht das
der Projekt-``.venv``. Dieses Skript sucht deshalb deren Interpreter und
startet die schnelle Suite (``-m "not slow"``) damit, parallel, wenn
``pytest-xdist`` installiert ist (rund 25 s).

Im selben Lauf wird die Abdeckung gemessen (``.coveragerc``) und danach je
Bereich geprüft (``coverage_gate.py``). Ohne ``pytest-cov`` entfällt nur diese
Prüfung. Die ``slow``-Tests (echter Quarto-Render) bleiben beim vollständigen
Lauf (``pytest -q``) -- sie brauchen Quarto.

Überspringen nur bewusst: ``git commit --no-verify``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Mehr Prozesse bringen hier nichts mehr, belasten aber GUI-Tests.
MAX_PROZESSE = 12


def venv_python(root: Path = ROOT) -> str:
    """Der Interpreter der Projekt-``.venv`` (Windows oder POSIX), sonst dieser."""
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python"):
        kandidat = root / rel
        if kandidat.is_file():
            return str(kandidat)
    return sys.executable


def pytest_befehl(python: str, *, parallel: bool, abdeckung: bool = False) -> list[str]:
    befehl = [
        python, "-m", "pytest", "-q", "-m", "not slow",
        "-p", "no:cacheprovider",
    ]
    # Quellen aus .coveragerc; kein Bericht im Terminal (das Gate druckt ihn).
    befehl += ["--cov", "--cov-report="] if abdeckung else ["--no-cov"]
    if parallel:
        befehl += ["-n", str(max(1, min(MAX_PROZESSE, os.cpu_count() or 1)))]
    return befehl


def _hat_modul(python: str, modul: str) -> bool:
    return subprocess.run(
        [python, "-c", f"import {modul}"], capture_output=True, check=False
    ).returncode == 0


def hat_xdist(python: str) -> bool:
    return _hat_modul(python, "xdist")


def main() -> int:
    python = venv_python()
    abdeckung = _hat_modul(python, "pytest_cov")
    befehl = pytest_befehl(python, parallel=hat_xdist(python), abdeckung=abdeckung)
    umgebung = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    print("Test-Sperre:", " ".join(befehl[1:]), flush=True)
    ergebnis = subprocess.run(befehl, cwd=ROOT, env=umgebung, check=False)
    if ergebnis.returncode != 0:
        print(
            "\nTest-Sperre: rot -- Commit abgebrochen. Tests reparieren "
            "(oder bewusst: git commit --no-verify).",
            flush=True,
        )
        return ergebnis.returncode
    if not abdeckung:
        print("Test-Sperre: pytest-cov fehlt -- Abdeckungs-Gate übersprungen.", flush=True)
        return 0
    gate = subprocess.run(
        [python, str(ROOT / "tools" / "dev" / "coverage_gate.py")],
        cwd=ROOT, check=False,
    )
    if gate.returncode != 0:
        print(
            "\nTest-Sperre: Abdeckung unter der Untergrenze -- Commit abgebrochen. "
            "Tests ergänzen (Schwellen in tools/dev/coverage_gate.py nie senken).",
            flush=True,
        )
    return gate.returncode


if __name__ == "__main__":
    raise SystemExit(main())
