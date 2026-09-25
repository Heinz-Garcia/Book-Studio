"""Keine Datei der Oberfläche über 1500 Zeilen (Konsolidierungsplan, Paket 7).

Bis 2026-09-25 waren vier Dialoge 2000–6000 Zeilen lang (KDP-Cover,
Stylecloud, Text-Editor, Layout-Editor). Aufgeteilt nach Zuständigkeit in
Mixin-Pakete unter ``ui_qt/dialogs/<dialog>/``; der Einstieg behält Namen und
Importweg. Wer einen Dialog erweitert, legt das Neue in das passende Mixin —
wächst eines über die Grenze, ist es Zeit für eine weitere Aufteilung.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRENZE = 1500


def test_keine_ui_datei_ueber_der_grenze():
    zu_gross = sorted(
        (len(f.read_text(encoding="utf-8").splitlines()), f.relative_to(ROOT).as_posix())
        for f in (ROOT / "ui_qt").rglob("*.py")
        if "__pycache__" not in f.parts
    )
    zu_gross = [(n, f) for n, f in zu_gross if n > GRENZE]
    assert not zu_gross, f"Über {GRENZE} Zeilen: {zu_gross}"
