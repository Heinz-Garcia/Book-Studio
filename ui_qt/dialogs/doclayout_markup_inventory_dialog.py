"""Textauszeichnungs-Inventar -- die Draufsicht auf alle Fenced-Div-Klassen.

Eine Zeile je Auszeichnung, vier Fragen beantwortet: Woher kommt sie, wie oft
steht sie im Buch, welches Absatzformat bekommt sie, und was ist daran zu tun.

Abgrenzung: Der **Assistent** (``doclayout_wizard``) geht das Buch Schritt fuer
Schritt durch und behandelt alle Formatierungsobjekte. Diese Tabelle ist die
Uebersicht, und nur ueber die Auszeichnungen -- dafuer zeigt sie auch, was im
Buch gar nicht vorkommt (Vorlagen ohne Benutzung).

Nur Widgets: gezaehlt und bewertet wird in
``tools.doclayout.markup_inventory`` (siehe ``.doc/gui_architektur.md``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.doclayout.markup_inventory import (
    MarkupInventory,
    MarkupRow,
    Verdict,
    build_markup_inventory,
)

_LOG = logging.getLogger(__name__)

#: Farbe je Befund -- nur fuer die Befundspalte, nicht fuer die ganze Zeile.
_VERDICT_COLORS = {
    Verdict.OHNE_VORLAGE: "#991b1b",
    Verdict.KARTEILEICHE: "#92400e",
    Verdict.OK: "#166534",
    Verdict.QUARTO: "#475569",
}

_SPALTEN = (
    "Auszeichnung", "kommt aus", "im Buch", "Vorlage", "Befund",
    "Zu tun", "gestaltet?", "Aussehen",
)

#: Spalte, in der die naechste Handlung steht -- sie wird hervorgehoben.
_SPALTE_ZU_TUN = 5
_SPALTE_BEFUND = 4

#: Kurzzeichen der Spalte "gestaltet?": Haken, Kreuz, oder nichts zu sagen.
_GESTALTET_ZEICHEN = {True: "✓", False: "✗", None: "—"}

#: Letzter Eintrag der Auswahlliste -- der Ausweg fuer alles Unbekannte.
_ANDERES_VERZEICHNIS = "Anderes Verzeichnis …"


class MarkupInventoryDialog(QDialog):
    """Tabelle aller Textauszeichnungen eines Buchprojekts."""

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
        self._inventory: Optional[MarkupInventory] = None
        self.setWindowTitle("Textauszeichnungs-Inventar")
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
        # die Anwendung selbst (``book_projects.catalog``). Wer hier einen Pfad
        # zusammensuchen muss, kennt entweder die Verzeichnisstruktur auswendig
        # oder gibt auf.
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

        self.tabelle = QTableWidget(0, len(_SPALTEN), self)
        self.tabelle.setHorizontalHeaderLabels(list(_SPALTEN))
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabelle.setAlternatingRowColors(True)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        kopf.setStretchLastSection(True)
        # Doppelklick fuehrt dorthin, wo man mit dieser Zeile weiterarbeitet:
        # zur Fundstelle im Text, oder -- wenn es keine gibt -- zur Vorlage im
        # Layout-Editor. Rechtsklick bietet beides plus den Namen zum Kopieren.
        self.tabelle.cellDoubleClicked.connect(self._auf_doppelklick)
        self.tabelle.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabelle.customContextMenuRequested.connect(self._auf_kontextmenue)
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

        self.btn_editor = QPushButton("Layout-Editor öffnen …")
        self.btn_editor.setToolTip(
            "Dort werden Absatzformate angelegt und gestaltet; "
            "„Fehlende Formate anlegen“ schließt alle Lücken in einem Zug."
        )
        self.btn_editor.clicked.connect(self._editor_oeffnen)
        knopfleiste.addWidget(self.btn_editor)

        self.btn_schliessen = QPushButton("Schließen")
        self.btn_schliessen.clicked.connect(self.accept)
        knopfleiste.addWidget(self.btn_schliessen)
        layout.addLayout(knopfleiste)

    # -- Daten -------------------------------------------------------------
    def refresh(self) -> None:
        """Inventar neu erheben und anzeigen."""
        if self._book_path is None:
            self.buch_label.setText("Kein Buchprojekt gewählt.")
            return
        try:
            self._inventory = build_markup_inventory(self._book_path)
        except OSError as exc:
            QMessageBox.warning(self, "Inventar", f"Buch nicht lesbar:\n{exc}")
            return
        self._fill(self._inventory)

    def _fill(self, inventar: MarkupInventory) -> None:
        quelle = (
            f" · Generator-Meldung aus {inventar.generator_source}"
            if inventar.generator_source
            else ""
        )
        self.buch_label.setText(f"Buch: {inventar.book_path}{quelle}")

        self.tabelle.setRowCount(len(inventar.rows))
        for zeile, row in enumerate(inventar.rows):
            self._fill_row(zeile, row)
        self.tabelle.resizeColumnsToContents()

        offen = len(inventar.without_template)
        leichen = len(inventar.orphans)
        if offen:
            self.befund_label.setText(
                f"<b style='color:#991b1b;'>{offen} ohne Vorlage</b> — "
                + Verdict.OHNE_VORLAGE.explanation
            )
        elif leichen:
            self.befund_label.setText(
                f"<b style='color:#92400e;'>{leichen} unbenutzt</b> — "
                + Verdict.KARTEILEICHE.explanation
            )
        else:
            self.befund_label.setText(
                "<b style='color:#166534;'>Alles zugeordnet.</b>"
            )
        _LOG.info("Textauszeichnungs-Inventar: %s", inventar.summary())

    def _fill_row(self, zeile: int, row: MarkupRow) -> None:
        werte = (
            f".{row.name}",
            row.origin,
            f"{row.book_count}×",
            row.styles[0] if row.styles else "—",
            row.verdict.label + (" (Altform)" if row.legacy_form else ""),
            row.todo or "—",
            _GESTALTET_ZEICHEN.get(row.styled, "—"),
            row.appearance or "—",
        )
        for spalte, text in enumerate(werte):
            item = QTableWidgetItem(text)
            if spalte == 2:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            if spalte == _SPALTE_BEFUND:
                item.setForeground(QBrush(QColor(_VERDICT_COLORS[row.verdict])))
            if spalte == _SPALTE_ZU_TUN and row.todo:
                # Die Handlungsspalte traegt die Dringlichkeit des Befundes --
                # sie ist die Zeile, an der man entlangliest.
                item.setForeground(QBrush(QColor(_VERDICT_COLORS[row.verdict])))
                schrift = item.font()
                schrift.setBold(True)
                item.setFont(schrift)
            item.setToolTip(self._tooltip(row))
            self.tabelle.setItem(zeile, spalte, item)

    @staticmethod
    def _tooltip(row: MarkupRow) -> str:
        teile = [row.verdict.explanation]
        if row.todo:
            teile.append(f"Nächster Schritt: {row.todo}")
        if row.styled is False:
            teile.append(
                "Das Format existiert, trägt aber keine eigene Gestaltung -- "
                "der Abschnitt sieht im Satz aus wie Fließtext."
            )
        if row.layouts:
            teile.append("Layouts: " + ", ".join(row.layouts))
        if row.files:
            gezeigt = ", ".join(row.files[:6])
            rest = "" if len(row.files) <= 6 else f" (+{len(row.files) - 6})"
            teile.append("Dateien: " + gezeigt + rest)
        if row.generator_count is not None:
            teile.append(f"Vom Generator gemeldet: {row.generator_count}×")
        return "\n".join(teile)

    # -- Aktionen je Zeile -------------------------------------------------
    def _row_at(self, zeile: int) -> Optional[MarkupRow]:
        if self._inventory is None or not (0 <= zeile < len(self._inventory.rows)):
            return None
        return self._inventory.rows[zeile]

    def _auf_doppelklick(self, zeile: int, _spalte: int) -> None:
        """Dorthin springen, wo man mit dieser Zeile weiterarbeitet.

        Gibt es Fundstellen, ist die Frage meistens *wie sieht das im Text
        aus* -- dann oeffnet der Doppelklick die Datei an der Fundstelle.
        Gibt es keine (Karteileiche), sitzt die einzige Spur im Layout.
        """
        row = self._row_at(zeile)
        if row is None:
            return
        # Der Doppelklick tut, was in "Zu tun" steht -- Anzeige und Aktion
        # duerfen nicht auseinanderlaufen. Steht dort nichts an, fuehrt er zur
        # Fundstelle im Text.
        if row.todo_targets_layout:
            self._layout_oeffnen(row)
        elif row.files:
            self._fundstelle_oeffnen(row)
        else:
            self._layout_oeffnen(row)

    def _auf_kontextmenue(self, punkt) -> None:
        zeile = self.tabelle.rowAt(punkt.y())
        row = self._row_at(zeile)
        if row is None:
            return
        menu = QMenu(self)
        if row.files:
            anzahl = len(row.files)
            datei_text = "Fundstelle öffnen …" if anzahl == 1 else f"Fundstelle öffnen … ({anzahl} Dateien)"
            menu.addAction(datei_text).triggered.connect(
                lambda _=False, r=row: self._fundstelle_oeffnen(r)
            )
        if row.layouts:
            ziel = row.layouts[0] if len(row.layouts) == 1 else ""
            beschriftung = (
                f"Vorlage im Layout „{ziel}“ ansehen …" if ziel
                else f"Vorlage ansehen … ({len(row.layouts)} Layouts)"
            )
            menu.addAction(beschriftung).triggered.connect(
                lambda _=False, r=row: self._layout_oeffnen(r)
            )
        else:
            menu.addAction("Absatzformat anlegen …").triggered.connect(
                lambda _=False, r=row: self._layout_oeffnen(r)
            )
        menu.addSeparator()
        menu.addAction("Klassennamen kopieren").triggered.connect(
            lambda _=False, r=row: self._namen_kopieren(r)
        )
        menu.exec(self.tabelle.viewport().mapToGlobal(punkt))

    def _fundstelle_oeffnen(self, row: MarkupRow) -> None:
        """Die Datei an der Fundstelle oeffnen -- Suchbegriff vorbelegt."""
        if self._book_path is None or not row.files:
            return
        datei = row.files[0]
        if len(row.files) > 1:
            gewaehlt, ok = QInputDialog.getItem(
                self,
                f".{row.name}",
                f"In welcher Datei? ({row.book_count}× im Buch)",
                list(row.files),
                0,
                False,
            )
            if not ok or not gewaehlt:
                return
            datei = gewaehlt
        pfad = self._book_path / datei
        if not pfad.is_file():
            QMessageBox.warning(self, "Fundstelle", f"Datei nicht gefunden:\n{pfad}")
            return
        try:
            from ui_qt.dialogs.text_dialogs import TextEditorDialog
        except ImportError as exc:
            QMessageBox.warning(self, "Fundstelle", f"Editor nicht verfügbar:\n{exc}")
            return
        dialog = TextEditorDialog(
            self,
            pfad,
            title="Fundstelle",
            initial_find_term=f".{row.name}",
            book_path=self._book_path,
        )
        dialog.exec()
        self.refresh()

    def _layout_oeffnen(self, row: MarkupRow) -> None:
        """Layout-Editor oeffnen -- wenn moeglich gleich auf dem richtigen Layout."""
        try:
            from ui_qt.dialogs.doclayout_editor_dialog import open_doclayout_editor_qt
        except ImportError as exc:
            QMessageBox.warning(self, "Layout-Editor", f"Nicht verfügbar:\n{exc}")
            return
        ziel = row.layouts[0] if len(row.layouts) == 1 else None
        open_doclayout_editor_qt(
            studio=self._studio,
            parent=self,
            book_path=self._book_path,
            select=ziel,
        )
        self.refresh()

    def _namen_kopieren(self, row: MarkupRow) -> None:
        from PySide6.QtWidgets import QApplication

        zwischenablage = QApplication.clipboard()
        if zwischenablage is not None:
            zwischenablage.setText(f".{row.name}")

    # -- Aktionen ----------------------------------------------------------
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
            # mitfuehren und deshalb wie Buchprojekte aussehen. Fuer das
            # Inventar sind sie die falsche Seite: Man pflegt das Layout an der
            # Quelle, nicht am Ausdruck.
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
        self.fill_book_choices()
        self.refresh()

    def _editor_oeffnen(self) -> None:
        try:
            from ui_qt.dialogs.doclayout_editor_dialog import open_doclayout_editor_qt
        except ImportError as exc:
            QMessageBox.warning(self, "Layout-Editor", f"Nicht verfügbar:\n{exc}")
            return
        open_doclayout_editor_qt(
            studio=self._studio, parent=self, book_path=self._book_path
        )
        self.refresh()

    @property
    def inventory(self) -> Optional[MarkupInventory]:
        return self._inventory


def open_markup_inventory_qt(
    studio: Any = None, parent: Optional[QWidget] = None, **kwargs: Any
) -> int:
    """Entrypoint fuer den Plugin-Adapter."""
    book_path = kwargs.get("book_path")
    if book_path is None and studio is not None:
        # ``current_book`` zuerst: Das ist der Name, unter dem das aktive Buch
        # am Studio-Objekt haengt (``ui_qt/studio_bridge.py``, ``ui_qt/facade.py``).
        # Frueher stand hier nur ``book_path`` -- ein Attribut, das es dort nie
        # gab. Der Ausdruck lieferte damit immer ``None``, und das Werkzeug
        # fragte jedes Mal nach dem Buch, obwohl Book Studio es kannte.
        book_path = getattr(studio, "current_book", None) or getattr(
            studio, "book_path", None
        )
    dialog = MarkupInventoryDialog(
        Path(book_path) if book_path else None, studio=studio, parent=parent
    )
    dialog.exec()
    return 0


__all__ = ["MarkupInventoryDialog", "open_markup_inventory_qt"]
