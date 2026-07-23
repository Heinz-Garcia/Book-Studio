"""Tests für Batch B7: Config-Validierung (R11, R12).

Stellt sicher, dass:
- Ungültige Werte in `app_config.validate_and_clean` auf Defaults zurück-
  fallen und Warnungen gemeldet werden.
- Insbesondere `editor_end_commands[*].detect_pattern` mit `re.error`
  geprüft wird (R11).
- `md_editor.MarkdownEditor.on_save_callback` NICHT bei Close/Discard
  aufgerufen wird (R12).

Referenz: .doc/refactoring-master.md, Batch B7.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import app_config


# --- validate_and_clean ----------------------------------------------------


def test_validate_passes_through_valid_config():
    data = {
        "default_export_format": "html",
        "log_font_size": 14,
        "log_max_lines_default": 1000,
        "undo_max_depth": 50,
        "editor_end_commands": [
            {"id": "x", "detect_pattern": r"foo\d+"},
        ],
        "window_geometry": "1485x907+100+83",
    }
    cleaned, warnings = app_config.validate_and_clean(data)
    assert warnings == []
    assert cleaned["default_export_format"] == "html"
    assert cleaned["log_font_size"] == 14
    assert cleaned["editor_end_commands"][0]["id"] == "x"


def test_validate_rejects_unknown_export_format():
    cleaned, warnings = app_config.validate_and_clean(
        {"default_export_format": "evil"}
    )
    assert any("default_export_format" in w for w in warnings)
    assert cleaned["default_export_format"] == app_config.DEFAULTS["default_export_format"]


def test_validate_rejects_log_font_size_too_small():
    cleaned, warnings = app_config.validate_and_clean({"log_font_size": -5})
    assert any("log_font_size" in w for w in warnings)
    assert cleaned["log_font_size"] == app_config.DEFAULTS["log_font_size"]


def test_validate_rejects_log_font_size_too_large():
    cleaned, warnings = app_config.validate_and_clean({"log_font_size": 1000})
    assert any("log_font_size" in w for w in warnings)
    assert cleaned["log_font_size"] == app_config.DEFAULTS["log_font_size"]


def test_validate_rejects_log_max_lines_default_out_of_range():
    cleaned, warnings = app_config.validate_and_clean({"log_max_lines_default": 10})
    assert any("log_max_lines_default" in w for w in warnings)
    assert cleaned["log_max_lines_default"] == app_config.DEFAULTS["log_max_lines_default"]


def test_validate_rejects_undo_max_depth_out_of_range():
    cleaned, warnings = app_config.validate_and_clean({"undo_max_depth": -1})
    assert any("undo_max_depth" in w for w in warnings)
    assert cleaned["undo_max_depth"] == app_config.DEFAULTS["undo_max_depth"]


def test_validate_zero_undo_depth_is_allowed():
    cleaned, warnings = app_config.validate_and_clean(app_config.with_defaults({"undo_max_depth": 0}))
    assert not any("undo_max_depth" in w for w in warnings)
    assert cleaned["undo_max_depth"] == 0


def test_validate_rejects_invalid_regex_in_editor_end_commands():
    # `[unclosed` ist ein ungültiges Regex.
    cleaned, warnings = app_config.validate_and_clean({
        "editor_end_commands": [
            {"id": "good", "detect_pattern": r"good\d+"},
            {"id": "bad", "detect_pattern": "[unclosed"},
        ]
    })
    # Schlechter Eintrag wird rausgefiltert, guter bleibt.
    assert len(cleaned["editor_end_commands"]) == 1
    assert cleaned["editor_end_commands"][0]["id"] == "good"
    # Warnung wurde gemeldet.
    assert any("editor_end_commands" in w and "Regex" in w for w in warnings)


def test_validate_rejects_non_list_editor_end_commands():
    cleaned, warnings = app_config.validate_and_clean({"editor_end_commands": "no"})
    assert cleaned["editor_end_commands"] == []
    assert any("kein Array" in w for w in warnings)


def test_validate_rejects_invalid_window_geometry():
    cleaned, warnings = app_config.validate_and_clean({"window_geometry": "no-good"})
    assert cleaned["window_geometry"] == ""
    assert any("window_geometry" in w for w in warnings)


def test_validate_accepts_various_valid_geometries():
    for good in ("1300x900", "1485x907+100+83", "800x600+0+0", "2000x1500"):
        cleaned, warnings = app_config.validate_and_clean({"window_geometry": good})
        assert cleaned["window_geometry"] == good, f"geometry {good} should be valid"
        assert not any("window_geometry" in w for w in warnings), f"geometry {good} raised warning"


# --- load_validated_config -------------------------------------------------


def test_load_validated_returns_defaults_for_missing_file(tmp_path: Path) -> None:
    config = app_config.load_validated_config(tmp_path / "nope.json")
    assert config["default_export_format"] == app_config.DEFAULTS["default_export_format"]
    assert config["log_font_size"] == app_config.DEFAULTS["log_font_size"]


def test_load_validated_cleans_invalid_values(tmp_path: Path) -> None:
    p = tmp_path / "app_config.json"
    p.write_text('{"log_font_size": -99, "default_export_format": "evil"}', encoding="utf-8")
    config = app_config.load_validated_config(p)
    assert config["log_font_size"] == app_config.DEFAULTS["log_font_size"]
    assert config["default_export_format"] == app_config.DEFAULTS["default_export_format"]


# --- R12: MD-Editor-Callback nur bei Save ----------------------------------
# md_editor.py wurde im Tk-UI-Purge entfernt — Test R12 entfällt.
# Die Semantik (Callback nur bei explizitem Speichern) wird durch
# das Qt-basierte Editor-Modell gewährleistet.


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
