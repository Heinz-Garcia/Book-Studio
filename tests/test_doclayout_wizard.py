"""Tests fuer den Assistenten.

Der Assistent war zunaechst ein Vortrag: Er zeigte, was im Buch steht, und bot
zwei Handgriffe an -- Format anlegen, Klasse zuordnen. Fuer alles Vorhandene
gab es nichts zu tun. Diese Tests sichern das ab, was daraus geworden ist:
einstellen, ohne den Assistenten zu verlassen.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QInputDialog  # noqa: E402

from tools.doclayout.library import load_layout  # noqa: E402
from tools.doclayout.schema import LayoutDefinition, ParagraphStyle  # noqa: E402
from ui_qt.dialogs.doclayout_wizard import (  # noqa: E402
    VIEW_BY_CHAPTER,
    VIEW_BY_TYPE,
    VIEWS,
    DocLayoutWizard,
)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def layout() -> LayoutDefinition:
    return replace(load_layout("IFJN_Referenz"), name="Probe")


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    (tmp_path / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (tmp_path / "content").mkdir()
    (tmp_path / "content" / "eins.md").write_text(
        "# Kapitel\n\nEin Absatz.\n\n- Punkt\n\n```\ncode\n```\n\n"
        "::: {.merksatz}\nHinweis\n:::\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def wizard(qapp, layout: LayoutDefinition, book: Path):
    w = DocLayoutWizard(None, layout, book)
    w.resize(900, 800)
    w.show()
    QApplication.processEvents()
    yield w
    w.close()


def _goto(w: DocLayoutWizard, titel: str) -> None:
    w._index = next(i for i, s in enumerate(w._steps) if s.title.startswith(titel))
    w._show_step()
    QApplication.processEvents()


# ---------------------------------------------------------------------------
# Die zwei Ansichten
# ---------------------------------------------------------------------------


def test_both_views_are_offered(wizard):
    assert wizard.view_combo.count() == len(VIEWS)
    assert {wizard.view_combo.itemData(i) for i in range(wizard.view_combo.count())} == {
        VIEW_BY_TYPE,
        VIEW_BY_CHAPTER,
    }


def test_switching_the_view_rebuilds_the_steps(wizard):
    vorher = len(wizard._steps)
    wizard.view_combo.setCurrentIndex(1)
    QApplication.processEvents()
    assert wizard._view == VIEW_BY_CHAPTER
    assert len(wizard._steps) != vorher or vorher == 1


def test_the_chapter_view_warns_that_styles_are_global(wizard):
    """Ohne diesen Hinweis waere die Ansicht eine Falle."""
    wizard.view_combo.setCurrentIndex(1)
    QApplication.processEvents()
    assert wizard.scope_label.isVisible()
    assert "ganzen Buch" in wizard.scope_label.text()


def test_the_type_view_does_not_show_that_warning(wizard):
    assert wizard._view == VIEW_BY_TYPE
    assert wizard.scope_label.isVisible() is False


# ---------------------------------------------------------------------------
# Einstellen -- der eigentliche Zweck
# ---------------------------------------------------------------------------


def test_an_existing_style_can_be_edited_right_there(wizard):
    """Regression: fuer vorhandene Formate gab es ueberhaupt keinen Handgriff."""
    _goto(wizard, "Überschrift Ebene 1")
    assert wizard._edit_host.isVisible()
    assert wizard._editing == "Heading1"


def test_a_change_reaches_the_layout_immediately(wizard):
    """Kein eigener Speichern-Knopf: Wer weiterblaettert, verlaere sonst alles."""
    _goto(wizard, "Überschrift Ebene 1")
    wizard.style_form.size.setValue(28.0)
    QApplication.processEvents()
    assert wizard.definition.styles["Heading1"].size_pt == 28.0
    assert wizard.changed is True


def test_a_step_with_two_target_styles_offers_both(wizard):
    """Fliesstext heisst BodyText **und** FirstParagraph."""
    _goto(wizard, "Fließtext")
    angeboten = {
        wizard.style_combo.itemData(i) for i in range(wizard.style_combo.count())
    }
    assert angeboten == {"BodyText", "FirstParagraph"}


def test_choosing_the_other_style_edits_that_one(wizard):
    _goto(wizard, "Fließtext")
    wizard.style_combo.setCurrentIndex(1)
    QApplication.processEvents()
    zweites = wizard.style_combo.currentData()
    wizard.style_form.space_after.setValue(12.0)
    QApplication.processEvents()
    assert wizard.definition.styles[zweites].space_after_pt == 12.0


def test_editing_one_style_leaves_the_other_alone(wizard):
    _goto(wizard, "Überschrift Ebene 1")
    wizard.style_form.size.setValue(28.0)
    QApplication.processEvents()
    vorher = wizard.definition.styles["BodyText"]
    _goto(wizard, "Fließtext")
    wizard.style_form.size.setValue(11.5)
    QApplication.processEvents()
    assert wizard.definition.styles["Heading1"].size_pt == 28.0
    assert wizard.definition.styles["BodyText"] != vorher


def test_moving_on_keeps_the_change(wizard):
    """Weiterblaettern darf nichts verschlucken."""
    _goto(wizard, "Überschrift Ebene 1")
    wizard.style_form.size.setValue(23.0)
    wizard._forward()
    QApplication.processEvents()
    assert wizard.definition.styles["Heading1"].size_pt == 23.0


def test_a_step_without_an_existing_style_hides_the_form(wizard):
    """Bei einer Klasse ohne Zuordnung gibt es nichts zu bearbeiten."""
    _goto(wizard, "Klasse .merksatz")
    assert wizard._edit_host.isVisible() is False


def test_the_summary_hides_the_form(wizard):
    wizard._index = len(wizard._steps)
    wizard._show_step()
    QApplication.processEvents()
    assert wizard._edit_host.isVisible() is False
    assert "beendet" in wizard.title_label.text()


# ---------------------------------------------------------------------------
# Anlegen und Zuordnen
# ---------------------------------------------------------------------------


def test_a_missing_style_can_be_created(wizard):
    """SourceCode fehlt selbst in Pandocs Basisvorlage."""
    assert "SourceCode" not in wizard.definition.styles
    wizard._create_styles(("SourceCode",))
    QApplication.processEvents()
    assert "SourceCode" in wizard.definition.styles
    assert wizard.definition.styles["SourceCode"].based_on == "BodyText"


def test_a_created_style_is_editable_at_once(wizard):
    """Sonst muesste man den Assistenten verlassen, um ihn zu gestalten."""
    wizard._create_styles(("SourceCode",))
    QApplication.processEvents()
    _goto(wizard, "Codeblock")
    assert wizard._edit_host.isVisible()
    assert wizard._editing == "SourceCode"


def test_a_class_can_be_mapped_to_a_new_style(wizard, monkeypatch):
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        staticmethod(lambda parent, titel, label, items, cur=0, ed=True, **k: (items[0], True)),
    )
    wizard._map_class("merksatz")
    QApplication.processEvents()
    assert wizard.definition.classmap["merksatz"] == "Merksatz"
    assert "Merksatz" in wizard.definition.styles


def test_a_class_can_be_mapped_to_an_existing_style(wizard, monkeypatch):
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        staticmethod(
            lambda parent, titel, label, items, cur=0, ed=True, **k: (
                next(i for i in items if i == "BodyText"),
                True,
            )
        ),
    )
    wizard._map_class("merksatz")
    QApplication.processEvents()
    assert wizard.definition.classmap["merksatz"] == "BodyText"


def test_cancelling_the_mapping_changes_nothing(wizard, monkeypatch):
    monkeypatch.setattr(
        QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False))
    )
    vorher = dict(wizard.definition.classmap)
    wizard._map_class("merksatz")
    assert wizard.definition.classmap == vorher


# ---------------------------------------------------------------------------
# Buchfuehrung
# ---------------------------------------------------------------------------


def test_nothing_done_means_nothing_changed(wizard):
    assert wizard.changed is False
    assert wizard._touched == []


def test_each_action_is_recorded_once(wizard):
    _goto(wizard, "Überschrift Ebene 1")
    wizard.style_form.size.setValue(20.0)
    QApplication.processEvents()
    wizard.style_form.size.setValue(21.0)
    QApplication.processEvents()
    assert wizard._touched.count("Heading1 bearbeitet") == 1


def test_the_definition_of_the_caller_is_never_mutated(qapp, layout, book):
    """Der Aufrufer bekommt das Ergebnis zurueck -- er verliert nicht sein Original."""
    original_size = layout.styles["Heading1"].size_pt
    w = DocLayoutWizard(None, layout, book)
    w.show()
    QApplication.processEvents()
    try:
        _goto(w, "Überschrift Ebene 1")
        w.style_form.size.setValue(33.0)
        QApplication.processEvents()
        assert w.definition.styles["Heading1"].size_pt == 33.0
        assert layout.styles["Heading1"].size_pt == original_size
    finally:
        w.close()


def test_an_unchanged_form_does_not_count_as_work(wizard):
    """Nur Durchblaettern ist keine Aenderung."""
    _goto(wizard, "Überschrift Ebene 1")
    wizard._forward()
    wizard._forward()
    QApplication.processEvents()
    assert wizard.changed is False


def test_a_style_created_for_a_class_lands_in_the_layout(wizard, monkeypatch):
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        staticmethod(lambda parent, titel, label, items, cur=0, ed=True, **k: (items[0], True)),
    )
    wizard._map_class("merksatz")
    QApplication.processEvents()
    neu = wizard.definition.styles["Merksatz"]
    assert isinstance(neu, ParagraphStyle)
    assert neu.based_on == "BodyText"


# ---------------------------------------------------------------------------
# Speichern und Uebertragen
# ---------------------------------------------------------------------------


@pytest.fixture()
def wizard_mit_speichern(qapp, layout: LayoutDefinition, book: Path):
    """Ein Assistent, der speichern kann -- mit Protokoll darueber."""
    from ui_qt.dialogs.doclayout_wizard import DocLayoutWizard

    abgelegt: list[LayoutDefinition] = []

    def speichern(definition: LayoutDefinition) -> bool:
        abgelegt.append(definition)
        return True

    w = DocLayoutWizard(None, layout, book, save=speichern)
    w.show()
    QApplication.processEvents()
    w.abgelegt = abgelegt
    yield w
    w.close()


def test_without_a_callback_there_is_no_save_button(wizard):
    """Ohne Weg zum Ablegen waere der Knopf ein leeres Versprechen."""
    assert wizard.save_button.isVisible() is False


def test_the_button_starts_disabled_but_honest(wizard_mit_speichern):
    """»Gespeichert« ohne Speichern waere eine Behauptung ueber ein Nichts."""
    w = wizard_mit_speichern
    assert w.save_button.isVisible() is True
    assert w.save_button.isEnabled() is False
    assert w.save_button.text() == "Layout speichern"


def test_a_change_enables_saving(wizard_mit_speichern):
    w = wizard_mit_speichern
    _goto(w, "Überschrift Ebene 1")
    w.style_form.size.setValue(29.0)
    QApplication.processEvents()
    assert w.save_button.isEnabled() is True


def test_saving_hands_the_current_state_over(wizard_mit_speichern):
    w = wizard_mit_speichern
    _goto(w, "Überschrift Ebene 1")
    w.style_form.size.setValue(29.0)
    QApplication.processEvents()
    w._save_layout()
    assert w.abgelegt, "es wurde nichts abgelegt"
    assert w.abgelegt[-1].styles["Heading1"].size_pt == 29.0


def test_after_saving_the_button_rests(wizard_mit_speichern):
    w = wizard_mit_speichern
    _goto(w, "Überschrift Ebene 1")
    w.style_form.size.setValue(29.0)
    QApplication.processEvents()
    w._save_layout()
    assert w.save_button.text() == "Gespeichert"
    assert w.save_button.isEnabled() is False


def test_a_further_change_reopens_the_button(wizard_mit_speichern):
    """Nach dem Speichern weitergearbeitet heisst: wieder ungesichert."""
    w = wizard_mit_speichern
    _goto(w, "Überschrift Ebene 1")
    w.style_form.size.setValue(29.0)
    QApplication.processEvents()
    w._save_layout()
    w.style_form.size.setValue(31.0)
    QApplication.processEvents()
    assert w.save_button.isEnabled() is True
    assert w.save_button.text() == "Layout speichern"


def test_the_summary_says_whether_it_is_saved(wizard_mit_speichern):
    w = wizard_mit_speichern
    _goto(w, "Überschrift Ebene 1")
    w.style_form.size.setValue(29.0)
    QApplication.processEvents()
    w._index = len(w._steps)
    w._show_step()
    QApplication.processEvents()
    assert "Noch nicht gespeichert" in w.body.toPlainText()

    w._save_layout()
    w._index = len(w._steps)
    w._show_step()
    QApplication.processEvents()
    assert "ist gespeichert" in w.body.toPlainText()


def test_the_summary_explains_the_transfer(wizard_mit_speichern):
    """Die Frage »auf andere Buecher uebertragbar?« gehoert dorthin beantwortet."""
    w = wizard_mit_speichern
    w._index = len(w._steps)
    w._show_step()
    QApplication.processEvents()
    text = w.body.toPlainText()
    assert "Auf Buchprojekt anwenden" in text
    assert "gehört zu keinem Buch" in text
