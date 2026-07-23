"""Phase-4-Tests: Export-Dialog und Doctor-Bridge (offscreen)."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_ask_export_options_cancel(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.export_dialog import ExportDialog

    app = QApplication.instance() or QApplication([])
    dlg = ExportDialog(None, ["Standard"], initial={"format": "html"})
    assert dlg.format_combo.currentText() == "html"
    dlg.reject()
    assert dlg.result is None
    assert dlg.exec is not None  # callable
    _ = app


def test_export_dialog_confirm(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.export_dialog import ExportDialog

    app = QApplication.instance() or QApplication([])
    dlg = ExportDialog(None, ["Standard", "EXT: typstdoc"])
    dlg.format_combo.setCurrentText("typst")
    dlg.template_combo.setCurrentText("EXT: typstdoc")
    dlg._confirm()
    assert dlg.result is not None
    assert dlg.result["format"] == "typst"
    assert dlg.result["template"] == "EXT: typstdoc"
    assert "layout_profile" in dlg.result
    _ = app


def test_studio_bridge_doctor(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.book_workspace import StructureSession
    from ui_qt.facade import StudioFacade
    from ui_qt.shell import MainWindow
    from ui_qt.studio_bridge import QtStudioBridge
    from ui_qt.theme import apply_theme

    book = tmp_path / "Band_T"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: T\n---\n\nHi\n", encoding="utf-8")
    (book / "content").mkdir()

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    facade = StudioFacade()
    win = MainWindow(facade)
    session = StructureSession(book, log=facade.log)
    session.load()
    win._session = session
    facade.current_book = book
    win.structure.set_session(session)

    bridge = QtStudioBridge(win)
    healthy, analysis = bridge.run_doctor_preflight("Test", emit_success_log=False)
    assert analysis is not None
    assert isinstance(healthy, bool)
    win.close()
