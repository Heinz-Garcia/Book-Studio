"""Tests fuer die Feld-Erklaerungen im Layout-Editor.

Jedes Feld, dessen Bedeutung nicht offensichtlich ist, traegt ein (i) vor der
Beschriftung. Bewusst nicht jedes: "Breite" und "Oben" erklaeren sich selbst,
und ein Symbol davor waere Rauschen, das die echten Hinweise entwertet.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from ui_qt.dialogs.doclayout_editor_dialog import (  # noqa: E402
    _PageForm,
    _StyleForm,
    _TypographyForm,
    _info,
)

@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _symbole(widget) -> list[QLabel]:
    """Alle (i)-Symbole eines Formulars.

    Erkennbar am Bild: Seit das Symbol gemalt statt gesetzt wird, traegt das
    Etikett keinen Text mehr. Das schliesst die Kurzhilfe-Leiste gleich mit
    aus -- die benutzt eine Glyphe.
    """
    return [
        w
        for w in widget.findChildren(QLabel)
        if w.pixmap() is not None and not w.pixmap().isNull()
    ]


# ---------------------------------------------------------------------------
# Der Helfer
# ---------------------------------------------------------------------------


def test_the_helper_shows_symbol_and_text(qapp):
    host = _info("Beschriftung", "Die Erklärung.")
    assert len(_symbole(host)) == 1
    assert "Beschriftung" in [w.text() for w in host.findChildren(QLabel)]


def test_the_explanation_hangs_on_everything(qapp):
    """Man soll den Tooltip nicht genau treffen muessen."""
    host = _info("Beschriftung", "Die Erklärung.")
    assert host.toolTip() == "Die Erklärung."
    for w in host.findChildren(QLabel):
        assert w.toolTip() == "Die Erklärung."


def test_a_checkbox_row_gets_only_the_symbol(qapp):
    """Ankreuzfelder tragen ihren Text selbst -- die Beschriftung bleibt leer."""
    host = _info("", "Die Erklärung.")
    assert len(_symbole(host)) == 1
    assert [w.text() for w in host.findChildren(QLabel)] == [""]


# ---------------------------------------------------------------------------
# Die Formulare
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("klasse", "mindestens"),
    [(_PageForm, 4), (_TypographyForm, 6), (_StyleForm, 14)],
)
def test_every_form_carries_explanations(qapp, klasse, mindestens: int):
    form = klasse()
    try:
        assert len(_symbole(form)) >= mindestens
    finally:
        form.close()


@pytest.mark.parametrize("klasse", [_PageForm, _TypographyForm, _StyleForm])
def test_no_symbol_is_left_without_an_explanation(qapp, klasse):
    """Ein (i) ohne Inhalt waere ein gebrochenes Versprechen."""
    form = klasse()
    try:
        leer = [w for w in _symbole(form) if not w.toolTip().strip()]
        assert leer == []
    finally:
        form.close()


def test_the_word_terms_are_explained(qapp):
    """Die Begriffe, an denen die Benutzung haengenblieb."""
    form = _StyleForm()
    try:
        erklaerungen = " ".join(w.toolTip() for w in _symbole(form))
        for begriff in ("Eingabetaste", "übernimmt", "geerbt", "Sperrung"):
            assert begriff in erklaerungen, f"{begriff} wird nicht erklärt"
    finally:
        form.close()


def test_hanging_indent_and_first_line_are_explained(qapp):
    """Zwei Einzugsarten, die man leicht verwechselt."""
    form = _StyleForm()
    try:
        erklaerungen = " ".join(w.toolTip() for w in _symbole(form))
        assert "erste Zeile nach links heraussteht" in erklaerungen
        assert "Absatzeinzug im Buchsatz" in erklaerungen
    finally:
        form.close()


def test_the_typography_explains_its_reach(qapp):
    """Sprache und Grundgroesse wirken an anderer Stelle."""
    form = _TypographyForm()
    try:
        erklaerungen = " ".join(w.toolTip() for w in _symbole(form))
        assert "Inhaltsverzeichnis" in erklaerungen
        assert "erbt" in erklaerungen
    finally:
        form.close()


def test_obvious_fields_stay_free_of_symbols(qapp):
    """Ein Symbol vor jedem Feld entwertete die echten Hinweise."""
    form = _StyleForm()
    try:
        # Fett und Kursiv brauchen keine Erklaerung.
        erklaerungen = " ".join(w.toolTip() for w in _symbole(form))
        assert "Fett" not in erklaerungen.split("\n")[0]
    finally:
        form.close()


# ---------------------------------------------------------------------------
# Farben und Klassen-Abbildung
# ---------------------------------------------------------------------------


def test_every_colour_token_explains_itself(qapp):
    """Ein Token ist ein Name fuer eine Farbe -- das sieht man ihm nicht an."""
    from tools.doclayout.library import load_layout
    from ui_qt.dialogs.doclayout_editor_dialog import _ColorsForm

    definition = load_layout("IFJN_Referenz")
    form = _ColorsForm()
    try:
        form.load(definition.colors)
        symbole = _symbole(form)
        assert len(symbole) >= len(definition.colors)
        assert all(w.toolTip().strip() for w in symbole)
        assert any("überall" in w.toolTip() for w in symbole)
    finally:
        form.close()


def test_every_class_row_names_its_consequence(qapp):
    """Ohne Eintrag bleibt der Block Fliesstext -- das gehoert an die Zeile."""
    from tools.doclayout.library import load_layout
    from ui_qt.dialogs.doclayout_editor_dialog import _ClassmapForm

    definition = load_layout("IFJN_Referenz")
    form = _ClassmapForm()
    try:
        form.load(definition.classmap, sorted(definition.styles))
        symbole = _symbole(form)
        assert len(symbole) == len(definition.classmap)
        assert all("Fließtext" in w.toolTip() for w in symbole)
    finally:
        form.close()


def test_a_class_explanation_names_that_very_class(qapp):
    """Eine allgemeine Erklaerung haette man auch einmal oben hinschreiben koennen."""
    from ui_qt.dialogs.doclayout_editor_dialog import _ClassmapForm

    form = _ClassmapForm()
    try:
        form.load({"merksatz": "BodyText"}, ["BodyText"])
        assert any("{.merksatz}" in w.toolTip() for w in _symbole(form))
    finally:
        form.close()


# ---------------------------------------------------------------------------
# Das Symbol selbst
# ---------------------------------------------------------------------------


def test_the_icon_is_painted_not_a_glyph(qapp):
    """Eine Glyphe haengt an der Systemschrift und fehlt im schlimmsten Fall."""
    from ui_qt.dialogs.doclayout_editor_dialog import _INFO_ICON_SIZE, _info_icon

    icon = _info_icon()
    assert not icon.isNull()
    assert icon.width() == _INFO_ICON_SIZE


def test_the_icon_is_painted_only_once(qapp):
    """Der Editor zeigt ueber vierzig davon."""
    from ui_qt.dialogs.doclayout_editor_dialog import _info_icon

    assert _info_icon() is _info_icon()


def test_the_icon_is_blue_in_the_middle(qapp):
    """Ein blaues Symbol war ausdruecklich gewuenscht."""
    from PySide6.QtGui import QColor

    from services.constants import StatusFg
    from ui_qt.dialogs.doclayout_editor_dialog import _info_icon

    bild = _info_icon().toImage()
    rand = bild.pixelColor(1, bild.height() // 2)
    blau = QColor(StatusFg.PRIMARY)
    # Am linken Rand des Kreises: deutlich blau, nicht grau.
    assert rand.blue() > rand.red(), "das Symbol ist nicht blau"
    assert abs(rand.blue() - blau.blue()) < 90


def test_the_label_carries_no_stylesheet(qapp):
    """Regression: ein Stylesheet am Etikett faerbte auch dessen Tooltip.

    Daher kam grauer Text auf dem dunkelblauen Grund der App -- kaum zu lesen,
    und niemand haette den Zusammenhang vermutet.
    """
    host = _info("Beschriftung", "Die Erklärung.")
    for w in [host, *host.findChildren(QLabel)]:
        assert w.styleSheet() == "", "ein Stylesheet hier faerbt den Tooltip mit"


def test_the_symbol_invites_a_hover(qapp):
    """Ein Fragezeichen-Zeiger sagt, dass es hier etwas zu holen gibt."""
    from PySide6.QtCore import Qt

    host = _info("Beschriftung", "Die Erklärung.")
    symbol = _symbole(host)[0]
    assert symbol.cursor().shape() == Qt.CursorShape.WhatsThisCursor


# ---------------------------------------------------------------------------
# Eine Erklaerung, zwei Orte, eine Quelle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("klasse", "feld"),
    [
        (_StyleForm, "based_on"),
        (_StyleForm, "next_style"),
        (_StyleForm, "letter_spacing"),
        (_TypographyForm, "language"),
        (_TypographyForm, "hyphenation_zone"),
        (_PageForm, "margin_inner"),
    ],
)
def test_the_field_answers_like_its_label(qapp, klasse, feld: str):
    """Man faehrt mal ueber das (i), mal ueber das Feld -- beide antworten."""
    form = klasse()
    if hasattr(form, "connect_signals"):
        form.connect_signals()
    try:
        assert getattr(form, feld).toolTip().strip(), f"{feld} schweigt"
    finally:
        form.close()


def test_the_explanation_is_written_only_once(qapp):
    """Zwei Kopien laufen auseinander -- eine war es schon.

    Gezaehlt wird ueber **alle** Dateien des Editors, nicht nur ueber den
    Dialog: Seit die Formulare eigene Module haben, waere ein Blick in eine
    einzelne Datei kein Beleg mehr -- eine Kopie in einer anderen faende er
    nicht, und genau darum geht es hier.
    """
    from pathlib import Path

    dialoge = Path(__file__).resolve().parent.parent / "ui_qt" / "dialogs"
    quellen = sorted(dialoge.glob("doclayout_*.py"))
    assert quellen, "keine Editor-Module gefunden"
    gesamt = "\n".join(p.read_text(encoding="utf-8") for p in quellen)

    for satzanfang in (
        "Das Format, von dem dieses alles übernimmt",
        "Welches Format der nächste Absatz bekommt",
        "Zusätzlicher Abstand zwischen den Buchstaben",
    ):
        anzahl = gesamt.count(satzanfang)
        assert anzahl == 1, f"»{satzanfang}…« steht {anzahl}-mal"


def test_a_field_with_its_own_words_keeps_them(qapp):
    """Wo etwas Spezifischeres steht, ist es Absicht."""
    from PySide6.QtWidgets import QFormLayout, QLineEdit, QWidget

    from ui_qt.dialogs.doclayout_editor_dialog import _info, _share_label_tooltips

    host = QWidget()
    layout = QFormLayout(host)
    feld = QLineEdit()
    feld.setToolTip("Etwas Eigenes.")
    layout.addRow(_info("Feld", "Die allgemeine Erklärung."), feld)
    _share_label_tooltips(host)
    assert feld.toolTip() == "Etwas Eigenes."


# ---------------------------------------------------------------------------
# Schriften: auswaehlen statt tippen
# ---------------------------------------------------------------------------
#
# Aus dem Live-Test: Die drei Schriftfelder waren freie Texteingaben. Das ist
# fuer diesen Zweck die schlechteste Form -- man muss den Namen genau kennen,
# ein Tippfehler faellt nicht auf, und die Schrift faellt im fertigen Dokument
# stillschweigend auf eine Ersatzschrift zurueck. Sichtbar erst auf Papier.


def test_die_schriftfelder_bieten_eine_auswahl(qapp):
    from PySide6.QtWidgets import QComboBox

    from ui_qt.dialogs.doclayout_forms import _TypographyForm

    form = _TypographyForm()
    try:
        for feld in (form.body_font, form.heading_font, form.mono_font):
            assert isinstance(feld, QComboBox), "Schrift muss waehlbar sein"
    finally:
        form.close()


def test_die_schriftfelder_bleiben_beschreibbar(qapp):
    """Eine Vorlage darf eine Schrift nennen, die nur bei der Druckerei liegt."""
    from ui_qt.dialogs.doclayout_forms import _TypographyForm
    from ui_qt.dialogs.doclayout_widgets import font_value, set_font_value

    form = _TypographyForm()
    try:
        assert form.body_font.isEditable()
        set_font_value(form.body_font, "Nur-Bei-Der-Druckerei")
        assert font_value(form.body_font) == "Nur-Bei-Der-Druckerei"
    finally:
        form.close()


def test_die_ueberschriftenschrift_kann_leer_bleiben(qapp):
    """»leer = wie Grundschrift« muss ein waehlbarer Zustand sein."""
    from ui_qt.dialogs.doclayout_forms import _TypographyForm
    from ui_qt.dialogs.doclayout_widgets import font_value, set_font_value

    form = _TypographyForm()
    try:
        set_font_value(form.heading_font, "")
        assert font_value(form.heading_font) == ""
        assert "Grundschrift" in form.heading_font.currentText(), (
            "der leere Zustand braucht einen Namen, sonst sieht er kaputt aus"
        )
    finally:
        form.close()


def test_der_anzeigetext_des_leereintrags_wird_nie_zum_schriftnamen(qapp):
    """Sonst stuende »— wie Grundschrift —« als Schrift im Layout."""
    from tools.doclayout.library import load_layout
    from ui_qt.dialogs.doclayout_forms import _TypographyForm
    from ui_qt.dialogs.doclayout_widgets import set_font_value

    typografie = load_layout("IFJN_layout").typography
    form = _TypographyForm()
    try:
        form.load(typografie)
        set_font_value(form.heading_font, "")
        assert form.collect(typografie).heading_font == ""
    finally:
        form.close()
