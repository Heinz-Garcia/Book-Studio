"""Tests for ui_qt.autonomous_window — non-modal plugin windows + size persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QWidget  # noqa: E402 - nach importorskip (ohne PySide6 überspringen)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_prepare_sets_non_modal_and_window_flags():
    _app()
    from ui_qt.autonomous_window import prepare_autonomous_window

    host = QWidget()
    dlg = QDialog(None)
    prepare_autonomous_window(dlg, host)
    assert dlg.isModal() is False
    assert dlg._host is host  # type: ignore[attr-defined]
    assert dlg.parent() is None


def test_show_keeps_strong_ref_and_is_visible():
    _app()
    from ui_qt.autonomous_window import (
        prepare_autonomous_window,
        show_autonomous_window,
    )

    registry: list[QDialog] = []
    dlg = QDialog(None)
    prepare_autonomous_window(dlg, None)
    shown = show_autonomous_window(dlg, registry)
    assert shown is dlg
    assert dlg in registry
    assert dlg.isVisible()
    assert dlg.parent() is None
    dlg.close()
    QApplication.processEvents()


def test_raise_if_open_brings_existing_to_front():
    _app()
    from ui_qt.autonomous_window import (
        prepare_autonomous_window,
        raise_if_open,
        show_autonomous_window,
    )

    registry: list[QDialog] = []
    dlg = QDialog(None)
    prepare_autonomous_window(dlg, None)
    show_autonomous_window(dlg, registry)
    found = raise_if_open(registry, lambda d: True)
    assert found is dlg
    dlg.close()
    QApplication.processEvents()


def test_size_persistence_roundtrip(tmp_path: Path, monkeypatch):
    _app()
    from ui_qt import qt_session
    from ui_qt.autonomous_window import apply_persisted_size, persist_window_size

    monkeypatch.setattr(qt_session, "session_path", lambda root=None: tmp_path / "session_state.json")
    monkeypatch.setattr(qt_session, "repo_root", lambda: tmp_path)

    dlg = QDialog(None)
    apply_persisted_size(
        dlg,
        "test_tool_size",
        default=(640, 480),
        min_size=(320, 240),
        maximized_key="test_tool_maximized",
    )
    assert dlg.size().width() == 640
    assert dlg.size().height() == 480
    assert dlg._loaded_size == (640, 480)  # type: ignore[attr-defined]

    dlg.resize(900, 700)
    persist_window_size(dlg, "test_tool_size", maximized_key="test_tool_maximized")

    dlg2 = QDialog(None)
    apply_persisted_size(
        dlg2,
        "test_tool_size",
        default=(640, 480),
        min_size=(320, 240),
        maximized_key="test_tool_maximized",
    )
    assert dlg2._loaded_size == (900, 700)  # type: ignore[attr-defined]
