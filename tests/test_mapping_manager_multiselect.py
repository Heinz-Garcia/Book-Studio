"""Tests für Mehrfachauswahl im "Fertige PDFs"-Dialog (MappingManagerQtDialog)."""

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
