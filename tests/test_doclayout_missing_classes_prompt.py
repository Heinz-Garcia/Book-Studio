"""Neue Textarten ohne Absatzformat muessen auffallen.

Der Generator fuehrt jederzeit neue Fenced-Div-Klassen ein (``.spanisch``,
``.key-takeaway``). Ohne Zuordnung bleibt der Abschnitt in der ``.docx``
Fliesstext -- die Auszeichnung steht im Markdown und ist im Druck wirkungslos.
Bis hierher gab es dafuer keine Rueckmeldung: Der Abgleich lief nur in der CLI
und im bereits geoeffneten Layout-Editor.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dataclasses import replace

from tools.doclayout.library import load_layout
from tools.doclayout.registry import classes_without_template, write_registry


@pytest.fixture()
def bibliothek(tmp_path: Path) -> Path:
    """Bibliothek mit genau einem Layout, das nur ``fachtext`` kennt."""
    basis = load_layout("IFJN_layout")
    replace(basis, name="Test", classmap={"fachtext": "Fachtext"}).save(
        tmp_path / "Test.yaml"
    )
    write_registry(tmp_path)
    return tmp_path


class TestLueckenerkennung:
    def test_neue_klassen_werden_gemeldet(self, bibliothek: Path) -> None:
        fehlend = classes_without_template(
            ["fachtext", "spanisch", "key-takeaway"], bibliothek
        )
        assert fehlend == ["spanisch", "key-takeaway"]

    def test_bekannte_klassen_erzeugen_keine_meldung(self, bibliothek: Path) -> None:
        assert classes_without_template(["fachtext"], bibliothek) == []

    def test_fuehrender_punkt_wird_toleriert(self, bibliothek: Path) -> None:
        assert classes_without_template([".fachtext"], bibliothek) == []
        assert classes_without_template([".spanisch"], bibliothek) == ["spanisch"]

    def test_reihenfolge_und_eindeutigkeit(self, bibliothek: Path) -> None:
        """Reihenfolge des Generators bleibt, Dubletten fallen weg."""
        assert classes_without_template(
            ["b", "a", "b", "a"], bibliothek
        ) == ["b", "a"]

    def test_ohne_registry_gilt_nichts_als_bekannt(self, tmp_path: Path) -> None:
        """Lieber einmal zu viel fragen als eine Luecke verschweigen."""
        assert classes_without_template(["fachtext"], tmp_path) == ["fachtext"]

    def test_leere_eingabe(self, bibliothek: Path) -> None:
        assert classes_without_template([], bibliothek) == []
        assert classes_without_template(["", "   "], bibliothek) == []


@pytest.mark.gui
class TestDialog:
    @pytest.fixture(scope="class")
    def qapp(self):
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication

        yield QApplication.instance() or QApplication([])

    def _dialog(self, anlass):
        from ui_qt.dialogs.doclayout_missing_classes_dialog import MissingClassesDialog

        return MissingClassesDialog(
            ["spanisch", "key-takeaway"],
            anlass=anlass,
            counts={"spanisch": 4, "key-takeaway": 4},
        )

    def test_import_bietet_an_und_sperrt_nicht(self, qapp) -> None:
        from ui_qt.dialogs.doclayout_missing_classes_dialog import Anlass

        d = self._dialog(Anlass.IMPORT)
        assert d.btn_weiter.text() == "Später"
        assert not hasattr(d, "btn_abbruch")

    def test_typeset_warnt_deutlich_und_laesst_fortfahren(self, qapp) -> None:
        from ui_qt.dialogs.doclayout_missing_classes_dialog import Anlass

        d = self._dialog(Anlass.TYPESET)
        assert d.btn_weiter.text() == "Trotzdem fortfahren"
        assert hasattr(d, "btn_abbruch")

    def test_vorschlag_je_klasse(self, qapp) -> None:
        from ui_qt.dialogs.doclayout_missing_classes_dialog import Anlass

        d = self._dialog(Anlass.IMPORT)
        vorschlaege = [d.table.item(r, 2).text() for r in range(d.table.rowCount())]
        assert vorschlaege == ["Spanisch", "KeyTakeaway"]

    def test_ohne_fehlende_klassen_kein_dialog(self, qapp) -> None:
        from ui_qt.dialogs.doclayout_missing_classes_dialog import (
            Anlass,
            Antwort,
            ask_about_missing_classes,
        )

        assert ask_about_missing_classes([], anlass=Anlass.TYPESET) is Antwort.WEITER
