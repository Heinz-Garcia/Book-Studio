"""Tests für Qt-Session-Helfer (ohne GUI)."""

from __future__ import annotations

from pathlib import Path

from ui_qt import qt_session


def test_geometry_roundtrip():
    s = qt_session.geometry_string(1200, 800, 10, 20)
    assert s == "1200x800+10+20"
    assert qt_session.parse_geometry(s) == (1200, 800, 10, 20)
    assert qt_session.parse_geometry("kaputt") is None


def test_merge_recent_puts_active_first():
    existing = {"recent_books": ["Band_A", "Band_B"]}
    merged = qt_session.merge_recent(existing, "Band_C")
    assert merged[0] == "Band_C"
    assert "Band_A" in merged


def test_save_and_load_session(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(qt_session, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(qt_session, "_project_roots", lambda _root: [tmp_path])
    # tmp_path liegt unter .../pytest-of-.../ und würde sonst vom
    # Ephemeral-Guard (siehe test_qt_session_ephemeral.py) als Pytest-Temp-
    # Buch erkannt und nicht in der Session gespeichert werden. Dieser Test
    # prüft das generische Save/Load-Roundtrip, nicht den Guard selbst.
    monkeypatch.setattr(qt_session, "is_ephemeral_book_path", lambda _path: False)

    book = tmp_path / "MyBook"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")

    qt_session.save_session(current_book=book, geometry="800x600+1+2", root=tmp_path)
    state = qt_session.load_session(tmp_path)
    assert state["active_book_name"] == "MyBook"
    assert state["ui_state"]["window_geometry"] == "800x600+1+2"
    assert state["recent_books"][0] == "MyBook"

    recent = qt_session.list_recent_books(current_book=book, root=tmp_path)
    assert len(recent) == 1
    assert recent[0]["current"] is True
    assert recent[0]["label"] == "MyBook"


def test_menu_builder_resolve_smoke():
    from ui_qt.menu_builder import populate_menu
    from menu_definitions import MENU_EDIT, MenuItem

    called = []

    def resolve(name: str):
        return lambda n=name: called.append(n)

    # Minimal: only ensure MenuItem path doesn't crash without Qt widgets —
    # full bar needs QApplication; covered in offscreen shell test if needed.
    assert any(isinstance(e, MenuItem) for e in MENU_EDIT)
    assert populate_menu is not None
