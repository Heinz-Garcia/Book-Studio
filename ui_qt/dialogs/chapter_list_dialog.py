"""Kapitelliste exportieren -- die Uebergabeliste eines Buchs als CSV.

Eine Zeile je Manuskriptdatei, in Lesereihenfolge: Nummer, Pfad, Titel,
Umfang. Der Dialog zeigt genau das, was anschliessend in der CSV steht --
keine Vorschau, die etwas anderes behauptet als die Datei.

Wofuer das gut ist: Lektorat, Uebersetzung und Satz haben Book Studio nicht.
Die CSV ist das Einzige, was man ihnen in die Hand geben kann.

Nur Widgets: gelesen, gezaehlt und geschrieben wird in
``tools.chapter_list.builder`` (siehe ``.doc/gui_architektur.md``).
"""

from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.chapter_list.builder import (
    CSV_HEADER,
    ChapterList,
    ChapterListError,
    ChapterRow,
    build_chapter_list_detailed,
    write_chapter_list,
)

_LOG = logging.getLogger(__name__)

#: Letzter Eintrag der Auswahlliste -- der Ausweg fuer alles Unbekannte.
_ANDERES_VERZEICHNIS = "Anderes Verzeichnis …"

#: Rechtsbuendige Spalten: Nummer und die beiden Umfangsangaben.
_ZAHLENSPALTEN = (0, 3, 4)


class ChapterListDialog(QDialog):
    """Vorschau und CSV-Export der Kapitelliste eines Buchprojekts."""

    def __init__(
        self,
        book_path: Optional[Path] = None,
        *,
        studio: Any = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._studio = studio
        self._book_path = Path(book_path) if book_path else None
        self._liste: Optional[ChapterList] = None
        self._letzte_csv: Optional[Path] = None
        self.setWindowTitle("Kapitelliste exportieren")
        self.resize(880, 520)
        self._build()
        self.fill_book_choices()
        if self._book_path is None:
            # Kein aktives Buch: das erste bekannte nehmen, statt den Benutzer
            # vor eine leere Tabelle und einen Dateidialog zu setzen.
            daten = self.buch_auswahl.itemData(0)
            if daten:
                self._book_path = Path(str(daten))
        if self._book_path is not None:
            self.refresh()

    # -- Aufbau ------------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        # Auswahlliste statt Ordnerdialog: Welche Buchprojekte es gibt, weiss
        # die Anwendung selbst (``book_projects.catalog``).
        auswahl_zeile = QHBoxLayout()
        auswahl_zeile.setSpacing(8)
        auswahl_zeile.addWidget(QLabel("Buch:"))
        self.buch_auswahl = QComboBox()
        self.buch_auswahl.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.buch_auswahl.setMinimumWidth(360)
        self.buch_auswahl.currentIndexChanged.connect(self._auf_buch_gewechselt)
        auswahl_zeile.addWidget(self.buch_auswahl, 1)
        layout.addLayout(auswahl_zeile)

        self.buch_label = QLabel("")
        self.buch_label.setStyleSheet("QLabel { color: #475569; }")
        self.buch_label.setWordWrap(True)
        layout.addWidget(self.buch_label)

        # Fehlt die Kapitelliste in _quarto.yml, ist die Reihenfolge nicht
        # bekannt. Das muss ueber der Tabelle stehen und nicht im Log: Wer die
        # CSV weitergibt, haelt sie sonst fuer die Kapitelfolge des Buchs.
        self.hinweis_label = QLabel("")
        self.hinweis_label.setWordWrap(True)
        self.hinweis_label.setTextFormat(Qt.TextFormat.RichText)
        self.hinweis_label.setVisible(False)
        layout.addWidget(self.hinweis_label)

        self.tabelle = QTableWidget(0, len(CSV_HEADER), self)
        self.tabelle.setHorizontalHeaderLabels(list(CSV_HEADER))
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabelle.setAlternatingRowColors(True)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        kopf.setStretchLastSection(True)
        layout.addWidget(self.tabelle, 1)

        self.befund_label = QLabel("")
        self.befund_label.setWordWrap(True)
        self.befund_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.befund_label)

        knopfleiste = QHBoxLayout()
        self.btn_aktualisieren = QPushButton("Aktualisieren")
        self.btn_aktualisieren.clicked.connect(self.refresh)
        knopfleiste.addWidget(self.btn_aktualisieren)
        knopfleiste.addStretch(1)

        self.btn_schreiben = QPushButton("CSV schreiben")
        self.btn_schreiben.setToolTip(
            "Schreibt <Buchprojekt>/export/kapitelliste.csv "
            "(utf-8 mit BOM, Trennzeichen Semikolon)."
        )
        self.btn_schreiben.clicked.connect(self.write_csv)
        knopfleiste.addWidget(self.btn_schreiben)

        # Die CLI kennt ``--out`` seit jeher. Ohne diesen Knopf musste im
        # Dialog jede Liste, die an zwei Empfaenger geht, von Hand aus
        # ``export/`` weggetragen werden, bevor die naechste sie ueberschrieb.
        self.btn_speichern_unter = QPushButton("Speichern unter …")
        self.btn_speichern_unter.setToolTip(
            "Schreibt dieselbe CSV an einen frei gewählten Ort."
        )
        self.btn_speichern_unter.clicked.connect(self.write_csv_as)
        knopfleiste.addWidget(self.btn_speichern_unter)

        self.btn_ordner = QPushButton("Ordner öffnen")
        self.btn_ordner.clicked.connect(self._ordner_oeffnen)
        knopfleiste.addWidget(self.btn_ordner)

        self.btn_schliessen = QPushButton("Schließen")
        self.btn_schliessen.clicked.connect(self.accept)
        knopfleiste.addWidget(self.btn_schliessen)
        layout.addLayout(knopfleiste)

    # -- Daten -------------------------------------------------------------
    def refresh(self) -> None:
        """Kapitelliste neu erheben und anzeigen."""
        if self._book_path is None:
            self.buch_label.setText("Kein Buchprojekt gewählt.")
            return
        try:
            self._liste = build_chapter_list_detailed(self._book_path)
        except (ChapterListError, OSError) as exc:
            self._liste = None
            self.tabelle.setRowCount(0)
            self.buch_label.setText(f"Buch: {self._book_path}")
            self.befund_label.setText("")
            self._zeige_hinweis(str(exc))
            return
        self._fill(self._liste)

    def _fill(self, liste: ChapterList) -> None:
        self.buch_label.setText(f"Buch: {liste.book_path}")

        self.tabelle.setRowCount(len(liste.rows))
        for zeile, row in enumerate(liste.rows):
            self._fill_row(zeile, row)
        self.tabelle.resizeColumnsToContents()

        if liste.order_problem:
            self._zeige_hinweis(
                liste.order_problem + " Die Spalte NR bleibt leer, die Zeilen stehen alphabetisch."
            )
        else:
            self.hinweis_label.setVisible(False)

        teile = [
            f"<b>{len(liste.chapters)}</b> Kapitel",
            f"<b>{liste.words}</b> Wörter",
        ]
        if liste.extras:
            teile.append(
                f"<b>{len(liste.extras)}</b> Datei(en) stehen nicht in _quarto.yml "
                "(am Ende, IN_QUARTO=nein)"
            )
        self.befund_label.setText(" · ".join(teile))
        _LOG.info("Kapitelliste: %s", liste.summary())

    def _fill_row(self, zeile: int, row: ChapterRow) -> None:
        for spalte, text in enumerate(row.as_csv_row()):
            item = QTableWidgetItem(text)
            if spalte in _ZAHLENSPALTEN:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabelle.setItem(zeile, spalte, item)

    def _zeige_hinweis(self, text: str) -> None:
        """Den Vorbehalt ueber die Tabelle setzen -- als Text, nicht als Markup.

        Das Label ist Rich-Text, ``text`` kommt aber aus einer Fehlermeldung
        mit Dateipfad. Ein ``<`` darin zerlegte die Anzeige, und ausgerechnet
        der Hinweis, dass die Reihenfolge fehlt, verschwand dann still.
        """
        self.hinweis_label.setText(
            f"<b style='color:#92400e;'>{html.escape(text)}</b>"
        )
        self.hinweis_label.setVisible(True)

    # -- Aktionen ----------------------------------------------------------
    def write_csv(self) -> Optional[Path]:
        """Die angezeigte Liste an den Regelort schreiben."""
        return self._schreibe(None)

    def write_csv_as(self) -> Optional[Path]:
        """Dieselbe Liste an einen frei gewaehlten Ort schreiben."""
        if self._liste is None or self._book_path is None:
            QMessageBox.warning(self, "Kapitelliste", "Es ist keine Liste zum Schreiben da.")
            return None
        vorschlag = self._letzte_csv or (
            self._book_path / "export" / f"kapitelliste_{self._book_path.name}.csv"
        )
        gewaehlt, _ = QFileDialog.getSaveFileName(
            self,
            "Kapitelliste speichern unter",
            str(vorschlag),
            "CSV-Datei (*.csv);;Alle Dateien (*)",
        )
        if not gewaehlt:
            return None
        return self._schreibe(Path(gewaehlt))

    def _schreibe(self, ziel: Optional[Path]) -> Optional[Path]:
        """Gemeinsamer Schreibweg beider Knoepfe.

        ``ziel=None`` heisst ``<Buchprojekt>/export/kapitelliste.csv`` -- der
        Regelort, der ohne Rueckfrage ueberschrieben wird.
        """
        if self._liste is None or self._book_path is None:
            QMessageBox.warning(self, "Kapitelliste", "Es ist keine Liste zum Schreiben da.")
            return None
        try:
            geschrieben = write_chapter_list(
                self._liste.book_path, list(self._liste.rows), target=ziel
            )
        except OSError as exc:
            QMessageBox.warning(self, "Kapitelliste", f"CSV nicht schreibbar:\n{exc}")
            return None
        self._letzte_csv = geschrieben
        self._log(f"Kapitelliste geschrieben: {geschrieben} ({self._liste.summary()})")
        QMessageBox.information(
            self,
            "Kapitelliste",
            f"{len(self._liste.rows)} Zeilen geschrieben:\n{geschrieben}",
        )
        return geschrieben

    def _ordner_oeffnen(self) -> None:
        """Den Zielordner zeigen -- die CSV markiert, wenn es sie schon gibt."""
        if self._book_path is None:
            return
        ziel = self._letzte_csv if self._letzte_csv else self._book_path / "export"
        if not ziel.exists():
            QMessageBox.information(
                self,
                "Ordner öffnen",
                "Der Ordner entsteht erst mit der CSV. " "Bitte zuerst „CSV schreiben“.",
            )
            return
        from tools.mapping_manager.actions import reveal_in_explorer

        reveal_in_explorer(ziel)

    def fill_book_choices(self) -> None:
        """Bekannte Buchprojekte in die Auswahlliste stellen.

        Quelle ist ``book_projects.catalog`` -- dieselbe Entdeckung, die auch
        die Buchverwaltung benutzt. Der letzte Eintrag bleibt der Ausweg fuer
        ein Buch ausserhalb der bekannten Wurzeln.
        """
        try:
            from tools.book_projects.catalog import list_books
            from tools.production_paths.paths import is_publish_run_folder_name

            # ``Publish_*`` sind Export-Ergebnisse, die eine ``_quarto.yml``
            # mitfuehren und deshalb wie Buchprojekte aussehen. Eine
            # Kapitelliste zieht man aus der Quelle, nicht aus dem Ausdruck.
            buecher = [
                info for info in list_books()
                if not is_publish_run_folder_name(info.name)
            ]
        except (ImportError, OSError, TypeError, ValueError) as exc:
            _LOG.warning("Buchliste nicht lesbar: %s", exc)
            buecher = []

        self.buch_auswahl.blockSignals(True)
        try:
            self.buch_auswahl.clear()
            aktiv = -1
            for info in buecher:
                beschriftung = info.display_name or info.name
                if info.display_name and info.display_name != info.name:
                    beschriftung = f"{info.display_name}  ({info.name})"
                self.buch_auswahl.addItem(beschriftung, str(info.path))
                if self._book_path and Path(info.path) == self._book_path:
                    aktiv = self.buch_auswahl.count() - 1
            if self._book_path is not None and aktiv < 0:
                # Geoeffnet auf einem Buch, das die Entdeckung nicht kennt.
                self.buch_auswahl.addItem(self._book_path.name, str(self._book_path))
                aktiv = self.buch_auswahl.count() - 1
            self.buch_auswahl.addItem(_ANDERES_VERZEICHNIS, "")
            if aktiv >= 0:
                self.buch_auswahl.setCurrentIndex(aktiv)
            elif self.buch_auswahl.count() > 1:
                self.buch_auswahl.setCurrentIndex(0)
        finally:
            self.buch_auswahl.blockSignals(False)

    def _auf_buch_gewechselt(self, index: int) -> None:
        daten = self.buch_auswahl.itemData(index)
        if daten:
            self._book_path = Path(str(daten))
            self._letzte_csv = None
            self.refresh()
        elif self.buch_auswahl.itemText(index) == _ANDERES_VERZEICHNIS:
            self._buch_waehlen()

    def _buch_waehlen(self) -> None:
        """Ausweg fuer Buecher ausserhalb der bekannten Wurzeln."""
        start = str(self._book_path) if self._book_path else ""
        gewaehlt = QFileDialog.getExistingDirectory(self, "Buchprojekt wählen", start)
        if not gewaehlt:
            self.fill_book_choices()  # Auswahl auf den vorherigen Stand zurueck
            return
        pfad = Path(gewaehlt)
        if not (pfad / "_quarto.yml").is_file():
            QMessageBox.warning(
                self,
                "Kein Buchprojekt",
                f"{pfad.name} enthält keine _quarto.yml.",
            )
            self.fill_book_choices()
            return
        self._book_path = pfad
        self._letzte_csv = None
        self.fill_book_choices()
        self.refresh()

    def _log(self, message: str) -> None:
        log = getattr(self._studio, "log", None)
        if callable(log):
            log(message, "success")

    @property
    def chapter_list(self) -> Optional[ChapterList]:
        return self._liste


def open_chapter_list_qt(
    studio: Any = None, parent: Optional[QWidget] = None, **kwargs: Any
) -> int:
    """Entrypoint fuer den Plugin-Adapter."""
    book_path = kwargs.get("book_path")
    if book_path is None and studio is not None:
        book_path = getattr(studio, "current_book", None) or getattr(studio, "book_path", None)
    dialog = ChapterListDialog(Path(book_path) if book_path else None, studio=studio, parent=parent)
    # Der Rueckgabewert des Dialogs geht hinaus, statt fest ``0`` zu melden:
    # Der Adapter deklariert ``-> int``, und ein abgebrochener Dialog soll
    # nicht wie ein erfolgreicher Lauf aussehen.
    return int(dialog.exec())


__all__ = ["ChapterListDialog", "open_chapter_list_qt"]
