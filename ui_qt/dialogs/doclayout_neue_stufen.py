"""Neue Stufen gestalten: jede Stufe ohne Absatzformat, eine nach der anderen, mit Vorschau.

Der Layout-Assistent geht durch alles, was im Buch **steht**. Eine Stufe, die
noch nie gelaufen ist, steht aber nirgends -- sie fiele erst nach einem
bezahlten Lauf in der Nacharbeit auf (Nutzer, 14.10.2026). Dieses Fenster legt
genau die Stufen vor, denen die Formatvorlage noch kein Absatzformat gibt:

* links die offenen Stufen (✓ = zugeordnet),
* rechts Anzeigename, Herkunft des Beispieltexts und die Wahl des Formats --
  vorbelegt mit einem Vorschlag (Haupttext → Fließtext, Kasten → eigenes
  Format nach Stufenname),
* darunter das Formular des Editors (dieselben Felder, keine zweite Fassung)
* und die echte Vorschau des Editors (Pandoc + LibreOffice) mit dem Text aus
  dem jüngsten Lauf der Stufe, sonst einem Platzhalter.

Zugeordnet wird unter dem Stufentyp -- die Gestaltung gilt für jedes Buch mit
dieser Stufe. Gespeichert wird erst auf Knopfdruck, ins Layout der Bibliothek.

Logik: ``tools.doclayout.neue_stufen``. Hier nur Widgets.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from tools.doclayout.neue_stufen import (
    Stufe,
    beispiel_markdown,
    beispieltext,
    fehlende_stufen,
    vorschlag,
    zuordnen,
)
from tools.doclayout.schema import LayoutDefinition, LayoutError
from ui_qt.dialogs.doclayout_editor.common import _PreviewPane
from ui_qt.dialogs.doclayout_preview_runner import PreviewRunner
from ui_qt.dialogs.doclayout_style_form import _StyleForm

#: Erster Eintrag der Formatwahl, wenn das Vorschlagsformat noch nicht existiert.
_NEU = "neu:"


class NeueStufenDialog(QDialog):
    """Führt durch die Stufen ohne Absatzformat -- mit Vorschau."""

    def __init__(
        self,
        parent: QWidget | None,
        definition: LayoutDefinition,
        stufen: list[Stufe],
        *,
        gg_output: Path | None = None,
        save: Callable[[LayoutDefinition], bool] | None = None,
        projekt_name: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Neue Stufen gestalten — {definition.label or definition.name}")
        self.resize(1300, 860)
        self._definition = definition
        self._stufen = list(stufen)
        self._save = save
        self._zugeordnet: dict[str, str] = {}  # stufentyp -> style_id
        self._gespeichert = True
        self._geaendert = False
        self._editing: str | None = None
        self._texte = {s.stage_id: beispieltext(s, gg_output) for s in self._stufen}

        self._runner = PreviewRunner(self)
        self._build_ui(projekt_name)
        self._runner.due.connect(self._vorschau)
        self._runner.busy.connect(self.preview.show_busy)
        self._runner.ready.connect(self.preview.show_result)
        self._runner.failed.connect(self.preview.show_error)
        if self._stufen:
            self.liste.setCurrentRow(0)
        self._vorschau()

    # -- Aufbau ------------------------------------------------------------

    def _build_ui(self, projekt_name: str) -> None:
        outer = QVBoxLayout(self)
        kopf = QLabel(
            f"<b>{len(self._stufen)} Stufe(n)</b>"
            + (f" aus <b>{projekt_name}</b>" if projekt_name else "")
            + " haben in dieser Formatvorlage noch kein Absatzformat. Wähle je Stufe "
            "ein Format, prüfe es in der Vorschau und speichere am Ende. "
            "Die Zuordnung gilt für jedes Buch mit dieser Stufe."
        )
        kopf.setWordWrap(True)
        kopf.setTextFormat(Qt.TextFormat.RichText)
        outer.addWidget(kopf)

        teiler = QSplitter(Qt.Orientation.Horizontal)
        self.liste = QListWidget()
        for stufe in self._stufen:
            eintrag = QListWidgetItem(f"○ {stufe.anzeigename}")
            eintrag.setData(Qt.ItemDataRole.UserRole, stufe.stage_id)
            eintrag.setToolTip(f".{stufe.klasse} → Stufentyp {stufe.stufentyp}")
            self.liste.addItem(eintrag)
        self.liste.currentRowChanged.connect(self._zeige_stufe)
        teiler.addWidget(self.liste)

        mitte = QWidget()
        mitte_layout = QVBoxLayout(mitte)
        mitte_layout.setContentsMargins(0, 0, 0, 0)
        self.titel = QLabel()
        schrift = self.titel.font()
        schrift.setBold(True)
        schrift.setPointSize(schrift.pointSize() + 2)
        self.titel.setFont(schrift)
        mitte_layout.addWidget(self.titel)
        self.info = QLabel()
        self.info.setWordWrap(True)
        mitte_layout.addWidget(self.info)

        wahl = QHBoxLayout()
        wahl.addWidget(QLabel("Absatzformat:"))
        self.format_wahl = QComboBox()
        wahl.addWidget(self.format_wahl, 1)
        self.zuordnen_knopf = QPushButton("Zuordnen und weiter")
        self.zuordnen_knopf.clicked.connect(self._zuordnen_und_weiter)
        wahl.addWidget(self.zuordnen_knopf)
        self.ueberspringen_knopf = QPushButton("Überspringen")
        self.ueberspringen_knopf.setToolTip("Diese Stufe jetzt nicht gestalten (kommt z. B. nicht ins Buch).")
        self.ueberspringen_knopf.clicked.connect(self._weiter)
        wahl.addWidget(self.ueberspringen_knopf)
        mitte_layout.addLayout(wahl)

        bereich = QScrollArea()
        bereich.setWidgetResizable(True)
        self.form = _StyleForm()
        self.form.connect_signals()
        self.form.set_colour_resolver(self._farbe)
        self.form.changed.connect(self._formular_geaendert)
        bereich.setWidget(self.form)
        mitte_layout.addWidget(bereich, 1)
        teiler.addWidget(mitte)

        self.preview = _PreviewPane()
        self.preview.refresh_button.clicked.connect(self._vorschau)
        self.preview.open_button.clicked.connect(self._oeffne_docx)
        teiler.addWidget(self.preview)
        teiler.setSizes([240, 520, 540])
        outer.addWidget(teiler, 1)

        fuss = QHBoxLayout()
        self.status = QLabel()
        fuss.addWidget(self.status, 1)
        self.speichern_knopf = QPushButton("Layout speichern")
        self.speichern_knopf.clicked.connect(self._speichern)
        self.speichern_knopf.setVisible(self._save is not None)
        fuss.addWidget(self.speichern_knopf)
        schliessen = QPushButton("Schließen")
        schliessen.clicked.connect(self.reject)
        fuss.addWidget(schliessen)
        outer.addLayout(fuss)
        self._status_aktualisieren()

    # -- Schritte ----------------------------------------------------------

    def _aktuelle(self) -> Stufe | None:
        zeile = self.liste.currentRow()
        return self._stufen[zeile] if 0 <= zeile < len(self._stufen) else None

    def _zeige_stufe(self, _zeile: int = 0) -> None:
        self._formular_uebernehmen()
        stufe = self._aktuelle()
        if stufe is None:
            return
        _text, herkunft = self._texte[stufe.stage_id]
        self.titel.setText(stufe.anzeigename)
        self.info.setText(
            f"Klasse im Buch: .{stufe.klasse} · Stufentyp: {stufe.stufentyp}"
            + (" · Haupttext des Kapitels" if stufe.pflicht else "")
            + f"\nBeispieltext in der Vorschau: {herkunft}"
        )
        gewaehlt = self._zugeordnet.get(stufe.stufentyp)
        vorschlags_id, gibt_es = vorschlag(self._definition, stufe)
        self.format_wahl.blockSignals(True)
        self.format_wahl.clear()
        if not gibt_es:
            self.format_wahl.addItem(f"Neues Format »{vorschlags_id}« anlegen (Vorschlag)", _NEU + vorschlags_id)
        for style_id in sorted(self._definition.styles):
            text = style_id + (" (Vorschlag)" if gibt_es and style_id == vorschlags_id else "")
            self.format_wahl.addItem(text, style_id)
        ziel = gewaehlt or (vorschlags_id if gibt_es else _NEU + vorschlags_id)
        index = self.format_wahl.findData(ziel)
        self.format_wahl.setCurrentIndex(max(0, index))
        self.format_wahl.blockSignals(False)
        self._formular_laden(gewaehlt)

    def _zuordnen_und_weiter(self) -> None:
        stufe = self._aktuelle()
        if stufe is None:
            return
        wert = str(self.format_wahl.currentData() or "")
        style_id = wert.removeprefix(_NEU)
        if not style_id:
            return
        try:
            self._definition = zuordnen(self._definition, stufe, style_id)
        except LayoutError as exc:
            QMessageBox.warning(self, "Neue Stufen", str(exc))
            return
        self._zugeordnet[stufe.stufentyp] = style_id
        self._gespeichert = False
        self._geaendert = True
        eintrag = self.liste.item(self.liste.currentRow())
        eintrag.setText(f"✓ {stufe.anzeigename} → {style_id}")
        self._formular_laden(style_id)
        self._status_aktualisieren()
        self._runner.schedule()
        # Erst zur nächsten offenen Stufe -- das Formular des gerade gewählten
        # Formats bleibt bis dahin zum Feinschliff stehen.
        if self._naechste_offene() is not None:
            self._weiter()

    def _naechste_offene(self) -> int | None:
        for zeile, stufe in enumerate(self._stufen):
            if stufe.stufentyp not in self._zugeordnet and zeile != self.liste.currentRow():
                return zeile
        return None

    def _weiter(self) -> None:
        naechste = self._naechste_offene()
        if naechste is not None:
            self.liste.setCurrentRow(naechste)

    # -- Formular ----------------------------------------------------------

    def _farbe(self, wert: str | None) -> str | None:
        if not wert:
            return None
        try:
            return self._definition.resolve_color(wert)
        except LayoutError:
            return None

    def _formular_laden(self, style_id: str | None) -> None:
        style = self._definition.styles.get(style_id or "")
        self.form.setEnabled(style is not None)
        if style is None:
            self._editing = None
            return
        self.form.blockSignals(True)
        self.form.set_context(self._definition, style.style_id)
        self.form.load(style)
        self.form.blockSignals(False)
        self._editing = style.style_id

    def _formular_uebernehmen(self) -> bool:
        if self._editing is None:
            return False
        style = self.form.collect()
        if style is None or style.style_id != self._editing:
            return False
        if self._definition.styles.get(style.style_id) == style:
            return False
        self._definition = self._definition.with_style(style)
        self._gespeichert = False
        self._geaendert = True
        return True

    def _formular_geaendert(self) -> None:
        if self._formular_uebernehmen():
            self._status_aktualisieren()
            self._runner.schedule()

    # -- Vorschau und Speichern -------------------------------------------

    def _vorschau(self) -> None:
        self._formular_uebernehmen()
        probleme = self._definition.validate()
        if probleme:
            self.preview.show_error("Das Layout ist noch nicht erzeugbar:\n" + "\n".join(f"- {p}" for p in probleme))
            return
        inhalt = beispiel_markdown(
            self._definition, [(s, self._texte[s.stage_id][0]) for s in self._stufen]
        )
        self._runner.start(self._definition, inhalt)

    def _oeffne_docx(self) -> None:
        pfad = self.preview.docx_path()
        if pfad and pfad.is_file():
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(str(pfad)))

    def _speichern(self) -> None:
        if self._save is None:
            return
        self._formular_uebernehmen()
        if self._save(self._definition):
            self._gespeichert = True
        self._status_aktualisieren()

    def _status_aktualisieren(self) -> None:
        offen = len(fehlende_stufen(self._definition, self._stufen))
        teile = [f"{len(self._stufen) - offen} von {len(self._stufen)} zugeordnet"]
        teile.append("gespeichert" if self._gespeichert else "noch nicht gespeichert")
        self.status.setText(" · ".join(teile))
        self.speichern_knopf.setEnabled(not self._gespeichert)

    def reject(self) -> None:
        self._formular_uebernehmen()
        if not self._gespeichert and self._save is not None:
            antwort = QMessageBox.question(
                self,
                "Neue Stufen",
                "Die Zuordnungen sind noch nicht gespeichert. Jetzt speichern?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if antwort == QMessageBox.StandardButton.Cancel:
                return
            if antwort == QMessageBox.StandardButton.Save:
                self._speichern()
        self._runner.release()
        super().reject()

    @property
    def definition(self) -> LayoutDefinition:
        return self._definition

    @property
    def gespeichert(self) -> bool:
        return self._gespeichert

    @property
    def geaendert(self) -> bool:
        """Wurde überhaupt etwas zugeordnet oder gestaltet?"""
        return self._geaendert


def open_neue_stufen(
    parent: QWidget | None,
    layout_name: str,
    manifest: Path,
    *,
    gg_output: Path | None = None,
) -> NeueStufenDialog | None:
    """Prüft *manifest* gegen das Layout und öffnet das Fenster -- oder sagt, dass nichts fehlt.

    Gespeichert wird in die Bibliothek, wie im Editor (``LayoutDefinition.save``).
    """
    from tools.doclayout.library import layout_path, load_layout
    from tools.doclayout.neue_stufen import stufen_des_projekts

    definition = load_layout(layout_name)
    stufen = stufen_des_projekts(manifest)
    offen = fehlende_stufen(definition, stufen)
    projekt = Path(manifest).parent.name
    if not offen:
        QMessageBox.information(
            parent,
            "Neue Stufen",
            f"Alle {len(stufen)} Stufen von {projekt} haben in »{layout_name}« ein Absatzformat.",
        )
        return None

    def speichern(neu: LayoutDefinition) -> bool:
        try:
            neu.save(layout_path(neu.name))
        except (OSError, LayoutError) as exc:
            QMessageBox.warning(parent, "Neue Stufen", f"Nicht gespeichert:\n{exc}")
            return False
        return True

    dialog = NeueStufenDialog(
        parent, definition, offen, gg_output=gg_output, save=speichern, projekt_name=projekt
    )
    dialog.exec()
    return dialog


__all__ = ["NeueStufenDialog", "open_neue_stufen"]
