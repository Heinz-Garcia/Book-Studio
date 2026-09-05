"""Regressionstests: Aenderungen im Layout-Editor muessen bestehen bleiben.

Alle drei hier gesicherten Fehler sahen fuer den Benutzer gleich aus -- "meine
Aenderung ist wieder weg" -- hatten aber verschiedene Ursachen.

Die Tests brauchen ein **sichtbares** Fenster: ``_commit_current_style`` fragt
``style_form.isVisible()``, und das ist ohne ``show()`` immer falsch. Genau
deshalb blieb der Fehler zunaechst unentdeckt.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from tools.doclayout.library import load_layout  # noqa: E402
from tools.doclayout.schema import LayoutDefinition  # noqa: E402
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
def confirm_yes(monkeypatch):
    """Rueckfragen bejahen, ohne auf einen Klick zu warten."""
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )


@pytest.fixture()
def library(tmp_path: Path) -> Path:
    base = load_layout("IFJN_layout")
    replace(base, name="Probe").save(tmp_path / "Probe.yaml")
    return tmp_path


def _open(library: Path, select: str = "Probe") -> DocLayoutEditorDialog:
    dialog = DocLayoutEditorDialog(library_dir=library, select=select)
    dialog.show()
    QApplication.processEvents()
    return dialog


def _select_style(dialog: DocLayoutEditorDialog, style_id: str) -> bool:
    for row in range(dialog.nav_list.count()):
        if dialog.nav_list.item(row).text().strip() == style_id:
            dialog.nav_list.setCurrentRow(row)
            QApplication.processEvents()
            return True
    return False


# ---------------------------------------------------------------------------


def test_a_removed_style_stays_removed(qapp, library, confirm_yes):
    """Regression: das Formular trug das geloeschte Format sofort wieder ein."""
    dialog = _open(library)
    try:
        assert _select_style(dialog, "Fachtext")
        assert dialog.style_form.isVisible(), "ohne sichtbares Formular greift der Fehler nicht"
        dialog._remove_style()
        assert "Fachtext" not in dialog._definition.styles
    finally:
        dialog.close()


def test_a_removed_style_survives_saving_and_reloading(qapp, library, confirm_yes):
    dialog = _open(library)
    try:
        _select_style(dialog, "Prompt-Trenner")
        dialog._remove_style()
        dialog._save()
    finally:
        dialog.close()
    assert "Prompt-Trenner" not in load_layout("Probe", library).styles


def test_switching_layouts_does_not_drag_a_style_along(qapp, library):
    """Regression: ein Format wanderte aus dem alten Layout ins neue."""
    base = load_layout("Probe", library)
    lean = replace(
        base,
        name="Schlank",
        styles={k: v for k, v in base.styles.items() if k != "Fachtext"},
        classmap={k: v for k, v in base.classmap.items() if v != "Fachtext"},
    )
    lean.save(library / "Schlank.yaml")

    dialog = _open(library)
    try:
        _select_style(dialog, "Fachtext")
        dialog.layout_combo.setCurrentIndex(dialog.layout_combo.findText("Schlank"))
        QApplication.processEvents()
        assert dialog._definition.name == "Schlank"
        assert "Fachtext" not in dialog._definition.styles
    finally:
        dialog.close()


def test_editing_a_style_still_persists(qapp, library):
    """Die Absicherung darf das normale Bearbeiten nicht aushebeln."""
    dialog = _open(library)
    try:
        _select_style(dialog, "Fachtext")
        dialog.style_form.size.setValue(33.0)
        _select_style(dialog, "BodyText")
        assert dialog._definition.styles["Fachtext"].size_pt == 33.0
        dialog._save()
    finally:
        dialog.close()
    assert load_layout("Probe", library).styles["Fachtext"].size_pt == 33.0


def test_saving_writes_the_file_it_was_loaded_from(qapp, tmp_path: Path, confirm_yes):
    """Regression: bei abweichendem Dateinamen entstand stillschweigend eine zweite Datei."""
    source = tmp_path / "AndererDateiname.yaml"
    load_layout("IFJN_layout").save(source)   # name im Layout: IFJN_layout
    dialog = _open(tmp_path, select="AndererDateiname")
    try:
        _select_style(dialog, "Fachtext")
        dialog._remove_style()
        dialog._save()
    finally:
        dialog.close()
    # Neben dem Layout entsteht beim Speichern das Klassenverzeichnis fuer den
    # Generator (Stufe 3 der Bruecke). Entscheidend bleibt: keine **zweite**
    # Layoutdatei.
    layouts = sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".yaml")
    assert layouts == ["AndererDateiname.yaml"]
    assert "Fachtext" not in LayoutDefinition.load(source).styles


# ---------------------------------------------------------------------------
# Schliessen darf nichts verschlucken
# ---------------------------------------------------------------------------


def test_closing_with_unsaved_changes_asks(qapp, library, monkeypatch):
    """Regression: Der Schliessen-Knopf warf alles wortlos weg.

    Der Layoutwechsel fragte schon nach -- das Schliessen nicht. Wer im
    Assistenten lange eingestellt hatte, verlor beim Verlassen alles.
    """
    gefragt: list[str] = []

    def question(parent, title, text, *args, **kwargs):
        gefragt.append(text)
        return QMessageBox.StandardButton.Discard

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    dialog = _open(library)
    try:
        _select_style(dialog, "Fachtext")
        dialog.style_form.size.setValue(42.0)
        QApplication.processEvents()
        assert dialog._dirty
        dialog.reject()
        assert len(gefragt) == 1
    finally:
        dialog.close()


def test_cancelling_the_close_keeps_the_window(qapp, library, monkeypatch):
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    dialog = _open(library)
    try:
        _select_style(dialog, "Fachtext")
        dialog.style_form.size.setValue(42.0)
        QApplication.processEvents()
        dialog.reject()
        QApplication.processEvents()
        assert dialog.isVisible(), "das Fenster hätte offen bleiben müssen"
        assert dialog._dirty is True
    finally:
        dialog._session.mark_clean()
        dialog.close()


def test_closing_without_changes_asks_nothing(qapp, library, monkeypatch):
    gefragt: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda p, t, text, *a, **k: (gefragt.append(text), QMessageBox.StandardButton.Discard)[1]),
    )
    dialog = _open(library)
    dialog.reject()
    assert gefragt == []


def test_saving_on_close_writes_the_file(qapp, library, monkeypatch):
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Save),
    )
    dialog = _open(library)
    try:
        _select_style(dialog, "Fachtext")
        dialog.style_form.size.setValue(42.0)
        QApplication.processEvents()
        dialog.reject()
    finally:
        dialog.close()
    assert load_layout("Probe", library).styles["Fachtext"].size_pt == 42.0
