"""Dialog: Gliederungspunkt (content_role: outline) anlegen."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from page_outline import suggest_outline_rel_path, write_outline_page


class OutlinePageDialog(QDialog):
    """Titel + Dateipfad + optional in Buchstruktur übernehmen."""

    def __init__(self, parent: Optional[QWidget] = None, *, book_path: Path) -> None:
        super().__init__(parent)
        self._book = Path(book_path)
        self.setWindowTitle("🧭 Gliederungspunkt anlegen")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Erzeugt eine Markdown-Datei mit "
            "<code>content_role: outline</code> (Icon 🧭). "
            "Kein GrammarGraph-Nutzinhalt — nur strukturelle Gliederung."
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("z. B. Teil I — Grundlagen")
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("content/Teil_I.md")
        form.addRow("Titel:", self.title_edit)
        form.addRow("Datei (relativ):", self.path_edit)
        layout.addLayout(form)

        self.add_to_book = QCheckBox("Sofort in die Buchstruktur (rechts) übernehmen")
        self.add_to_book.setChecked(True)
        layout.addWidget(self.add_to_book)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.title_edit.textChanged.connect(self._sync_path_from_title)
        self._path_touched = False
        self.path_edit.textEdited.connect(self._mark_path_touched)

        self.created_rel_path: Optional[str] = None
        self.should_add_to_book = True

    def _mark_path_touched(self, _text: str) -> None:
        self._path_touched = True

    def _sync_path_from_title(self, text: str) -> None:
        if self._path_touched:
            return
        title = text.strip()
        if title:
            self.path_edit.setText(suggest_outline_rel_path(title))
        else:
            self.path_edit.clear()

    def _accept(self) -> None:
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Gliederungspunkt", "Bitte einen Titel eingeben.")
            return
        rel = self.path_edit.text().strip().replace("\\", "/")
        if not rel:
            rel = suggest_outline_rel_path(title)
        if ".." in Path(rel).parts:
            QMessageBox.warning(self, "Gliederungspunkt", "Ungültiger Dateipfad.")
            return
        try:
            self.created_rel_path = write_outline_page(
                self._book, title, rel_path=rel, overwrite=False
            )
        except (OSError, ValueError, FileExistsError) as exc:
            QMessageBox.warning(self, "Gliederungspunkt", str(exc))
            return
        self.should_add_to_book = self.add_to_book.isChecked()
        self.accept()


def open_outline_page_dialog(
    parent: QWidget, book_path: Path
) -> Optional[tuple[str, bool]]:
    """``(rel_path, add_to_book)`` oder ``None`` bei Abbruch."""
    dlg = OutlinePageDialog(parent, book_path=book_path)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    if not dlg.created_rel_path:
        return None
    return dlg.created_rel_path, bool(dlg.should_add_to_book)
