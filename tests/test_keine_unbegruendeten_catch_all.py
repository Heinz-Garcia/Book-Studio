"""Schutztest: Jedes ``except Exception`` trägt seine Begründung in der Zeile.

Projektregel (AGENTS.md): kein nacktes ``except:`` und kein ``except
Exception`` ohne Weiterwerfen oder dokumentierten Grund. Am 25.09. standen
13 unbegründete da; mehrere verschluckten Fehler still (z. B. fehlende
Begleit-SVGs im Render). Wer einen neuen braucht, schreibt den Grund als
Kommentar in dieselbe Zeile (``# noqa: BLE001 - …`` oder ``# …``) — oder
fängt die tatsächlich möglichen Ausnahmen.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("services", "ui_qt", "tools", "plugins")
_CATCH_ALL = re.compile(r"^\s*except\s+(Exception|BaseException)\b[^#]*$")
_BARE = re.compile(r"^\s*except\s*:")


def _python_files():
    yield from ROOT.glob("*.py")
    for name in SCAN_DIRS:
        yield from (ROOT / name).rglob("*.py")


def test_catch_all_nur_mit_begruendung():
    befunde = []
    for path in _python_files():
        if "__pycache__" in path.parts:
            continue
        for nr, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _CATCH_ALL.match(line) or _BARE.match(line):
                befunde.append(f"{path.relative_to(ROOT)}:{nr}: {line.strip()}")
    assert not befunde, "Unbegründete Catch-all-Handler:\n" + "\n".join(befunde)
