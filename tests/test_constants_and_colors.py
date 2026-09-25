"""Tests für Batch B9: Magic-String-Eliminierung & Color-Konsolidierung.

Stellt sicher, dass:
- `services.constants` importierbar ist und die dokumentierten Enums liefert.
- `StatusFg` Hex-SSOT in `services.constants` ist (ui_theme wurde entfernt).
- `EXTRA_HEX_ALIASES` die Legacy-Aliase enthält.
- `export_manager.py` Statusfarben nur aus `StatusFg` setzt (keine Hex-Literale).

Referenz: .doc/refactoring-master.md, Batch B9.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services import constants


# --- Enums -----------------------------------------------------------------


def test_log_level_values():
    assert constants.LogLevel.INFO.value == "info"
    assert constants.LogLevel.SUCCESS.value == "success"
    assert constants.LogLevel.WARNING.value == "warning"
    assert constants.LogLevel.ERROR.value == "error"


def test_marker_state_values():
    assert constants.MarkerState.PDF_PAGEBREAK_END.value == "pdf_pagebreak_end"


def test_filter_value_values():
    assert constants.FilterValue.ALL.value == "Alle"
    assert constants.FilterValue.LEFT.value == "Links"


def test_log_level_is_string_enum():
    assert constants.LogLevel.SUCCESS == "success"  # str-Enum


# --- StatusFg -------------------------------------------------------------


def test_status_fg_hex_values():
    """StatusFg ist jetzt Hex-SSOT direkt in services.constants (kein ui_theme mehr)."""
    fg = constants.StatusFg
    for attr in ("SUCCESS", "DANGER", "DANGER_SOFT", "INFO", "WARNING", "PRIMARY"):
        value = getattr(fg, attr)
        assert isinstance(value, str), f"{attr} ist kein str (Typ: {type(value)})"
        assert value.startswith("#"), f"{attr} returned non-hex value: {value}"
        assert len(value) == 7, f"{attr} = {value!r} ist kein gültiger Hex-Farbwert"


def test_extra_hex_aliases_keys_present():
    """EXTRA_HEX_ALIASES enthält die erwarteten Legacy-Schlüssel."""
    aliases = constants.EXTRA_HEX_ALIASES
    for key in ("success_legacy", "danger_legacy", "info_legacy", "success_alt", "warning_legacy"):
        assert key in aliases, f"Erwarteter Alias '{key}' fehlt in EXTRA_HEX_ALIASES"
    for key, value in aliases.items():
        assert value.startswith("#"), f"Alias '{key}' = {value!r} ist kein Hex-Wert"


# --- Magic-String-Reduktion -----------------------------------------------


def _status_farben_in_export_manager() -> list[ast.expr]:
    path = Path(__file__).resolve().parent.parent / "export_manager.py"
    baum = ast.parse(path.read_text(encoding="utf-8"))
    return [
        n.args[1]
        for n in ast.walk(baum)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "_set_status"
        and len(n.args) >= 2
    ]


def test_export_manager_status_farben_kommen_aus_status_fg():
    """Jede Statusfarbe im Export-Manager kommt aus ``StatusFg`` (Hex-SSOT).

    Bis 2026-09-25 suchte dieser Test per Regex nach dem Tk-Aufruf
    ``self.status.config(fg="#…")`` — den gab es längst nicht mehr, und
    ``_set_status("Export abgebrochen", "#95a5a6")`` rutschte durch.
    """
    farben = _status_farben_in_export_manager()
    assert len(farben) > 10, "Aufrufe von _set_status nicht gefunden — Test prüft nichts"
    literale = [
        f"Zeile {f.lineno}: {f.value!r}"
        for f in farben
        if isinstance(f, ast.Constant) and isinstance(f.value, str)
    ]
    assert not literale, f"Hartkodierte Farben statt StatusFg: {literale}"


def test_book_studio_startet_die_qt_oberflaeche(monkeypatch):
    """``book_studio.main`` ist nur Einstieg: es reicht an ``run_qt_app`` weiter."""
    pytest.importorskip("PySide6")
    import book_studio
    import ui_qt

    aufrufe: list[dict] = []
    monkeypatch.setattr(ui_qt, "run_qt_app", lambda **kw: aufrufe.append(kw) or 0)
    assert book_studio.main([]) == 0
    assert aufrufe == [{"import_path": None, "activate_book": None}]
    assert not hasattr(book_studio, "BookStudio")


def test_book_studio_lehnt_tk_ab(monkeypatch):
    pytest.importorskip("PySide6")
    import book_studio
    import ui_qt

    monkeypatch.setattr(ui_qt, "run_qt_app", lambda **_kw: pytest.fail("Qt trotz --ui tk"))
    assert book_studio.main(["--ui", "tk"]) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
