"""Phase-1-Tests für den Qt-Migrationspfad (ohne GUI-Event-Loop)."""

from __future__ import annotations

import pytest

from ui_qt.toolkit import resolve_ui_toolkit, wants_qt_ui


@pytest.mark.parametrize(
    ("cli", "env", "expected"),
    [
        (None, None, "qt"),  # Phase 6: Qt ist Default
        ("tk", "qt", "tk"),
        ("qt", None, "qt"),
        (None, "qt", "qt"),
        (None, "PySide6", "qt"),
        (None, "tk", "tk"),
        ("qt", "tk", "qt"),
        ("legacy", None, "tk"),
    ],
)
def test_resolve_ui_toolkit(cli, env, expected, monkeypatch):
    if env is None:
        monkeypatch.delenv("BOOK_STUDIO_UI", raising=False)
    else:
        monkeypatch.setenv("BOOK_STUDIO_UI", env)
    assert resolve_ui_toolkit(cli) == expected


def test_wants_qt_ui(monkeypatch):
    monkeypatch.setenv("BOOK_STUDIO_UI", "tk")
    assert wants_qt_ui() is False
    monkeypatch.delenv("BOOK_STUDIO_UI", raising=False)
    assert wants_qt_ui() is True


def test_studio_facade_log_hook():
    from ui_qt.facade import StudioFacade

    seen: list[tuple[str, str]] = []
    facade = StudioFacade(log_hook=lambda m, lvl: seen.append((m, lvl)))
    facade.log("Hallo", "success")
    assert seen == [("Hallo", "success")]


def test_main_window_constructs_offscreen(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from ui_qt.facade import StudioFacade
    from ui_qt.shell import MainWindow
    from ui_qt.theme import apply_theme

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    apply_theme(app)
    facade = StudioFacade()
    win = MainWindow(facade)
    assert "Qt" in win.windowTitle()
    win.close()
