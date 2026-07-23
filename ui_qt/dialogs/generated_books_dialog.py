"""Qt-Dialog: generierte Bücher (PDF-Liste)."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.generated_books.discovery import (
    collect_book_paths_from_studio,
    delete_generated_pdf,
    find_generated_pdfs,
    load_settings,
    sort_generated_pdfs,
)
from tools.mapping_manager.actions import open_path, reveal_in_explorer


class GeneratedBooksQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], studio: Any) -> None:
        super().__init__(parent)
        self._studio = studio
        self.setWindowTitle("Generierte Bücher")
        self.resize(860, 480)
        self._entries = []
        self._sort_column = "date"
        self._sort_reverse = True

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Gefundene Render-PDFs"))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Datei", "Buch", "Datum"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        for label, slot in (
            ("Öffnen", self._open),
            ("Explorer", self._reveal),
            ("Löschen", self._delete),
            ("Aktualisieren", self._reload),
            ("Schließen", self.accept),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        layout.addLayout(row)
        self._reload()

    def _reload(self) -> None:
        settings = load_settings()
        books = collect_book_paths_from_studio(
            self._studio, recent_only=bool(settings.get("recent_only", True))
        )
        self._entries = find_generated_pdfs(
            books,
            max_entries=int(settings.get("max_entries", 15)),
        )
        self._entries = sort_generated_pdfs(
            self._entries, self._sort_column, reverse=self._sort_reverse
        )
        self.table.setRowCount(len(self._entries))
        for i, entry in enumerate(self._entries):
            self.table.setItem(i, 0, QTableWidgetItem(entry.path.name))
            self.table.setItem(i, 1, QTableWidgetItem(entry.book_name))
            self.table.setItem(i, 2, QTableWidgetItem(entry.date_str))

    def _selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._entries):
            return self._entries[idx]
        return None

    def _open(self) -> None:
        entry = self._selected()
        if not entry:
            QMessageBox.information(self, "Generierte Bücher", "Bitte eine Zeile wählen.")
            return
        try:
            open_path(entry.path)
        except OSError as exc:
            QMessageBox.critical(self, "Generierte Bücher", str(exc))

    def _reveal(self) -> None:
        entry = self._selected()
        if not entry:
            return
        try:
            reveal_in_explorer(entry.path)
        except OSError as exc:
            QMessageBox.critical(self, "Generierte Bücher", str(exc))

    def _delete(self) -> None:
        entry = self._selected()
        if not entry:
            return
        if (
            QMessageBox.question(self, "Löschen", f"PDF löschen?\n{entry.path}")
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            delete_generated_pdf(entry.path)
            self._reload()
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Generierte Bücher", str(exc))


def open_generated_books_qt(studio: Any, parent: Optional[QWidget] = None) -> int:
    GeneratedBooksQtDialog(parent, studio).exec()
    return 0
