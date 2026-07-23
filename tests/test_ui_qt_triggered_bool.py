"""Regression: QAction.triggered darf Command-Callbacks keinen bool unterschieben."""

from __future__ import annotations

import pytest


def test_bind_action_ignores_triggered_checked():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtGui import QAction

    from ui_qt.menu_builder import _bind_action

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    action = QAction("x", parent)
    seen: list[object] = []

    def cb() -> None:
        seen.append("ok")

    _bind_action(action, cb)
    action.triggered.emit(True)
    assert seen == ["ok"]
    _ = app


def test_command_host_plugin_resolve_zero_arg():
    pytest.importorskip("PySide6")
    from ui_qt.command_host import CommandHost

    class FakeWin:
        def __init__(self):
            self.calls = []

        class _F:
            def log(self, *a, **k):
                pass

        _facade = _F()

        def as_export_studio(self):
            return self

    w = FakeWin()
    host = CommandHost(w)  # type: ignore[arg-type]
    called: list[str] = []

    def fake_run(name: str) -> None:
        called.append(name)

    host._run_plugin = fake_run  # type: ignore[method-assign]
    cb = host.resolve("plugin:mapping_manager")
    assert cb is not None
    cb()
    assert called == ["mapping_manager"]
