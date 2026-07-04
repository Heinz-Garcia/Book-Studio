"""Tests für Batch B9: Magic-String-Eliminierung & Color-Konsolidierung.

Stellt sicher, dass:
- `services.constants` importierbar ist und die dokumentierten Enums liefert.
- `StatusFg` über `ui_theme.COLORS` aufgelöst wird.
- Hot-Spots in `book_studio.py` und `export_manager.py` keine hartkodierten
  Hex-Farben mehr enthalten (B9-Akzeptanzkriterium).

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


def test_status_fg_resolves_via_ui_theme():
    fg = constants.StatusFg
    # Semantische Aliase müssen Strings zurückliefern, die in `ui_theme.COLORS`
    # registriert sind.
    from ui_theme import COLORS
    for attr in ("SUCCESS", "DANGER", "INFO", "WARNING", "PRIMARY"):
        value = getattr(fg, attr)
        assert isinstance(value, str), f"{attr} ist kein str (Typ: {type(value)})"
        assert value.startswith("#"), f"{attr} returned non-hex value: {value}"
        assert value in COLORS.values(), (
            f"{attr} = {value!r} ist nicht in ui_theme.COLORS registriert"
        )


def test_extra_hex_aliases_registered_in_ui_theme():
    from ui_theme import COLORS
    # Mindestens die Legacy-Werte müssen registriert sein.
    for key in ("success_legacy", "danger_legacy", "info_legacy", "success_alt", "warning_legacy"):
        assert key in COLORS, f"Erwarteter Alias '{key}' fehlt in ui_theme.COLORS"


# --- Magic-String-Reduktion -----------------------------------------------


HEX_RE = re.compile(r'self\.status\.config\([^)]*fg="#[0-9a-fA-F]{6}"')

HOTSPOT_FILES = (
    "book_studio.py",
    "export_manager.py",
)


@pytest.mark.parametrize("filename", HOTSPOT_FILES)
def test_no_hardcoded_hex_in_status_config_hotspots(filename: str):
    """In `self.status.config(...fg="…")`-Aufrufen dürfen keine hartkodierten
    Hex-Farben mehr vorkommen – sie müssen über `_StatusFg.X` aus
    `services.constants` aufgelöst werden. Andere `fg="…"`-Stellen
    (tk.Label, tag_configure) sind in dieser Stufe bewusst ausgenommen."""
    path = Path(__file__).resolve().parent.parent / filename
    src = path.read_text(encoding="utf-8")
    matches = HEX_RE.findall(src)
    assert not matches, (
        f"{filename} enthält noch hartkodierte Hex-Farben in status.config: {matches}"
    )


def test_book_studio_uses_status_fg():
    """Spot-Check: book_studio importiert StatusFg."""
    path = Path(__file__).resolve().parent.parent / "book_studio.py"
    src = path.read_text(encoding="utf-8")
    assert "from services.constants import StatusFg" in src
    # Mindestens ein Anwendungsfall
    assert "_StatusFg." in src


def test_export_manager_uses_status_fg():
    path = Path(__file__).resolve().parent.parent / "export_manager.py"
    src = path.read_text(encoding="utf-8")
    assert "from services.constants import StatusFg" in src
    assert "_StatusFg." in src


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
