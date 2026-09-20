"""Read-only-Viewer für bookconfig/publish_record.json (Ereignisprotokoll)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.publish_record.record import publish_record_path, read_record
from ui_qt.autonomous_window import (
    apply_persisted_size,
    persist_window_size,
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)
from ui_qt.widgets.help_bar import HelpBar

_EVENT_LABELS = {
    "book_import": "Import",
    "doctor_check": "Buch-Doktor",
    "render_success": "Render",
}

_SIZE_KEY = "publish_record_viewer_size"
_DEFAULT_SIZE = (900, 560)
_MIN_SIZE = (560, 360)
_active: list[PublishRecordViewerDialog] = []


def _payload_summary(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "book_import":
        return str(payload.get("book_name") or payload.get("import_path") or "")
    if event_type == "doctor_check":
        healthy = payload.get("is_healthy")
        status = "gesund" if healthy else "Befunde"
        errs = payload.get("error_count", "?")
        warns = payload.get("warning_count", "?")
        ctx = payload.get("context_label") or ""
        return f"{status} · {errs} Fehler · {warns} Warnungen · {ctx}".strip(" ·")
    if event_type == "render_success":
        fmt = payload.get("format") or payload.get("target_format") or ""
        profile = payload.get("layout_profile") or payload.get("profile_name") or ""
        return " · ".join(p for p in (fmt, profile) if p)
    return ", ".join(f"{k}={v}" for k, v in list(payload.items())[:3])


class PublishRecordViewerDialog(QDialog):
    """Zeigt das Veröffentlichungs-Protokoll — nur Lesen."""

    def __init__(
        self,
        host: Optional[QWidget],
        *,
        book_path: Path,
        record: dict[str, Any],
    ) -> None:
        super().__init__(None)
        self._book_path = Path(book_path)
        self._events = list(record.get("events") or [])
        self.setWindowTitle("Publish Record (Veröffentlichungs-Protokoll)")
        apply_persisted_size(
            self, _SIZE_KEY, default=_DEFAULT_SIZE, min_size=_MIN_SIZE
        )

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "publish_record")

        path = publish_record_path(book_path)
        layout.addWidget(QLabel(f"Buch: {book_path.name}"))
        layout.addWidget(
            QLabel(
                f"Datei: {path} · Schema {record.get('schema_version', '—')} · "
                f"{len(self._events)} Ereignis(se) · "
                f"aktualisiert {record.get('updated_at') or '—'}"
            )
        )

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Zeit", "Typ", "Kurz", "ID"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setRowCount(len(self._events))
        # Neueste zuerst
        display = list(reversed(self._events))
        self._display = display
        for row, event in enumerate(display):
            etype = str(event.get("type") or "")
            label = _EVENT_LABELS.get(etype, etype)
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            vals = [
                str(event.get("at") or ""),
                label,
                _payload_summary(etype, payload)[:120],
                str(event.get("id") or "")[:8],
            ]
            for col, text in enumerate(vals):
                self.table.setItem(row, col, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()
        self.table.itemSelectionChanged.connect(self._show_detail)
        splitter.addWidget(self.table)

        detail_box = QWidget()
        detail_layout = QVBoxLayout(detail_box)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(QLabel("Ereignis-Details (JSON):"))
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        detail_layout.addWidget(self.detail)
        splitter.addWidget(detail_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(buttons, tool_key="publish_record", host=self)
        buttons.addStretch(1)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        if self._display:
            self.table.selectRow(0)
        prepare_autonomous_window(self, host)

    def done(self, result: int) -> None:
        persist_window_size(self, _SIZE_KEY)
        super().done(result)

    def _show_detail(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.detail.clear()
            return
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._display):
            self.detail.clear()
            return
        event = self._display[idx]
        self.detail.setPlainText(json.dumps(event, indent=2, ensure_ascii=False))


def open_publish_record_viewer_qt(studio: Any, parent: Optional[QWidget] = None) -> None:
    book = getattr(studio, "current_book", None)
    if not book:
        from ui_qt.work_path_guidance import warn_need_book

        warn_need_book(parent, title="Publish Record", studio=studio)
        return
    book_path = Path(book)
    existing = raise_if_open(
        _active, lambda d: Path(d._book_path) == book_path
    )
    if existing is not None:
        return
    record = read_record(book_path)
    if record is None:
        QMessageBox.information(
            parent,
            "Publish Record",
            "Noch kein Veröffentlichungs-Protokoll vorhanden "
            "(bookconfig/publish_record.json).",
        )
        return
    dlg = PublishRecordViewerDialog(parent, book_path=book_path, record=record)
    show_autonomous_window(dlg, _active)
