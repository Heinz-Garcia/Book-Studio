"""Die Eigenschafts-Formulare des Layout-Editors — außer dem Absatzformat.

Seite und Ränder, Typografie, Farbtokens, Klassen-Abbildung. Alle vier folgen
demselben Vertrag: load() füllt die Felder, collect() liest sie zurück,
und changed meldet jede Eingabe. Keines kennt den Dialog, keines hält
Zustand außer dem, was es gerade anzeigt.

Genau deshalb lagen die Fehler dieses Editors nie hier, sondern in der Klasse,
die alles zusammenhält — siehe doclayout_session.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services.constants import StatusFg
from tools.doclayout import DOCX_ONLY_NOTICE
from tools.doclayout.profiles import GeometryComparison, list_profiles
from tools.doclayout.schema import ALIGNMENTS, Page, PageMargin, Typography
from tools.doclayout.usage import Comparison
from ui_qt.dialogs.doclayout_editor_style import ALERT_NAME, MUTED_NAME
from ui_qt.dialogs.doclayout_widgets import (
    _ALIGN_LABELS,
    _font_combo,
    _CHECK_ALERT,
    _CHECK_OK,
    _ColorButton,
    _escape_html,
    _info,
    _mm_spin,
    _pt_spin,
    apply_tone,
    font_value,
    set_font_value,
    _share_label_tooltips,
)


class _PageForm(QWidget):
    """Seitenformat, Ränder, Fußzeile."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)

        profile_box = QGroupBox("Aus einem Layout-Profil übernehmen")
        profile_layout = QHBoxLayout(profile_box)
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("— auswählen —", "")
        for profile_id, label in list_profiles():
            self.profile_combo.addItem(label, profile_id)
        self.profile_combo.setToolTip(
            "Übernimmt Seitenmaße, Ränder, Schriftgröße und Zeilenabstand aus "
            "den Druckprofilen von Book Studio — inklusive Beschnittzugabe."
        )
        profile_layout.addWidget(self.profile_combo, 1)
        self.profile_apply = QPushButton("Übernehmen")
        profile_layout.addWidget(self.profile_apply)
        outer.addWidget(profile_box)

        # Der Abgleich mit dem Profil, mit dem tatsaechlich gedruckt wird.
        # Ohne ihn faellt eine A4-Vorlage fuer ein 135-mm-Buch erst auf, wenn
        # jemand beides nebeneinanderlegt -- genau der Fehler, den die
        # Bruecke zu ``layout_profiles`` verhindern soll.
        self.profile_match = QLabel()
        self.profile_match.setWordWrap(True)
        self.profile_match.setTextFormat(Qt.TextFormat.RichText)
        self.profile_match.setObjectName("DocLayoutProfileMatch")
        self.profile_match.hide()
        outer.addWidget(self.profile_match)

        size_box = QGroupBox("Seite")
        size_form = QFormLayout(size_box)
        self.width = _mm_spin()
        self.height = _mm_spin()
        self.mirrored = QCheckBox("Doppelseitig (Bundsteg innen/außen)")
        self.mirrored.setToolTip(
            "Bei gebundenen Büchern wandert der innere Rand beim Blättern die "
            "Seite; Word und Writer spiegeln ihn dann automatisch."
        )
        size_form.addRow("Breite", self.width)
        size_form.addRow("Höhe", self.height)
        size_form.addRow(
            _info(
            "",
            "Für gebundene Bücher: Die Ränder heißen dann Innen und Außen statt "
            "Links und Rechts, und Word spiegelt sie auf geraden Seiten.",
        ),
            self.mirrored,
        )
        outer.addWidget(size_box)

        margin_box = QGroupBox("Ränder")
        margin_form = QFormLayout(margin_box)
        self.margin_top = _mm_spin(500)
        self.margin_bottom = _mm_spin(500)
        self.margin_inner = _mm_spin(500)
        self.margin_outer = _mm_spin(500)
        margin_form.addRow("Oben", self.margin_top)
        margin_form.addRow("Unten", self.margin_bottom)
        margin_form.addRow(
            _info(
            "Innen (Bund)",
            "Der Rand an der Bindung. Nur bei doppelseitigen Büchern getrennt "
            "vom äußeren Rand — Word spiegelt ihn dann auf geraden Seiten.\n"
            "Er darf größer sein als der äußere: Was im Falz verschwindet, "
            "kann man nicht lesen.",
        ),
            self.margin_inner,
        )
        margin_form.addRow(
            _info(
            "Außen",
            "Der Rand zur offenen Seite hin. Bei einseitigem Druck einfach der "
            "rechte Rand.",
        ),
            self.margin_outer,
        )
        self.text_width_label = QLabel()
        self.text_width_label.setObjectName(MUTED_NAME)
        margin_form.addRow(
            _info(
            "Textbreite",
            "Ergibt sich aus Breite minus den beiden seitlichen Rändern — "
            "nichts einzustellen, nur zum Mitrechnen.\n"
            "Als Faustregel gelten 60 bis 75 Zeichen je Zeile als gut lesbar.",
        ),
            self.text_width_label,
        )
        outer.addWidget(margin_box)

        footer_box = QGroupBox("Fußzeile")
        footer_form = QFormLayout(footer_box)
        self.footer_number = QCheckBox("Seitenzahl anzeigen")
        self.footer_align = QComboBox()
        for value in ALIGNMENTS:
            self.footer_align.addItem(_ALIGN_LABELS[value], value)
        footer_form.addRow("", self.footer_number)
        footer_form.addRow("Ausrichtung", self.footer_align)
        outer.addWidget(footer_box)
        outer.addStretch(1)

        for widget in (
            self.width, self.height, self.margin_top, self.margin_bottom,
            self.margin_inner, self.margin_outer,
        ):
            widget.valueChanged.connect(self._on_change)
        self.mirrored.toggled.connect(self._on_change)
        self.footer_number.toggled.connect(self._on_change)
        self.footer_align.currentIndexChanged.connect(self._on_change)
        _share_label_tooltips(self)

    def _on_change(self, *_args: Any) -> None:
        self._update_text_width()
        self.changed.emit()

    def show_profile_comparison(
        self, comparison: Optional["GeometryComparison"]
    ) -> None:
        """Sagt, ob diese Seite die Geometrie des Drucks trifft.

        Eine Abweichung ist kein Fehler -- eine Fassung fuer das Lektorat darf
        grosszuegiger gesetzt sein als der Druck. Deshalb steht hier ein
        Hinweis und keine Warnung, und der Knopf oben bietet den Weg zur
        Deckung an, ohne ihn zu erzwingen.

        Ausdruecklich dazugesagt wird, dass die Definition den Druck **nicht**
        steuert. Wer Breite und Raender einstellt, nimmt sonst an, damit auch
        die PDF zu bestimmen -- und die kommt bis auf Weiteres allein aus dem
        Layout-Profil.
        """
        if comparison is None:
            self.profile_match.hide()
            return
        if comparison.matches:
            self.profile_match.setText(
                f'<span style="color:{_CHECK_OK}">Deckt sich mit dem Druckprofil '
                f"«{_escape_html(comparison.profile_label)}».</span>"
            )
            self.profile_match.show()
            return
        zeilen = "<br>".join(
            f"&nbsp;&nbsp;{_escape_html(d.label)}: <b>{_escape_html(d.definition)}</b> "
            f"— gedruckt wird {_escape_html(d.profile)}"
            for d in comparison.differences
        )
        self.profile_match.setText(
            f'<span style="color:{_CHECK_ALERT}">Weicht vom Druckprofil '
            f"«{_escape_html(comparison.profile_label)}» ab:</span><br>{zeilen}<br>"
            "<i>Diese Seite gilt für die Word-Fassung. Die PDF wird weiterhin "
            "nach dem Layout-Profil gesetzt — beides zu vereinen geht über "
            "»Übernehmen« oben.</i>"
        )
        self.profile_match.show()

    def _update_text_width(self) -> None:
        remaining = self.width.value() - self.margin_inner.value() - self.margin_outer.value()
        if remaining <= 0:
            self.text_width_label.setText("Die Ränder lassen keine Textbreite übrig.")
            self.text_width_label.setObjectName(ALERT_NAME)
            apply_tone(self.text_width_label)
        else:
            self.text_width_label.setText(f"{remaining:g} mm")
            self.text_width_label.setObjectName(MUTED_NAME)
            apply_tone(self.text_width_label)

    def load(self, page: Page) -> None:
        blockers = [w.blockSignals(True) for w in self._widgets()]
        self.width.setValue(page.width_mm)
        self.height.setValue(page.height_mm)
        self.mirrored.setChecked(page.mirrored)
        self.margin_top.setValue(page.margin.top_mm)
        self.margin_bottom.setValue(page.margin.bottom_mm)
        self.margin_inner.setValue(page.margin.inner_mm)
        self.margin_outer.setValue(page.margin.outer_mm)
        self.footer_number.setChecked(page.footer_page_number)
        index = self.footer_align.findData(page.footer_align)
        self.footer_align.setCurrentIndex(max(0, index))
        for widget, blocked in zip(self._widgets(), blockers):
            widget.blockSignals(blocked)
        self._update_text_width()

    def _widgets(self) -> list[QWidget]:
        return [
            self.width, self.height, self.mirrored, self.margin_top,
            self.margin_bottom, self.margin_inner, self.margin_outer,
            self.footer_number, self.footer_align,
        ]

    def collect(self, page: Page) -> Page:
        return replace(
            page,
            width_mm=self.width.value(),
            height_mm=self.height.value(),
            mirrored=self.mirrored.isChecked(),
            margin=PageMargin(
                top_mm=self.margin_top.value(),
                bottom_mm=self.margin_bottom.value(),
                inner_mm=self.margin_inner.value(),
                outer_mm=self.margin_outer.value(),
            ),
            footer_page_number=self.footer_number.isChecked(),
            footer_align=self.footer_align.currentData() or "center",
        )


class _TypographyForm(QWidget):
    """Grundschrift, Zeilenabstand, Sprache, Silbentrennung."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        form = QFormLayout(self)

        # Auswahl statt Freitext: Man muss den Namen sonst genau kennen, ein
        # Tippfehler faellt nicht auf, und die Schrift faellt im fertigen
        # Dokument stillschweigend auf eine Ersatzschrift zurueck -- sichtbar
        # erst auf Papier. Die Felder bleiben beschreibbar, weil eine Vorlage
        # auch eine Schrift nennen darf, die nur bei der Druckerei liegt.
        self.body_font = _font_combo()
        self.heading_font = _font_combo(empty_label="— wie Grundschrift —")
        self.mono_font = _font_combo(fixed_pitch=True)
        self.base_size = _pt_spin(maximum=72.0, minimum=4.0)
        self.line_height = QDoubleSpinBox()
        self.line_height.setRange(0.5, 4.0)
        self.line_height.setSingleStep(0.05)
        self.line_height.setDecimals(2)
        self.language = QLineEdit()
        self.language.setPlaceholderText("de-DE")
        self.hyphenation = QCheckBox("Silbentrennung")
        self.hyphenate_caps = QCheckBox("Auch Wörter in Großbuchstaben trennen")
        self.hyphenation_zone = _mm_spin(50)

        form.addRow("Grundschrift", self.body_font)
        form.addRow(
            _info(
            "Überschriften",
            "Schrift für alle Überschriftenebenen. Leer lassen heißt: dieselbe "
            "wie der Fließtext.",
        ),
            self.heading_font,
        )
        form.addRow(
            _info(
            "Feste Breite",
            "Schrift für Codeblöcke und Inline-Code — jedes Zeichen gleich "
            "breit, damit Einrückungen stimmen.",
        ),
            self.mono_font,
        )
        form.addRow(
            _info(
            "Grundgröße",
            "Die Schriftgröße des Fließtextes. Jedes Absatzformat ohne eigene "
            "Größe erbt diese — im Formatformular steht sie dann als "
            "»geerbt« mit dieser Zahl daneben.",
        ),
            self.base_size,
        )
        form.addRow("Zeilenhöhe", self.line_height)
        form.addRow(
            _info(
            "Sprache",
            "Steuert zweierlei: nach welchen Regeln getrennt wird und wie die "
            "Überschrift des Inhaltsverzeichnisses heißt (de-DE → "
            "»Inhaltsverzeichnis«).",
        ),
            self.language,
        )
        form.addRow(
            _info(
            "",
            "Trennt lange Wörter am Zeilenende. Im Blocksatz fast immer "
            "sinnvoll, sonst entstehen große Lücken zwischen den Wörtern.",
        ),
            self.hyphenation,
        )
        form.addRow(
            _info(
            "Trennzone",
            "Wie nah ein Wort an den rechten Rand heranreichen muss, bevor "
            "getrennt wird. Kleine Werte trennen häufiger, große seltener — "
            "und lassen den Rand unruhiger wirken.",
        ),
            self.hyphenation_zone,
        )
        form.addRow(
            _info(
            "",
            "Betrifft Wörter in Versalien wie ABKÜRZUNGEN. Viele Verlage "
            "trennen sie nicht, weil es im Satzbild stört.",
        ),
            self.hyphenate_caps,
        )

        for widget in (self.body_font, self.heading_font, self.mono_font):
            widget.currentTextChanged.connect(self._emit)
        self.language.textChanged.connect(self._emit)
        for widget in (self.base_size, self.line_height, self.hyphenation_zone):
            widget.valueChanged.connect(self._emit)
        for widget in (self.hyphenation, self.hyphenate_caps):
            widget.toggled.connect(self._emit)
        _share_label_tooltips(self)

    def _emit(self, *_args: Any) -> None:
        self.changed.emit()

    def load(self, typography: Typography) -> None:
        widgets = self._widgets()
        blockers = [w.blockSignals(True) for w in widgets]
        set_font_value(self.body_font, typography.body_font)
        set_font_value(self.heading_font, typography.heading_font)
        set_font_value(self.mono_font, typography.mono_font)
        self.base_size.setValue(typography.base_size_pt)
        self.line_height.setValue(typography.line_height)
        self.language.setText(typography.language)
        self.hyphenation.setChecked(typography.hyphenation)
        self.hyphenation_zone.setValue(typography.hyphenation_zone_mm)
        self.hyphenate_caps.setChecked(typography.hyphenate_caps)
        for widget, blocked in zip(widgets, blockers):
            widget.blockSignals(blocked)

    def _widgets(self) -> list[QWidget]:
        return [
            self.body_font, self.heading_font, self.mono_font, self.base_size,
            self.line_height, self.language, self.hyphenation,
            self.hyphenation_zone, self.hyphenate_caps,
        ]

    def collect(self, typography: Typography) -> Typography:
        return replace(
            typography,
            body_font=font_value(self.body_font) or typography.body_font,
            heading_font=font_value(self.heading_font),
            mono_font=font_value(self.mono_font) or typography.mono_font,
            base_size_pt=self.base_size.value(),
            line_height=self.line_height.value(),
            language=self.language.text().strip() or "de-DE",
            hyphenation=self.hyphenation.isChecked(),
            hyphenation_zone_mm=self.hyphenation_zone.value(),
            hyphenate_caps=self.hyphenate_caps.isChecked(),
        )


class _ColorsForm(QWidget):
    """Die Farbtokens des Layouts -- eine Aenderung wirkt ueberall."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._colors: dict[str, str] = {}
        outer = QVBoxLayout(self)

        hint = QLabel(
            "Formate verweisen über den Namen auf diese Farben. Wer »accent« "
            "hier ändert, ändert Titel, Überschriften und Fragetext auf einmal."
        )
        hint.setWordWrap(True)
        hint.setObjectName(MUTED_NAME)
        outer.addWidget(hint)

        self._form_host = QWidget()
        self._form = QFormLayout(self._form_host)
        outer.addWidget(self._form_host)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Farbe hinzufügen…")
        buttons.addWidget(self.add_button)
        buttons.addStretch(1)
        outer.addLayout(buttons)
        outer.addStretch(1)

        self.add_button.clicked.connect(self._add_colour)

    def set_usage_lookup(self, lookup: Any) -> None:
        """Sagt, welche Absatzformate einen Token benutzen -- fuer die Rueckfrage.

        Der Dialog weiss das, dieses Formular nicht: Es sieht nur die Farben.
        Ohne die Auskunft muesste die Rueckfrage vor dem Loeschen schweigen,
        und gerade sie ist die einzige Angabe, die die Entscheidung beeinflusst.
        """
        self._usage_lookup = lookup

    def load(self, colors: dict[str, str]) -> None:
        self._colors = dict(colors)
        while self._form.rowCount():
            self._form.removeRow(0)
        for token in sorted(self._colors):
            zeile = QWidget()
            zeilen_layout = QHBoxLayout(zeile)
            zeilen_layout.setContentsMargins(0, 0, 0, 0)

            button = _ColorButton()
            button.set_resolver(lambda value: value)
            button.set_value(self._colors[token])
            button.changed.connect(
                lambda _=None, name=token, widget=button: self._on_colour(name, widget)
            )
            zeilen_layout.addWidget(button, 1)

            weg = QToolButton()
            weg.setText("×")
            weg.setToolTip(f"Farbe »{token}« entfernen")
            weg.clicked.connect(lambda _=None, name=token: self._remove(name))
            zeilen_layout.addWidget(weg)

            self._form.addRow(
            _info(
                token,
                f"Der Farbtoken »{token}«. Absatzformate verweisen auf den "
                "Namen, nicht auf den Hexwert — eine Änderung hier wirkt "
                "deshalb überall, wo er benutzt wird.\n"
                "Genau dafür sind Tokens da: eine Farbe, eine Stelle.",
            ),
            zeile,
        )

    def _on_colour(self, token: str, widget: _ColorButton) -> None:
        value = widget.value()
        if value:
            self._colors[token] = value
            self.changed.emit()

    def _remove(self, token: str) -> None:
        """Entfernt einen Farbtoken -- nach einer Rueckfrage, die ihn einordnet.

        Wer einen benutzten Token entfernt, hinterlaesst Formate, die auf einen
        Namen zeigen, den es nicht mehr gibt. Das Layout ist dann nicht mehr
        erzeugbar, und die Problemzeile sagt es auch -- aber erst hinterher.
        Besser vorher.
        """
        benutzer = list(getattr(self, "_usage_lookup", lambda _t: [])(token))
        frage = f"Farbe »{token}« entfernen?"
        if benutzer:
            frage += (
                "\n\nDarauf zeigen noch: "
                + ", ".join(sorted(benutzer))
                + "\nDiese Formate wären danach nicht mehr erzeugbar, bis du "
                "ihnen eine andere Farbe gibst."
            )
        if QMessageBox.question(self, "Farbe entfernen", frage) != (
            QMessageBox.StandardButton.Yes
        ):
            return
        self._colors.pop(token, None)
        self.load(self._colors)
        self.changed.emit()

    def _add_colour(self) -> None:
        token, ok = QInputDialog.getText(self, "Neue Farbe", "Name (z. B. accent3):")
        token = (token or "").strip()
        if not ok or not token:
            return
        if token in self._colors:
            QMessageBox.information(self, "Farbe", f"»{token}« gibt es schon.")
            return
        self._colors[token] = "888888"
        self.load(self._colors)
        self.changed.emit()

    def collect(self) -> dict[str, str]:
        return dict(self._colors)


class _ClassmapForm(QWidget):
    """Welche Markdown-Klasse auf welches Absatzformat zeigt."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._entries: dict[str, str] = {}
        self._style_ids: list[str] = []

        outer = QVBoxLayout(self)
        hint = QLabel(
            "Die Brücke zwischen Auszeichnung und Gestaltung: Was der Generator "
            "als <code>::: {.prompt}</code> schreibt, wird hier zu einem "
            "benannten Absatzformat der .docx. Ohne diesen Eintrag bleibt der Absatz "
            "Fließtext."
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setObjectName(MUTED_NAME)
        outer.addWidget(hint)

        # Hier faellt die Verwechslung am ehesten an: Wer eine Klasse zuordnet,
        # denkt an "den Kasten im Buch" -- und meint damit oft das PDF.
        reichweite = QLabel(DOCX_ONLY_NOTICE)
        reichweite.setWordWrap(True)
        reichweite.setObjectName(ALERT_NAME)
        outer.addWidget(reichweite)

        self._form_host = QWidget()
        self._form = QFormLayout(self._form_host)
        outer.addWidget(self._form_host)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Klasse hinzufügen…")
        self.remove_button = QPushButton("Ausgewählte entfernen")
        self.remove_button.hide()
        buttons.addWidget(self.add_button)
        buttons.addStretch(1)
        outer.addLayout(buttons)

        outer.addWidget(self._build_book_check())
        outer.addStretch(1)

        self.add_button.clicked.connect(self._add_entry)

    def _build_book_check(self) -> QWidget:
        """Der Abgleich mit dem Buch -- die Antwort auf \"warum passiert nichts?\".

        Die Klassen-Abbildung allein sagt nur, was zugeordnet **ist**. Erst der
        Blick in den Text sagt, was zugeordnet sein **muesste**. Ohne diesen
        Vergleich faellt eine fehlende Zuordnung erst in der fertigen ``.docx``
        auf, und dort sieht sie aus wie ein Fehler der Vorlage.
        """
        box = QGroupBox("Abgleich mit dem Buch")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        self.check_button = QPushButton("Buch prüfen…")
        self.check_button.setToolTip(
            "Durchsucht die Markdown-Dateien eines Buchprojekts nach "
            "::: {.klasse}-Blöcken und hält sie gegen diese Zuordnung."
        )
        row.addWidget(self.check_button)
        self.book_label = QLabel("Noch kein Buch geprüft.")
        self.book_label.setObjectName(MUTED_NAME)
        row.addWidget(self.book_label, 1)
        layout.addLayout(row)

        self.check_result = QLabel()
        self.check_result.setWordWrap(True)
        self.check_result.setTextFormat(Qt.TextFormat.RichText)
        self.check_result.hide()
        layout.addWidget(self.check_result)

        self.create_missing_button = QPushButton("Fehlende Klassen anlegen")
        self.create_missing_button.setToolTip(
            "Legt für jede gefundene Klasse ohne Zuordnung ein Absatzformat an "
            "und verbindet es. Vorhandene Formate werden nicht angefasst."
        )
        self.create_missing_button.hide()
        layout.addWidget(self.create_missing_button)
        return box

    def show_comparison(
        self,
        comparison: Optional[Comparison],
        book: str,
        generator: Any = None,
    ) -> None:
        """Stellt das Ergebnis eines Abgleichs dar."""
        self.book_label.setText(book or "Noch kein Buch geprüft.")
        if comparison is None:
            self.check_result.hide()
            self.create_missing_button.hide()
            return

        teile: list[str] = []
        if comparison.unmapped:
            zeilen = "<br>".join(
                f"&nbsp;&nbsp;<b>.{u.name}</b> — {u.count}× in "
                f"{len(u.files)} Datei(en)"
                for u in comparison.unmapped
            )
            teile.append(
                f'<span style="color:{_CHECK_ALERT}">'
                f"{len(comparison.unmapped)} Klasse(n) fehlen in der "
                f"DOCX-Vorlage — diese Absätze bleiben in der Word-Fassung "
                f"unformatiert:</span><br>{zeilen}"
            )
        else:
            teile.append(
                f'<span style="color:{_CHECK_OK}">Jede benutzte Klasse hat '
                f"eine Zuordnung.</span>"
            )
        if comparison.mapped:
            teile.append(f"{len(comparison.mapped)} zugeordnet und benutzt.")
        if comparison.builtin:
            namen = ", ".join(f".{b.name}" for b in comparison.builtin)
            teile.append(f"Von Quarto selbst bedient: {namen}")
        if comparison.unused:
            namen = ", ".join(f".{n}" for n in comparison.unused)
            teile.append(f"Zugeordnet, aber im Buch nicht benutzt: {namen}")
        if comparison.legacy_form:
            zeilen = "<br>".join(
                f"&nbsp;&nbsp;<b>{{{m.name}}}</b> — {m.count}×"
                for m in comparison.legacy_form
            )
            teile.append(
                f'<span style="color:{_CHECK_OK}">In der Altform geschrieben '
                f"(<code>::: {{name}}</code> statt <code>::: {{.name}}</code>) — "
                f"<b>funktioniert</b>: classmap.lua fängt diese Form ab, die "
                f"Blöcke bekommen ihr Absatzformat. Wer den Export "
                f"geradezieht, wird sie los:</span><br>{zeilen}"
            )
        if generator is not None and not generator.is_empty:
            quelle = f" (aus {generator.source})" if generator.source else ""
            namen = ", ".join(f".{n}" for n in generator.names) or "keine"
            zeile = f"Laut letztem Generator-Export{quelle}: {namen}"
            if generator.malformed:
                altform = ", ".join(f"{{{n}}}" for n in sorted(generator.malformed))
                zeile += (
                    f'<br><span style="color:{StatusFg.NEUTRAL}">'
                    f"In der Altform schon im Export: {altform}</span>"
                )
            teile.append(zeile)

        self.check_result.setText("<br><br>".join(teile))
        self.check_result.show()
        anzahl = len(comparison.unmapped)
        self.create_missing_button.setVisible(anzahl > 0)
        self.create_missing_button.setText(
            f"Fehlende Klassen anlegen ({anzahl})" if anzahl else "Fehlende Klassen anlegen"
        )

    def load(self, classmap: dict[str, str], style_ids: list[str]) -> None:
        self._entries = dict(classmap)
        self._style_ids = list(style_ids)
        while self._form.rowCount():
            self._form.removeRow(0)
        for cls in sorted(self._entries):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            combo = QComboBox()
            combo.addItems(self._style_ids)
            index = combo.findText(self._entries[cls])
            if index < 0:
                combo.addItem(self._entries[cls])
                index = combo.count() - 1
                combo.setObjectName(ALERT_NAME)
            combo.setCurrentIndex(index)
            combo.currentTextChanged.connect(
                lambda text, name=cls: self._on_target(name, text)
            )
            row_layout.addWidget(combo, 1)
            drop = QToolButton()
            drop.setText("×")
            drop.setToolTip(f"Klasse .{cls} entfernen")
            drop.clicked.connect(lambda _=None, name=cls: self._remove(name))
            row_layout.addWidget(drop)
            self._form.addRow(
                _info(
                    f".{cls}",
                    f"Blöcke der Form ::: {{.{cls}}} bekommen das hier "
                    "gewählte Absatzformat.\n"
                    "Ohne diesen Eintrag bleiben sie Fließtext — das ist die "
                    "häufigste Ursache für einen fehlenden Kasten in der "
                    ".docx.",
                ),
                row,
            )

    def _on_target(self, cls: str, style_id: str) -> None:
        self._entries[cls] = style_id
        self.changed.emit()

    def _remove(self, cls: str) -> None:
        self._entries.pop(cls, None)
        self.load(self._entries, self._style_ids)
        self.changed.emit()

    def _add_entry(self) -> None:
        cls, ok = QInputDialog.getText(
            self, "Neue Klasse", "Markdown-Klasse ohne Punkt (z. B. merksatz):"
        )
        cls = (cls or "").strip().lstrip(".")
        if not ok or not cls:
            return
        if cls in self._entries:
            QMessageBox.information(self, "Klasse", f"».{cls}« gibt es schon.")
            return
        self._entries[cls] = self._style_ids[0] if self._style_ids else ""
        self.load(self._entries, self._style_ids)
        self.changed.emit()

    def collect(self) -> dict[str, str]:
        return {k: v for k, v in self._entries.items() if v}


__all__ = [
    "_ClassmapForm",
    "_ColorsForm",
    "_PageForm",
    "_TypographyForm",
]
