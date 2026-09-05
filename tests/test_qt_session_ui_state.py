"""Tests fuer ``qt_session.update_ui_state``."""

from __future__ import annotations

import json
from pathlib import Path

import ui_qt.qt_session as qt_session


def _write(root: Path, payload: dict) -> Path:
    target = root / "session_state.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_update_ui_state_keeps_the_active_book(tmp_path: Path):
    """Regression: ``save_session`` haette das aktive Buch geloescht."""
    _write(
        tmp_path,
        {
            "active_book_path": "Band_Dummy",
            "active_book_name": "Band_Dummy",
            "ui_state": {"window_geometry": "100x100+0+0"},
        },
    )
    qt_session.update_ui_state({"doclayout_editor_size": [1234, 777]}, root=tmp_path)
    after = json.loads((tmp_path / "session_state.json").read_text(encoding="utf-8"))
    assert after["active_book_path"] == "Band_Dummy"
    assert after["active_book_name"] == "Band_Dummy"


def test_update_ui_state_keeps_other_ui_keys(tmp_path: Path):
    _write(tmp_path, {"ui_state": {"window_geometry": "100x100+0+0"}})
    qt_session.update_ui_state({"doclayout_editor_size": [800, 600]}, root=tmp_path)
    ui = json.loads((tmp_path / "session_state.json").read_text(encoding="utf-8"))["ui_state"]
    assert ui["window_geometry"] == "100x100+0+0"
    assert ui["doclayout_editor_size"] == [800, 600]


def test_update_ui_state_overwrites_its_own_key(tmp_path: Path):
    _write(tmp_path, {"ui_state": {"doclayout_editor_size": [1, 1]}})
    qt_session.update_ui_state({"doclayout_editor_size": [640, 480]}, root=tmp_path)
    ui = json.loads((tmp_path / "session_state.json").read_text(encoding="utf-8"))["ui_state"]
    assert ui["doclayout_editor_size"] == [640, 480]


def test_update_ui_state_creates_ui_state_when_missing(tmp_path: Path):
    _write(tmp_path, {"active_book_path": "Band_Dummy"})
    qt_session.update_ui_state({"doclayout_editor_maximized": True}, root=tmp_path)
    data = json.loads((tmp_path / "session_state.json").read_text(encoding="utf-8"))
    assert data["ui_state"]["doclayout_editor_maximized"] is True
    assert data["active_book_path"] == "Band_Dummy"


def test_update_ui_state_does_nothing_without_updates(tmp_path: Path):
    target = _write(tmp_path, {"active_book_path": "Band_Dummy", "ui_state": {}})
    before = target.read_text(encoding="utf-8")
    qt_session.update_ui_state({}, root=tmp_path)
    assert target.read_text(encoding="utf-8") == before
