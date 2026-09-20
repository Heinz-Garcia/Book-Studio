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
    QFrame,
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
    StylePreview,
    Verdict,
    build_markup_inventory,
)
from ui_qt.autonomous_window import (
    apply_persisted_size,
    persist_window_size,
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)

_LOG = logging.getLogger(__name__)

#: Farbe je Befund -- nur fuer die Befundspalte, nicht fuer die ganze Zeile.
_VERDICT_COLORS = {
    Verdict.OHNE_VORLAGE: "#991b1b",
    # Karteileiche: klares Blauviolett — nicht braun neben dem Rot der Lücken.
    Verdict.KARTEILEICHE: "#6d28d9",
    Verdict.OK: "#166534",
    Verdict.QUARTO: "#475569",
}

_SPALTEN = (
    "Auszeichnung", "kommt aus", "im Buch", "Vorlage", "Befund",
    "Zu tun", "gestaltet?", "Erbfolge",
)

#: Erklaerung je Spaltenkopf (Tooltip) -- besonders "kommt aus".
_SPALTEN_TIPPS = (
    "Markdown-Klasse eines Fenced-Divs (::: {.name}). "
    "Nur Absatz-Auszeichnungen — keine Zeichenformate (fett/kursiv im Fließtext).",
    "Buchtext = steht jetzt in den Kapiteln (nachgezählt).\n"
    "Import-Meldung = beim Übernehmen aus Pitugrafo hat der Import "
    "mitgeschrieben: „diese Kästen habe ich geliefert“ — wie ein Lieferschein.\n"
    "Kann vom heutigen Buch abweichen (gelöscht, umbenannt, nie angekommen).\n"
    "Layout(s) = in der Format-Bibliothek schon zugeordnet.",
    "Wie oft die Klasse im aktuellen Buch vorkommt (Scan der Kapitel).",
    "Zugeordnetes Absatzformat in der Vorlage (reference.docx).",
    "Bewertung: fehlt Vorlage, Quarto-Builtin, ok, unbenutzt …",
    "Nächster Schritt für diese Zeile.",
    "Ob das Absatzformat eigene Gestaltung trägt (nicht nur Name).",
    "based_on-Kette und Folgeformat (Enter).",
)

#: Spalte, in der die naechste Handlung steht -- sie wird hervorgehoben.
_SPALTE_ZU_TUN = 5
_SPALTE_BEFUND = 4
_SPALTE_ERBFOLGE = 7
#: Sortierschluessel neben dem Anzeigenamen (UserRole = Klassenname).
_ROLE_NAME = int(Qt.ItemDataRole.UserRole)
_ROLE_SORT = int(Qt.ItemDataRole.UserRole) + 1

#: Kurzzeichen der Spalte "gestaltet?": Haken, Kreuz, oder nichts zu sagen.
_GESTALTET_ZEICHEN = {True: "✓", False: "✗", None: "—"}

#: Probe-Bereich: Elfenbein / hellgelb (Papier-Anmutung).
_PROBE_BG = "#fffbeb"
_PROBE_BORDER = "#fde68a"

#: Letzter Eintrag der Auswahlliste -- der Ausweg fuer alles Unbekannte.
_ANDERES_VERZEICHNIS = "Anderes Verzeichnis …"

# v2: breiter + Detailbereich; alte gespeicherte Groesse sonst zu schmal.
_SIZE_KEY = "doclayout_markup_inventory_size_v2"
_DEFAULT_SIZE = (980, 640)
_MIN_SIZE = (760, 480)
_active: list["MarkupInventoryDialog"] = []


class _SortItem(QTableWidgetItem):
    """Anzeige-Text sortiert nach ``_ROLE_SORT`` (Zahl oder Kleinbuchstaben)."""

    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        links = self.data(_ROLE_SORT)
        rechts = other.data(_ROLE_SORT)
        if links is not None and rechts is not None:
            try:
                return links < rechts
            except TypeError:
                pass
        return super().__lt__(other)


class MarkupInventoryDialog(QDialog):
    """Tabelle aller Textauszeichnungen eines Buchprojekts."""

    def __init__(
        self,
        book_path: Optional[Path] = None,
        *,
        studio: Any = None,
        parent: Optional[QWidget] = None,
        focus_gaps: bool = False,
    ) -> None:
        super().__init__(None)
        self._studio = studio
        self._book_path = Path(book_path) if book_path else None
        self._inventory: Optional[MarkupInventory] = None
        self._display_rows: list[MarkupRow] = []
        self._focus_gaps = bool(focus_gaps)
        self.setWindowTitle("Textauszeichnungs-Inventar")
        apply_persisted_size(
            self, _SIZE_KEY, default=_DEFAULT_SIZE, min_size=_MIN_SIZE
        )
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
        prepare_autonomous_window(self, parent)

    def done(self, result: int) -> None:
        persist_window_size(self, _SIZE_KEY)
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt-Vertrag
        # Wie Hilfe/Editor: auch beim Fensterkreuz speichern (nicht nur accept).
        persist_window_size(self, _SIZE_KEY)
        super().closeEvent(event)

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

        self.umfang_hint = QLabel(
            "Nur Absatz-Auszeichnungen (::: {.klasse} → Word-Absatzformat). "
            "Zeichenformate (fett/kursiv im Fließtext) gehören nicht hierher."
        )
        self.umfang_hint.setStyleSheet("QLabel { color: #64748b; font-size: 11px; }")
        self.umfang_hint.setWordWrap(True)
        layout.addWidget(self.umfang_hint)

        self.tabelle = QTableWidget(0, len(_SPALTEN), self)
        self.tabelle.setHorizontalHeaderLabels(list(_SPALTEN))
        for spalte, tipp in enumerate(_SPALTEN_TIPPS):
            item = self.tabelle.horizontalHeaderItem(spalte)
            if item is not None:
                item.setToolTip(tipp)
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabelle.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabelle.setAlternatingRowColors(True)
        self.tabelle.setWordWrap(True)
        # Sortierung erst nach Klick auf den Spaltenkopf -- sonst zerstoert
        # Alphabetsortierung die Luecken-zuerst-Reihenfolge beim Befuellen.
        self.tabelle.setSortingEnabled(False)
        self.tabelle.horizontalHeader().setSortIndicatorShown(True)
        self.tabelle.horizontalHeader().sectionClicked.connect(self._auf_spaltenkopf)
        self.tabelle.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        kopf.setSectionResizeMode(_SPALTE_ERBFOLGE, QHeaderView.ResizeMode.Stretch)
        kopf.setStretchLastSection(True)
        # Doppelklick fuehrt dorthin, wo man mit dieser Zeile weiterarbeitet:
        # zur Fundstelle im Text, oder -- wenn es keine gibt -- zur Vorlage im
        # Layout-Editor. Rechtsklick bietet beides plus den Namen zum Kopieren.
        self.tabelle.cellDoubleClicked.connect(self._auf_doppelklick)
        self.tabelle.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabelle.customContextMenuRequested.connect(self._auf_kontextmenue)
        self.tabelle.itemSelectionChanged.connect(self._auf_auswahl)
        layout.addWidget(self.tabelle, 1)

        # Detailbereich: Aussehen, Probe und Bewertung -- immer sichtbar,
        # nicht am rechten Tabellenrand versteckt.
        detail = QFrame()
        detail.setObjectName("markupInventoryDetail")
        detail.setStyleSheet(
            "QFrame#markupInventoryDetail {"
            "  background: #f8fafc; border: 1px solid #e2e8f0;"
            "  border-radius: 6px;"
            "}"
        )
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(12, 10, 12, 10)
        detail_layout.setSpacing(6)

        self.detail_title = QLabel("Zeile wählen — dann erscheinen Aussehen, Probe und Bewertung.")
        self.detail_title.setStyleSheet("font-weight: 700; color: #1c2740;")
        detail_layout.addWidget(self.detail_title)

        self.detail_snippets = QLabel("")
        self.detail_snippets.setWordWrap(True)
        self.detail_snippets.setStyleSheet(
            "color: #475569; font-style: italic; padding: 2px 0 4px 0;"
        )
        self.detail_snippets.hide()
        detail_layout.addWidget(self.detail_snippets)

        self.detail_erbfolge = QLabel("")
        self.detail_erbfolge.setWordWrap(True)
        self.detail_erbfolge.setStyleSheet("color: #334155;")
        detail_layout.addWidget(self.detail_erbfolge)

        self.detail_aussehen = QLabel("")
        self.detail_aussehen.setWordWrap(True)
        self.detail_aussehen.setStyleSheet("color: #334155;")
        detail_layout.addWidget(self.detail_aussehen)

        self.detail_bewertung = QLabel("")
        self.detail_bewertung.setWordWrap(True)
        self.detail_bewertung.setStyleSheet(
            "color: #1e3a5f; background: #eef6ff; border-left: 3px solid #2f5cc8;"
            " padding: 6px 8px;"
        )
        detail_layout.addWidget(self.detail_bewertung)

        defaults_zeile = QHBoxLayout()
        defaults_zeile.setSpacing(8)
        from tools.doclayout.print_defaults import PRINT_DEFAULTS_LABEL

        self.btn_druck_defaults = QPushButton("Druck-Defaults übernehmen")
        self.btn_druck_defaults.setToolTip(
            "Ein Klick: sinnvolle Taschenbuch-Vorgaben auf das Layout schreiben.\n"
            f"{PRINT_DEFAULTS_LABEL}\n"
            "Fließtext (BodyText): Blocksatz, Zeilenabstand 1,2."
        )
        self.btn_druck_defaults.clicked.connect(self._druck_defaults_uebernehmen)
        self.btn_druck_defaults.hide()
        defaults_zeile.addWidget(self.btn_druck_defaults)
        defaults_zeile.addStretch(1)
        detail_layout.addLayout(defaults_zeile)

        self.detail_probe_host = QWidget()
        probe_box = QVBoxLayout(self.detail_probe_host)
        probe_box.setContentsMargins(0, 4, 0, 0)
        probe_box.setSpacing(2)
        probe_caption = QLabel("Probe (wirksames Format):")
        probe_caption.setStyleSheet("color: #92400e; font-size: 11px; font-weight: 600;")
        probe_box.addWidget(probe_caption)
        self.detail_probe = QLabel("—")
        self.detail_probe.setWordWrap(True)
        self.detail_probe.setMinimumHeight(56)
        self.detail_probe.setStyleSheet(
            f"QLabel {{ background: {_PROBE_BG}; border: 1px solid {_PROBE_BORDER};"
            f" padding: 8px; color: #64748b; }}"
        )
        probe_box.addWidget(self.detail_probe)
        detail_layout.addWidget(self.detail_probe_host)

        layout.addWidget(detail)

        self.befund_label = QLabel("")
        self.befund_label.setWordWrap(True)
        self.befund_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.befund_label)

        knopfleiste = QHBoxLayout()
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(
            knopfleiste, tool_key="markup_inventory", host=self
        )
        self.btn_aktualisieren = QPushButton("Aktualisieren")
        self.btn_aktualisieren.clicked.connect(self.refresh)
        knopfleiste.addWidget(self.btn_aktualisieren)
        knopfleiste.addStretch(1)

        self.btn_fehlende = QPushButton("Fehlende Formate anlegen…")
        self.btn_fehlende.setToolTip(
            "Öffnet den Layout-Editor bei der Klassen-Abbildung und zeigt "
            "den Buchabgleich — dort „Fehlende Klassen anlegen“."
        )
        self.btn_fehlende.clicked.connect(self._fehlende_anlegen)
        self.btn_fehlende.hide()
        knopfleiste.addWidget(self.btn_fehlende)

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

    def _auf_spaltenkopf(self, spalte: int) -> None:
        """Erster Klick aktiviert Sortierung; weitere Klicks drehen die Richtung."""
        kopf = self.tabelle.horizontalHeader()
        if not self.tabelle.isSortingEnabled():
            self.tabelle.setSortingEnabled(True)
        # Qt setzt den Indikator beim sectionClicked nicht immer selbst um,
        # wenn vorher -1 (unsortiert) war -- dann explizit aufsteigend sortieren.
        if kopf.sortIndicatorSection() != spalte:
            self.tabelle.sortItems(spalte, Qt.SortOrder.AscendingOrder)
            kopf.setSortIndicator(spalte, Qt.SortOrder.AscendingOrder)

    # -- Daten -------------------------------------------------------------
    def refresh(self) -> None:
        """Inventar neu erheben und anzeigen."""
        if self._book_path is None:
            self.buch_label.setText(
                "Kein Buchprojekt gewählt — oben in der Liste wählen "
                "oder über Ansicht → Arbeitsweg → Bücher verwalten."
            )
            return
        try:
            self._inventory = build_markup_inventory(self._book_path)
        except OSError as exc:
            QMessageBox.warning(self, "Inventar", f"Buch nicht lesbar:\n{exc}")
            return
        self._fill(self._inventory)

    def _fill(self, inventar: MarkupInventory) -> None:
        quelle = (
            f" · Import-Meldung von {inventar.generator_source}"
            if inventar.generator_source
            else ""
        )
        self.buch_label.setText(f"Buch: {inventar.book_path}{quelle}")
        if inventar.generator_source:
            self.buch_label.setToolTip(
                "Beim letzten Übernehmen aus Pitugrafo/GrammarGraph hat der "
                "Import eine Liste mitgeliefert: welche Text-Kästen "
                "(::: {.…}) er geliefert hat — wie ein Lieferschein.\n\n"
                "Spalte „kommt aus“:\n"
                "• Buchtext = steht jetzt wirklich in den Kapiteln\n"
                "• Import-Meldung = stand auf dem Lieferschein\n\n"
                "Beides kann auseinanderlaufen: etwas wurde gelöscht, "
                "umbenannt oder nie übernommen — dann siehst du "
                "Import-Meldung bei 0× im Buch."
            )
        else:
            self.buch_label.setToolTip(
                "Kein Inhalts-Import mit Klassenliste hinterlegt. "
                "„kommt aus“ zeigt dann nur Buchtext und/oder Layouts."
            )

        rows = list(inventar.rows)
        if self._focus_gaps:
            # Lücken zuerst — Arbeitsweg springt hierhin zum Zuordnen.
            rows.sort(
                key=lambda r: (
                    0 if r.verdict is Verdict.OHNE_VORLAGE else 1,
                    r.name.lower(),
                )
            )
        self._display_rows = rows
        # Waehrend des Befuellens Sortierung aus -- sonst verrutschen Zeilen
        # unter der Schleife (wie Mapping-Manager).
        self.tabelle.setSortingEnabled(False)
        self.tabelle.setRowCount(len(rows))
        for zeile, row in enumerate(rows):
            self._fill_row(zeile, row)
        self.tabelle.resizeColumnsToContents()
        # Sortierung wieder an, ohne sofort umzusortieren (Indikator -1).
        self.tabelle.horizontalHeader().setSortIndicator(
            -1, Qt.SortOrder.AscendingOrder
        )
        self.tabelle.setSortingEnabled(True)
        if rows:
            # Erste Zeile mit Vorlage anwählen — Detailbereich sofort sichtbar.
            ziel = next(
                (i for i, r in enumerate(rows) if r.preview is not None),
                0,
            )
            self.tabelle.selectRow(ziel)
            self._show_detail(rows[ziel])
        else:
            self._clear_detail()

        offen = len(inventar.without_template)
        leichen = len(inventar.orphans)
        self.btn_fehlende.setVisible(offen > 0)
        if offen:
            self.btn_fehlende.setText(f"Fehlende Formate anlegen… ({offen})")
        else:
            self.btn_fehlende.setText("Fehlende Formate anlegen…")

        if offen:
            self.befund_label.setText(
                f"<b style='color:#991b1b;'>{offen} ohne Vorlage</b> — "
                + Verdict.OHNE_VORLAGE.explanation
            )
        elif leichen:
            self.befund_label.setText(
                f"<b style='color:{_VERDICT_COLORS[Verdict.KARTEILEICHE]};'>"
                f"{leichen} unbenutzt</b> — "
                + Verdict.KARTEILEICHE.explanation
            )
        else:
            self.befund_label.setText(
                "<b style='color:#166534;'>Alles zugeordnet.</b>"
            )
        if self._focus_gaps and offen:
            self._select_first_gap()
        _LOG.info("Textauszeichnungs-Inventar: %s", inventar.summary())

    def _select_first_gap(self) -> None:
        """Erste Zeile ohne Vorlage markieren und in Sicht scrollen."""
        for zeile in range(self.tabelle.rowCount()):
            row = self._row_at(zeile)
            if row is None or row.verdict is not Verdict.OHNE_VORLAGE:
                continue
            self.tabelle.selectRow(zeile)
            item = self.tabelle.item(zeile, 0)
            if item is not None:
                self.tabelle.scrollToItem(item)
            return

    def apply_focus_gaps(self) -> None:
        """Arbeitsweg: Lücken nach oben und erste Lücke anwählen."""
        self._focus_gaps = True
        if self._inventory is not None:
            self._fill(self._inventory)
        else:
            self.refresh()

    def _fill_row(self, zeile: int, row: MarkupRow) -> None:
        vorschau = row.preview
        erbfolge = vorschau.inheritance if vorschau else "—"
        befund = row.verdict.label + (" (Altform)" if row.legacy_form else "")
        zu_tun = row.todo or "—"
        gestaltet = _GESTALTET_ZEICHEN.get(row.styled, "—")
        vorlage = ", ".join(row.styles) if row.styles else "—"
        anzeige = (
            (f".{row.name}", row.name.lower()),
            (row.origin, row.origin.lower()),
            (f"{row.book_count}×", row.book_count),
            (vorlage, vorlage.lower()),
            (befund, befund.lower()),
            (zu_tun, zu_tun.lower()),
            (gestaltet, gestaltet),
            (erbfolge, erbfolge.lower()),
        )
        tip = self._tooltip(row)
        for spalte, (text, sort_key) in enumerate(anzeige):
            self.tabelle.removeCellWidget(zeile, spalte)
            item = _SortItem(text)
            item.setData(_ROLE_NAME, row.name)
            item.setData(_ROLE_SORT, sort_key)
            if spalte == 2:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            if spalte == _SPALTE_BEFUND:
                item.setForeground(QBrush(QColor(_VERDICT_COLORS[row.verdict])))
            item.setToolTip(tip)
            self.tabelle.setItem(zeile, spalte, item)
            if spalte == _SPALTE_ZU_TUN and row.todo:
                self.tabelle.setCellWidget(
                    zeile, spalte, self._todo_button(row)
                )

    def _auf_auswahl(self) -> None:
        """Detailbereich mit Aussehen, Probe und Bewertung der gewählten Zeile."""
        ausgewaehlt = self.tabelle.selectedIndexes()
        if not ausgewaehlt:
            self._clear_detail()
            return
        zeile = ausgewaehlt[0].row()
        row = self._row_at(zeile)
        if row is None:
            self._clear_detail()
            return
        self._show_detail(row)

    def _clear_detail(self) -> None:
        self.detail_title.setText(
            "Zeile wählen — dann erscheinen Aussehen, Probe und Bewertung."
        )
        self.detail_title.setToolTip("")
        self.detail_snippets.setText("")
        self.detail_snippets.hide()
        self.detail_erbfolge.setText("")
        self.detail_aussehen.setText("")
        self.detail_bewertung.setText("")
        self.detail_bewertung.hide()
        self.btn_druck_defaults.hide()
        self.detail_probe.setText("—")
        self.detail_probe.setStyleSheet(
            f"QLabel {{ background: {_PROBE_BG}; border: 1px solid {_PROBE_BORDER};"
            f" padding: 8px; color: #64748b; }}"
        )

    def _fill_snippets(self, row: MarkupRow) -> None:
        """Buchzitate unter dem Namen -- dieselben wie im Zeilen-Tooltip."""
        if not row.snippets:
            self.detail_snippets.setText("")
            self.detail_snippets.hide()
            self.detail_title.setToolTip("")
            return
        # Kurzform im Detail; vollstaendig im Tooltip der Zeile und des Titels.
        erste = row.snippets[0]
        if ": " in erste:
            erste = erste.split(": ", 1)[1]
        mehr = f" (+{len(row.snippets) - 1})" if len(row.snippets) > 1 else ""
        self.detail_snippets.setText(f"Im Buch: «{erste}»{mehr}")
        self.detail_snippets.show()
        tip = "Im Buch:\n" + "\n".join(f"• {s}" for s in row.snippets)
        self.detail_title.setToolTip(tip)
        self.detail_snippets.setToolTip(tip)

    def _show_detail(self, row: MarkupRow) -> None:
        self.detail_title.setText(f".{row.name}")
        self._fill_snippets(row)
        vorschau = row.preview
        if vorschau is None:
            self.detail_erbfolge.setText("Erbfolge: — (keine Vorlage in der Bibliothek)")
            eigen = f"Eigenes Aussehen: {row.appearance}" if row.appearance else ""
            self.detail_aussehen.setText(eigen or "Aussehen: —")
            self.detail_bewertung.hide()
            self.detail_bewertung.setText("")
            self.btn_druck_defaults.hide()
            self.detail_probe.setText("—")
            self.detail_probe.setStyleSheet(
                f"QLabel {{ background: {_PROBE_BG}; border: 1px solid {_PROBE_BORDER};"
                f" padding: 8px; color: #64748b; }}"
            )
            return

        self.detail_erbfolge.setText(f"Erbfolge: {vorschau.inheritance or '—'}")
        eigen = f" (eigen: {row.appearance})" if row.appearance else ""
        self.detail_aussehen.setText(
            f"Aussehen (wirksam): {vorschau.effective_appearance or '—'}{eigen}"
        )
        if vorschau.layout_comment:
            self.detail_bewertung.setText(f"Bewertung: {vorschau.layout_comment}")
            self.detail_bewertung.show()
        else:
            self.detail_bewertung.hide()
            self.detail_bewertung.setText("")

        layout_name = vorschau.layout_name or (
            row.layouts[0] if len(row.layouts) == 1 else ""
        )
        if layout_name and not vorschau.print_defaults_applied:
            from tools.doclayout.print_defaults import PRINT_DEFAULTS_LABEL

            self.btn_druck_defaults.setText(
                f"Druck-Defaults übernehmen ({layout_name})"
            )
            self.btn_druck_defaults.setToolTip(
                "Schreibt die Taschenbuch-Vorgaben in dieses Layout:\n"
                f"{PRINT_DEFAULTS_LABEL}\n"
                "BodyText: Blocksatz, Zeilenabstand 1,2 (falls noch leer)."
            )
            self.btn_druck_defaults.setProperty("layoutName", layout_name)
            self.btn_druck_defaults.show()
        else:
            self.btn_druck_defaults.hide()

        probe = self._probe_label(vorschau)
        self.detail_probe.setText(probe.text())
        self.detail_probe.setStyleSheet(probe.styleSheet())
        self.detail_probe.setToolTip(probe.toolTip())

    def _druck_defaults_uebernehmen(self) -> None:
        """Ein Klick: Taschenbuch-Defaults auf das Vorschau-Layout schreiben."""
        from tools.doclayout.print_defaults import apply_print_defaults_to_layout

        layout_name = str(
            self.btn_druck_defaults.property("layoutName") or ""
        ).strip()
        if not layout_name:
            indexes = self.tabelle.selectedIndexes()
            if indexes:
                row = self._row_at(indexes[0].row())
                if row is not None and row.preview and row.preview.layout_name:
                    layout_name = row.preview.layout_name
                elif row is not None and row.layouts:
                    layout_name = row.layouts[0]
        if not layout_name:
            QMessageBox.information(
                self,
                "Druck-Defaults",
                "Kein Layout ermittelt — zuerst eine Auszeichnung mit Vorlage wählen.",
            )
            return
        antwort = QMessageBox.question(
            self,
            "Druck-Defaults übernehmen",
            f"Layout „{layout_name}“ auf Taschenbuch-Defaults setzen?\n\n"
            "• Fließtext-Schrift: Cambria (Serife)\n"
            "• Überschriften: Calibri\n"
            "• 11 pt, Zeilenabstand 1,2\n"
            "• BodyText: Blocksatz (falls noch ohne Ausrichtung)\n\n"
            "Die Datei in der Layout-Bibliothek wird überschrieben.",
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        ok, message = apply_print_defaults_to_layout(layout_name)
        if not ok:
            QMessageBox.warning(self, "Druck-Defaults", message)
            return
        self.refresh()
        QMessageBox.information(self, "Druck-Defaults", message)

    def _probe_label(self, vorschau: StylePreview) -> QLabel:
        """Lorem-Ipsum-Absatz im wirksamen Format (naeherungsweise per QSS)."""
        label = QLabel(vorschau.sample_text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        farbe = f"#{vorschau.color_hex}" if vorschau.color_hex else "#1e293b"
        # Ohne eigene Hinterlegung: Elfenbein als „Papier“ der Probe.
        hintergrund = (
            f"#{vorschau.shading_hex}" if vorschau.shading_hex else _PROBE_BG
        )
        gewicht = "700" if vorschau.bold else "400"
        stil = "italic" if vorschau.italic else "normal"
        ausrichtung = {
            "center": "center",
            "right": "right",
            "justify": "justify",
        }.get(vorschau.align, "left")
        # pt ≈ px bei 96dpi-Desktop; fuer die Inventar-Probe ausreichend.
        groesse = max(9.0, min(float(vorschau.size_pt), 22.0))
        oben = max(0, int(round(vorschau.space_before_pt)))
        unten = max(0, int(round(vorschau.space_after_pt)))
        font = vorschau.font_family.replace("'", "")
        label.setStyleSheet(
            f"QLabel {{"
            f"  font-family: '{font}';"
            f"  font-size: {groesse:.0f}pt;"
            f"  font-weight: {gewicht};"
            f"  font-style: {stil};"
            f"  color: {farbe};"
            f"  background-color: {hintergrund};"
            f"  text-align: {ausrichtung};"
            f"  padding: {oben}px 6px {unten}px 6px;"
            f"  border: 1px solid {_PROBE_BORDER};"
            f"}}"
        )
        label.setMinimumWidth(220)
        label.setToolTip(
            f"Wirksam: {vorschau.effective_appearance or '—'}\n"
            f"Erbfolge: {vorschau.inheritance or '—'}"
        )
        return label

    def _todo_button(self, row: MarkupRow) -> QWidget:
        """Aktionsknopf in „Zu tun“ — führt genau den angezeigten Schritt aus."""
        host = QWidget()
        row_layout = QHBoxLayout(host)
        row_layout.setContentsMargins(2, 2, 2, 2)
        row_layout.setSpacing(0)
        btn = QPushButton(row.todo)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        farbe = _VERDICT_COLORS.get(row.verdict, "#334155")
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {farbe}; color: #ffffff; font-weight: 600;"
            f"  border: none; border-radius: 4px; padding: 4px 10px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {farbe}; }}"
        )
        btn.setToolTip(
            f"Führt aus: {row.todo}\n"
            + (
                "Entfernt die unbenutzte Klasse aus der Layout-Bibliothek."
                if row.verdict is Verdict.KARTEILEICHE
                else "Öffnet den Layout-Editor an der richtigen Stelle."
            )
        )
        name = row.name
        btn.clicked.connect(lambda _=False, n=name: self._todo_ausfuehren(n))
        row_layout.addWidget(btn)
        row_layout.addStretch(1)
        return host

    def _todo_ausfuehren(self, name_oder_zeile: Any) -> None:
        """Aktion aus der Spalte „Zu tun“ für diese Klasse (Name oder Zeilenindex)."""
        if isinstance(name_oder_zeile, int):
            row = self._row_at(name_oder_zeile)
        else:
            row = self._row_by_name(str(name_oder_zeile))
        if row is None or not row.todo:
            return
        befund = row.verdict
        if befund is Verdict.OHNE_VORLAGE:
            self._format_anlegen(row)
            return
        if befund is Verdict.KARTEILEICHE:
            self._orphan_pruefen(row)
            return
        if row.todo == "Gestalten" and row.styles:
            self._gestalten(row)
            return
        if row.todo == "Vorlage vereinheitlichen":
            self._layout_oeffnen(row)
            return
        # Fallback: Fundstelle oder Editor
        if row.files:
            self._fundstelle_oeffnen(row)
        else:
            self._layout_oeffnen(row)

    def _open_layout_editor(self, **kwargs: Any) -> None:
        """Layout-Editor im Auftrag des Inventars -- nach Anwenden zurück hierher."""
        try:
            from ui_qt.dialogs.doclayout_editor_dialog import open_doclayout_editor_qt
        except ImportError as exc:
            QMessageBox.warning(self, "Layout-Editor", f"Nicht verfügbar:\n{exc}")
            return
        open_doclayout_editor_qt(
            studio=self._studio,
            parent=self,
            book_path=self._book_path,
            return_after_apply=True,
            on_closed=self._nach_editor_zurueck,
            **kwargs,
        )

    def _nach_editor_zurueck(self, *_args: Any) -> None:
        """Inventar aktualisieren und nach vorn holen (Auftragskette zu)."""
        self.refresh()
        self.raise_()
        self.activateWindow()

    def _format_anlegen(self, row: MarkupRow) -> None:
        """Fehlende Klasse: Layout-Editor → Klassen-Abbildung → Format anlegen."""
        ziel = row.layouts[0] if len(row.layouts) == 1 else None
        self._open_layout_editor(
            select=ziel,
            focus_unmapped=True,
            focus_class=row.name,
        )

    def _gestalten(self, row: MarkupRow) -> None:
        """Existierendes Format öffnen und im Editor gestalten."""
        style = row.styles[0] if row.styles else None
        ziel = row.layouts[0] if len(row.layouts) == 1 else None
        self._open_layout_editor(
            select=ziel,
            focus_style=style,
        )

    def _orphan_pruefen(self, row: MarkupRow) -> None:
        """Karteileiche streichen: aus Bibliothek entfernen und Liste aktualisieren."""
        from tools.doclayout.markup_inventory import remove_unused_class_from_library

        layouts = row.layouts or ()
        layout_hinweis = (
            f"\n\nLayouts: {', '.join(layouts)}" if layouts else ""
        )
        antwort = QMessageBox.question(
            self,
            "Karteileiche streichen",
            f".{row.name} kommt 0× im Buch vor.\n\n"
            f"Eintrag aus der Layout-Bibliothek entfernen "
            f"(Klassen-Abbildung und ggf. Absatzformat)?{layout_hinweis}",
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        ok, message = remove_unused_class_from_library(
            row.name, layout_names=layouts or None
        )
        if not ok:
            QMessageBox.warning(self, "Streichen", message)
            return
        self.refresh()

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
        if row.preview and row.preview.inheritance:
            teile.append(f"Erbfolge: {row.preview.inheritance}")
        if row.appearance:
            teile.append(f"Eigenes Aussehen: {row.appearance}")
        if row.preview and row.preview.effective_appearance:
            teile.append(f"Wirksam (mit Erbe): {row.preview.effective_appearance}")
        if row.preview and row.preview.layout_comment:
            teile.append(f"Bewertung: {row.preview.layout_comment}")
        if row.snippets:
            teile.append("Im Buch:")
            for i, snip in enumerate(row.snippets, start=1):
                teile.append(f"  {i}. {snip}")
        if row.layouts:
            teile.append("Layouts: " + ", ".join(row.layouts))
        if row.files:
            gezeigt = ", ".join(row.files[:6])
            rest = "" if len(row.files) <= 6 else f" (+{len(row.files) - 6})"
            teile.append("Dateien: " + gezeigt + rest)
        if row.generator_count is not None:
            teile.append(
                f"Import-Meldung: {row.generator_count}× "
                "(Lieferschein vom Pitugrafo-Übernehmen — nicht nachgezählt)"
            )
        return "\n".join(teile)

    # -- Aktionen je Zeile -------------------------------------------------
    def _row_by_name(self, name: str) -> Optional[MarkupRow]:
        name = name.lstrip(".").strip()
        if self._inventory is not None:
            for row in self._inventory.rows:
                if row.name == name:
                    return row
        for row in self._display_rows:
            if row.name == name:
                return row
        return None

    def _row_at(self, zeile: int) -> Optional[MarkupRow]:
        """Zeile der Tabelle → MarkupRow (auch nach Umsortieren korrekt)."""
        item = self.tabelle.item(zeile, 0)
        if item is None:
            return None
        name = item.data(_ROLE_NAME)
        if isinstance(name, str) and name:
            return self._row_by_name(name)
        if 0 <= zeile < len(self._display_rows):
            return self._display_rows[zeile]
        return None

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
        ziel = row.layouts[0] if len(row.layouts) == 1 else None
        self._open_layout_editor(select=ziel)

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
        self._open_layout_editor()

    def _fehlende_anlegen(self) -> None:
        """Layout-Editor mit Fokus auf Klassen-Abbildung und Buchabgleich."""
        self._open_layout_editor(focus_unmapped=True)

    @property
    def inventory(self) -> Optional[MarkupInventory]:
        return self._inventory


def open_markup_inventory_qt(
    studio: Any = None, parent: Optional[QWidget] = None, **kwargs: Any
) -> int:
    """Entrypoint fuer den Plugin-Adapter."""
    focus_gaps = bool(kwargs.get("focus_gaps"))
    existing = raise_if_open(_active, lambda _d: True)
    if existing is not None:
        if focus_gaps:
            existing.apply_focus_gaps()
        return 0
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
        Path(book_path) if book_path else None,
        studio=studio,
        parent=parent,
        focus_gaps=focus_gaps,
    )
    show_autonomous_window(dialog, _active)
    return 0


__all__ = ["MarkupInventoryDialog", "open_markup_inventory_qt"]
