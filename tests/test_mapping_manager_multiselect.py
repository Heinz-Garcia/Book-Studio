"""Tests für Mehrfachauswahl im "PDF Manager"-Dialog (MappingManagerQtDialog)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_book_with_renders(tmp_path: Path, count: int = 3) -> Path:
    book = tmp_path / "Band"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")

    export_dir = book / "export" / "publish_renders" / "snap-a"
    export_dir.mkdir(parents=True)

    renders = []
    for i in range(count):
        pdf = export_dir / f"render_{i}.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        renders.append(
            {
                "id": f"r{i}",
                "artifact_path": str(pdf),
                "format": "typst",
                "at": f"2026-08-0{i + 1}T10:00:00",
                "notes": f"Render {i}",
            }
        )

    payload = {
        "active_snapshot_id": "snap-a",
        "snapshots": [
            {
                "id": "snap-a",
                "origin": "local",
                "created_at": "2026-08-01T00:00:00",
                "renders": renders,
            }
        ],
    }
    (cfg / "publish_map.json").write_text(json.dumps(payload), encoding="utf-8")
    return book


def _make_dialog(monkeypatch, tmp_path, count=3):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    book = _make_book_with_renders(tmp_path, count=count)

    class Studio:
        current_book = book

        def log(self, *a, **k):
            pass

    monkeypatch.setattr("ui_qt.book_workspace.discover_books", lambda base=None: [book])
    monkeypatch.setattr("ui_qt.qt_session.is_ephemeral_book_path", lambda _p: False)

    from ui_qt.dialogs.mapping_manager_dialog import MappingManagerQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = MappingManagerQtDialog(None, Studio())
    return app, dlg, book


def _select_all_rows(dlg) -> None:
    dlg.table.selectAll()


def test_selection_mode_is_extended(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QTableWidget

    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path)
    assert dlg.table.selectionMode() == QTableWidget.SelectionMode.ExtendedSelection
    dlg.close()


def test_selected_renders_returns_all_selected_rows(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=3)
    assert dlg.table.rowCount() == 3
    _select_all_rows(dlg)
    renders = dlg._selected_renders()
    assert len(renders) == 3
    dlg.close()


def test_copy_selected_path_joins_multiple_paths(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=3)
    _select_all_rows(dlg)
    dlg._copy_selected_path()
    clipboard_text = QApplication.clipboard().text()
    assert clipboard_text.count("\n") == 2
    assert clipboard_text.count("render_") == 3
    dlg.close()


def test_delete_selected_removes_all_selected(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    _app, dlg, book = _make_dialog(monkeypatch, tmp_path, count=3)
    _select_all_rows(dlg)
    renders_before = dlg._selected_renders()
    pdf_paths = [r.pdf_path for r in renders_before]
    assert all(p.is_file() for p in pdf_paths)

    with patch.object(mod, "QMessageBox") as mock_box:
        mock_box.StandardButton = mod.QMessageBox.StandardButton
        mock_box.question.return_value = mod.QMessageBox.StandardButton.Yes
        dlg._delete_selected()

    assert all(not p.is_file() for p in pdf_paths)
    assert dlg.table.rowCount() == 0
    dlg.close()


def test_edit_display_name_refuses_multi_selection(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=3)
    _select_all_rows(dlg)

    with patch.object(mod, "QMessageBox") as mock_box:
        dlg._edit_display_name()
        mock_box.information.assert_called_once()
        args = mock_box.information.call_args[0]
        assert "genau eine Zeile" in args[2]
    dlg.close()


def test_rename_selected_refuses_multi_selection(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=3)
    _select_all_rows(dlg)

    with patch.object(mod, "QMessageBox") as mock_box:
        dlg._rename_selected()
        mock_box.information.assert_called_once()
        args = mock_box.information.call_args[0]
        assert "genau eine Zeile" in args[2]
    dlg.close()


def test_reveal_selected_refuses_multi_selection(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=3)
    _select_all_rows(dlg)

    with patch.object(mod, "QMessageBox") as mock_box:
        dlg._reveal_selected()
        mock_box.information.assert_called_once()
        args = mock_box.information.call_args[0]
        assert "genau eine Zeile" in args[2]
    dlg.close()


def test_open_selected_opens_all_existing(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=3)
    _select_all_rows(dlg)

    opened = []
    with patch.object(mod, "open_path", side_effect=lambda p: opened.append(p)):
        dlg._open_selected()
    assert len(opened) == 3
    dlg.close()


def test_selection_summary_label_for_multiple_rows(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=3)
    _select_all_rows(dlg)
    assert "3 PDFs ausgewählt" in dlg.path_label.text()
    dlg.close()


def test_sorting_is_enabled(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path)
    assert dlg.table.isSortingEnabled() is True
    dlg.close()


def test_selection_stays_correct_after_sorting(monkeypatch, tmp_path):
    """Kernstueck: nach dem Sortieren per Spaltenkopf muss die Auswahl
    weiterhin auf den tatsaechlich sichtbar markierten Datensatz zeigen,
    nicht auf den urspruenglich an dieser Zeilennummer erzeugten."""
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt as _Qt

    from ui_qt.dialogs.mapping_manager_dialog import _COL_FILE

    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=3)

    # Reihenfolge vor dem Sortieren merken (neueste zuerst -> render_2, 1, 0).
    ids_before = [dlg.table.item(r, _COL_FILE).data(_Qt.ItemDataRole.UserRole) for r in range(3)]
    assert ids_before == ["r2", "r1", "r0"]

    # Nach Dateiname aufsteigend sortieren -> render_0, render_1, render_2.
    dlg.table.sortItems(_COL_FILE, _Qt.SortOrder.AscendingOrder)
    ids_after = [dlg.table.item(r, _COL_FILE).data(_Qt.ItemDataRole.UserRole) for r in range(3)]
    assert ids_after == ["r0", "r1", "r2"]

    # Erste sichtbare Zeile nach dem Sortieren markieren -> muss "r0" sein,
    # nicht mehr "r2" (das waere die alte, jetzt falsche Positions-Annahme).
    dlg.table.selectRow(0)
    selected = dlg._selected_renders()
    assert len(selected) == 1
    assert selected[0].id == "r0"
    dlg.close()


# --- "open production folder": Sprung zum GrammarGraph-Export-Ordner ----


def _make_book_with_provenance_import_path(tmp_path: Path, import_path: str) -> Path:
    book = tmp_path / "Band"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    payload = {
        "active_snapshot_id": "snap-a",
        "snapshots": [
            {
                "id": "snap-a",
                "origin": "grammargraph_import",
                "created_at": "2026-07-27T20:54:26+00:00",
                "provenance": {"import_path": import_path},
                "renders": [],
            }
        ],
    }
    (cfg / "publish_map.json").write_text(json.dumps(payload), encoding="utf-8")
    return book


def test_open_production_folder_shows_info_without_provenance(monkeypatch, tmp_path):
    """Rein lokale Produktionslinien ohne GrammarGraph-Import haben keinen
    Export-Ordner -- muss klar kommuniziert werden, nicht crashen."""
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=1)

    with patch.object(mod, "QMessageBox") as mock_box:
        dlg._open_production_folder()
        mock_box.information.assert_called_once()
        args = mock_box.information.call_args[0]
        assert "kein GrammarGraph-Quellordner" in args[2]


def _mock_missing_folder_box(mock_box_cls, *, clicked="ok"):
    """Richtet den QMessageBox-Mock fuer den 'Ordner nicht gefunden'-Dialog
    ein (eigene QMessageBox-Instanz mit OK + 'copy folder to clipboard'-
    Button, siehe `_open_production_folder`). `clicked` waehlt, welcher der
    beiden Buttons als geklickt simuliert wird."""
    instance = mock_box_cls.return_value
    ok_btn = object()
    copy_btn = object()
    instance.addButton.side_effect = [ok_btn, copy_btn]
    instance.clickedButton.return_value = copy_btn if clicked == "copy" else ok_btn
    return instance, ok_btn, copy_btn


def test_open_production_folder_shows_info_when_folder_missing(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    missing = str(tmp_path / "GrammarGraph" / "Publish" / "Publish_Demo_gone")
    book = _make_book_with_provenance_import_path(tmp_path, missing)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)

    with patch.object(mod, "QMessageBox") as mock_box_cls:
        instance, _ok_btn, _copy_btn = _mock_missing_folder_box(mock_box_cls, clicked="ok")
        dlg._open_production_folder()
        instance.setText.assert_called_once_with(f"Ordner nicht gefunden:\n{Path(missing)}")
        instance.exec.assert_called_once()


def test_open_production_folder_copy_to_clipboard_button(monkeypatch, tmp_path):
    """Der zusaetzliche 'copy folder to clipboard'-Button im
    'Ordner nicht gefunden'-Dialog kopiert den Pfad -- gedacht fuer den
    Fall, dass der GrammarGraph-Export weg ist, aber per Backup an anderer
    Stelle wiedergefunden werden soll."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import mapping_manager_dialog as mod

    missing = str(tmp_path / "GrammarGraph" / "Publish" / "Publish_Demo_gone")
    book = _make_book_with_provenance_import_path(tmp_path, missing)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)

    with patch.object(mod, "QMessageBox") as mock_box_cls:
        _mock_missing_folder_box(mock_box_cls, clicked="copy")
        dlg._open_production_folder()

    assert QApplication.clipboard().text() == str(Path(missing))


def test_open_production_folder_reveals_existing_folder(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    gg_export = tmp_path / "GrammarGraph" / "Publish" / "Publish_Demo_27.07.2026_22.53"
    gg_export.mkdir(parents=True)
    book = _make_book_with_provenance_import_path(tmp_path, str(gg_export))
    _app, dlg = _make_dialog_for_book(monkeypatch, book)

    revealed = []
    with patch.object(mod, "reveal_in_explorer", side_effect=lambda p: revealed.append(p)):
        dlg._open_production_folder()
    assert revealed == [gg_export]


# --- Archivierte Quelle: ansehen (read-only) / wiederherstellen (destruktiv) -


def _make_book_with_source_archive(tmp_path: Path) -> Path:
    """Ein Buch mit genau einem Render, dessen Quelle archiviert wurde."""
    book = tmp_path / "Band"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    (book / "content").mkdir()
    (book / "content" / "01.md").write_text("aktueller Stand", encoding="utf-8")
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")

    export_dir = book / "export" / "publish_renders" / "snap-a"
    pdf = export_dir / "render_0.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4 fake")

    source_dir = export_dir / "source_20260802_000329"
    (source_dir / "content").mkdir(parents=True)
    (source_dir / "content" / "01.md").write_text("archivierter Stand", encoding="utf-8")

    payload = {
        "active_snapshot_id": "snap-a",
        "snapshots": [
            {
                "id": "snap-a",
                "origin": "local",
                "created_at": "2026-08-01T00:00:00",
                "renders": [
                    {
                        "id": "r0",
                        "artifact_path": str(pdf),
                        "source_archive_path": str(source_dir),
                        "format": "typst",
                        "at": "2026-08-02T00:03:29",
                        "notes": "",
                    }
                ],
            }
        ],
    }
    (cfg / "publish_map.json").write_text(json.dumps(payload), encoding="utf-8")
    return book


def _make_dialog_for_book(monkeypatch, book):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    class Studio:
        current_book = book

        def log(self, *a, **k):
            pass

    monkeypatch.setattr("ui_qt.book_workspace.discover_books", lambda base=None: [book])
    monkeypatch.setattr("ui_qt.qt_session.is_ephemeral_book_path", lambda _p: False)

    from ui_qt.dialogs.mapping_manager_dialog import MappingManagerQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = MappingManagerQtDialog(None, Studio())
    return app, dlg


def test_source_column_shows_green_dot_when_available(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_source_archive(tmp_path)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)

    item = dlg.table.item(0, mod._COL_SOURCE)
    assert item.text() == "●"
    assert item.foreground().color().name() == mod._SOURCE_DOT_AVAILABLE
    dlg.close()


def test_source_column_shows_red_dot_when_missing(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_renders(tmp_path, count=1)  # kein source_archive_path
    _app, dlg = _make_dialog_for_book(monkeypatch, book)

    item = dlg.table.item(0, mod._COL_SOURCE)
    assert item.text() == "●"
    assert item.foreground().color().name() == mod._SOURCE_DOT_MISSING
    dlg.close()


def test_delete_selected_asks_about_source_and_keeps_it_when_declined(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_source_archive(tmp_path)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)
    dlg.table.selectRow(0)
    render = dlg._selected_render()
    pdf_path = render.pdf_path
    source_path = render.source_archive_path
    assert pdf_path.is_file()
    assert source_path.is_dir()

    with patch.object(mod, "QMessageBox") as mock_box:
        mock_box.StandardButton = mod.QMessageBox.StandardButton
        mock_box.question.side_effect = [
            mod.QMessageBox.StandardButton.Yes,  # PDF löschen? -> Ja
            mod.QMessageBox.StandardButton.No,  # Quelle mitlöschen? -> Nein
        ]
        dlg._delete_selected()
        assert mock_box.question.call_count == 2

    assert not pdf_path.is_file()
    assert source_path.is_dir()  # Quelle bleibt erhalten (Default: sicher)
    assert dlg.table.rowCount() == 0
    dlg.close()


def test_delete_selected_deletes_source_when_confirmed(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_source_archive(tmp_path)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)
    dlg.table.selectRow(0)
    render = dlg._selected_render()
    pdf_path = render.pdf_path
    source_path = render.source_archive_path

    with patch.object(mod, "QMessageBox") as mock_box:
        mock_box.StandardButton = mod.QMessageBox.StandardButton
        mock_box.question.return_value = mod.QMessageBox.StandardButton.Yes
        dlg._delete_selected()
        assert mock_box.question.call_count == 2

    assert not pdf_path.is_file()
    assert not source_path.exists()
    dlg.close()


def test_delete_selected_skips_source_prompt_when_no_source_archived(monkeypatch, tmp_path):
    """Renders ohne archivierten Quellstand (z. B. von vor Einführung des
    Felds) dürfen keine zusätzliche Frage auslösen."""
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    _app, dlg, _book = _make_dialog(monkeypatch, tmp_path, count=1)
    _select_all_rows(dlg)

    with patch.object(mod, "QMessageBox") as mock_box:
        mock_box.StandardButton = mod.QMessageBox.StandardButton
        mock_box.question.return_value = mod.QMessageBox.StandardButton.Yes
        dlg._delete_selected()
        assert mock_box.question.call_count == 1
    dlg.close()


def test_delete_selected_cancelled_does_not_ask_about_source(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_source_archive(tmp_path)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)
    dlg.table.selectRow(0)
    render = dlg._selected_render()
    pdf_path = render.pdf_path
    source_path = render.source_archive_path

    with patch.object(mod, "QMessageBox") as mock_box:
        mock_box.StandardButton = mod.QMessageBox.StandardButton
        mock_box.question.return_value = mod.QMessageBox.StandardButton.No
        dlg._delete_selected()
        assert mock_box.question.call_count == 1

    assert pdf_path.is_file()
    assert source_path.is_dir()
    dlg.close()


def test_reveal_source_shows_info_when_no_row_selected(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_source_archive(tmp_path)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)

    with patch.object(mod, "QMessageBox") as mock_box:
        dlg._reveal_source_selected()
        mock_box.information.assert_called_once()
    dlg.close()


def test_reveal_source_shows_info_when_no_archive_available(monkeypatch, tmp_path):
    """Renders von vor Einfuehrung dieses Felds haben keinen archivierten
    Quellstand -- muss klar kommuniziert werden, nicht crashen."""
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_renders(tmp_path, count=1)  # kein source_archive_path
    _app, dlg = _make_dialog_for_book(monkeypatch, book)
    dlg.table.selectRow(0)

    with patch.object(mod, "QMessageBox") as mock_box:
        dlg._reveal_source_selected()
        mock_box.information.assert_called_once()
        args = mock_box.information.call_args[0]
        assert "kein archivierter Quellstand" in args[2]
    dlg.close()


def test_reveal_source_opens_archive_directory(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_source_archive(tmp_path)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)
    dlg.table.selectRow(0)

    revealed = []
    with patch.object(mod, "reveal_in_explorer", side_effect=lambda p: revealed.append(p)):
        dlg._reveal_source_selected()
    assert len(revealed) == 1
    assert revealed[0].name == "source_20260802_000329"
    dlg.close()


def test_restore_source_cancelled_leaves_content_untouched(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_source_archive(tmp_path)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)
    dlg.table.selectRow(0)

    with patch.object(mod, "QMessageBox") as mock_box:
        mock_box.StandardButton = mod.QMessageBox.StandardButton
        mock_box.question.return_value = mod.QMessageBox.StandardButton.No
        dlg._restore_source_selected()

    assert (book / "content" / "01.md").read_text(encoding="utf-8") == "aktueller Stand"
    dlg.close()


def test_restore_source_confirmed_without_main_window_still_restores(monkeypatch, tmp_path):
    """Kein Hauptfenster verfuegbar (Dialog ohne Parent, z. B. headless):
    das Wiederherstellen selbst funktioniert trotzdem, es fehlt nur die
    Aktivierung im Hauptfenster -- entsprechend zwei Hinweise statt einem
    (kein Hauptfenster + Ergebnis), Dialog bleibt offen."""
    pytest.importorskip("PySide6")
    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_source_archive(tmp_path)
    _app, dlg = _make_dialog_for_book(monkeypatch, book)
    dlg.table.selectRow(0)

    with patch.object(mod, "QMessageBox") as mock_box:
        mock_box.StandardButton = mod.QMessageBox.StandardButton
        mock_box.question.return_value = mod.QMessageBox.StandardButton.Yes
        dlg._restore_source_selected()
        assert mock_box.information.call_count == 2

    # Wiederhergestellt: der archivierte Stand ist jetzt im lebenden Projekt.
    assert (book / "content" / "01.md").read_text(encoding="utf-8") == "archivierter Stand"
    # Der VORHERIGE Stand ("aktueller Stand") muss automatisch gesichert
    # worden sein -- ein Restore darf nie unwiderruflich sein.
    backups = list((book / "export" / "pre_restore_backups").glob("source_*"))
    assert len(backups) == 1
    assert (backups[0] / "content" / "01.md").read_text(encoding="utf-8") == "aktueller Stand"
    assert dlg.result() != mod.QDialog.DialogCode.Accepted
    dlg.close()


def test_restore_source_confirmed_activates_book_shows_banner_and_closes(monkeypatch, tmp_path):
    """Mit Hauptfenster: Dialog schliesst sich, das Buch wird IN SITU
    aktiviert (Kapitelbaum zeigt den wiederhergestellten Stand) und ein
    Banner im Hauptfenster weist auf den wiederhergestellten Stand hin."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QDialog, QWidget

    from ui_qt.dialogs import mapping_manager_dialog as mod

    book = _make_book_with_source_archive(tmp_path)

    class FakeMainWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.selected: list[Path] = []
            self.banner_text: str | None = None

        def _try_select_book(self, path: Path) -> None:
            self.selected.append(Path(path))

        def show_restored_source_banner(self, text: str) -> None:
            self.banner_text = text

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    class Studio:
        current_book = book

        def log(self, *a, **k):
            pass

    monkeypatch.setattr("ui_qt.book_workspace.discover_books", lambda base=None: [book])
    monkeypatch.setattr("ui_qt.qt_session.is_ephemeral_book_path", lambda _p: False)

    app = QApplication.instance() or QApplication([])
    parent = FakeMainWindow()
    dlg = mod.MappingManagerQtDialog(parent, Studio())
    dlg.table.selectRow(0)
    parent.selected.clear()  # Init-Sync beim Dialogaufbau zaehlt nicht mit

    with patch.object(mod, "QMessageBox") as mock_box:
        mock_box.StandardButton = mod.QMessageBox.StandardButton
        mock_box.question.return_value = mod.QMessageBox.StandardButton.Yes
        dlg._restore_source_selected()
        mock_box.information.assert_not_called()

    assert (book / "content" / "01.md").read_text(encoding="utf-8") == "archivierter Stand"
    assert parent.selected == [book]
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert parent.banner_text is not None
    assert "render_0.pdf" in parent.banner_text
    assert "2026-08-02" in parent.banner_text
    dlg.close()
    _ = app
