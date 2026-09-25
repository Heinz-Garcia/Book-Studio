"""Gemeinsame Hilfen von ``ui_qt.dialogs.doclayout_editor_dialog`` und seinen Mixins."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.constants import StatusFg
from tools.doclayout.origins import StyleOrigin
from tools.doclayout.preview import PreviewResult
from ui_qt.dialogs.doclayout_editor_style import (
    MUTED_NAME,
)

_LOG = logging.getLogger(__name__)


_ORIGIN_COLORS_LIGHT = {
    StyleOrigin.CONTENT: StatusFg.PRIMARY,      # #2563eb
    StyleOrigin.UNUSED: "#b45309",              # dunkler als StatusFg.WARNING,
                                                # das auf Weiss zu blass wirkt
    StyleOrigin.STANDARD: StatusFg.NEUTRAL,     # #64748b
}


_ORIGIN_COLORS_DARK = {
    StyleOrigin.CONTENT: "#4da3ff",
    StyleOrigin.UNUSED: StatusFg.WARNING_ALT,   # #f59e0b
    StyleOrigin.STANDARD: StatusFg.NEUTRAL_MUTED,  # #95a5a6
}


_REQUIREMENT_COLORS_LIGHT = ("#fdf3d8", "#e0b568", "#6b4b16")


_REQUIREMENT_COLORS_DARK = ("#5a3a00", "#8a6000", "#ffe0a0")


_SCOPE_COLORS_LIGHT = ("#e7f0fb", "#7aa7d9", "#1a3f66")


_SCOPE_COLORS_DARK = ("#16324d", "#2f5d94", "#cfe3fa")


_FALLBACK_LAYOUT_PROFILE = "taschenbuch-bod"


_DARK_KEY = "doclayout_editor_dark"


_SECTION_PAGE = "□  Seite und Ränder"


_SECTION_TYPOGRAPHY = "Aa  Typografie"


_SECTION_COLORS = "●  Farben"


_SECTION_CLASSMAP = "→  Klassen-Abbildung"


class _PreviewPane(QWidget):
    """Zeigt die gesetzte PDF an -- oder sagt, warum es keine gibt."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document: Any = None
        self._view: Any = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self.refresh_button = QPushButton("Vorschau erneuern")
        self.refresh_button.setToolTip(
            "Setzt den Musterinhalt mit dem aktuellen Layout neu "
            "(Pandoc + LibreOffice, wenige Sekunden)."
        )
        header.addWidget(self.refresh_button)
        self.open_button = QPushButton(".docx öffnen")
        self.open_button.setEnabled(False)
        header.addWidget(self.open_button)
        header.addStretch(1)
        self.status_label = QLabel("Noch nicht gesetzt.")
        self.status_label.setObjectName(MUTED_NAME)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        self._stack_host = QWidget()
        self._stack_layout = QVBoxLayout(self._stack_host)
        self._stack_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack_host, 1)

        self._message = QLabel(
            "Die Vorschau wird gesetzt, sobald du etwas änderst –\n"
            "oder sofort über »Vorschau erneuern«."
        )
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._message.setObjectName(MUTED_NAME)
        self._stack_layout.addWidget(self._message)

        self._init_pdf_view()

    def _init_pdf_view(self) -> None:
        """QtPdf ist Teil von PySide6, aber nicht in jedem Build vorhanden."""
        try:
            from PySide6.QtPdf import QPdfDocument
            from PySide6.QtPdfWidgets import QPdfView
        except ImportError:
            _LOG.info("QtPdf nicht verfügbar — Vorschau nur als Datei.")
            return
        self._document = QPdfDocument(self)
        self._view = QPdfView(self)
        self._view.setDocument(self._document)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._view.hide()
        self._stack_layout.addWidget(self._view)

    def show_busy(self) -> None:
        self.status_label.setText("wird gesetzt …")

    def show_result(self, result: PreviewResult) -> None:
        self.open_button.setEnabled(result.docx.is_file())
        self._docx = result.docx
        if result.pdf and self._document is not None and self._view is not None:
            self._document.load(str(result.pdf))
            self._message.hide()
            self._view.show()
            self.status_label.setText("gesetzt")
            return
        self._view.hide() if self._view else None
        self._message.setText(
            result.note
            or "Die Vorschau liegt als .docx vor; zum Anzeigen fehlt QtPdf."
        )
        self._message.show()
        self.status_label.setText("nur als Datei")

    def show_error(self, message: str) -> None:
        if self._view is not None:
            self._view.hide()
        self._message.setText(message)
        self._message.show()
        self.status_label.setText("fehlgeschlagen")

    def docx_path(self) -> Optional[Path]:
        return getattr(self, "_docx", None)
