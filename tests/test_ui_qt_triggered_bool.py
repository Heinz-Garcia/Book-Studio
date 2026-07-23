"""Regression: QAction.triggered darf Command-Callbacks keinen bool unterschieben."""

from __future__ import annotations

import pytest


def test_bind_action_ignores_triggered_checked():
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QApplication, QWidget

    from ui_qt.menu_builder import _bind_action

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    action = QAction("x", parent)
    seen: list[object] = []

    def cb() -> None:
        seen.append("ok")

    _bind_action(action, cb)
    action.trigger()
    assert seen == ["ok"]
    _ = app


def test_command_host_plugin_resolve_zero_arg():
    pytest.importorskip("PySide6")
    from ui_qt.command_host import CommandHost

    class FakeWin:
        class _F:
            def log(self, *a, **k):
                pass

        _facade = _F()

        def as_export_studio(self):
            return self

    host = CommandHost(FakeWin())  # type: ignore[arg-type]
    called: list[str] = []
    host._run_plugin = lambda name: called.append(name)  # type: ignore[method-assign]
    cb = host.resolve("plugin:mapping_manager")
    assert cb is not None
    cb()
    assert called == ["mapping_manager"]
