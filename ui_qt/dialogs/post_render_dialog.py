"""Nach erfolgreichem Render: PDF öffnen, Fertige PDFs zeigen, oder schließen."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Rückgabewerte für ui_hooks.ask_post_render_action
ACTION_OPEN_PDF = "open_pdf"
ACTION_SHOW_PDFS = "show_pdfs"
ACTION_DISMISS = "dismiss"


class PostRenderDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        artifact_path: str,
        format_name: str = "",
        notes: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Render erfolgreich")
        self.setModal(True)
        self.resize(480, 200)
        self.choice = ACTION_DISMISS

        layout = QVBoxLayout(self)
        fmt = (format_name or "Ausgabe").upper()
        title = QLabel(f"{fmt} ist fertig.")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(title)

        if notes.strip():
            layout.addWidget(QLabel(f"Anzeigename: {notes.strip()}"))

        path_label = QLabel(str(artifact_path))
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #5b6573;")
        layout.addWidget(path_label)

        layout.addWidget(
            QLabel(
                "Fertige PDFs dieses Buchs verwaltest du unter Plugins → Fertige PDFs…"
            )
        )

        row = QHBoxLayout()
        btn_open = QPushButton("PDF öffnen")
        btn_open.setDefault(True)
        btn_open.clicked.connect(self._choose_open)
        row.addWidget(btn_open)

        btn_map = QPushButton("In Fertige PDFs zeigen…")
        btn_map.clicked.connect(self._choose_mapping)
        row.addWidget(btn_map)

        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self._choose_dismiss)
        row.addWidget(btn_close)
        layout.addLayout(row)

    def _choose_open(self) -> None:
        self.choice = ACTION_OPEN_PDF
        self.accept()

    def _choose_mapping(self) -> None:
        self.choice = ACTION_SHOW_PDFS
        self.accept()

    def _choose_dismiss(self) -> None:
        self.choice = ACTION_DISMISS
        self.accept()


def ask_post_render_action(
    parent: Optional[QWidget],
    *,
    artifact_path: str,
    format_name: str = "",
    notes: str = "",
) -> str:
    """Zeigt den Post-Render-Dialog. Rückgabe: open_pdf | show_pdfs | dismiss."""
    if not artifact_path:
        return ACTION_DISMISS
    dlg = PostRenderDialog(
        parent,
        artifact_path=artifact_path,
        format_name=format_name,
        notes=notes,
    )
    dlg.exec()
    return dlg.choice


def open_finished_pdfs_for_book(
    parent: Optional[QWidget],
    book_path: Path,
    *,
    log: Optional[object] = None,
) -> None:
    """Öffnet Fertige-PDFs-Dialog für ein bestimmtes Buch."""
    from types import SimpleNamespace

    from ui_qt.dialogs.mapping_manager_dialog import open_mapping_manager_qt

    def _log(msg: str, level: str = "info") -> None:
        if callable(log):
            log(msg, level)

    studio = SimpleNamespace(current_book=Path(book_path), log=_log, root=parent)
    open_mapping_manager_qt(studio, parent)


__all__ = [
    "ACTION_DISMISS",
    "ACTION_OPEN_PDF",
    "ACTION_SHOW_PDFS",
    "PostRenderDialog",
    "ask_post_render_action",
    "open_finished_pdfs_for_book",
]
