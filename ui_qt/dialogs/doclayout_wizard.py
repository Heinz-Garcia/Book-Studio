"""Assistent: systematisch durch alle Formatierungsobjekte eines Buches.

Der Layout-Editor zeigt, was ein Layout **hat**. Dieser Assistent geht von der
anderen Seite heran: Er liest das Buch und fuehrt durch das, was darin
**vorkommt** -- Ueberschriften, Listen, Zitate, Codebloecke, Fussnoten, die
eigenen Klassen. Nur was da ist; nichts auf Vorrat.

Zwei Wege durch dasselbe Material, umschaltbar:

* **Nach Formatierungsobjekt** -- jedes genau einmal, ueber das ganze
  Buch.
  Kurz, ohne Wiederholung, gut zum Fertigwerden.
* **Nach Kapitel** -- das Buch in Lesereihenfolge. Laenger, dafuer im
  Zusammenhang: man sieht, womit ein Kapitel tatsaechlich gebaut ist.

Welcher Weg besser passt, entscheidet sich in der Benutzung. Deshalb steht der
Umschalter oben und nicht in einer Einstellung.

**Wichtig in der Kapitelansicht:** Ein Absatzformat gilt im ganzen Buch. Wer es
in Kapitel 3 aendert, aendert es ueberall. Der Dialog sagt das ausdruecklich --
ohne diesen Hinweis waere die Ansicht eine Falle.

Nur Widgets: Was gezaehlt und zugeordnet wird, steht in
``tools.doclayout.inventory`` (siehe ``.doc/gui_architektur.md``).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from services.constants import StatusFg
from tools.doclayout.inventory import (
    STATUS_LABELS,
    Finding,
    Inventory,
    Step,
    open_findings,
    scan_inventory,
    steps_by_chapter,
    steps_by_type,
)
from tools.doclayout.schema import LayoutDefinition, LayoutError, ParagraphStyle
from tools.doclayout.usage import suggested_style_id
from ui_qt.dialogs.doclayout_style_form import _StyleForm

_LOG = logging.getLogger(__name__)

#: Ansichten des Assistenten. Die Reihenfolge ist die im Auswahlfeld.
VIEW_BY_TYPE = "type"
VIEW_BY_CHAPTER = "chapter"
VIEWS = (
    (VIEW_BY_TYPE, "Nach Formatierungsobjekt — jedes einmal"),
    (VIEW_BY_CHAPTER, "Nach Kapitel — das Buch der Reihe nach"),
)

#: Farbe je Zustand. Bewusst dieselben Rollen wie im Editor.
_STATUS_COLORS = {
    "ok": StatusFg.SUCCESS,
    # Kein Alarm: Die Vorlage steht, sie ist nur noch nicht gestaltet.
    "plain": StatusFg.NEUTRAL,
    "missing": "#b45309",
    "unmapped": "#b45309",
    "nothing": StatusFg.NEUTRAL,
}


class DocLayoutWizard(QDialog):
    """Fuehrt durch die Formatierungsobjekte eines Buches."""

    def __init__(
        self,
        parent: Optional[QWidget],
        definition: LayoutDefinition,
        book_path: Path,
        save: Optional[Callable[[LayoutDefinition], bool]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Formatierungsobjekte durchgehen")
        self.resize(880, 720)

        self._definition = definition
        self._book_path = Path(book_path)
        self._inventory: Inventory = scan_inventory(self._book_path, definition)
        self._view = VIEW_BY_TYPE
        self._steps: list[Step] = []
        self._index = 0
        self._touched: list[str] = []
        self._editing: Optional[str] = None
        self._save_callback = save
        self._saved = False

        self._build_ui()
        self._rebuild_steps()
        self._update_save_state()

    # -- Aufbau ------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        kopf = QHBoxLayout()
        kopf.addWidget(QLabel("Ansicht:"))
        self.view_combo = QComboBox()
        for key, label in VIEWS:
            self.view_combo.addItem(label, key)
        self.view_combo.setToolTip(
            "Nach Formatierungsobjekt: kurz, jedes genau einmal.\n"
            "Nach Kapitel: länger, dafür im Zusammenhang des Buches."
        )
        kopf.addWidget(self.view_combo, 1)
        outer.addLayout(kopf)

        # Die Erklaerung steht im Fenster, nicht im Handbuch: der Begriff ist
        # kein gelaeufiges Wort, und wer hier zum ersten Mal steht, soll nicht
        # erst nachschlagen muessen, worueber der Assistent eigentlich redet.
        self.what_label = QLabel(
            "Ein <b>Formatierungsobjekt</b> ist der <b>Adressat</b> eines "
            "Absatzformats — "
            "die Sorte Absatz, die es bekommt: Überschrift, Fließtext, "
            "Aufzählung, Blockzitat, Codeblock, Fußnote oder ein "
            "<code>::: {.klasse}</code>-Block."
        )
        self.what_label.setWordWrap(True)
        self.what_label.setTextFormat(Qt.TextFormat.RichText)
        self.what_label.setStyleSheet(f"color: {StatusFg.NEUTRAL};")
        outer.addWidget(self.what_label)

        self.book_label = QLabel(str(self._book_path))
        self.book_label.setStyleSheet(f"color: {StatusFg.NEUTRAL};")
        outer.addWidget(self.book_label)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        outer.addWidget(self.progress)

        self.title_label = QLabel()
        titel_font = self.title_label.font()
        titel_font.setBold(True)
        titel_font.setPointSize(titel_font.pointSize() + 3)
        self.title_label.setFont(titel_font)
        self.title_label.setWordWrap(True)
        outer.addWidget(self.title_label)

        self.subtitle_label = QLabel()
        self.subtitle_label.setStyleSheet(f"color: {StatusFg.NEUTRAL};")
        self.subtitle_label.setWordWrap(True)
        outer.addWidget(self.subtitle_label)

        self.scope_label = QLabel()
        self.scope_label.setWordWrap(True)
        self.scope_label.setStyleSheet(f"color: {_STATUS_COLORS['missing']};")
        self.scope_label.hide()
        outer.addWidget(self.scope_label)

        # Ein Textfeld statt vieler Labels in einer Bildlauffläche: Umbrechende
        # Labels melden als Mindesthoehe eine Zeile, worauf das Layout sie bei
        # neun Funden auf je eine halbe Zeile staucht, statt zu scrollen. Ein
        # QTextBrowser bringt seinen eigenen Bildlauf mit und hat das Problem
        # nicht.
        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(False)
        self.body.setMaximumHeight(210)
        outer.addWidget(self.body)

        self._actions_host = QWidget()
        self._actions = QVBoxLayout(self._actions_host)
        self._actions.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._actions_host)

        # Das Formular des Editors, nicht ein zweites: Wer hier etwas
        # einstellt, soll dieselben Felder sehen wie dort -- und eine Aenderung
        # an den Feldern soll an einer Stelle genuegen.
        self._edit_host = QWidget()
        edit_layout = QVBoxLayout(self._edit_host)
        edit_layout.setContentsMargins(0, 6, 0, 0)

        auswahl = QHBoxLayout()
        auswahl.addWidget(QLabel("Absatzformat bearbeiten:"))
        self.style_combo = QComboBox()
        auswahl.addWidget(self.style_combo, 1)
        edit_layout.addLayout(auswahl)

        bereich = QScrollArea()
        bereich.setWidgetResizable(True)
        self.style_form = _StyleForm()
        self.style_form.connect_signals()
        self.style_form.set_colour_resolver(self._resolve_colour)
        bereich.setWidget(self.style_form)
        edit_layout.addWidget(bereich, 1)
        outer.addWidget(self._edit_host, 1)

        self.style_combo.currentIndexChanged.connect(self._on_style_chosen)
        self.style_form.changed.connect(self._on_form_changed)

        fuss = QHBoxLayout()
        # Wer hier fertig wird, soll nicht erst in den Editor zurueck muessen,
        # um seine Arbeit festzuhalten.
        self.save_button = QPushButton("Layout speichern")
        self.save_button.setToolTip(
            "Schreibt das Layout in die Bibliothek — dieselbe Wirkung wie "
            "»Speichern« im Editor."
        )
        self.save_button.clicked.connect(self._save_layout)
        fuss.addWidget(self.save_button)

        self.back_button = QPushButton("Zurück")
        self.skip_button = QPushButton("Überspringen")
        self.next_button = QPushButton("Weiter")
        self.close_button = QPushButton("Schließen")
        fuss.addWidget(self.back_button)
        fuss.addWidget(self.skip_button)
        fuss.addStretch(1)
        fuss.addWidget(self.next_button)
        fuss.addWidget(self.close_button)
        outer.addLayout(fuss)

        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        self.back_button.clicked.connect(self._back)
        self.skip_button.clicked.connect(self._forward)
        self.next_button.clicked.connect(self._forward)
        self.close_button.clicked.connect(self.accept)

    # -- Schritte ----------------------------------------------------------

    def _rebuild_steps(self, *, keep_position: bool = False) -> None:
        """Baut die Schrittliste neu -- nach Wechsel der Ansicht oder Änderung."""
        vorher = self._steps[self._index].key if (keep_position and self._steps) else None
        bauer = steps_by_type if self._view == VIEW_BY_TYPE else steps_by_chapter
        self._steps = bauer(self._inventory)
        if vorher is not None:
            self._index = next(
                (i for i, s in enumerate(self._steps) if s.key == vorher), 0
            )
        else:
            self._index = 0
        self._show_step()

    def _on_view_changed(self) -> None:
        self._commit_form()
        self._view = self.view_combo.currentData() or VIEW_BY_TYPE
        # Bewusst von vorn: Die beiden Ansichten haben verschiedene Schritte,
        # eine gemeinsame Position gaebe es nur scheinbar.
        self._rebuild_steps()

    def _current(self) -> Optional[Step]:
        if not self._steps or not 0 <= self._index < len(self._steps):
            return None
        return self._steps[self._index]

    def _clear_actions(self) -> None:
        """Raeumt die Knoepfe des vorigen Schritts ab.

        ``setParent(None)`` muss sein: ``deleteLater`` raeumt erst auf, wenn
        die Ereignisschleife wieder drankommt -- bis dahin bliebe der alte
        Knopf sichtbar und zeichnete ueber den neuen.
        """
        while self._actions.count():
            item = self._actions.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _show_step(self) -> None:
        self._clear_actions()

        schritt = self._current()
        gesamt = len(self._steps)
        self.progress.setMaximum(max(1, gesamt))
        self.progress.setValue(self._index + 1 if schritt else gesamt)
        self.progress.setFormat(
            f"Schritt {self._index + 1} von {gesamt}" if schritt else "fertig"
        )
        self.back_button.setEnabled(self._index > 0)
        letzter = schritt is None or self._index >= gesamt - 1
        self.next_button.setText("Fertig" if letzter else "Weiter")
        self.skip_button.setVisible(not letzter)

        if schritt is None:
            self._show_summary()
            return

        self.title_label.setText(schritt.title)
        self.subtitle_label.setText(schritt.subtitle)
        self.scope_label.setVisible(self._view == VIEW_BY_CHAPTER)
        self.scope_label.setText(
            "Ein Absatzformat gilt im ganzen Buch — was du hier änderst, wirkt "
            "in jedem Kapitel. Diese Ansicht ordnet den Weg, nicht die Wirkung."
        )
        self.body.setHtml(
            "".join(self._finding_html(f) for f in schritt.findings)
        )
        for finding in schritt.findings:
            knopf = self._action_button(finding, finding.status(self._definition))
            if knopf is not None:
                self._actions.addWidget(knopf)
        self._fill_style_choice(schritt)

    def _finding_html(self, finding: Finding) -> str:
        """Ein Fund als Textabschnitt: Zustand, Erklärung, echte Beispiele."""
        zustand = finding.status(self._definition)
        ziel = ", ".join(finding.element.style_ids) or "kein eigenes Format"
        teile = [
            f"<p><b>{_escape(finding.element.label)}</b> — "
            f'<span style="color:{_STATUS_COLORS[zustand]}">'
            f"{STATUS_LABELS[zustand]}</span><br>"
            f'<span style="color:{StatusFg.NEUTRAL}">Absatzformat: '
            f"{_escape(ziel)}<br>{_escape(finding.element.note)}</span></p>"
        ]
        if finding.samples:
            zeilen = "<br>".join(
                f"<code>{_escape(o.file)}:{o.line}</code> &nbsp; "
                f"{_escape(o.excerpt)}"
                for o in finding.samples
            )
            teile.append(f"<p>Aus deinem Buch:<br>{zeilen}</p>")
        return "".join(teile)

    def _action_button(self, finding: Finding, zustand: str) -> Optional[QPushButton]:
        """Der Handgriff, der zu diesem Zustand passt -- oder keiner."""
        if zustand == "missing":
            fehlend = finding.missing_styles(self._definition)
            knopf = QPushButton(f"Format {', '.join(fehlend)} anlegen")
            knopf.clicked.connect(lambda: self._create_styles(fehlend))
            return knopf
        if zustand == "unmapped":
            name = finding.element.key.split(":", 1)[1]
            knopf = QPushButton(f"Klasse .{name} zuordnen…")
            knopf.clicked.connect(lambda: self._map_class(name))
            return knopf
        return None

    # -- Bearbeiten --------------------------------------------------------

    def _resolve_colour(self, wert: Optional[str]) -> Optional[str]:
        """Loest einen Farbtoken in seinen Hexwert auf.

        Ueber ``LayoutDefinition.resolve_color`` und nicht mit einem eigenen
        ``colors.get`` -- die zweite, schwaechere Fassung reichte einen
        unbekannten Token als vermeintlichen Hexwert durch, und der
        Farbknopf malte sich dann mit ``background-color: #accent``.
        """
        if not wert:
            return None
        try:
            return self._definition.resolve_color(wert)
        except LayoutError:
            # Unbekannter Token: keine Farbe zeigen ist ehrlicher, als eine
            # zu erfinden. Das Problem meldet die Pruefzeile im Editor.
            return None

    def _editable_styles(self, schritt: Step) -> list[tuple[str, str]]:
        """Die Absatzformate dieses Schritts, die es schon gibt.

        Ein Schritt kann mehrere haben (Fliesstext heisst BodyText **und**
        FirstParagraph), und in der Kapitelansicht bringt jede Datei gleich
        mehrere Formatierungsobjekte mit. Deshalb eine Auswahl.
        """
        gefunden: list[tuple[str, str]] = []
        for finding in schritt.findings:
            if not finding.element.reachable:
                continue
            for style_id in finding.element.style_ids:
                if style_id in self._definition.styles and not any(
                    style_id == vorhanden for _, vorhanden in gefunden
                ):
                    gefunden.append((f"{finding.element.label} — {style_id}", style_id))
        return gefunden

    def _fill_style_choice(self, schritt: Step) -> None:
        """Fuellt die Formatauswahl und laedt das erste Format."""
        self._commit_form()
        auswahl = self._editable_styles(schritt)
        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        for label, style_id in auswahl:
            self.style_combo.addItem(label, style_id)
        self.style_combo.blockSignals(False)
        self._edit_host.setVisible(bool(auswahl))
        if auswahl:
            self.style_combo.setCurrentIndex(0)
            self._load_style(auswahl[0][1])
        else:
            self._editing = None

    def _on_style_chosen(self) -> None:
        self._commit_form()
        style_id = self.style_combo.currentData()
        if style_id:
            self._load_style(style_id)

    def _load_style(self, style_id: str) -> None:
        style = self._definition.styles.get(style_id)
        if style is None:
            self._editing = None
            return
        self.style_form.blockSignals(True)
        # Der Kontext zuerst: Er fuellt die Auswahllisten und weiss, welche
        # Groesse ein geerbter Wert am Ende bedeutet.
        self.style_form.set_context(self._definition, style_id)
        self.style_form.load(style)
        self.style_form.blockSignals(False)
        self._editing = style_id

    def _on_form_changed(self) -> None:
        """Uebernimmt eine Aenderung sofort -- ohne eigenen Speichern-Knopf.

        Ein zusaetzlicher Knopf waere eine Falle: Wer weiterblaettert, ohne ihn
        gedrueckt zu haben, verlaere seine Arbeit wortlos.
        """
        if not self._commit_form():
            return
        self._merke(f"{self._editing} bearbeitet")
        self._update_status_line()

    def _commit_form(self) -> bool:
        """Schreibt die Feldwerte ins Layout. Wahr, wenn sich etwas geaendert hat."""
        if self._editing is None or not self._edit_host.isVisible():
            return False
        style = self.style_form.collect()
        if style is None or style.style_id != self._editing:
            return False
        if self._definition.styles.get(style.style_id) == style:
            return False
        self._definition = self._definition.with_style(style)
        return True

    def _merke(self, eintrag: str) -> None:
        """Haelt fest, was getan wurde -- jede Sache nur einmal."""
        if eintrag not in self._touched:
            self._touched.append(eintrag)
        if eintrag != "gespeichert":
            self._saved = False
        self._update_save_state()

    def _update_status_line(self) -> None:
        """Zeichnet den Kopf des Schritts neu, ohne das Formular zu stoeren."""
        schritt = self._current()
        if schritt is None:
            return
        self.body.setHtml(
            "".join(self._finding_html(f) for f in schritt.findings)
        )

    # -- Handgriffe --------------------------------------------------------

    def _create_styles(self, style_ids: tuple[str, ...]) -> None:
        """Legt fehlende Absatzformate an -- leer, auf BodyText aufbauend."""
        definition = self._definition
        for style_id in style_ids:
            if style_id in definition.styles:
                continue
            definition = definition.with_style(
                ParagraphStyle(style_id=style_id, name=style_id, based_on="BodyText")
            )
            self._merke(style_id)
        self._definition = definition
        self._refresh_after_change()

    def _map_class(self, name: str) -> None:
        """Verbindet eine Klasse mit einem Absatzformat."""
        vorhandene = sorted(self._definition.styles)
        vorschlag = suggested_style_id(name, self._definition.styles)
        auswahl = [f"Neues Format »{vorschlag}« anlegen", *vorhandene]
        wahl, ok = QInputDialog.getItem(
            self,
            f"Klasse .{name}",
            "Welches Absatzformat soll dieser Block bekommen?",
            auswahl,
            0,
            False,
        )
        if not ok or not wahl:
            return
        definition = self._definition
        if wahl == auswahl[0]:
            definition = definition.with_style(
                ParagraphStyle(style_id=vorschlag, name=vorschlag, based_on="BodyText")
            )
            ziel = vorschlag
        else:
            ziel = wahl
        definition = replace(
            definition, classmap={**definition.classmap, name: ziel}
        )
        self._definition = definition
        self._merke(f".{name} → {ziel}")
        self._refresh_after_change()

    def _refresh_after_change(self) -> None:
        """Nach einer Änderung neu einlesen -- die Zustände stimmen sonst nicht.

        Nur die Zuordnung wird neu berechnet, nicht das Buch: Der Text hat sich
        nicht geändert, und ihn erneut zu durchsuchen kostete bei 116 Dateien
        spürbar Zeit.
        """
        self._inventory = _reclassify(self._inventory, self._definition)
        self._rebuild_steps(keep_position=True)

    def _save_layout(self) -> None:
        """Legt den aktuellen Stand ab -- ueber den Weg, den der Editor kennt."""
        if self._save_callback is None:
            return
        self._commit_form()
        if self._save_callback(self._definition):
            self._saved = True
            self._merke("gespeichert")
        self._update_save_state()

    def _update_save_state(self) -> None:
        """Der Knopf sagt, ob es etwas zu speichern gibt."""
        moeglich = self._save_callback is not None
        self.save_button.setVisible(moeglich)
        if not moeglich:
            return
        offen = self.changed and not self._saved
        self.save_button.setEnabled(offen)
        # »Gespeichert« nur, wenn wirklich gespeichert wurde. Ohne jede
        # Aenderung waere es eine Behauptung ueber etwas, das nie geschah.
        self.save_button.setText("Gespeichert" if self._saved else "Layout speichern")

    # -- Abschluss ---------------------------------------------------------

    def _show_summary(self) -> None:
        offen = open_findings(self._inventory, self._definition)
        self._edit_host.hide()
        self.title_label.setText("Durchgang beendet")
        self.subtitle_label.setText(self._inventory.summary())
        self.scope_label.hide()

        teile = []
        if self._touched:
            zeilen = "<br>".join(f"&nbsp;&nbsp;{_escape(t)}" for t in self._touched)
            teile.append(f"<p><b>Angelegt oder zugeordnet:</b><br>{zeilen}</p>")
        else:
            teile.append("<p>Es wurde nichts geändert.</p>")

        if offen:
            zeilen = "<br>".join(
                f"&nbsp;&nbsp;{_escape(f.element.label)} — "
                f"{STATUS_LABELS[f.status(self._definition)]}"
                for f in offen
            )
            teile.append(
                f'<p><span style="color:{_STATUS_COLORS["missing"]}">'
                f"<b>Noch offen:</b></span><br>{zeilen}</p>"
            )
        else:
            teile.append(
                f'<p><span style="color:{_STATUS_COLORS["ok"]}">'
                "Jedes Formatierungsobjekt deines Buches hat eine Vorlage.</span></p>"
            )

        if self.changed and not self._saved:
            teile.append(
                f'<p><span style="color:{_STATUS_COLORS["missing"]}">Noch nicht '
                "gespeichert — »Layout speichern« unten links, oder später im "
                "Editor.</span></p>"
            )
        elif self._saved:
            teile.append(
                f'<p><span style="color:{_STATUS_COLORS["ok"]}">Das Layout ist '
                "gespeichert.</span></p>"
            )
        teile.append(
            f'<p><span style="color:{StatusFg.NEUTRAL}">Neu angelegte Formate '
            "sind leer — gestaltet werden sie hier oder im Editor. Auf ein Buch "
            "übertragen wird das Layout mit »Auf Buchprojekt anwenden…«; es "
            "gehört zu keinem Buch und passt auf jedes.</span></p>"
        )
        self.body.setHtml("".join(teile))

    def _back(self) -> None:
        self._commit_form()
        if self._index > 0:
            self._index -= 1
            self._show_step()

    def _forward(self) -> None:
        """Einen Schritt weiter -- und von der Abschlussseite hinaus.

        Die Reihenfolge der beiden Faelle war vertauscht: Der erste fing auch
        ``_index == len(self._steps)`` mit ab, weshalb "Fertig" auf der
        Abschlussseite die Abschlussseite erneut zeichnete statt zu schliessen.
        Der ``accept()``-Zweig war unerreichbar, und der Knopf tat sichtbar
        nichts -- man kam nur ueber "Schliessen" heraus.
        """
        self._commit_form()
        if self._index >= len(self._steps):
            # Wir stehen schon auf der Abschlussseite: Der Durchgang ist vorbei.
            self.accept()
            return
        if self._index >= len(self._steps) - 1:
            # Letzter Schritt -- weiter geht es nur noch zur Abschlussseite.
            self._index = len(self._steps)
            self._show_step()
            return
        self._index += 1
        self._show_step()

    # -- Ergebnis ----------------------------------------------------------

    @property
    def definition(self) -> LayoutDefinition:
        """Das -- moeglicherweise ergaenzte -- Layout."""
        return self._definition

    @property
    def changed(self) -> bool:
        return bool(self._touched)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _reclassify(inventory: Inventory, definition: LayoutDefinition) -> Inventory:
    """Stuft die vorhandenen Funde mit einer neuen Definition neu ein."""
    from tools.doclayout.inventory import CLASS_PREFIX, class_element

    def neu(finding: Finding) -> Finding:
        if not finding.element.key.startswith(CLASS_PREFIX):
            return finding
        name = finding.element.key[len(CLASS_PREFIX):]
        return replace(
            finding, element=class_element(name, definition.classmap.get(name))
        )

    return replace(
        inventory,
        findings=tuple(neu(f) for f in inventory.findings),
        per_file={
            datei: tuple(neu(f) for f in findings)
            for datei, findings in inventory.per_file.items()
        },
    )


def run_wizard(
    parent: Optional[QWidget],
    definition: LayoutDefinition,
    book_path: Path,
    save: Optional[Callable[[LayoutDefinition], bool]] = None,
) -> tuple[LayoutDefinition, bool]:
    """Oeffnet den Assistenten und liefert (Layout, wurde-etwas-geaendert).

    *save* legt den Stand ab, ohne den Assistenten zu verlassen; ohne den
    Rueckruf bleibt der Knopf verborgen.
    """
    dialog = DocLayoutWizard(parent, definition, book_path, save=save)
    dialog.exec()
    return dialog.definition, dialog.changed


__all__ = [
    "VIEWS",
    "VIEW_BY_CHAPTER",
    "VIEW_BY_TYPE",
    "DocLayoutWizard",
    "run_wizard",
]
