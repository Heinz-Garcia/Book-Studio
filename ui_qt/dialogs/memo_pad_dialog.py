"""Memo-Block — ein Fenster, eine Notiz.

Bewusst schmucklos: kein Projektbezug, keine Historie, keine Ordner. Wer beim
Arbeiten etwas festhalten will, soll nicht erst entscheiden muessen, wohin es
gehoert.

Das Fenster ist **nicht modal** und traegt ``Qt.Window``: Es soll neben dem
Studio offen bleiben duerfen, waehrend man weiterarbeitet -- ein Notizblock,
den man zum Schreiben zuklappen muss, ist keiner.

Nur Widgets: Lesen und Schreiben steht in ``tools.memo_pad.store``
(siehe ``.doc/gui_architektur.md``).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.constants import StatusFg
from tools.memo_pad import store
from ui_qt.widgets.help_bar import HelpBar

_LOG = logging.getLogger(__name__)


class MemoPadDialog(QDialog):
    """Eine Notiz, die das Studio ueberdauert."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Memo-Block")
        self.setMinimumSize(store.MIN_WIDTH, store.MIN_HEIGHT)

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "memo_pad")

        self.status_label = QLabel()
        self.status_label.setStyleSheet(
            f"color: {StatusFg.NEUTRAL}; font-size: 11px;"
        )
        layout.addWidget(self.status_label)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Notiz eingeben …")
        self.editor.textChanged.connect(self._mark_dirty)
        layout.addWidget(self.editor, 1)

        knoepfe = QHBoxLayout()
        self.save_button = QPushButton("Speichern")
        self.save_button.setToolTip("Notiz jetzt speichern.")
        self.save_button.clicked.connect(self._save)
        knoepfe.addWidget(self.save_button)

        self.clear_button = QPushButton("Löschen")
        self.clear_button.setToolTip("Notiz komplett leeren.")
        self.clear_button.clicked.connect(self._clear)
        knoepfe.addWidget(self.clear_button)

        knoepfe.addStretch(1)
        self.close_button = QPushButton("Schließen")
        self.close_button.clicked.connect(self.close)
        knoepfe.addWidget(self.close_button)
        layout.addLayout(knoepfe)

        self._dirty = False
        self._reload()

    # -- Zustand -----------------------------------------------------------

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _reload(self) -> None:
        memo = store.load()
        self.resize(memo.width, memo.height)
        self.editor.blockSignals(True)
        self.editor.setPlainText(memo.text)
        self.editor.blockSignals(False)
        self._dirty = False
        self._show_status(memo.updated_at)

    def _show_status(self, updated_at: str) -> None:
        self.status_label.setText(
            f"Zuletzt gespeichert: {updated_at}"
            if updated_at
            else "Noch nichts gespeichert."
        )

    # -- Handgriffe --------------------------------------------------------

    def _save(self) -> None:
        groesse = self.size()
        try:
            memo = store.save(
                self.editor.toPlainText(),
                width=groesse.width(),
                height=groesse.height(),
            )
        except OSError as exc:
            QMessageBox.warning(self, "Memo-Block", f"Nicht schreibbar: {exc}")
            return
        self._dirty = False
        self._show_status(memo.updated_at)

    def _clear(self) -> None:
        if not self.editor.toPlainText().strip():
            return
        antwort = QMessageBox.question(
            self,
            "Memo-Block",
            "Notiz wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        self.editor.clear()
        self._save()

    # -- Schliessen --------------------------------------------------------

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Vertrag
        """Sichert ungespeicherte Notizen, ohne danach zu fragen.

        Eine Rueckfrage waere hier falsch: Der Block hat genau einen Inhalt und
        keine Versionen -- es gibt nichts, wogegen man sich entscheiden koennte.
        Wer nichts geschrieben hat, bekommt auch keinen neuen Zeitstempel.
        """
        try:
            if self._dirty:
                self._save()
            else:
                groesse = self.size()
                store.save_size(groesse.width(), groesse.height())
        except OSError:
            _LOG.debug("Memo-Block konnte nicht abgelegt werden", exc_info=True)
        # Selbst austragen: ``destroyed`` feuert bei ``WA_DeleteOnClose = False``
        # erst zum Programmende, die Liste waechse sonst mit jedem Oeffnen.
        if self in _offene_fenster:
            _offene_fenster.remove(self)
        super().closeEvent(event)


#: Solange ein nicht-modales Fenster offen ist, muss jemand es festhalten.
#: Ohne diese Liste raeumt Pythons Speicherverwaltung den Dialog ab, sobald
#: ``open_memo_pad`` zurueckkehrt -- das Fenster verschwaende, bevor es einmal
#: gezeichnet waere.
_offene_fenster: list[MemoPadDialog] = []


def open_memo_pad(
    studio: Any = None, parent: Optional[QWidget] = None, **kwargs: Any
) -> int:
    """Oeffnet den Memo-Block -- oder holt das offene Fenster nach vorn.

    "Ein Fenster, eine Notiz" stand bisher nur im Docstring. Jeder Aufruf baute
    bedingungslos ein neues Fenster, und da der Block absichtlich nicht modal
    neben dem Studio stehen bleibt, ist der zweite Menue-Aufruf der Normalfall.
    Beide Fenster luden dann ihren eigenen Stand und schrieben beim Schliessen
    den ganzen Text -- das zuletzt geschlossene gewann, der Inhalt des anderen
    war weg. Ohne Rueckfrage, denn ``closeEvent`` verzichtet bewusst darauf:
    "Der Block hat genau einen Inhalt und keine Versionen." Das stimmt eben
    nur, solange es auch genau ein Fenster gibt.
    """
    _ = kwargs
    vorhanden = _erstes_lebendes_fenster()
    if vorhanden is not None:
        vorhanden.show()
        vorhanden.raise_()
        vorhanden.activateWindow()
        return 0

    ziel = parent or getattr(studio, "root", None)
    dialog = MemoPadDialog(ziel)

    def _freigeben() -> None:
        if dialog in _offene_fenster:
            _offene_fenster.remove(dialog)

    # ``destroyed`` feuert bei ``WA_DeleteOnClose = False`` erst zum
    # Programmende; ``_teardown`` traegt das Fenster deshalb selbst aus, sobald
    # es geschlossen wird. Ohne das wuchs die Liste mit jedem Oeffnen um einen
    # dauerhaft gehaltenen Dialog samt Editor.
    dialog.destroyed.connect(_freigeben)
    dialog.setWindowFlags(Qt.WindowType.Window)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    _offene_fenster.append(dialog)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return 0


def _erstes_lebendes_fenster() -> Optional[MemoPadDialog]:
    """Ein noch benutzbares Memo-Fenster, oder ``None``.

    Ein bereits abgeraeumtes C++-Objekt meldet sich beim Zugriff mit
    ``RuntimeError``; solche Leichen fliegen hier heraus.
    """
    for fenster in list(_offene_fenster):
        try:
            fenster.isVisible()
        except RuntimeError:
            _offene_fenster.remove(fenster)
            continue
        return fenster
    return None


__all__ = ["MemoPadDialog", "open_memo_pad"]
