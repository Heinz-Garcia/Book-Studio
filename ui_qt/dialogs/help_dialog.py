"""Hilfe-Dialog: HTML-Handbuch in QTextBrowser."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class HelpDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        html_path: Path,
        *,
        md_path: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Handbuch")
        self.resize(900, 700)
        self._html_path = Path(html_path)
        self._md_path = Path(md_path) if md_path else None

        layout = QVBoxLayout(self)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen…")
        find_btn = QPushButton("Finden")
        find_btn.clicked.connect(self._find)
        search_row.addWidget(self.search)
        search_row.addWidget(find_btn)
        layout.addLayout(search_row)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        layout.addWidget(self.browser)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        try:
            html = self._html_path.read_text(encoding="utf-8")
            self.browser.setHtml(html)
            self.browser.setSearchPaths([str(self._html_path.parent)])
        except OSError as exc:
            self.browser.setPlainText(f"Hilfe konnte nicht geladen werden:\n{exc}")

    def _find(self) -> None:
        term = self.search.text().strip()
        if term:
            self.browser.find(term)
