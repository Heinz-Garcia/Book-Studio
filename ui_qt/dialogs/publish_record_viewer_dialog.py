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
from ui_qt.widgets.help_bar import HelpBar

_EVENT_LABELS = {
    "book_import": "Import",
    "doctor_check": "Buch-Doktor",
    "render_success": "Render",
}


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
        parent: Optional[QWidget],
        *,
        book_path: Path,
        record: dict[str, Any],
    ) -> None:
        super().__init__(parent)
        self._events = list(record.get("events") or [])
        self.setWindowTitle("Publish Record (Veröffentlichungs-Protokoll)")
        self.resize(900, 560)

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
        buttons.addStretch(1)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        if self._display:
            self.table.selectRow(0)

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
        QMessageBox.warning(parent, "Publish Record", "Kein Buchprojekt aktiv.")
        return
    book_path = Path(book)
    record = read_record(book_path)
    if record is None:
        QMessageBox.information(
            parent,
            "Publish Record",
            "Noch kein Veröffentlichungs-Protokoll vorhanden "
            "(bookconfig/publish_record.json).",
        )
        return
    PublishRecordViewerDialog(parent, book_path=book_path, record=record).exec()
