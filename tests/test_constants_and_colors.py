"""Tests für Batch B9: Magic-String-Eliminierung & Color-Konsolidierung.

Stellt sicher, dass:
- `services.constants` importierbar ist und die dokumentierten Enums liefert.
- `StatusFg` Hex-SSOT in `services.constants` ist (ui_theme wurde entfernt).
- `EXTRA_HEX_ALIASES` die Legacy-Aliase enthält.
- `export_manager.py` keine hartkodierten Hex-Farben in status.config hat.

Referenz: .doc/refactoring-master.md, Batch B9.
"""

from __future__ import annotations

import re
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
    for attr in ("SUCCESS", "DANGER", "INFO", "WARNING", "PRIMARY"):
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


HEX_RE = re.compile(r'self\.status\.config\([^)]*fg="#[0-9a-fA-F]{6}"')


def test_no_hardcoded_hex_in_export_manager_status_config():
    """In export_manager.py dürfen keine hartkodierten Hex-Farben in
    `self.status.config(...)` vorkommen."""
    path = Path(__file__).resolve().parent.parent / "export_manager.py"
    src = path.read_text(encoding="utf-8")
    matches = HEX_RE.findall(src)
    assert not matches, (
        f"export_manager.py enthält noch hartkodierte Hex-Farben in status.config: {matches}"
    )


def test_export_manager_uses_status_fg():
    path = Path(__file__).resolve().parent.parent / "export_manager.py"
    src = path.read_text(encoding="utf-8")
    assert "from services.constants import StatusFg" in src
    assert "_StatusFg." in src


def test_book_studio_is_qt_launcher():
    """book_studio.py ist jetzt ein schlanker Qt-Launcher ohne BookStudio-Klasse."""
    path = Path(__file__).resolve().parent.parent / "book_studio.py"
    src = path.read_text(encoding="utf-8")
    # Qt-Einstieg muss vorhanden sein
    assert "run_qt_app" in src or "ui_qt" in src, (
        "book_studio.py sollte den Qt-Launcher referenzieren"
    )
    # Keine hartkodierten Hex-Farben in status.config mehr möglich (keine BookStudio-Klasse)
    matches = HEX_RE.findall(src)
    assert not matches, (
        f"book_studio.py enthält hartkodierte Hex-Farben in status.config: {matches}"
    )


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
