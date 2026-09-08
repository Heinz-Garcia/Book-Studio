"""Read-only-Viewer für bookconfig/grammargraph_export.json (Provenance)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.provenance.io import provenance_path, read_provenance
from tools.publish_map.metadata import provenance_summary
from ui_qt.widgets.help_bar import HelpBar

_SUMMARY_ROWS = (
    ("exported_at", "Exportiert"),
    ("grammargraph_version", "GrammarGraph-Version"),
    ("llm_provider", "LLM-Anbieter"),
    ("llm_model", "LLM-Modell"),
    ("market_variant", "Marktvariante"),
    ("variant_system_prompt_path", "Variantensystemprompt"),
    ("import_path", "Export-Verzeichnis"),
    ("source", "Quelle"),
)


class ProvenanceViewerDialog(QDialog):
    """Zeigt Herkunftsnachweis des aktiven Buchs — nur Lesen."""

    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        book_path: Path,
        data: dict[str, Any],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Provenance (Herkunftsnachweis)")
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "provenance")

        path = provenance_path(book_path)
        layout.addWidget(QLabel(f"Buch: {book_path.name}"))
        layout.addWidget(QLabel(f"Datei: {path}"))

        summary = provenance_summary(book_path)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Feld", "Wert"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        rows = [(label, str(summary.get(key) or "—")) for key, label in _SUMMARY_ROWS]
        # Anker-IDs als eine Zeile
        anchors = summary.get("variant_anchor_ids") or []
        if isinstance(anchors, list) and anchors:
            rows.append(("Anker-IDs", ", ".join(str(a) for a in anchors)))
        self.table.setRowCount(len(rows))
        for row, (label, value) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(label))
            self.table.setItem(row, 1, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        layout.addWidget(QLabel("Rohdaten (JSON):"))
        raw = QPlainTextEdit()
        raw.setReadOnly(True)
        raw.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))
        layout.addWidget(raw, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)


def open_provenance_viewer_qt(studio: Any, parent: Optional[QWidget] = None) -> None:
    book = getattr(studio, "current_book", None)
    if not book:
        QMessageBox.warning(parent, "Provenance", "Kein Buchprojekt aktiv.")
        return
    book_path = Path(book)
    data = read_provenance(book_path)
    if data is None:
        QMessageBox.information(
            parent,
            "Provenance",
            "Kein Herkunftsnachweis vorhanden "
            "(bookconfig/grammargraph_export.json).",
        )
        return
    ProvenanceViewerDialog(parent, book_path=book_path, data=data).exec()
