"""Tests for Cover-UUID picker dialog (table + progress load)."""

from __future__ import annotations

from uuid import uuid4

import pytest


def test_uuid_pick_dialog_uses_sortable_table(monkeypatch) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QTableWidget

    from tools.kdp_cover.uuid_choices import UuidChoice
    from tools.uuid_manager.model import UuidStatus
    from ui_qt.dialogs.kdp_cover_uuid_dialog import CoverUuidPickDialog

    _app = QApplication.instance() or QApplication([])
    uid_a = str(uuid4())
    uid_b = str(uuid4())
    choices = [
        UuidChoice(
            uuid=uid_a,
            title="Zebra Buch",
            market_variant="DE",
            status=UuidStatus.imported_no_render,
            origins=("book_studio",),
            origin_label="Book-Studio-Buch (keine Lieferung gefunden)",
            status_label="importiert",
            content_label="ohne Inhalt/PDF",
        ),
        UuidChoice(
            uuid=uid_b,
            title="Alpha Lieferung",
            market_variant="",
            status=UuidStatus.pdf_uuid_match,
            origins=("grammargraph_delivery",),
            origin_label="GrammarGraph-Lieferung (noch kein Buch)",
            status_label="PDF ok",
            content_label="mit Render-PDF",
        ),
    ]
    dlg = CoverUuidPickDialog(None, choices=choices)
    assert isinstance(dlg.table, QTableWidget)
    assert dlg.table.columnCount() == 10
    assert dlg.table.rowCount() == 2
    headers = [
        dlg.table.horizontalHeaderItem(i).text() for i in range(dlg.table.columnCount())
    ]
    assert headers == [
        "UUID",
        "Titel",
        "Batch/Output",
        "Cover",
        "Herkunft",
        "Inhalt",
        "Status",
        "Markt",
        "Erstellt (Output)",
        "Erstellt (Produktion)",
    ]

    # Cover column shows em dash when no registry link
    cover_item = dlg.table.item(0, 3)
    assert cover_item is not None
    assert cover_item.text() in {"—", "-"}

    dlg.filter_edit.setText("alpha")
    visible = sum(
        1 for r in range(dlg.table.rowCount()) if not dlg.table.isRowHidden(r)
    )
    assert visible == 1
    dlg.close()


def test_uuid_pick_dialog_restores_persisted_size(monkeypatch, tmp_path) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from tools.kdp_cover import settings as settings_mod
    from tools.kdp_cover.settings import save_settings
    from tools.kdp_cover.uuid_choices import UuidChoice
    from tools.uuid_manager.model import UuidStatus
    from ui_qt.dialogs.kdp_cover_uuid_dialog import CoverUuidPickDialog, _COLUMNS

    _app = QApplication.instance() or QApplication([])
    path = tmp_path / "last_session.json"
    col_widths = [80, 220, 180, 140, 160, 100, 90, 60, 120, 120]
    assert len(col_widths) == len(_COLUMNS)
    save_settings(
        {
            "uuid_picker_window_width": 1100,
            "uuid_picker_window_height": 640,
            "uuid_picker_window_maximized": False,
            "uuid_picker_column_widths": col_widths,
        },
        path,
    )
    monkeypatch.setattr(settings_mod, "settings_path", lambda: path)

    dlg = CoverUuidPickDialog(
        None,
        choices=[
            UuidChoice(
                uuid=str(uuid4()),
                title="Demo",
                market_variant="",
                status=UuidStatus.delivery_only,
                origins=("grammargraph_delivery",),
                origin_label="x",
                status_label="y",
                content_label="z",
            )
        ],
    )
    dlg.show()
    _app.processEvents()
    dlg._apply_restored_geometry()
    _app.processEvents()
    assert dlg.width() == 1100
    assert dlg.height() == 640
    assert dlg._current_column_widths() == col_widths
    dlg.resize(1200, 700)
    dlg.table.setColumnWidth(1, 300)
    _app.processEvents()
    dlg._geometry_applied = True
    dlg._suppress_geometry_persist = False
    dlg._persist_geometry()
    loaded = settings_mod.load_settings(path)
    assert loaded["uuid_picker_window_width"] == 1200
    assert loaded["uuid_picker_window_height"] == 700
    assert loaded["uuid_picker_column_widths"][1] == 300
    dlg.close()


def test_pick_cover_uuid_shows_progress_before_dialog(monkeypatch) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDialog

    from tools.kdp_cover.uuid_choices import UuidChoice
    from tools.uuid_manager.model import UuidStatus
    from ui_qt.dialogs import kdp_cover_uuid_dialog as mod

    _app = QApplication.instance() or QApplication([])
    calls: list[str] = []

    def _fake_progress(parent, *, studio=None):
        calls.append("progress")
        return [
            UuidChoice(
                uuid=str(uuid4()),
                title="Demo",
                market_variant="",
                status=UuidStatus.delivery_only,
                origins=("grammargraph_delivery",),
                origin_label="GrammarGraph-Lieferung (noch kein Buch)",
                status_label="nur Lieferung",
                content_label="ohne Inhalt/PDF",
            )
        ]

    class _FakeDlg(mod.CoverUuidPickDialog):
        def exec(self) -> int:  # noqa: A003
            calls.append("dialog")
            assert self.table.rowCount() == 1
            self._result = {
                "uuid": self._choices[0].uuid,
                "cover_label": "",
                "cover_role": "primary",
                "title_hint": "Demo",
                "source_kinds": list(self._choices[0].origins),
                "origin_label": self._choices[0].origin_label,
                "content_label": self._choices[0].content_label,
            }
            return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(mod, "load_uuid_choices_with_progress", _fake_progress)
    monkeypatch.setattr(mod, "CoverUuidPickDialog", _FakeDlg)

    result = mod.pick_cover_uuid(None)
    assert result is not None
    assert calls == ["progress", "dialog"]
