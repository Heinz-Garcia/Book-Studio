"""Tests fuer die dunkle Fassung des Layout-Editors.

Sie ist bewusst auf diesen einen Dialog begrenzt: rechts steht ein weisses
Vorschaublatt, das sich von einer hellen Bedienung kaum abhebt.
"""

from __future__ import annotations

import re

import pytest

pytest.importorskip("PySide6")

from tools.doclayout.origins import StyleOrigin  # noqa: E402
from ui_qt.dialogs.doclayout_editor_dialog import (  # noqa: E402
    _ORIGIN_COLORS_DARK,
    _ORIGIN_COLORS_LIGHT,
    _REQUIREMENT_COLORS_DARK,
    _REQUIREMENT_COLORS_LIGHT,
    DocLayoutEditorDialog,
)
from ui_qt.dialogs.doclayout_editor_style import DARK_STYLESHEET  # noqa: E402
from ui_qt.pitugrafo_look import PITU_CORE_STYLESHEET  # noqa: E402


def _rule(stylesheet: str, selector: str) -> str:
    """Der Rumpf der ersten Regel zu *selector*."""
    match = re.search(
        re.escape(selector) + r"\s*\{(.*?)\}", stylesheet, re.S
    )
    assert match, f"Regel fehlt: {selector}"
    return match.group(1)


# ---------------------------------------------------------------------------
# Das dunkle Stylesheet muss die hellen Vorgaben wirklich ueberschreiben
# ---------------------------------------------------------------------------


def test_group_box_title_gets_its_own_background():
    """Regression: der Titel behielt die helle Flaeche des App-Themas."""
    assert "background" in _rule(PITU_CORE_STYLESHEET, "QGroupBox::title")
    assert "background" in _rule(DARK_STYLESHEET, "QGroupBox::title")


def test_help_bar_is_overridden():
    """Die App faerbt die Kurzhilfe hell mit dunkler Schrift."""
    assert "QFrame#HelpBar" in DARK_STYLESHEET
    assert "QLabel#HelpBarText" in DARK_STYLESHEET


@pytest.mark.parametrize(
    "selector",
    [
        "QGroupBox",
        "QPushButton",
        "QListWidget",
        "QCheckBox::indicator",
        "QComboBox QAbstractItemView",
    ],
)
def test_every_styled_widget_type_is_answered(selector: str):
    """Was das App-Thema einfaerbt, muss die dunkle Fassung beantworten."""
    assert selector in PITU_CORE_STYLESHEET
    assert selector in DARK_STYLESHEET


def test_dark_stylesheet_sets_no_colour_for_the_preview():
    """Das Vorschaublatt bleibt weiss -- es einzufaerben hiesse zu faelschen."""
    assert "QPdfView" not in DARK_STYLESHEET


# ---------------------------------------------------------------------------
# Zuordnung der Gruppenueberschriften beim Umfaerben
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("origin", list(StyleOrigin))
def test_group_headers_are_matched_back_to_their_origin(origin: StyleOrigin):
    """Beim Umschalten muessen auch die Ueberschriften ihre Farbe wechseln."""
    header = f"--- {origin.label} (7) ---"
    assert DocLayoutEditorDialog._origin_of_header(header) is origin


def test_a_foreign_entry_is_not_mistaken_for_a_group_header():
    assert DocLayoutEditorDialog._origin_of_header("    BodyText") is None
    assert DocLayoutEditorDialog._origin_of_header("Seite und Raender") is None


# ---------------------------------------------------------------------------
# Beide Paletten vollstaendig
# ---------------------------------------------------------------------------


def test_both_palettes_cover_every_origin():
    for palette in (_ORIGIN_COLORS_LIGHT, _ORIGIN_COLORS_DARK):
        assert set(palette) == set(StyleOrigin)


def test_the_two_palettes_differ_everywhere():
    """Gleiche Farbe in beiden Faellen waere ein vergessener Eintrag."""
    for origin in StyleOrigin:
        assert _ORIGIN_COLORS_LIGHT[origin] != _ORIGIN_COLORS_DARK[origin]


def test_requirement_colours_come_as_a_triple():
    for colours in (_REQUIREMENT_COLORS_LIGHT, _REQUIREMENT_COLORS_DARK):
        assert len(colours) == 3
        assert all(c.startswith("#") for c in colours)


# ---------------------------------------------------------------------------
# Aufklappliste des Layout-Auswahlkastens
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dark_app():
    from PySide6.QtWidgets import QApplication

    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    yield app


@pytest.mark.parametrize("count", [2, 4, 8])
def test_the_popup_shows_every_entry(dark_app, count: int):
    """Regression: ``padding`` am QComboBox verkuerzte die Liste um 16 Pixel.

    Die letzten Eintraege verschwanden dann hinter einem Bildlaufpfeil, obwohl
    reichlich Platz war -- der Auswahlkasten wirkte kaputt.
    """
    from PySide6.QtWidgets import QComboBox

    combo = QComboBox()
    combo.addItems([f"Layout_{i}" for i in range(count)])
    combo.setStyleSheet(DARK_STYLESHEET)
    combo.show()
    dark_app.processEvents()
    combo.showPopup()
    dark_app.processEvents()
    try:
        view = combo.view()
        model = view.model()
        last = view.visualRect(model.index(count - 1, 0))
        assert last.bottom() <= view.viewport().height(), (
            f"der letzte von {count} Eintraegen passt nicht in die Liste"
        )
        assert not view.verticalScrollBar().isVisible()
    finally:
        combo.hidePopup()
        combo.close()


def test_the_combobox_rule_carries_no_padding():
    """Der Grund fuer die Regression, als Regel festgehalten."""
    rule = _rule(DARK_STYLESHEET, "QComboBox ")
    assert "padding" not in rule
    assert "min-height" in rule, "ohne min-height waere der Kasten zu flach"


def test_the_dropdown_arrow_is_left_to_qt():
    """Regression: ein selbstgebauter Pfeil sah aus wie ein verdrehtes L.

    Zwei Rahmenlinien ergeben nur mit einer 45-Grad-Drehung einen Winkel, und
    ``transform`` gibt es in Qt-Stylesheets nicht. Auch ``::drop-down`` allein
    zu gestalten hilft nicht: Danach zeichnet Qt den nativen Pfeil gar nicht
    mehr. Ohne beide Regeln stimmt es.
    """
    regeln = re.sub(r"/\*.*?\*/", "", DARK_STYLESHEET, flags=re.S)
    assert "QComboBox::down-arrow" not in regeln
    assert "QComboBox::drop-down" not in regeln


def test_the_dropdown_still_shows_an_arrow(dark_app):
    """Der Kasten muss als Kasten erkennbar bleiben."""
    from PySide6.QtWidgets import QComboBox, QStyle, QStyleOptionComboBox

    combo = QComboBox()
    combo.addItems(["A", "B"])
    combo.setStyleSheet(DARK_STYLESHEET)
    combo.show()
    dark_app.processEvents()
    try:
        option = QStyleOptionComboBox()
        combo.initStyleOption(option)
        pfeil = combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            combo,
        )
        assert pfeil.width() > 0 and pfeil.height() > 0, (
            "für den Pfeil ist kein Platz vorgesehen"
        )
    finally:
        combo.close()
