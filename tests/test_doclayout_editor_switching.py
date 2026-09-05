"""Tests fuer den Layout-Auswahlkasten.

Der Wechsel warf ungespeicherte Aenderungen wortlos weg. Fuer den Benutzer sah
das aus, als funktioniere die Auswahl nicht -- die Arbeit war weg, ohne dass
irgendetwas danach gefragt haette.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

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
    base = load_layout("IFJN_layout")
    replace(base, name="Alpha").save(tmp_path / "Alpha.yaml")
    replace(base, name="Beta").save(tmp_path / "Beta.yaml")
    return tmp_path


def _answer(monkeypatch, button) -> list[str]:
    seen: list[str] = []

    def question(parent, title, text, *args, **kwargs):
        seen.append(text)
        return button

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return seen


def _dialog(library: Path) -> DocLayoutEditorDialog:
    dlg = DocLayoutEditorDialog(library_dir=library, select="Alpha")
    dlg.show()
    QApplication.processEvents()
    return dlg


def _edit(dlg: DocLayoutEditorDialog, value: float = 42.0) -> None:
    for row in range(dlg.nav_list.count()):
        if dlg.nav_list.item(row).text().strip() == "Fachtext":
            dlg.nav_list.setCurrentRow(row)
            break
    QApplication.processEvents()
    dlg.style_form.size.setValue(value)
    QApplication.processEvents()
    assert dlg._dirty, "die Aenderung wurde nicht als offen erkannt"


def _switch_to(dlg: DocLayoutEditorDialog, name: str) -> None:
    dlg.layout_combo.setCurrentIndex(dlg.layout_combo.findText(name))
    QApplication.processEvents()


# ---------------------------------------------------------------------------


def test_switching_without_changes_asks_nothing(qapp, library, monkeypatch):
    asked = _answer(monkeypatch, QMessageBox.StandardButton.Discard)
    dlg = _dialog(library)
    try:
        _switch_to(dlg, "Beta")
        assert dlg._definition.name == "Beta"
        assert asked == []
    finally:
        dlg.close()


def test_switching_with_changes_asks_once(qapp, library, monkeypatch):
    asked = _answer(monkeypatch, QMessageBox.StandardButton.Discard)
    dlg = _dialog(library)
    try:
        _edit(dlg)
        _switch_to(dlg, "Beta")
        assert len(asked) == 1
        assert "Alpha" in asked[0]
    finally:
        dlg.close()


def test_cancel_keeps_the_layout_and_the_changes(qapp, library, monkeypatch):
    _answer(monkeypatch, QMessageBox.StandardButton.Cancel)
    dlg = _dialog(library)
    try:
        _edit(dlg)
        _switch_to(dlg, "Beta")
        assert dlg._definition.name == "Alpha"
        assert dlg.layout_combo.currentText() == "Alpha", "der Kasten muss zurueckspringen"
        assert dlg._dirty is True
    finally:
        dlg.close()
    assert load_layout("Alpha", library).styles["Fachtext"].size_pt is None


def test_discard_switches_and_writes_nothing(qapp, library, monkeypatch):
    _answer(monkeypatch, QMessageBox.StandardButton.Discard)
    dlg = _dialog(library)
    try:
        _edit(dlg)
        _switch_to(dlg, "Beta")
        assert dlg._definition.name == "Beta"
        assert dlg._dirty is False
    finally:
        dlg.close()
    assert load_layout("Alpha", library).styles["Fachtext"].size_pt is None


def test_save_writes_the_old_layout_not_the_new_one(qapp, library, monkeypatch):
    """Regression: der Auswahlkasten stand beim Speichern schon auf dem Ziel."""
    _answer(monkeypatch, QMessageBox.StandardButton.Save)
    dlg = _dialog(library)
    try:
        _edit(dlg)
        _switch_to(dlg, "Beta")
        assert dlg._definition.name == "Beta"
    finally:
        dlg.close()
    assert load_layout("Alpha", library).styles["Fachtext"].size_pt == 42.0
    assert load_layout("Beta", library).styles["Fachtext"].size_pt is None


def test_a_multi_selection_does_not_survive_the_switch(qapp, library, monkeypatch):
    _answer(monkeypatch, QMessageBox.StandardButton.Discard)
    dlg = _dialog(library)
    try:
        rows = {
            dlg.nav_list.item(r).text().strip(): r for r in range(dlg.nav_list.count())
        }
        dlg.nav_list.setCurrentRow(rows["Fachtext"])
        dlg.nav_list.item(rows["Prompt-Frage"]).setSelected(True)
        QApplication.processEvents()
        assert len(dlg.selected_style_ids()) == 2
        _switch_to(dlg, "Beta")
        assert dlg.selected_style_ids() == []
        assert dlg.multi_label.isVisible() is False
        assert dlg.remove_style_button.text() == "Entfernen"
    finally:
        dlg.close()
