"""Das Formular für ein einzelnes Absatzformat.

Mit Abstand das größte der Formulare — ein Absatzformat hat Schrift, Abstände,
Einzüge, Rahmen und Fläche, und jede dieser Eigenschaften braucht eine
Erklärung, weil ihre Wirkung erst im gesetzten Dokument sichtbar wird.

Es wird an zwei Stellen benutzt: im Editor und im Assistenten. Ein zweites
Formular für denselben Zweck zu bauen hieße, jede Änderung an den Feldern
zweimal zu machen — und beim zweiten Mal irgendwann nicht mehr.

Der Vertrag ist derselbe wie bei den übrigen Formularen: set_context()
sagt, welche Formate zur Auswahl stehen und was ein geerbter Wert bedeutet,
load() füllt, collect() liest zurück, changed meldet.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.constants import StatusFg
from tools.doclayout.schema import (
    ALIGNMENTS,
    BORDER_EDGES,
    Border,
    Indent,
    LayoutDefinition,
    ParagraphStyle,
)
from ui_qt.dialogs.doclayout_widgets import (
    _ALIGN_LABELS,
    _ColorButton,
    _info,
    _mm_spin,
    _or_inherited,
    _pt_spin,
    _share_label_tooltips,
)

class _StyleForm(QWidget):
    """Ein Absatzformat -- Schrift, Abstände, Einzüge, Rahmen."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._style: Optional[ParagraphStyle] = None
        self._colour_buttons: list[_ColorButton] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        outer.addWidget(tabs)

        tabs.addTab(self._build_text_tab(), "Schrift")
        tabs.addTab(self._build_paragraph_tab(), "Absatz")
        tabs.addTab(self._build_frame_tab(), "Rahmen und Fläche")

    # -- Aufbau ------------------------------------------------------------

    def _build_text_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.name = QLineEdit()

        # Auswahl statt Freitext: Beide Felder verweisen auf ein anderes
        # Absatzformat. Ein Tippfehler erzeugte dort stillschweigend einen
        # Verweis ins Leere, den man erst in der fertigen .docx bemerkt.
        self.based_on = QComboBox()
        self.based_on.setEditable(True)
        self.based_on.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.next_style = QComboBox()
        self.next_style.setEditable(True)
        self.next_style.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.size = _pt_spin(maximum=200.0)
        self.size.setSpecialValueText("— geerbt —")
        self.size_hint = QLabel()
        self.size_hint.setStyleSheet(f"color: {StatusFg.NEUTRAL};")
        groesse_zeile = QWidget()
        groesse_layout = QHBoxLayout(groesse_zeile)
        groesse_layout.setContentsMargins(0, 0, 0, 0)
        groesse_layout.addWidget(self.size, 1)
        groesse_layout.addWidget(self.size_hint)

        self.bold = QCheckBox("Fett")
        self.italic = QCheckBox("Kursiv")
        self.colour = _ColorButton()
        self.letter_spacing = _pt_spin(maximum=40.0)
        # 0 ist hier der neutrale Wert, kein gesetzter -- ``collect`` macht
        # daraus ``None``. Als "0,00 pt" sah das aus wie eine Entscheidung.
        self.letter_spacing.setSpecialValueText("— normal —")

        form.addRow(
            _info(
            "Anzeigename",
            "Wie das Format in Words Formatkatalog heißt. Bleibt es leer, "
            "benutzt Word den Bezeichner — er steht grau im Feld.",
        ),
            self.name,
        )
        form.addRow(
            _info(
            "Basiert auf",
            "Das Format, von dem dieses alles übernimmt, was es nicht selbst "
            "setzt — Schrift, Größe, Abstände.\n"
            "Beispiel: »FirstParagraph basiert auf BodyText« heißt gleiche "
            "Schrift und Größe, nur der Einzug ist anders.\n"
            "Leer = baut auf nichts auf.\n"
            "Formate, die ihrerseits auf diesem aufbauen, stehen nicht zur "
            "Auswahl — das gäbe einen Ringschluss.",
        ),
            self.based_on,
        )
        form.addRow(
            _info(
            "Folgeformat",
            "Welches Format der nächste Absatz bekommt, wenn man in Word am "
            "Ende dieses Absatzes die Eingabetaste drückt.\n"
            "Beispiel: Nach einer Überschrift soll Fließtext kommen, nicht "
            "wieder eine Überschrift.\n"
            "Leer = dasselbe Format noch einmal.",
        ),
            self.next_style,
        )
        form.addRow(
            _info(
            "Größe",
            "»geerbt« heißt: keine eigene Größe — das Format übernimmt sie von "
            "dem, worauf es basiert, sonst vom Grundschriftgrad. Wie groß das "
            "am Ende ist, steht rechts daneben.",
        ),
            groesse_zeile,
        )
        form.addRow("", self.bold)
        form.addRow("", self.italic)
        form.addRow(
            _info(
            "Schriftfarbe",
            "Am besten ein Farbtoken (accent, rule …) statt eines festen "
            "Hexwerts: Eine Änderung unter »Farben« wirkt dann in allen "
            "Formaten, die dasselbe Token benutzen.",
        ),
            self.colour,
        )
        form.addRow(
            _info(
            "Laufweite",
            "Zusätzlicher Abstand zwischen den Buchstaben (Sperrung).\n"
            "»normal« heißt: keiner — die Schrift bleibt, wie sie gebaut ist.",
        ),
            self.letter_spacing,
        )
        self._colour_buttons.append(self.colour)
        return page

    def _build_paragraph_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.align = QComboBox()
        self.align.addItem("— geerbt —", None)
        for value in ALIGNMENTS:
            self.align.addItem(_ALIGN_LABELS[value], value)
        # -1 steht fuer «kein eigener Wert». Ohne diesen Unterschied waere
        # «ausdruecklich kein Abstand» (bei Listen ueblich) nicht von «erbt
        # den Abstand» zu unterscheiden -- und jedes Ansehen schriebe ein
        # solches Format still um. Betroffen waren zehn der neununddreissig
        # Formate im Referenz-Layout und jedes frisch angelegte.
        self.space_before = _pt_spin(maximum=200.0, minimum=-1.0)
        self.space_before.setSpecialValueText("— geerbt —")
        self.space_after = _pt_spin(maximum=200.0, minimum=-1.0)
        self.space_after.setSpecialValueText("— geerbt —")
        self.line_height = QDoubleSpinBox()
        self.line_height.setRange(0.0, 4.0)
        self.line_height.setSingleStep(0.05)
        self.line_height.setDecimals(2)
        self.line_height.setSpecialValueText("— geerbt —")
        self.indent_left = _mm_spin(200)
        self.indent_right = _mm_spin(200)
        self.indent_hanging = _mm_spin(200)
        self.indent_first = _mm_spin(200)
        self.keep_next = QCheckBox("Mit nächstem Absatz zusammenhalten")
        self.keep_lines = QCheckBox("Absatz nicht trennen")
        self.page_break = QCheckBox("Seitenumbruch davor")
        self.outline = QSpinBox()
        self.outline.setRange(-1, 8)
        self.outline.setSpecialValueText("— nicht im Verzeichnis —")

        form.addRow("Ausrichtung", self.align)
        form.addRow(
            _info(
            "Abstand davor",
            "Luft über dem Absatz.\n"
            "»geerbt« = kein eigener Wert; 0 = ausdrücklich kein Abstand. Das "
            "ist ein Unterschied: Listen setzen oft bewusst 0.",
        ),
            self.space_before,
        )
        form.addRow(
            _info(
            "Abstand danach",
            "Luft unter dem Absatz. Word addiert sie **nicht** zum Abstand "
            "davor des nächsten Absatzes, sondern nimmt den größeren von "
            "beiden.",
        ),
            self.space_after,
        )
        form.addRow("Zeilenhöhe", self.line_height)
        form.addRow("Einzug links", self.indent_left)
        form.addRow("Einzug rechts", self.indent_right)
        form.addRow(
            _info(
            "Hängend",
            "Alle Zeilen außer der ersten werden zusätzlich eingerückt — der "
            "typische Aufbau von Listen und Literaturangaben, bei denen die "
            "erste Zeile nach links heraussteht.",
        ),
            self.indent_hanging,
        )
        form.addRow(
            _info(
            "Erste Zeile",
            "Zusätzlicher Einzug nur der ersten Zeile — der klassische "
            "Absatzeinzug im Buchsatz. Deshalb gibt es FirstParagraph: der "
            "erste Absatz nach einer Überschrift bekommt ihn nicht.",
        ),
            self.indent_first,
        )
        form.addRow(
            _info(
            "",
            "Verhindert, dass zwischen diesem und dem nächsten Absatz eine "
            "Seite umbricht. Für Überschriften unverzichtbar — sonst steht "
            "eine allein am Seitenende.",
        ),
            self.keep_next,
        )
        form.addRow(
            _info(
            "",
            "Hält den Absatz als Ganzes zusammen, statt ihn über zwei Seiten "
            "zu verteilen.",
        ),
            self.keep_lines,
        )
        form.addRow(
            _info(
            "",
            "Beginnt vor diesem Absatz immer eine neue Seite. Üblich für "
            "Kapitelüberschriften.",
        ),
            self.page_break,
        )
        form.addRow(
            _info(
            "Gliederungsebene",
            "Auf welcher Stufe der Absatz im Inhaltsverzeichnis und in Words "
            "Navigationsbereich erscheint.\n"
            "0 ist die oberste Stufe (wie Überschrift 1), 8 die unterste. "
            "Gar nicht im Verzeichnis steht der Absatz mit "
            "»— nicht im Verzeichnis —«, dem Wert unterhalb der Null.",
        ),
            self.outline,
        )
        return page

    def _build_frame_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        fill_form = QFormLayout()
        self.shading = _ColorButton()
        self._colour_buttons.append(self.shading)
        fill_form.addRow(
            _info(
            "Hintergrund",
            "Füllfarbe hinter dem Absatz — damit entsteht der Kasten. Auch "
            "hier ist ein Farbtoken besser als ein fester Hexwert.",
        ),
            self.shading,
        )
        outer.addLayout(fill_form)

        self.border_widgets: dict[str, dict[str, Any]] = {}
        labels = {"top": "Oben", "bottom": "Unten", "left": "Links", "right": "Rechts"}
        for edge in BORDER_EDGES:
            box = QGroupBox(labels[edge])
            box.setCheckable(True)
            box.setChecked(False)
            form = QFormLayout(box)
            width = _pt_spin(maximum=12.0)
            colour = _ColorButton()
            self._colour_buttons.append(colour)
            space = _pt_spin(maximum=40.0)
            form.addRow(
            _info(
            "Stärke",
            "Dicke der Linie. Word rundet auf Achtelpunkte — sehr feine "
            "Unterschiede verschwinden.",
        ),
            width,
        )
            form.addRow(
            _info(
                "Farbe",
                "Farbe der Linie. Ein Farbtoken ist einem festen Hexwert "
                "vorzuziehen — sonst muss man beim Umfärben jede Kante "
                "einzeln suchen.",
            ),
            colour,
        )
            form.addRow(
            _info(
            "Abstand",
            "Luft zwischen Linie und Text. Ohne sie klebt der Text am Rahmen.",
        ),
            space,
        )
            outer.addWidget(box)
            self.border_widgets[edge] = {
                "box": box, "width": width, "colour": colour, "space": space,
            }
        outer.addStretch(1)
        return page

    def connect_signals(self) -> None:
        self.name.textChanged.connect(self._emit)
        # ``based_on`` und ``next_style`` sind Auswahlfelder mit freier Eingabe;
        # ``currentTextChanged`` deckt beides ab -- Auswahl wie Getipptes.
        for widget in (self.based_on, self.next_style):
            widget.currentTextChanged.connect(self._emit)
        self.size.valueChanged.connect(lambda _v: self._update_size_hint())
        for widget in (
            self.size, self.letter_spacing, self.space_before, self.space_after,
            self.line_height, self.indent_left, self.indent_right,
            self.indent_hanging, self.indent_first,
        ):
            widget.valueChanged.connect(self._emit)
        for widget in (self.bold, self.italic, self.keep_next, self.keep_lines, self.page_break):
            widget.toggled.connect(self._emit)
        self.align.currentIndexChanged.connect(self._emit)
        self.outline.valueChanged.connect(self._emit)
        for button in self._colour_buttons:
            button.changed.connect(self._emit)
        for widgets in self.border_widgets.values():
            widgets["box"].toggled.connect(self._emit)
            widgets["width"].valueChanged.connect(self._emit)
            widgets["space"].valueChanged.connect(self._emit)
        _share_label_tooltips(self)

    def set_colour_resolver(self, resolver: Callable[[Optional[str]], Optional[str]]) -> None:
        for button in self._colour_buttons:
            button.set_resolver(resolver)

    def _emit(self, *_args: Any) -> None:
        self.changed.emit()

    # -- Laden und Einsammeln ---------------------------------------------

    def set_context(self, definition: LayoutDefinition, style_id: str = "") -> None:
        """Gibt dem Formular, was es fuer seine Auskuenfte braucht.

        Ohne die Definition kann es zwei Fragen nicht beantworten, die sich
        beim Gestalten zwangslaeufig stellen: *welche* Formate stehen zur
        Auswahl, und *wie gross* ist eine geerbte Groesse am Ende. Beides ist
        keine Gestaltung, sondern Auskunft -- und ohne sie ist das Formular ein
        Ratespiel.
        """
        self._definition = definition
        # «Basiert auf» darf nur zeigen, was keinen Kreis ergibt: weder das
        # Format selbst noch etwas, das seinerseits darauf aufbaut. «Folgeformat»
        # kennt diese Einschraenkung nicht -- dort darf jedes Format stehen,
        # auch das eigene (ein Absatz, dem wieder derselbe folgt).
        moegliche_basen = (
            definition.possible_bases(style_id) if style_id else sorted(definition.styles)
        )
        for combo, auswahl in (
            (self.based_on, moegliche_basen),
            (self.next_style, sorted(definition.styles)),
        ):
            aktuell = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            combo.addItems(auswahl)
            combo.setCurrentText(aktuell)
            combo.blockSignals(False)
        self._update_size_hint(style_id)

    def _update_size_hint(self, style_id: str = "") -> None:
        """Schreibt neben das Groessenfeld, welche Groesse tatsaechlich gilt.

        «geerbt» allein ist eine Auskunft, die nichts sagt -- wer gestaltet,
        will die Zahl sehen und wissen, woher sie kommt.
        """
        definition = getattr(self, "_definition", None)
        ziel = style_id or (self._style.style_id if self._style else "")
        if definition is None or not ziel or self.size.value():
            self.size_hint.setText("")
            return
        gilt = definition.resolve_size_pt(ziel)
        if gilt is None:
            self.size_hint.setText("")
            return
        woher = definition.size_origin(ziel)
        quelle = f"von {woher}" if woher else "Grundschriftgrad"
        # Komma wie in den Feldern daneben -- ein Punkt sähe aus, als
        # käme die Zahl aus einem anderen Programm.
        zahl = f"{gilt:.1f}".replace(".", ",")
        self.size_hint.setText(f"= {zahl} pt ({quelle})")

    def load(self, style: ParagraphStyle) -> None:
        self._style = style
        widgets = self._all_widgets()
        blockers = [w.blockSignals(True) for w in widgets]

        self.name.setText(style.name)
        # Was ohne Anzeigenamen gilt, steht grau im Feld -- leer allein liesse
        # offen, wie das Format in Word heisst.
        self.name.setPlaceholderText(style.style_id)
        self.based_on.setCurrentText(style.based_on or "")
        self.next_style.setCurrentText(style.next_style or "")
        self.size.setValue(style.size_pt or 0.0)
        self.bold.setChecked(style.bold)
        self.italic.setChecked(style.italic)
        self.colour.set_value(style.color)
        self.letter_spacing.setValue(style.letter_spacing_pt or 0.0)

        index = self.align.findData(style.align)
        self.align.setCurrentIndex(max(0, index))
        self.space_before.setValue(
            style.space_before_pt if style.space_before_pt is not None else -1.0
        )
        self.space_after.setValue(
            style.space_after_pt if style.space_after_pt is not None else -1.0
        )
        self.line_height.setValue(style.line_height or 0.0)
        self.indent_left.setValue(style.indent.left_mm)
        self.indent_right.setValue(style.indent.right_mm)
        self.indent_hanging.setValue(style.indent.hanging_mm)
        self.indent_first.setValue(style.indent.first_line_mm)
        self.keep_next.setChecked(style.keep_next)
        self.keep_lines.setChecked(style.keep_lines)
        self.page_break.setChecked(style.page_break_before)
        self.outline.setValue(-1 if style.outline_level is None else style.outline_level)

        self.shading.set_value(style.shading)
        for edge, widgets_map in self.border_widgets.items():
            border = style.borders.get(edge)
            widgets_map["box"].setChecked(border is not None)
            widgets_map["width"].setValue(border.width_pt if border else 0.5)
            widgets_map["colour"].set_value(border.color if border else "rule")
            widgets_map["space"].setValue(border.space_pt if border else 3.0)

        for widget, blocked in zip(widgets, blockers):
            widget.blockSignals(blocked)
        self._update_size_hint(style.style_id)

    def _all_widgets(self) -> list[QWidget]:
        widgets: list[QWidget] = [
            self.name, self.based_on, self.next_style, self.size, self.bold,
            self.italic, self.colour, self.letter_spacing, self.align,
            self.space_before, self.space_after, self.line_height,
            self.indent_left, self.indent_right, self.indent_hanging,
            self.indent_first, self.keep_next, self.keep_lines, self.page_break,
            self.outline, self.shading,
        ]
        for widgets_map in self.border_widgets.values():
            widgets.extend(
                [widgets_map["box"], widgets_map["width"],
                 widgets_map["colour"], widgets_map["space"]]
            )
        return widgets

    def collect(self) -> Optional[ParagraphStyle]:
        if self._style is None:
            return None
        borders: dict[str, Border] = {}
        for edge, widgets_map in self.border_widgets.items():
            if not widgets_map["box"].isChecked():
                continue
            borders[edge] = Border(
                width_pt=widgets_map["width"].value(),
                color=widgets_map["colour"].value() or "auto",
                space_pt=widgets_map["space"].value(),
                style="single",
            )
        outline = self.outline.value()
        return replace(
            self._style,
            name=self.name.text().strip(),
            based_on=self.based_on.currentText().strip() or None,
            next_style=self.next_style.currentText().strip() or None,
            size_pt=self.size.value() or None,
            bold=self.bold.isChecked(),
            italic=self.italic.isChecked(),
            color=self.colour.value(),
            letter_spacing_pt=self.letter_spacing.value() or None,
            align=self.align.currentData(),
            space_before_pt=_or_inherited(self.space_before.value()),
            space_after_pt=_or_inherited(self.space_after.value()),
            line_height=self.line_height.value() or None,
            indent=Indent(
                left_mm=self.indent_left.value(),
                right_mm=self.indent_right.value(),
                hanging_mm=self.indent_hanging.value(),
                first_line_mm=self.indent_first.value(),
            ),
            keep_next=self.keep_next.isChecked(),
            keep_lines=self.keep_lines.isChecked(),
            page_break_before=self.page_break.isChecked(),
            outline_level=None if outline < 0 else outline,
            shading=self.shading.value(),
            borders=borders,
        )


__all__ = ["_StyleForm"]
