"""Hilfe-Dialog: HTML-Handbuch in QTextBrowser.

Mit ``anchor`` oeffnet er direkt bei einem Abschnitt. Das ist mehr als
Bequemlichkeit: Ein Handbuch mit dreiundzwanzig Kapiteln liest niemand von
vorn, wenn er gerade an einer Stelle nicht weiterkommt. Der Weg von der Frage
zur Antwort soll ein Klick sein, kein Suchlauf.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer
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
        anchor: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Handbuch")
        self.resize(900, 700)
        self._html_path = Path(html_path)
        self._md_path = Path(md_path) if md_path else None
        self._anchor = (anchor or "").strip()
        self._anchor_done = False

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
            try:
                from tools.directory_help import (
                    format_directory_help_html,
                    inject_directory_help_into_html,
                )
                from ui_qt.book_workspace import repo_root

                fragment = format_directory_help_html(repo_root())
                html = inject_directory_help_into_html(html, fragment)
            except (OSError, ImportError, ValueError, TypeError):
                pass
            self.browser.setHtml(html)
            self.browser.setSearchPaths([str(self._html_path.parent)])
        except OSError as exc:
            self.browser.setPlainText(f"Hilfe konnte nicht geladen werden:\n{exc}")

    def showEvent(self, event) -> None:  # noqa: N802 - Qt-Vertrag
        """Springt den Abschnitt an, sobald das Fenster wirklich steht.

        Im Konstruktor waere es vergeblich: Der Browser hat dort noch keine
        Groesse, sein Scrollbereich ist null, und ``scrollToAnchor`` laeuft ins
        Leere. Erst nach dem ersten Layout stimmen die Positionen -- deshalb
        der Umweg ueber die Ereignisschleife.
        """
        super().showEvent(event)
        if self._anchor and not self._anchor_done:
            self._anchor_done = True
            QTimer.singleShot(0, lambda: self.browser.scrollToAnchor(self._anchor))

    def _find(self) -> None:
        term = self.search.text().strip()
        if term:
            self.browser.find(term)


def open_manual(
    parent: Optional[QWidget] = None, *, anchor: Optional[str] = None
) -> bool:
    """Oeffnet das Handbuch, optional direkt bei *anchor*.

    Die Pfadaufloesung steht hier und nicht bei jedem Aufrufer: Sie haengt an
    ``app_config.json`` und aendert sich mit ihm. Zwei Kopien davon liefen
    frueher oder spaeter auseinander.

    Liefert ``False``, wenn das Handbuch nicht gefunden wurde -- der Aufrufer
    entscheidet dann, ob das eine Meldung wert ist.
    """
    from PySide6.QtWidgets import QMessageBox

    import app_config as _app_config
    from tools.handbook_html import resolve_handbook_html_path
    from tools.handbook_pdf import resolve_handbook_path
    from ui_qt.book_workspace import repo_root

    base = repo_root()
    try:
        cfg = _app_config.read_config(base / "app_config.json")
        html_path = resolve_handbook_html_path(base, cfg)
    except (ValueError, FileNotFoundError, OSError, TypeError) as exc:
        QMessageBox.warning(parent, "Hilfe", str(exc))
        return False
    try:
        md_path = resolve_handbook_path(base, cfg)
    except (ValueError, FileNotFoundError, OSError):
        md_path = None
    HelpDialog(parent, html_path, md_path=md_path, anchor=anchor).exec()
    return True


__all__ = ["HelpDialog", "open_manual"]
