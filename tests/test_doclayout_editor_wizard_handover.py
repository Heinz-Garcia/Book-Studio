"""Was der Assistent aendert, darf der Editor nicht zurueckschreiben.

Regression: Der Assistent arbeitet auf derselben Definition wie der Editor,
und sein Knopf »Layout speichern« geht ueber den Rueckruf in ``_save()``.
``_save`` uebernimmt aber zuerst die Feldwerte des Editor-Formulars
(``_commit_current_style``) -- und das stand hinter dem modalen Assistenten
noch auf dem **alten** Stand des Formats. Wer im Assistenten eine Groesse
einstellte und dort speicherte, bekam sie wortlos zurueckgesetzt: in den
Speicher und in die Datei.

Die Vorschau wird stillgelegt. Sie ruft Pandoc und LibreOffice auf, und
geprueft wird hier die Uebergabe zwischen zwei Dialogen, nicht der Satz.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import ui_qt.dialogs.doclayout_wizard as wizard_modul  # noqa: E402
from tools.doclayout.library import load_layout  # noqa: E402
from tools.doclayout.schema import LayoutDefinition  # noqa: E402
from ui_qt.dialogs.doclayout_editor_dialog import (  # noqa: E402
    DocLayoutEditorDialog,
)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def library(tmp_path: Path) -> Path:
    replace(load_layout("IFJN_layout"), name="Probe").save(tmp_path / "Probe.yaml")
    return tmp_path


@pytest.fixture()
def dialog(qapp, library: Path, tmp_path_factory, monkeypatch):
    """Ein Editor mit stillgelegter Vorschau und einem Buchprojekt."""
    monkeypatch.setattr(
        DocLayoutEditorDialog, "_start_preview", lambda self, **kwargs: None
    )
    buch = tmp_path_factory.mktemp("buch")
    (buch / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    dlg = DocLayoutEditorDialog(library_dir=library, book_path=buch, select="Probe")
    dlg.show()
    QApplication.processEvents()
    yield dlg
    dlg._session.mark_clean()
    dlg.close()


def _erstes_format(dlg: DocLayoutEditorDialog) -> str:
    """Waehlt das erste Absatzformat in der Liste an und gibt es zurueck."""
    for row in range(dlg.nav_list.count()):
        data = dlg.nav_list.item(row).data(Qt.ItemDataRole.UserRole)
        if data and data[0] == "style":
            dlg.nav_list.setCurrentRow(row)
            QApplication.processEvents()
            return data[1]
    raise AssertionError("kein Absatzformat in der Liste")


def _assistent(monkeypatch, *, aendert: str, auf: float, speichert: bool):
    """Ersetzt den Assistenten durch einen, der genau eine Groesse setzt."""

    def unecht(parent, definition, book_path, save=None):
        neu = replace(
            definition,
            styles={
                **definition.styles,
                aendert: replace(definition.styles[aendert], size_pt=auf),
            },
        )
        gespeichert = False
        if speichert and save is not None:
            gespeichert = bool(save(neu))
        # Drittes Feld: ob der **aktuelle** Stand auf der Platte steht (siehe
        # ``run_wizard``). Ohne diese Auskunft musste der Aufrufer raten.
        return neu, True, gespeichert

    monkeypatch.setattr(wizard_modul, "run_wizard", unecht)


def test_der_assistent_speichert_seine_eigene_aenderung(
    dialog: DocLayoutEditorDialog, library: Path, monkeypatch
):
    """Der Kern: 33 pt aus dem Assistenten muessen 33 pt bleiben."""
    ziel = _erstes_format(dialog)
    assert dialog._current_style == ziel, "Vorbedingung: das Format ist offen"

    _assistent(monkeypatch, aendert=ziel, auf=33.0, speichert=True)
    dialog._run_wizard()

    assert dialog._definition.styles[ziel].size_pt == 33.0
    gespeichert = load_layout("Probe", library)
    assert gespeichert.styles[ziel].size_pt == 33.0


def test_auch_ohne_offenes_format_bleibt_die_aenderung(
    dialog: DocLayoutEditorDialog, library: Path, monkeypatch
):
    """Der Fall, der vorher schon ging -- er darf nicht kaputtgehen."""
    ziel = sorted(dialog._definition.styles)[0]
    assert dialog._current_style is None, "Vorbedingung: kein Format offen"

    _assistent(monkeypatch, aendert=ziel, auf=27.0, speichert=True)
    dialog._run_wizard()

    assert load_layout("Probe", library).styles[ziel].size_pt == 27.0


def test_ohne_speichern_kommt_die_aenderung_trotzdem_an(
    dialog: DocLayoutEditorDialog, monkeypatch
):
    """Der Assistent ohne Speichern-Klick: der Editor uebernimmt am Ende."""
    ziel = _erstes_format(dialog)
    _assistent(monkeypatch, aendert=ziel, auf=19.0, speichert=False)
    dialog._run_wizard()

    assert dialog._definition.styles[ziel].size_pt == 19.0
    assert dialog._dirty is True


def test_ein_abgebrochener_assistent_laesst_das_formular_bedienbar(
    dialog: DocLayoutEditorDialog, monkeypatch
):
    """Ohne Aenderung muss das offene Format wieder als solches gelten.

    Sonst liefe die naechste Eingabe im Formular ins Leere: ``_current_style``
    waere ``None``, und ``_collect_into_definition`` schriebe sie nirgends hin.
    """
    ziel = _erstes_format(dialog)
    monkeypatch.setattr(
        wizard_modul, "run_wizard", lambda *a, **k: (dialog._definition, False, False)
    )
    dialog._run_wizard()

    assert dialog._current_style == ziel
    dialog.style_form.size.setValue(42.0)
    QApplication.processEvents()
    assert dialog._definition.styles[ziel].size_pt == 42.0


def test_nach_dem_assistenten_zeigt_das_formular_kein_altes_format_mehr(
    dialog: DocLayoutEditorDialog, monkeypatch
):
    """Mit Aenderung wird die Liste neu aufgebaut -- ohne offenes Format."""
    ziel = _erstes_format(dialog)
    _assistent(monkeypatch, aendert=ziel, auf=21.0, speichert=False)
    dialog._run_wizard()

    assert dialog._current_style is None


def test_die_definition_des_assistenten_gewinnt_gegen_das_formular(
    dialog: DocLayoutEditorDialog, monkeypatch
):
    """Auch wenn im Formular noch etwas anderes steht als im Assistenten."""
    ziel = _erstes_format(dialog)
    dialog.style_form.size.setValue(8.0)
    QApplication.processEvents()
    assert dialog._definition.styles[ziel].size_pt == 8.0

    _assistent(monkeypatch, aendert=ziel, auf=33.0, speichert=True)
    dialog._run_wizard()

    assert dialog._definition.styles[ziel].size_pt == 33.0


def test_der_assistent_sieht_die_noch_offene_formulareingabe(
    dialog: DocLayoutEditorDialog, monkeypatch
):
    """Was vor dem Klick eingestellt war, muss der Assistent mitbekommen."""
    ziel = _erstes_format(dialog)
    dialog.style_form.size.setValue(14.0)
    QApplication.processEvents()

    gesehen: list[LayoutDefinition] = []

    def unecht(parent, definition, book_path, save=None):
        gesehen.append(definition)
        return definition, False, False

    monkeypatch.setattr(wizard_modul, "run_wizard", unecht)
    dialog._run_wizard()

    assert gesehen and gesehen[0].styles[ziel].size_pt == 14.0
