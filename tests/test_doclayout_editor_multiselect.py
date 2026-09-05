"""Tests fuer die Mehrfachauswahl der Absatzformate.

Wie bei den Persistenz-Tests braucht es ein **sichtbares** Fenster: die
Auswahl-Signale und ``style_form.isVisible()`` verhalten sich ohne ``show()``
anders als im Betrieb.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QApplication,
    QMessageBox,
)

from tools.doclayout.library import load_layout  # noqa: E402
from ui_qt.dialogs.doclayout_editor_dialog import DocLayoutEditorDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])
@pytest.fixture(autouse=True)
def _ohne_vorschau(monkeypatch):
    """Legt den Vorschaulauf still -- diese Datei prueft ihn nicht.

    Jede Konstruktion des Dialogs startete sonst einen echten Lauf mit Pandoc
    und LibreOffice: ein paar Sekunden je Test, ein Temp-Verzeichnis mit
    LibreOffice-Profil je Lauf, und keiner davon wird hier ueberprueft. Bei
    neunzig Dialogen im Durchgang blieben tausende Ordner liegen und der
    gesamte Testlauf hing sich spaeter an einer ganz anderen Stelle auf.

    Den Vorschaulauf selbst pruefen ``test_doclayout_preview_runner.py`` und
    ``test_doclayout_editor_closing.py`` -- dort mit einem ersetzten
    ``render_preview``, ohne fremde Programme.
    """
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_start_preview", lambda self, **kwargs: None
    )


@pytest.fixture()
def library(tmp_path: Path) -> Path:
    replace(load_layout("IFJN_layout"), name="Probe").save(tmp_path / "Probe.yaml")
    return tmp_path


@pytest.fixture()
def dialog(qapp, library: Path):
    dlg = DocLayoutEditorDialog(library_dir=library, select="Probe")
    dlg.show()
    QApplication.processEvents()
    yield dlg
    # Der Abbau ist kein Benutzer, der das Fenster verlaesst: Blieben hier
    # offene Aenderungen stehen, fragte der Editor nach -- und weil pytest die
    # Ersatzantwort aus ``monkeypatch`` vorher schon zurueckgenommen hat, waere
    # das ein echter modaler Dialog. Der Testlauf bliebe daran haengen, ohne
    # Meldung und ohne Ende. Ob die Rueckfrage kommt, pruefen die Tests in
    # ``test_doclayout_editor_closing.py``, wo sie hingehoert.
    dlg._session.mark_clean()
    dlg.close()


@pytest.fixture()
def asked(monkeypatch) -> list[str]:
    """Faengt den Text der Rueckfrage ab und bejaht sie."""
    seen: list[str] = []

    def question(parent, title, text, *args, **kwargs):
        seen.append(text)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return seen


def _row(dlg: DocLayoutEditorDialog, style_id: str) -> int:
    for row in range(dlg.nav_list.count()):
        if dlg.nav_list.item(row).text().strip() == style_id:
            return row
    raise AssertionError(f"{style_id} steht nicht in der Liste")


def _select(dlg: DocLayoutEditorDialog, *style_ids: str) -> None:
    dlg.nav_list.setCurrentRow(_row(dlg, style_ids[0]))
    for style_id in style_ids[1:]:
        dlg.nav_list.item(_row(dlg, style_id)).setSelected(True)
    QApplication.processEvents()


# ---------------------------------------------------------------------------


def test_the_list_allows_more_than_one_selection(dialog):
    assert (
        dialog.nav_list.selectionMode()
        is QAbstractItemView.SelectionMode.ExtendedSelection
    )


def test_selected_style_ids_reports_all_of_them(dialog):
    _select(dialog, "Fachtext", "Prompt-Frage", "Themenblock")
    assert dialog.selected_style_ids() == ["Fachtext", "Prompt-Frage", "Themenblock"]


def test_sections_are_never_taken_for_styles(dialog):
    """Ein mitmarkierter Abschnitt darf nicht mitgeloescht werden."""
    _select(dialog, "Fachtext")
    dialog.nav_list.item(0).setSelected(True)      # "Seite und Raender"
    QApplication.processEvents()
    assert dialog.selected_style_ids() == ["Fachtext"]


def test_group_headers_cannot_be_selected(dialog):
    for row in range(dialog.nav_list.count()):
        item = dialog.nav_list.item(row)
        if item.text().strip().startswith("---"):
            item.setSelected(True)
    QApplication.processEvents()
    assert dialog.selected_style_ids() == []


def test_the_button_says_how_many_will_go(dialog):
    _select(dialog, "Fachtext")
    assert dialog.remove_style_button.text() == "Entfernen"
    _select(dialog, "Fachtext", "Prompt-Frage")
    assert dialog.remove_style_button.text() == "Entfernen (2)"


def test_the_button_is_off_without_a_selected_style(dialog):
    dialog.nav_list.setCurrentRow(0)               # ein Abschnitt
    QApplication.processEvents()
    assert dialog.remove_style_button.isEnabled() is False


def test_no_form_is_shown_for_several_styles(dialog):
    """Ein Formular koennte nur eines aendern -- welches, saehe man ihm nicht an."""
    _select(dialog, "Fachtext", "Prompt-Frage")
    assert dialog.style_form.isVisible() is False
    assert dialog.multi_label.isVisible() is True
    assert "2" in dialog.section_title.text()


def test_going_back_to_one_style_shows_its_form_again(dialog):
    _select(dialog, "Fachtext", "Prompt-Frage")
    _select(dialog, "Fachtext")
    assert dialog.multi_label.isVisible() is False
    assert dialog.style_form.isVisible() is True
    assert dialog._current_style == "Fachtext"


def test_removing_takes_every_selected_style(dialog, asked, library: Path):
    before = len(dialog._definition.styles)
    _select(dialog, "Fachtext", "Prompt-Frage", "Themenblock")
    dialog._remove_style()
    assert len(dialog._definition.styles) == before - 3
    for style_id in ("Fachtext", "Prompt-Frage", "Themenblock"):
        assert style_id not in dialog._definition.styles
    dialog._save()
    assert len(load_layout("Probe", library).styles) == before - 3


def test_the_question_names_the_classes_that_would_dangle(dialog, asked):
    _select(dialog, "Fachtext", "Prompt-Frage")
    dialog._remove_style()
    text = asked[-1]
    assert "2 Absatzformate entfernen?" in text
    assert ".fachtext" in text
    assert ".prompt" in text


def test_a_refused_question_removes_nothing(dialog, monkeypatch):
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    before = dict(dialog._definition.styles)
    _select(dialog, "Fachtext", "Prompt-Frage")
    dialog._remove_style()
    assert dialog._definition.styles == before
