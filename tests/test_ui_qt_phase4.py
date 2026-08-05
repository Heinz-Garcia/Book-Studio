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
    dlg = ExportDialog(
        None,
        ["Standard", "EXT: typstdoc"],
        initial={"notes": "  Paperback Probe  ", "pdf_stem": "Publish_Test_rev.01"},
    )
    dlg.format_combo.setCurrentText("typst")
    dlg.template_combo.setCurrentText("EXT: typstdoc")
    dlg._confirm()
    assert dlg.result is not None
    assert dlg.result["format"] == "typst"
    assert dlg.result["template"] == "EXT: typstdoc"
    assert "layout_profile" in dlg.result
    assert dlg.result["notes"] == "Paperback Probe"
    assert dlg.result["pdf_stem"] == "Publish_Test_rev.01"
    _ = app


def test_export_dialog_prefills_from_book_folder(tmp_path, monkeypatch):
    """Ohne project_label: Anzeigename = Ordnername, Dateiname daraus abgeleitet."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.export_dialog import ExportDialog

    book = tmp_path / "IFJN_Brustkrebs"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    # Publish_*.json darf den Dialog-Default nicht mehr steuern.
    (cfg / "Publish_IFJN_Brustkrebs_rev.07.json").write_text("{}", encoding="utf-8")

    app = QApplication.instance() or QApplication([])
    dlg = ExportDialog(None, ["Standard"], book_path=book)
    assert dlg.notes_edit.text() == "IFJN_Brustkrebs"
    assert dlg.pdf_stem_edit.text() == "IFJN_Brustkrebs"
    expected = book / "export" / "_book" / "IFJN_Brustkrebs.pdf"
    assert Path(dlg.path_edit.text()) == expected

    dlg.pdf_stem_edit.setText("Mein_Name")
    assert Path(dlg.path_edit.text()) == book / "export" / "_book" / "Mein_Name.pdf"
    dlg._confirm()
    assert dlg.result["pdf_stem"] == "Mein_Name"
    assert dlg.result["notes"] == "IFJN_Brustkrebs"
    _ = app


def test_export_dialog_prefills_from_project_label(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from tools.book_projects.label import write_display_name
    from ui_qt.dialogs.export_dialog import ExportDialog

    book = tmp_path / "IFJN_Brustkrebs"
    book.mkdir()
    write_display_name(book, "Brustkrebs Probe rev.07")

    app = QApplication.instance() or QApplication([])
    dlg = ExportDialog(None, ["Standard"], book_path=book)
    assert dlg.notes_edit.text() == "Brustkrebs Probe rev.07"
    assert dlg.pdf_stem_edit.text() == "Brustkrebs_Probe_rev.07"
    _ = app


def test_export_dialog_anzeigename_syncs_dateiname(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.export_dialog import ExportDialog

    book = tmp_path / "MeinBuch"
    book.mkdir()

    app = QApplication.instance() or QApplication([])
    dlg = ExportDialog(None, ["Standard"], book_path=book)
    assert dlg._stem_linked is True

    dlg.notes_edit.setText("Neue Probe A:B")
    assert dlg.pdf_stem_edit.text() == "Neue_Probe_A_B"

    dlg.pdf_stem_edit.setText("Custom_Stem")
    assert dlg._stem_linked is False
    dlg.notes_edit.setText("Noch einmal")
    assert dlg.pdf_stem_edit.text() == "Custom_Stem"

    dlg.pdf_stem_edit.setText("Noch_einmal")
    assert dlg._stem_linked is True
    dlg.notes_edit.setText("Wieder synced")
    assert dlg.pdf_stem_edit.text() == "Wieder_synced"
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
