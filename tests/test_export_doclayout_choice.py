"""Die Formatvorlage gehoert an den Render, nicht in den Layout-Editor.

Der Editor ist ein Werkzeug der Entwurfszeit: Man baut das Mapping der
Absatzformate einmal, bis es sitzt. Danach will man ihn nicht mehr oeffnen --
die Vorlage soll beim Rendern waehlbar sein, so wie ein Druckprofil.

Vorher entschied darueber, was zuletzt jemand mit »Auf Buchprojekt anwenden« in
die ``_quarto.yml`` geschrieben hatte: ein unsichtbarer Zustand im Buch, den man
nur durch Nachsehen erfuhr. Wer zwei Baende mit verschiedenen Vorlagen pflegt,
musste sich merken, welche gerade eingetragen war.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import ui_qt.dialogs.export_dialog as E  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def dialog(app):
    fenster = E.ExportDialog(None, ["Standard"], initial={"format": "typst"})
    yield fenster
    fenster.deleteLater()


# ---------------------------------------------------------------------------
# Die Auswahl
# ---------------------------------------------------------------------------


def test_the_library_shows_up_in_the_choice():
    auswahl = E._doclayout_choices()
    assert auswahl[0].startswith("— Buch-Stand belassen")
    assert "IFJN_layout" in auswahl


def test_a_broken_library_does_not_take_the_dialog_down(monkeypatch):
    """Der Export ist wichtiger als diese eine Zeile."""
    import tools.doclayout.library as L

    def kaputt():
        raise RuntimeError("Bibliothek unlesbar")

    monkeypatch.setattr(L, "available_layouts", kaputt)
    assert E._doclayout_choices() == [E._doclayout_none_label()]


def test_the_choice_is_offered_in_the_dialog(dialog):
    eintraege = [dialog.doclayout_combo.itemText(i)
                 for i in range(dialog.doclayout_combo.count())]
    assert eintraege[0].startswith("— Buch-Stand belassen")
    assert dialog.doclayout_combo.itemData(0) == ""
    assert "IFJN_layout" in eintraege


# ---------------------------------------------------------------------------
# Je Format nur, was dort auch wirkt
# ---------------------------------------------------------------------------


def test_for_docx_the_template_row_replaces_the_print_profile(dialog):
    """Beides zugleich anzubieten hiesse, eine wirkungslose Wahl zu erfragen."""
    dialog.format_combo.setCurrentText("docx")
    assert dialog.doclayout_combo.isVisibleTo(dialog) is True
    assert dialog.profile_combo.isVisibleTo(dialog) is False


def test_for_typst_the_print_profile_comes_back(dialog):
    dialog.format_combo.setCurrentText("docx")
    dialog.format_combo.setCurrentText("typst")
    assert dialog.doclayout_combo.isVisibleTo(dialog) is False
    assert dialog.profile_combo.isVisibleTo(dialog) is True


# ---------------------------------------------------------------------------
# Was zurueckkommt
# ---------------------------------------------------------------------------


def test_the_chosen_template_is_returned_for_docx(dialog):
    dialog.format_combo.setCurrentText("docx")
    dialog.doclayout_combo.setCurrentText("IFJN_layout")
    assert dialog._selected_doclayout() == "IFJN_layout"


def test_no_template_means_render_as_before(dialog):
    """Der Leereintrag ist keine Vorlage -- dann bleibt der Buch-Stand."""
    dialog.format_combo.setCurrentText("docx")
    dialog.doclayout_combo.setCurrentIndex(0)
    assert dialog._selected_doclayout() == ""


def test_none_label_shows_applied_layout_name(tmp_path, monkeypatch):
    """Wer den Namen vergessen hat, sieht ihn im Leereintrag."""
    book = tmp_path / "Band"
    doc = book / "bookconfig" / "doclayout"
    doc.mkdir(parents=True)
    (doc / "classmap.lua").write_text(
        "-- Layout: Reisefuehrer_Andalusien\nreturn {}\n", encoding="utf-8"
    )
    label = E._doclayout_none_label(book)
    assert "Reisefuehrer_Andalusien" in label
    assert "Buch-Stand belassen" in label


def test_for_other_formats_nothing_is_returned(dialog):
    """Eine Formatvorlage wirkt nur auf die Word-Fassung.

    Sie beim Typst-Render mitzugeben hiesse, dem Aufrufer eine Wirkung zu
    versprechen, die es dort nicht gibt.
    """
    dialog.format_combo.setCurrentText("docx")
    idx = dialog.doclayout_combo.findData("IFJN_layout")
    assert idx >= 0
    dialog.doclayout_combo.setCurrentIndex(idx)
    dialog.format_combo.setCurrentText("typst")
    assert dialog._selected_doclayout() == ""


def test_a_remembered_choice_comes_back(app):
    fenster = E.ExportDialog(
        None, ["Standard"], initial={"format": "docx", "doclayout": "IFJN_layout"}
    )
    try:
        assert fenster.doclayout_combo.currentData() == "IFJN_layout"
    finally:
        fenster.deleteLater()


def test_an_unknown_remembered_choice_falls_back(app):
    """Eine geloeschte Vorlage darf den Dialog nicht auf einen Geist zeigen lassen."""
    fenster = E.ExportDialog(
        None, ["Standard"], initial={"format": "docx", "doclayout": "gibt_es_nicht"}
    )
    try:
        assert fenster.doclayout_combo.currentIndex() == 0
        assert fenster.doclayout_combo.currentData() == ""
        assert "Buch-Stand belassen" in fenster.doclayout_combo.currentText()
    finally:
        fenster.deleteLater()
