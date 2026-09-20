"""Einstiegsmodus geführt / Werkstatt + Progressive Disclosure."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication


def test_resolve_ui_mode_defaults_to_guided(tmp_path: Path, monkeypatch) -> None:
    from ui_qt import qt_session

    monkeypatch.setattr(qt_session, "session_path", lambda root=None: tmp_path / "session_state.json")
    (tmp_path / "session_state.json").write_text("{}", encoding="utf-8")
    assert qt_session.resolve_ui_mode(tmp_path) == "guided"


def test_set_ui_mode_persists(tmp_path: Path, monkeypatch) -> None:
    from ui_qt import qt_session

    monkeypatch.setattr(qt_session, "session_path", lambda root=None: tmp_path / "session_state.json")
    qt_session.set_ui_mode("workshop", root=tmp_path)
    assert qt_session.resolve_ui_mode(tmp_path) == "workshop"
    qt_session.set_ui_mode("guided", root=tmp_path)
    assert qt_session.resolve_ui_mode(tmp_path) == "guided"


def test_build_menu_bar_guided_collapses_tools() -> None:
    from PySide6.QtWidgets import QMainWindow

    from ui_qt.menu_builder import build_menu_bar

    app = QApplication.instance() or QApplication([])
    host = QMainWindow()
    bar = build_menu_bar(
        host,
        resolve=lambda _n: (lambda: None),
        plugins_dir=Path(__file__).resolve().parent.parent / "plugins",
        ui_mode="guided",
    )
    host.setMenuBar(bar)
    titles = [a.text().replace("&", "") for a in bar.actions()]
    assert "Studio-Wartung" in titles
    assert "Buch-Werkzeuge" in titles
    assert "Werkzeuge" not in titles
    assert "Tools" not in titles
    assert "Plugins" not in titles
    assert "Alle Werkzeuge" not in " ".join(titles)
    host.close()
    app.processEvents()


def test_build_menu_bar_workshop_keeps_tools_plugins() -> None:
    from PySide6.QtWidgets import QMainWindow

    from ui_qt.menu_builder import build_menu_bar

    app = QApplication.instance() or QApplication([])
    host = QMainWindow()
    bar = build_menu_bar(
        host,
        resolve=lambda _n: (lambda: None),
        plugins_dir=Path(__file__).resolve().parent.parent / "plugins",
        ui_mode="workshop",
    )
    host.setMenuBar(bar)
    titles = [a.text().replace("&", "") for a in bar.actions()]
    assert "Tools" in titles
    assert "Plugins" in titles
    assert "Werkzeuge" not in titles
    host.close()
    app.processEvents()
