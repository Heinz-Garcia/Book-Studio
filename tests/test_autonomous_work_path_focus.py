"""Fokus zurück zur Arbeitsweg-Leiste nach autonomen Tools."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QWidget


def test_wire_work_path_refresh_calls_host_hooks() -> None:
    from ui_qt.autonomous_window import wire_work_path_refresh

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    calls: list[str] = []

    def _refresh() -> None:
        calls.append("refresh")

    def _focus() -> None:
        calls.append("focus")

    host._refresh_work_path = _refresh  # type: ignore[attr-defined]
    host.focus_work_path_bar = _focus  # type: ignore[attr-defined]

    dlg = QDialog(None)
    wire_work_path_refresh(dlg, host)
    dlg.finished.emit(0)
    app.processEvents()
    assert calls == ["refresh", "focus"]
    dlg.close()
    host.close()
    app.processEvents()


def test_show_autonomous_window_wires_refresh() -> None:
    from ui_qt.autonomous_window import prepare_autonomous_window, show_autonomous_window

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    seen: list[str] = []

    def _refresh() -> None:
        seen.append("refresh")

    def _focus() -> None:
        seen.append("focus")

    host._refresh_work_path = _refresh  # type: ignore[attr-defined]
    host.focus_work_path_bar = _focus  # type: ignore[attr-defined]

    registry: list[QDialog] = []
    dlg = QDialog(None)
    prepare_autonomous_window(dlg, host)
    show_autonomous_window(dlg, registry)
    assert dlg in registry
    dlg.finished.emit(1)
    app.processEvents()
    assert seen == ["refresh", "focus"]
    dlg.close()
    host.close()
    app.processEvents()


def test_focus_skipped_when_sibling_tool_still_open() -> None:
    """Zwei Tools offen: Schließen von A darf B nicht den Fokus stehlen."""
    from ui_qt.autonomous_window import prepare_autonomous_window, show_autonomous_window

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    seen: list[str] = []

    host._refresh_work_path = lambda: seen.append("refresh")  # type: ignore[attr-defined]
    host.focus_work_path_bar = lambda: seen.append("focus")  # type: ignore[attr-defined]

    registry: list[QDialog] = []
    first = QDialog(None)
    second = QDialog(None)
    prepare_autonomous_window(first, host)
    prepare_autonomous_window(second, host)
    show_autonomous_window(first, registry)
    show_autonomous_window(second, registry)
    first.finished.emit(0)
    app.processEvents()
    assert seen == ["refresh"]
    assert second.isVisible()
    second.close()
    first.close()
    host.close()
    app.processEvents()


def test_stray_dialog_without_host_does_not_block_focus() -> None:
    """Beliebiger nicht-modaler Dialog ohne ``_host`` blockiert Fokus nicht."""
    from ui_qt.autonomous_window import prepare_autonomous_window, show_autonomous_window

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    seen: list[str] = []
    host._refresh_work_path = lambda: seen.append("refresh")  # type: ignore[attr-defined]
    host.focus_work_path_bar = lambda: seen.append("focus")  # type: ignore[attr-defined]

    stray = QDialog(None)
    stray.setModal(False)
    stray.show()

    registry: list[QDialog] = []
    tool = QDialog(None)
    prepare_autonomous_window(tool, host)
    show_autonomous_window(tool, registry)
    tool.finished.emit(0)
    app.processEvents()
    assert seen == ["refresh", "focus"]
    stray.close()
    tool.close()
    host.close()
    app.processEvents()
