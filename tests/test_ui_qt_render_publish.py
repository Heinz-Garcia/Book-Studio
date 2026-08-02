"""Regression: Render-Shims bleiben installiert; Publish-Hooks existieren."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_install_export_manager_ui_persists(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import export_manager as em
    from ui_qt.dialogs.messagebox_shim import (
        QtMessageBoxShim,
        install_export_manager_ui,
        uninstall_export_manager_ui,
    )

    app = QApplication.instance() or QApplication([])
    install_export_manager_ui(None)
    assert isinstance(em.messagebox, QtMessageBoxShim)
    # Context-Manager darf Shims NICHT entfernen
    from ui_qt.dialogs.messagebox_shim import patch_export_manager_ui

    with patch_export_manager_ui(None):
        assert isinstance(em.messagebox, QtMessageBoxShim)
    assert isinstance(em.messagebox, QtMessageBoxShim)
    uninstall_export_manager_ui()
    _ = app


def test_post_render_dialog_defaults_dismiss(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.post_render_dialog import (
        ACTION_DISMISS,
        ACTION_OPEN_PDF,
        PostRenderDialog,
    )

    app = QApplication.instance() or QApplication([])
    dlg = PostRenderDialog(
        None, artifact_path="C:/out/a.pdf", format_name="typst", notes="Probe"
    )
    assert dlg.choice == ACTION_DISMISS
    dlg._choose_open()
    assert dlg.choice == ACTION_OPEN_PDF
    _ = app


def test_ui_hooks_headless_post_render_opens_pdf():
    import ui_hooks

    assert ui_hooks.ask_post_render_action(artifact_path="x.pdf") == "open_pdf"


def test_ui_hooks_headless_compliance_guard_is_noop():
    import ui_hooks

    # Darf nicht crashen und liefert nichts zurück -- headless-Default.
    assert ui_hooks.run_publisher_compliance_guard(pdf_path="x.pdf", book_path="b") is None


def test_install_export_manager_ui_registers_compliance_guard(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import ui_hooks
    from ui_qt.dialogs.messagebox_shim import (
        install_export_manager_ui,
        uninstall_export_manager_ui,
    )

    app = QApplication.instance() or QApplication([])
    original = ui_hooks.run_publisher_compliance_guard
    install_export_manager_ui(None)
    assert ui_hooks.run_publisher_compliance_guard is not original
    uninstall_export_manager_ui()
    assert ui_hooks.run_publisher_compliance_guard is original
    _ = app


def test_compliance_guard_opens_dialog_only_when_issues_found(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import fitz
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.messagebox_shim import (
        install_export_manager_ui,
        uninstall_export_manager_ui,
    )
    from ui_qt.dialogs.publisher_compliance_dialog import PublisherComplianceQtDialog

    app = QApplication.instance() or QApplication([])
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        'isbn: "978-3-000000-00-0"\nproject:\n  type: book\n', encoding="utf-8"
    )
    # Leere PDF ohne Text -> ISBN-Mismatch-Befund garantiert.
    doc = fitz.open()
    doc.new_page()
    pdf_path = book / "out.pdf"
    doc.save(pdf_path)
    doc.close()

    opened: list[int] = []
    monkeypatch.setattr(PublisherComplianceQtDialog, "exec", lambda self: opened.append(1) or 0)

    install_export_manager_ui(None)
    try:
        import ui_hooks

        ui_hooks.run_publisher_compliance_guard(pdf_path=str(pdf_path), book_path=str(book))
        assert opened == [1], "Bei Befunden muss der Dialog automatisch geöffnet werden."

        opened.clear()
        (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
        ui_hooks.run_publisher_compliance_guard(pdf_path=str(pdf_path), book_path=str(book))
        assert opened == [], "Ohne ISBN-SSOT und ohne sonstige Befunde darf nichts aufgehen."
    finally:
        uninstall_export_manager_ui()
    _ = app


def test_export_manager_compliance_guard_passes_layout_profile(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import export_manager as em
    import ui_hooks

    book = tmp_path / "Band"
    book.mkdir()
    manager = em.ExportManager(SimpleNamespace(current_book=book))
    manager._pending_render_context = {"layout_profile": "taschenbuch-bod"}

    captured = {}
    monkeypatch.setattr(
        ui_hooks,
        "run_publisher_compliance_guard",
        lambda **kwargs: captured.update(kwargs),
    )
    manager._run_publisher_compliance_guard(str(book / "out.pdf"))
    assert captured["book_path"] == str(book)
    assert captured["pdf_path"] == str(book / "out.pdf")
    assert captured["layout_profile_id"] == "taschenbuch-bod"


def test_export_manager_compliance_guard_skips_without_book(monkeypatch):
    from types import SimpleNamespace

    import export_manager as em
    import ui_hooks

    manager = em.ExportManager(SimpleNamespace(current_book=None))
    called = []
    monkeypatch.setattr(
        ui_hooks, "run_publisher_compliance_guard", lambda **kwargs: called.append(kwargs)
    )
    manager._run_publisher_compliance_guard("out.pdf")
    assert called == []


def test_qt_bridge_has_publish_hooks():
    pytest.importorskip("PySide6")
    from ui_qt.studio_bridge import QtStudioBridge

    for name in (
        "_fire_plugin_hooks_after_render",
        "_fire_plugin_hooks_after_book_import",
        "_fire_plugin_hooks_after_doctor_check",
    ):
        assert callable(getattr(QtStudioBridge, name, None)), name


def test_after_render_stores_notes(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from plugins.publish_record import on_after_render
    from tools.publish_map.store import read_map

    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  title: T\n",
        encoding="utf-8",
    )
    studio = SimpleNamespace(current_book=book)
    on_after_render(
        studio,
        format="typst",
        template="Standard",
        layout_profile="taschenbuch-bod",
        artifact_path=str(book / "out.pdf"),
        notes="  Paperback Probe rev.5  ",
    )
    data = read_map(book)
    assert data is not None
    renders = data["snapshots"][0]["renders"]
    assert len(renders) == 1
    assert renders[0]["notes"] == "Paperback Probe rev.5"


def test_mapping_manager_prefers_active_snapshot(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import json

    from PySide6.QtWidgets import QApplication

    book = tmp_path / "Band"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    payload = {
        "active_snapshot_id": "snap-b",
        "snapshots": [
            {
                "id": "snap-a",
                "origin": "local",
                "created_at": "2026-01-01T00:00:00",
                "renders": [],
            },
            {
                "id": "snap-b",
                "origin": "local",
                "created_at": "2026-02-01T00:00:00",
                "renders": [],
            },
        ],
    }
    (cfg / "publish_map.json").write_text(json.dumps(payload), encoding="utf-8")

    class Studio:
        current_book = book

        def log(self, *a, **k):
            pass

    monkeypatch.setattr(
        "ui_qt.book_workspace.discover_books",
        lambda base=None: [book],
    )
    monkeypatch.setattr(
        "ui_qt.qt_session.is_ephemeral_book_path",
        lambda _p: False,
    )

    from ui_qt.dialogs.mapping_manager_dialog import MappingManagerQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = MappingManagerQtDialog(None, Studio())
    assert dlg.snapshot_combo.currentData() == "snap-b"
    assert "★" in dlg.snapshot_combo.currentText()
    assert dlg.windowTitle() == "PDF Manager"
    dlg.close()
    _ = app


def test_open_source_activates_book_in_parent_and_closes_dialog(tmp_path: Path, monkeypatch):
    """"Quelle öffnen": aktiviert das Buchprojekt des markierten Renders IM
    HAUPTFENSTER (kein Kopieren/Extrahieren -- es gibt pro Snapshot keine
    eigene Quell-Kopie, nur das eine lebende Buchprojekt) und schließt den
    PDF-Manager-Dialog, damit direkt weiterbearbeitet werden kann."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import json

    from PySide6.QtWidgets import QApplication, QDialog, QWidget

    book = tmp_path / "Band"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    payload = {
        "active_snapshot_id": "snap-a",
        "snapshots": [
            {
                "id": "snap-a",
                "origin": "local",
                "created_at": "2026-01-01T00:00:00",
                "renders": [
                    {
                        "id": "render-1",
                        "at": "2026-01-01T00:00:00",
                        "artifact_path": str(book / "export" / "out.pdf"),
                        "layout_profile": "standard",
                        "format": "typst",
                    }
                ],
            }
        ],
    }
    (cfg / "publish_map.json").write_text(json.dumps(payload), encoding="utf-8")

    class Studio:
        current_book = book

        def log(self, *a, **k):
            pass

    monkeypatch.setattr("ui_qt.book_workspace.discover_books", lambda base=None: [book])
    monkeypatch.setattr("ui_qt.qt_session.is_ephemeral_book_path", lambda _p: False)

    from ui_qt.dialogs.mapping_manager_dialog import MappingManagerQtDialog

    app = QApplication.instance() or QApplication([])

    class FakeMainWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.selected: list[Path] = []

        def _try_select_book(self, path: Path) -> None:
            self.selected.append(Path(path))

    parent = FakeMainWindow()
    dlg = MappingManagerQtDialog(parent, Studio())
    assert dlg.table.rowCount() == 1
    dlg.table.selectRow(0)

    parent.selected.clear()  # Init-Sync (_fill_book_combo) zaehlt nicht mit
    dlg._open_source_selected()

    assert parent.selected == [book]
    assert dlg.result() == QDialog.DialogCode.Accepted
    _ = app
