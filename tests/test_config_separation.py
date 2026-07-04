"""Tests für Batch B5: Config-Trennung.

Stellt sicher, dass:
- `studio_config.json` automatisch nach `app_config.json` + `session_state.json`
  migriert wird.
- `app_config.py` Session-relevante Schlüssel strikt ablehnt.
- `session_state.py` unabhängig von `app_config.py` schreibt.
- `app_config.with_defaults` ergänzt fehlende Defaults.

Referenz: .doc/refactoring-master.md, Batch B5.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app_config
import session_state


# --- Migration --------------------------------------------------------------


def test_migrate_creates_app_config_and_session_state(tmp_path: Path) -> None:
    legacy = tmp_path / "studio_config.json"
    legacy.write_text(json.dumps({
        "content_root_path": ".",
        "log_font_size": 11,
        "default_export_format": "html",
        "window_geometry": "1000x800+10+10",
        "session_state": {
            "active_book_path": "Band_X",
            "active_book_name": "Band_X",
            "current_profile_name": "default",
            "ui_state": {"search_text": "foo"},
        },
    }), encoding="utf-8")

    app_path = tmp_path / "app_config.json"
    session_path = tmp_path / "session_state.json"

    migrated = app_config.migrate_from_legacy_studio_config(legacy, app_path, session_path)
    assert migrated is True

    # App-Config hat Defaults + die migrierten Werte.
    app_data = json.loads(app_path.read_text(encoding="utf-8"))
    assert app_data["content_root_path"] == "."
    assert app_data["log_font_size"] == 11
    assert app_data["default_export_format"] == "html"
    # KEIN Session-Block in app_config.
    assert "session_state" not in app_data
    assert "ui_state" not in app_data

    # Session-Config hat den Session-Block inkl. window_geometry.
    session_data = json.loads(session_path.read_text(encoding="utf-8"))
    assert session_data["active_book_path"] == "Band_X"
    assert session_data["ui_state"]["window_geometry"] == "1000x800+10+10"
    assert session_data["ui_state"]["search_text"] == "foo"

    # Backup wurde angelegt.
    assert (tmp_path / "studio_config.json.bak").exists()
    assert not legacy.exists()


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    legacy = tmp_path / "studio_config.json"
    legacy.write_text(json.dumps({"content_root_path": "."}), encoding="utf-8")
    app_path = tmp_path / "app_config.json"
    session_path = tmp_path / "session_state.json"

    assert app_config.migrate_from_legacy_studio_config(legacy, app_path, session_path) is True
    # Zweiter Aufruf: nichts mehr zu tun, weil Original weg ist.
    assert app_config.migrate_from_legacy_studio_config(legacy, app_path, session_path) is False


def test_migrate_skips_unrelated_file(tmp_path: Path) -> None:
    legacy = tmp_path / "studio_config.json"
    legacy.write_text(json.dumps({"irgendwas": "anderes"}), encoding="utf-8")
    app_path = tmp_path / "app_config.json"
    session_path = tmp_path / "session_state.json"

    # Kein Session-Block, kein App-Default → keine Migration.
    assert app_config.migrate_from_legacy_studio_config(legacy, app_path, session_path) is False
    assert not app_path.exists()
    assert not session_path.exists()
    assert legacy.exists()  # Original bleibt liegen


# --- Trennung ---------------------------------------------------------------


def test_app_config_strips_session_keys(tmp_path: Path) -> None:
    path = tmp_path / "app_config.json"
    app_config.write_config(path, {
        "content_root_path": ".",
        "session_state": {"active_book_path": "X"},
        "ui_state": {"search_text": "foo"},
        "window_geometry": "100x100",
    })
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "session_state" not in data
    assert "ui_state" not in data
    assert "window_geometry" not in data
    assert data["content_root_path"] == "."


def test_app_config_with_defaults_fills_missing(tmp_path: Path) -> None:
    merged = app_config.with_defaults({"log_font_size": 18})
    # gesetzter Wert bleibt
    assert merged["log_font_size"] == 18
    # fehlende Werte kommen aus DEFAULTS
    assert merged["content_root_path"] == "."
    assert merged["default_export_format"] == "typst"
    assert "frontmatter_requirements" in merged


def test_session_state_independent_file(tmp_path: Path) -> None:
    path = tmp_path / "session_state.json"
    session_state.write_session_state(path, {"active_book_name": "B", "ui_state": {}})
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "active_book_name": "B", "ui_state": {},
    }
    # Lese auch zurück.
    assert session_state.read_session_state(path) == {"active_book_name": "B", "ui_state": {}}


def test_app_config_handles_missing_or_invalid(tmp_path: Path) -> None:
    # Fehlend
    assert app_config.read_config(tmp_path / "does_not_exist.json") == {}
    # Korrupt
    p = tmp_path / "broken.json"
    p.write_text("nope{", encoding="utf-8")
    assert app_config.read_config(p) == {}


def test_session_state_handles_missing_or_invalid(tmp_path: Path) -> None:
    assert session_state.read_session_state(tmp_path / "nope.json") == {}
    p = tmp_path / "broken.json"
    p.write_text("[]", encoding="utf-8")  # kein dict
    assert session_state.read_session_state(p) == {}


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
