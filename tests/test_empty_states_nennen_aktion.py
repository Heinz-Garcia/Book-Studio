"""Empty States nennen die Policy-Aktion, nie nur den Fehler (B-10, 2026-09-29).

Plan (``.doc/1klick-orchestrierung-beide-apps.md``): „Empty States nennen
immer die **Policy-Aktion**, nie nur ‚Fehler‘.“ Dieser Wächter findet
Meldungstexte, die nur feststellen, dass kein Buch da ist -- etwa
„Kein Buch gewählt.“ -- ohne zu sagen, was als Nächstes zu tun ist.
Geprüft wird der Text von ``QMessageBox.information/warning/critical/question``
(drittes Argument) und von ``setText`` -- nicht Fenstertitel, nicht interne
Exceptions.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_WURZEL = Path(__file__).resolve().parent.parent
_NACKT = re.compile(
    r"^\s*(Kein|Keine)\s+(aktives\s+)?(Buch|Buchprojekt)"
    r"(\s+(gewählt|geladen|aktiv|gefunden))?\s*[.!]?\s*$"
)
_BOX = {"information", "warning", "critical", "question"}


def _meldungstexte(knoten: ast.Call) -> list[ast.AST]:
    func = knoten.func
    if not isinstance(func, ast.Attribute):
        return []
    if func.attr in _BOX and len(knoten.args) >= 3:
        return [knoten.args[2]]
    if func.attr == "setText" and knoten.args:
        return [knoten.args[0]]
    return []


def test_keine_nackte_kein_buch_meldung() -> None:
    funde: list[str] = []
    for datei in sorted((_WURZEL / "ui_qt").rglob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            for text in _meldungstexte(knoten):
                if isinstance(text, ast.Constant) and isinstance(text.value, str) and _NACKT.match(text.value):
                    funde.append(f"{datei.relative_to(_WURZEL)}:{text.lineno}: {text.value!r}")
    assert funde == [], "Empty State ohne nächsten Schritt:\n" + "\n".join(funde)
