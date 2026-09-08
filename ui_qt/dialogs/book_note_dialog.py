"""Qt-Dialog für die Buchnotiz.

Ein Buch links, der Text rechts. Mehr braucht es nicht — und mehr wäre auch
falsch: Eine Notiz, die nach Kategorien, Fälligkeiten oder Zuständen fragt,
schreibt man nicht mehr, wenn es schnell gehen muss.

Zwei Entscheidungen, die man dem Fenster ansieht:

**Die Buchliste steht daneben, nicht in einem Auswahlfeld.** Wer notiert, will
oft sehen, wo sonst noch etwas offen ist — deshalb trägt jeder Eintrag ein
Zeichen, ob dort eine Notiz liegt. Ein Auswahlfeld verstecke das hinter einem
Klick.

**Gespeichert wird beim Wechsel und beim Schließen, nicht nur auf Knopfdruck.**
Ein Notizfenster, das Arbeit wegwirft, weil jemand den Knopf nicht gefunden
hat, ist schlimmer als keines. Der Knopf bleibt trotzdem — er sagt, dass etwas
offen ist.

Kernlogik liegt in ``tools/book_note`` (GUI-frei, siehe
``.doc/gui_architektur.md``); dieser Dialog hält nur Widgets.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from tools.book_note import store
from ui_qt import qt_session

_LOG = logging.getLogger(__name__)

#: Zeichen vor einem Buch mit Notiz. Ein Zeichen, kein Wort: Die Liste soll auf
#: einen Blick lesbar bleiben.
_MARKER_MIT = "📝"
_MARKER_OHNE = "  "

_SIZE_KEY = "book_note_size"
_DEFAULT_SIZE = (900, 560)
_MIN_SIZE = (620, 380)


class BookNoteDialog(QDialog):
    """Notizen aller Buchprojekte -- eine je Buch."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        books: Optional[list[Path]] = None,
        select: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Buchnotizen")
        self._books: list[Path] = list(books or [])
        self._current: Optional[Path] = None
        self._dirty = False
        self._closed = False
        #: Waehrend die Auswahl programmgesteuert zurueckgesetzt wird, darf
        #: ``_on_book_changed`` nicht erneut anlaufen.
        self._switching = False

        self._apply_saved_size()
        self._build_ui()
        self._fill_books(select)

    # -- Aufbau ------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        kopf = QLabel(
            "Eine Notiz je Buchprojekt. Sie liegt im Buch selbst "
            "(<code>bookconfig/notiz.md</code>) und ist deshalb auch aus "
            "GrammarGraph erreichbar — dieselbe Datei, beide Programme."
        )
        kopf.setWordWrap(True)
        kopf.setTextFormat(Qt.TextFormat.RichText)
        outer.addWidget(kopf)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.book_list = QListWidget()
        self.book_list.setToolTip(
            "Bücher mit 📝 haben bereits eine Notiz."
        )
        self.book_list.currentItemChanged.connect(self._on_book_changed)
        splitter.addWidget(self.book_list)

        rechts = QWidget()
        rechts_layout = QVBoxLayout(rechts)
        rechts_layout.setContentsMargins(0, 0, 0, 0)

        self.book_label = QLabel()
        schrift = self.book_label.font()
        schrift.setBold(True)
        self.book_label.setFont(schrift)
        rechts_layout.addWidget(self.book_label)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Was zu diesem Band offen ist, wem es vorliegt, was beim nächsten "
            "Mal zu beachten ist …"
        )
        # Feste Breite: In Notizen stehen Pfade, Dateinamen und Listen.
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.textChanged.connect(self._on_text_changed)
        rechts_layout.addWidget(self.editor, 1)

        self.status_label = QLabel()
        rechts_layout.addWidget(self.status_label)

        splitter.addWidget(rechts)
        splitter.setSizes([260, 640])
        outer.addWidget(splitter, 1)

        fuss = QHBoxLayout()
        self.path_label = QLabel()
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        fuss.addWidget(self.path_label, 1)
        self.save_button = QPushButton("Speichern")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_current)
        fuss.addWidget(self.save_button)
        schliessen = QPushButton("Schließen")
        schliessen.clicked.connect(self.reject)
        fuss.addWidget(schliessen)
        outer.addLayout(fuss)

    # -- Buchliste ---------------------------------------------------------

    def _fill_books(self, select: Optional[Path]) -> None:
        self.book_list.blockSignals(True)
        self.book_list.clear()
        for buch in self._books:
            marker = _MARKER_MIT if store.has_note(buch) else _MARKER_OHNE
            eintrag = QListWidgetItem(f"{marker} {buch.name}")
            eintrag.setData(Qt.ItemDataRole.UserRole, str(buch))
            eintrag.setToolTip(str(buch))
            self.book_list.addItem(eintrag)
        self.book_list.blockSignals(False)

        if not self._books:
            self.book_label.setText("Kein Buchprojekt gefunden.")
            self.editor.setEnabled(False)
            self.status_label.setText(
                "Gesucht wurde nach Ordnern mit einer _quarto.yml."
            )
            return

        ziel = 0
        if select is not None:
            ziel = next(
                (i for i, b in enumerate(self._books) if b == Path(select)), 0
            )
        self.book_list.setCurrentRow(ziel)

    def _refresh_marker(self, buch: Path) -> None:
        """Zieht das 📝 eines Buches nach, ohne die Auswahl zu verlieren."""
        for row in range(self.book_list.count()):
            eintrag = self.book_list.item(row)
            if Path(str(eintrag.data(Qt.ItemDataRole.UserRole))) != buch:
                continue
            marker = _MARKER_MIT if store.has_note(buch) else _MARKER_OHNE
            eintrag.setText(f"{marker} {buch.name}")
            return

    # -- Bearbeiten --------------------------------------------------------

    def _on_book_changed(
        self, current: Optional[QListWidgetItem], previous: Any = None
    ) -> None:
        if self._switching:
            return
        # Erst sichern, was im Feld steht -- der Wechsel darf keine Arbeit
        # kosten, und niemand rechnet vor einem Listenklick mit einem Verlust.
        #
        # Scheitert das Schreiben, wird der Wechsel **zurueckgenommen**. Vorher
        # lief die Methode nach der Fehlermeldung einfach weiter, lud das neue
        # Buch in den Editor und setzte ``_dirty`` zurueck -- der ungesicherte
        # Text war damit weg. Wer die Notiz auf einem vollen oder gesperrten
        # Laufwerk hatte, verlor sie beim naechsten Listenklick.
        if not self._save_current():
            self._restore_selection(previous)
            return
        if current is None:
            return
        buch = Path(str(current.data(Qt.ItemDataRole.UserRole)))
        notiz = store.load(buch)
        self._current = buch
        self.editor.blockSignals(True)
        self.editor.setPlainText(notiz.text)
        self.editor.blockSignals(False)
        if notiz.load_error:
            self.editor.setEnabled(False)
            self.book_label.setText(buch.name)
            self.path_label.setText(str(store.note_path(buch)))
            self._dirty = False
            self.save_button.setEnabled(False)
            self.status_label.setText("Lesefehler — Speichern gesperrt")
            QMessageBox.warning(
                self,
                "Buchnotiz nicht lesbar",
                f"{store.note_path(buch)}\n\n{notiz.load_error}\n\n"
                "Die Datei wird nicht überschrieben. Bitte Kodierung prüfen "
                "(UTF-8) oder die Datei manuell reparieren.",
            )
            return
        self.editor.setEnabled(True)
        self.book_label.setText(buch.name)
        self.path_label.setText(str(store.note_path(buch)))
        self._dirty = False
        self.save_button.setEnabled(False)
        self._update_status(notiz)

    def _on_text_changed(self) -> None:
        self._dirty = True
        self.save_button.setEnabled(True)
        self.status_label.setText("ungespeichert")

    def _update_status(self, notiz: store.BookNote) -> None:
        if notiz.is_empty:
            self.status_label.setText("noch keine Notiz")
        else:
            self.status_label.setText(f"zuletzt geändert: {notiz.updated_at}")

    def _save_current(self) -> bool:
        """Schreibt die offene Notiz. ``False`` heisst: Text ist noch im Feld.

        Der Rueckgabewert ist der Grund fuer diese Signatur: Der Aufrufer muss
        wissen, ob er weitermachen darf. Ein Buchwechsel nach einem
        gescheiterten Schreibvorgang ueberschriebe den Editor und verwuerfe
        genau den Text, der nicht auf die Platte kam.
        """
        if not self._dirty or self._current is None:
            return True
        buch = self._current
        try:
            notiz = store.save(buch, self.editor.toPlainText())
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Notiz nicht gespeichert",
                f"{store.note_path(buch)}\n\n{exc}\n\n"
                "Der Text steht weiterhin im Feld — bitte das Problem beheben "
                "und erneut speichern.",
            )
            return False
        self._dirty = False
        self.save_button.setEnabled(False)
        self._refresh_marker(buch)
        self._update_status(notiz)
        _LOG.info("Buchnotiz gespeichert: %s", store.note_path(buch))
        return True

    def _restore_selection(self, previous: Any) -> None:
        """Setzt die Listenauswahl zurueck, ohne den Handler erneut auszuloesen."""
        self._switching = True
        try:
            if isinstance(previous, QListWidgetItem):
                self.book_list.setCurrentItem(previous)
            else:
                self.book_list.setCurrentItem(None)
        finally:
            self._switching = False

    # -- Fenstergroesse und Schliessen -------------------------------------

    def _apply_saved_size(self) -> None:
        breite, hoehe = _DEFAULT_SIZE
        try:
            state = qt_session.load_session()
        except (OSError, ValueError):
            state = {}
        ui = state.get("ui_state") if isinstance(state, dict) else None
        if isinstance(ui, dict):
            gemerkt = ui.get(_SIZE_KEY)
            if isinstance(gemerkt, (list, tuple)) and len(gemerkt) == 2:
                try:
                    breite, hoehe = int(gemerkt[0]), int(gemerkt[1])
                except (TypeError, ValueError):
                    breite, hoehe = _DEFAULT_SIZE
        self.resize(max(_MIN_SIZE[0], breite), max(_MIN_SIZE[1], hoehe))

    def _teardown(self) -> None:
        """Sichern und Groesse merken -- genau einmal, egal auf welchem Weg."""
        if self._closed:
            return
        self._closed = True
        self._save_current()
        try:
            qt_session.update_ui_state(
                {_SIZE_KEY: [int(self.width()), int(self.height())]}
            )
        except OSError:
            _LOG.debug("Fenstergroesse nicht abgelegt", exc_info=True)

    def reject(self) -> None:  # noqa: D102 - Qt-Vertrag
        self._teardown()
        super().reject()

    def accept(self) -> None:  # noqa: D102 - Qt-Vertrag
        self._teardown()
        super().accept()

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Vertrag
        self._teardown()
        super().closeEvent(event)


def _discover_books(studio: Any = None) -> list[Path]:
    """Alle Buchprojekte, die Book Studio kennt.

    SSOT: ``tools.book_projects.catalog.list_books`` (Content-Roots,
    Anzeigenamen). Fallbacks: ``ui_qt.book_workspace.discover_books``, dann
    flache Suche ab Repo-Wurzel.
    """
    try:
        from tools.book_projects.catalog import list_books

        gefunden = [Path(info.path) for info in list_books()]
        if gefunden:
            return sorted(set(gefunden), key=lambda p: p.name.lower())
    except (ImportError, OSError, TypeError, ValueError):
        _LOG.debug("book_projects.catalog nicht verfuegbar", exc_info=True)
    try:
        from ui_qt.book_workspace import discover_books

        gefunden = [Path(p) for p in discover_books()]
        if gefunden:
            return sorted(set(gefunden), key=lambda p: p.name.lower())
    except (ImportError, OSError, TypeError, ValueError):
        _LOG.debug("Buchsuche der App nicht verfuegbar", exc_info=True)
    return store.find_books(Path(__file__).resolve().parent.parent.parent)


def open_book_note_qt(
    studio: Any = None, parent: Optional[QWidget] = None, **kwargs: Any
) -> int:
    """Entrypoint fuer den Plugin-Adapter."""
    auswahl = kwargs.get("book_path")
    if auswahl is None and studio is not None:
        auswahl = getattr(studio, "current_book", None) or getattr(
            studio, "book_path", None
        )
    dialog = BookNoteDialog(
        parent=parent,
        books=_discover_books(studio),
        select=Path(auswahl) if auswahl else None,
    )
    dialog.exec()
    return 0


__all__ = ["BookNoteDialog", "open_book_note_qt"]
