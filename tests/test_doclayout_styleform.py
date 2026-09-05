"""Tests fuer das Absatzformat-Formular.

Sechs Beanstandungen aus der Benutzung, fuenf davon berechtigt: leerer
Anzeigename ohne Hinweis, zwei unerklaerte Freitextfelder, eine geerbte Groesse
ohne Zahl und ein neutraler Wert, der wie eine Entscheidung aussah.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from tools.doclayout.library import load_layout  # noqa: E402
from tools.doclayout.schema import LayoutDefinition, ParagraphStyle  # noqa: E402
from ui_qt.dialogs.doclayout_editor_dialog import _StyleForm  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def layout() -> LayoutDefinition:
    return load_layout("IFJN_Referenz")


@pytest.fixture()
def form(qapp, layout: LayoutDefinition):
    f = _StyleForm()
    f.connect_signals()
    yield f
    f.close()


def _zeige(form: _StyleForm, layout: LayoutDefinition, style_id: str) -> None:
    form.set_context(layout, style_id)
    form.load(layout.styles[style_id])
    QApplication.processEvents()


# ---------------------------------------------------------------------------
# 1) Anzeigename
# ---------------------------------------------------------------------------


def test_the_effective_name_is_shown_as_a_placeholder(form, layout):
    """Leer allein liess offen, wie das Format in Word heisst."""
    _zeige(form, layout, "BodyText")
    assert form.name.text() == ""
    assert form.name.placeholderText() == "BodyText"


# ---------------------------------------------------------------------------
# 2+3) Basiert auf / Folgeformat
# ---------------------------------------------------------------------------


def test_both_references_are_choosable_not_typed(form, layout):
    """Ein Tippfehler erzeugte sonst stillschweigend einen Verweis ins Leere."""
    assert isinstance(form.based_on, QComboBox)
    assert isinstance(form.next_style, QComboBox)


def test_the_choices_are_the_existing_styles(form, layout):
    _zeige(form, layout, "BodyText")
    angeboten = {form.based_on.itemText(i) for i in range(form.based_on.count())}
    assert "Heading1" in angeboten
    assert "" in angeboten, "leer muss waehlbar bleiben"


def test_a_style_is_not_offered_as_its_own_base(form, layout):
    """Ein Format kann nicht auf sich selbst aufbauen."""
    _zeige(form, layout, "BodyText")
    angeboten = {form.based_on.itemText(i) for i in range(form.based_on.count())}
    assert "BodyText" not in angeboten


def test_own_text_remains_possible(form, layout):
    """Ein Format aus einer fremden Vorlage muss eintragbar bleiben."""
    _zeige(form, layout, "BodyText")
    assert form.based_on.isEditable()
    form.based_on.setCurrentText("Fremdformat")
    assert form.collect().based_on == "Fremdformat"


def test_both_fields_explain_themselves(form):
    """«Folgeformat» kennt niemand von selbst."""
    assert "nächste" in form.next_style.toolTip()
    assert "übernimmt" in form.based_on.toolTip()


def test_choosing_a_base_reaches_the_style(form, layout):
    _zeige(form, layout, "BodyText")
    form.based_on.setCurrentText("Heading1")
    assert form.collect().based_on == "Heading1"


# ---------------------------------------------------------------------------
# 4) Groesse
# ---------------------------------------------------------------------------


def test_an_inherited_size_shows_the_actual_number(form, layout):
    """«geerbt» ohne Zahl ist eine Auskunft, die nichts sagt."""
    _zeige(form, layout, "BodyText")
    assert form.size.text() == "— geerbt —"
    assert "11" in form.size_hint.text()
    assert "Grundschriftgrad" in form.size_hint.text()


def test_the_hint_names_where_the_size_comes_from(form, layout):
    _zeige(form, layout, "ImageCaption")
    assert layout.styles["ImageCaption"].size_pt is None
    assert "Caption" in form.size_hint.text()


def test_the_hint_uses_a_decimal_comma(form, layout):
    """Ein Punkt saehe aus, als kaeme die Zahl aus einem anderen Programm."""
    _zeige(form, layout, "BodyText")
    assert "," in form.size_hint.text()
    assert "11.0" not in form.size_hint.text()


def test_an_own_size_needs_no_hint(form, layout):
    _zeige(form, layout, "Heading1")
    assert layout.styles["Heading1"].size_pt == 17.0
    assert form.size_hint.text() == ""


def test_setting_a_size_removes_the_hint(form, layout):
    _zeige(form, layout, "BodyText")
    assert form.size_hint.text() != ""
    form.size.setValue(13.0)
    QApplication.processEvents()
    assert form.size_hint.text() == ""


# ---------------------------------------------------------------------------
# 6) Laufweite
# ---------------------------------------------------------------------------


def test_zero_letter_spacing_reads_as_normal(form, layout):
    """«0,00 pt» sah aus wie eine Entscheidung; es ist der neutrale Wert."""
    _zeige(form, layout, "BodyText")
    assert form.letter_spacing.text() == "— normal —"


def test_normal_letter_spacing_is_not_stored(form, layout):
    _zeige(form, layout, "BodyText")
    assert form.collect().letter_spacing_pt is None


def test_a_real_letter_spacing_is_stored(form, layout):
    _zeige(form, layout, "BodyText")
    form.letter_spacing.setValue(1.5)
    assert form.collect().letter_spacing_pt == 1.5


# ---------------------------------------------------------------------------
# Nichts kaputtgemacht
# ---------------------------------------------------------------------------


def test_loading_and_collecting_round_trips(form, layout):
    """Ohne Zutun darf sich ein Format nicht veraendern."""
    for style_id in ("BodyText", "Heading1", "Compact", "Fachtext"):
        _zeige(form, layout, style_id)
        assert form.collect() == layout.styles[style_id], style_id


def test_a_style_created_empty_survives_the_form(form, layout):
    neu = ParagraphStyle(style_id="Frisch", based_on="BodyText")
    erweitert = replace(layout, styles={**layout.styles, "Frisch": neu})
    _zeige(form, erweitert, "Frisch")
    assert form.collect() == neu


# ---------------------------------------------------------------------------
# 7) «kein Wert» ist nicht «null» -- gefunden durch den Rundlauf-Test
# ---------------------------------------------------------------------------


def test_a_style_without_spacing_stays_without_spacing(form, layout):
    """Regression: ein Format ohne eigenen Abstand kam als 0.0 zurueck.

    ``Normal`` ist so eines -- zehn der neununddreissig Formate im
    Referenz-Layout haben keinen eigenen Wert fuer ``space_before``.
    """
    _zeige(form, layout, "Normal")
    assert layout.styles["Normal"].space_before_pt is None
    assert form.collect().space_before_pt is None


def test_an_inherited_spacing_reads_as_inherited(form, layout):
    _zeige(form, layout, "Normal")
    assert form.space_before.text() == "— geerbt —"


def test_an_explicit_zero_is_kept(form, layout):
    """Bei Listen ist «kein Abstand davor» eine Entscheidung, keine Luecke."""

    _zeige(form, layout, "BodyText")
    assert layout.styles["BodyText"].space_before_pt == 0.0
    assert form.space_before.text() == "0,00 pt"
    assert form.collect().space_before_pt == 0.0


def test_a_real_spacing_survives(form, layout):
    _zeige(form, layout, "Heading1")
    assert layout.styles["Heading1"].space_before_pt == 20.0
    assert form.collect().space_before_pt == 20.0


def test_every_style_of_the_reference_survives_a_visit(form, layout):
    """Nur Hinsehen darf kein einziges Format veraendern."""
    veraendert = []
    for style_id in sorted(layout.styles):
        _zeige(form, layout, style_id)
        if form.collect() != layout.styles[style_id]:
            veraendert.append(style_id)
    assert veraendert == [], f"durch blosses Ansehen veraendert: {veraendert}"


# ---------------------------------------------------------------------------
# Was «Basiert auf» anbieten darf
# ---------------------------------------------------------------------------


def test_a_descendant_is_not_offered_as_a_base(form, layout):
    """Regression: »BodyText basiert auf Fachtext« ergab einen Ringschluss."""
    _zeige(form, layout, "BodyText")
    angeboten = {form.based_on.itemText(i) for i in range(form.based_on.count())}
    assert layout.styles["Fachtext"].based_on == "BodyText"
    assert "Fachtext" not in angeboten


def test_an_unrelated_style_is_still_offered(form, layout):
    _zeige(form, layout, "Heading1")
    angeboten = {form.based_on.itemText(i) for i in range(form.based_on.count())}
    assert "Fachtext" in angeboten


def test_the_follow_up_style_has_no_such_limit(form, layout):
    """Ein Absatz darf sehr wohl wieder denselben Typ nach sich ziehen."""
    _zeige(form, layout, "BodyText")
    angeboten = {form.next_style.itemText(i) for i in range(form.next_style.count())}
    assert "BodyText" in angeboten
    assert "Fachtext" in angeboten


def test_the_tooltip_says_why_something_is_missing(form, layout):
    """Ein leerer Platz ohne Grund waere schlimmer als gar keine Einschraenkung."""
    assert "Ringschluss" in form.based_on.toolTip()
