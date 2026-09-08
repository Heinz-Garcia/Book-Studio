"""Erreichbarkeit: Inventar und Assistent muessen im Menue stehen.

Beide Werkzeuge existierten fachlich schon oder waren schnell gebaut -- der
eigentliche Mangel war, dass man sie nur fand, wenn man sie kannte. Diese
Tests halten die Erreichbarkeit fest, nicht die Optik.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"


class TestPluginManifeste:
    @pytest.mark.parametrize("name", ["markup_inventory", "doclayout_wizard"])
    def test_manifest_ist_vollstaendig(self, name: str) -> None:
        pfad = PLUGIN_DIR / name / "plugin.json"
        assert pfad.is_file(), f"{name} hat kein plugin.json"
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        for feld in ("name", "label", "description", "entrypoint", "help_text"):
            assert daten.get(feld), f"{name}: {feld} fehlt"
        assert daten["name"] == name
        assert daten["entrypoint"] == f"plugins.{name}:run"

    @pytest.mark.parametrize("name", ["markup_inventory", "doclayout_wizard"])
    def test_adapter_bietet_run_und_verfuegbarkeit(self, name: str) -> None:
        modul = __import__(f"plugins.{name}", fromlist=["run", "is_available"])
        assert callable(modul.run)
        assert modul.is_available() is True

    def test_beide_werden_entdeckt(self) -> None:
        from services.plugin_loader import PluginLoader

        gefunden = {
            getattr(p, "name", "") for p in PluginLoader(PLUGIN_DIR).discover()
        }
        assert {"markup_inventory", "doclayout_wizard"} <= gefunden

    def test_label_nennt_das_werkzeug_beim_namen(self) -> None:
        """Der Menuetext ist die einzige Chance, das Werkzeug zu finden."""
        daten = json.loads(
            (PLUGIN_DIR / "markup_inventory" / "plugin.json").read_text(encoding="utf-8")
        )
        assert "Textauszeichnungs-Inventar" in daten["label"]

    def test_assistent_verweist_auf_das_inventar(self) -> None:
        """Zwei Sichten auf dasselbe -- die Hilfe soll das sagen."""
        daten = json.loads(
            (PLUGIN_DIR / "doclayout_wizard" / "plugin.json").read_text(encoding="utf-8")
        )
        assert "Textauszeichnungs-Inventar" in daten["help_text"]


@pytest.mark.gui
class TestDialog:
    @pytest.fixture(scope="class")
    def qapp(self):
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication

        yield QApplication.instance() or QApplication([])

    @pytest.fixture()
    def buch(self, tmp_path: Path) -> Path:
        root = tmp_path / "buch"
        (root / "content").mkdir(parents=True)
        (root / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
        (root / "content" / "k.qmd").write_text(
            "::: {.spanisch}\nUrgencias\n:::\n", encoding="utf-8"
        )
        return root

    def test_tabelle_zeigt_die_befunde(self, qapp, buch: Path) -> None:
        from ui_qt.dialogs.doclayout_markup_inventory_dialog import MarkupInventoryDialog

        dialog = MarkupInventoryDialog(buch)
        try:
            namen = [
                dialog.tabelle.item(r, 0).text()
                for r in range(dialog.tabelle.rowCount())
            ]
            assert ".spanisch" in namen
            zeile = namen.index(".spanisch")
            assert dialog.tabelle.item(zeile, 4).text().startswith("ohne Vorlage")
        finally:
            dialog.deleteLater()

    def test_ohne_aktives_buch_zeigt_der_dialog_trotzdem_etwas(self, qapp) -> None:
        """Frueher stand hier ein leerer Dialog plus Ordnerdialog.

        Seit es die Auswahlliste gibt, waehlt der Dialog selbst ein bekanntes
        Buch vor -- niemand muss einen Pfad zusammensuchen.
        """
        from ui_qt.dialogs.doclayout_markup_inventory_dialog import MarkupInventoryDialog

        dialog = MarkupInventoryDialog(None)
        try:
            dialog.refresh()
            assert dialog.buch_label.text().startswith("Buch: ")
        finally:
            dialog.deleteLater()


@pytest.mark.gui
class TestBuchauswahl:
    """Kein Ordnerdialog beim Oeffnen -- die Anwendung kennt ihre Buecher.

    Ein Dateidialog auf der Repo-Wurzel verlangt, die Verzeichnisstruktur
    auswendig zu kennen. ``book_projects.catalog`` weiss, wo die Buecher
    liegen; die Liste kommt von dort.
    """

    @pytest.fixture(scope="class")
    def qapp(self):
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication

        yield QApplication.instance() or QApplication([])

    @pytest.fixture()
    def dialog(self, qapp):
        from ui_qt.dialogs.doclayout_markup_inventory_dialog import MarkupInventoryDialog

        d = MarkupInventoryDialog(None)
        yield d
        d.deleteLater()

    def test_liste_ist_gefuellt(self, dialog) -> None:
        assert dialog.buch_auswahl.count() > 1

    def test_ohne_aktives_buch_wird_eines_vorgewaehlt(self, dialog) -> None:
        """Sonst steht der Benutzer vor einer leeren Tabelle."""
        assert dialog.buch_auswahl.itemData(dialog.buch_auswahl.currentIndex())
        assert dialog.tabelle.rowCount() > 0

    def test_ausweg_steht_am_ende(self, dialog) -> None:
        from ui_qt.dialogs.doclayout_markup_inventory_dialog import _ANDERES_VERZEICHNIS

        letzter = dialog.buch_auswahl.count() - 1
        assert dialog.buch_auswahl.itemText(letzter) == _ANDERES_VERZEICHNIS
        assert not dialog.buch_auswahl.itemData(letzter)

    def test_export_ordner_stehen_nicht_zur_wahl(self, dialog) -> None:
        """``Publish_*`` sind Ergebnisse, nicht Quellen."""
        eintraege = [
            dialog.buch_auswahl.itemText(i) for i in range(dialog.buch_auswahl.count())
        ]
        assert not [e for e in eintraege if e.startswith("Publish_")]

    def test_aktives_buch_wird_vorgewaehlt(self, qapp) -> None:
        from tools.book_projects.catalog import list_books
        from ui_qt.dialogs.doclayout_markup_inventory_dialog import MarkupInventoryDialog

        buecher = [b for b in list_books() if not b.name.startswith("Publish_")]
        if len(buecher) < 2:
            pytest.skip("Zu wenige Buchprojekte fuer diesen Test")
        ziel = buecher[1]
        d = MarkupInventoryDialog(Path(ziel.path))
        try:
            assert d.buch_auswahl.currentText().startswith(
                ziel.display_name or ziel.name
            )
        finally:
            d.deleteLater()

    def test_assistent_waehlt_ebenfalls_aus_der_liste(self) -> None:
        """Derselbe Mangel steckte im Assistenten-Adapter."""
        import plugins.doclayout_wizard as adapter

        assert callable(adapter._buch_waehlen)

    def test_assistent_fragt_vor_stillem_speichern(self, monkeypatch, tmp_path: Path) -> None:
        """Nach Close ohne »Layout speichern« darf nichts still geschrieben werden."""
        pytest.importorskip("PySide6")
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QMessageBox

        from tools.doclayout.schema import LayoutDefinition

        QApplication.instance() or QApplication([])
        import plugins.doclayout_wizard as adapter

        buch = tmp_path / "Band"
        buch.mkdir()
        (buch / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
        layout = LayoutDefinition(name="demo")
        ziel = tmp_path / "demo.yaml"
        speicher_aufrufe: list[object] = []

        monkeypatch.setattr(adapter, "_buch_waehlen", lambda *a, **k: buch)
        monkeypatch.setattr(
            "tools.doclayout.library.available_layouts",
            lambda: [ziel],
        )
        monkeypatch.setattr(
            "tools.doclayout.library.load_layout",
            lambda name: layout,
        )
        monkeypatch.setattr(
            "tools.doclayout.library.layout_path",
            lambda name: ziel,
        )
        monkeypatch.setattr(
            "ui_qt.dialogs.doclayout_wizard.run_wizard",
            # (Layout, geaendert, gespeichert): geaendert und **nicht**
            # gespeichert -- genau der Fall, in dem der Adapter nachfragen muss.
            lambda *a, **k: (layout, True, False),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QInputDialog.getItem",
            lambda *a, **k: ("demo", True),
        )
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **k: QMessageBox.StandardButton.No,
        )

        def _fake_save(self, path):  # noqa: ANN001
            speicher_aufrufe.append(path)

        monkeypatch.setattr(LayoutDefinition, "save", _fake_save)
        assert adapter.run(studio=None, book_path=buch, parent=None) == 0
        assert speicher_aufrufe == []


@pytest.mark.gui
class TestZeilenaktionen:
    """Ein Doppelklick muss irgendwohin fuehren -- und zwar zum Passenden.

    Wo die Auszeichnung im Text steht, ist die naechste Frage meistens „wie
    sieht das dort aus“; gibt es keine Fundstelle (Karteileiche), sitzt die
    einzige Spur im Layout.
    """

    @pytest.fixture(scope="class")
    def qapp(self):
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication

        yield QApplication.instance() or QApplication([])

    @pytest.fixture()
    def dialog(self, qapp, tmp_path: Path):
        from ui_qt.dialogs.doclayout_markup_inventory_dialog import MarkupInventoryDialog

        buch = tmp_path / "buch"
        (buch / "content").mkdir(parents=True)
        (buch / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
        # ``spanisch`` ohne Vorlage (dort steht etwas an), ``prompt`` mit
        # gestalteter Vorlage aus der echten Bibliothek (dort steht nichts an).
        (buch / "content" / "k.qmd").write_text(
            "::: {.spanisch}\nUrgencias\n:::\n\n::: {.prompt}\nFrage?\n:::\n",
            encoding="utf-8",
        )
        d = MarkupInventoryDialog(buch)
        yield d
        d.deleteLater()

    def _zeile_von(self, dialog, name: str) -> int:
        for i, row in enumerate(dialog.inventory.rows):
            if row.name == name:
                return i
        raise AssertionError(f"{name} nicht in der Tabelle")

    def test_zeile_findet_ihren_datensatz(self, dialog) -> None:
        zeile = self._zeile_von(dialog, "spanisch")
        assert dialog._row_at(zeile).name == "spanisch"
        assert dialog._row_at(999) is None

    def test_doppelklick_folgt_der_handlungsspalte(self, dialog, monkeypatch) -> None:
        """Steht etwas an, fuehrt der Doppelklick dorthin -- nicht in den Text.

        Anzeige und Aktion muessen dasselbe sagen: In der Spalte „Zu tun“ steht
        bei ``.spanisch`` „Format anlegen“, und das passiert im Layout-Editor.
        """
        gerufen = []
        monkeypatch.setattr(dialog, "_fundstelle_oeffnen", lambda row: gerufen.append("DATEI"))
        monkeypatch.setattr(dialog, "_layout_oeffnen", lambda row: gerufen.append(row.name))
        zeile = self._zeile_von(dialog, "spanisch")
        assert dialog._row_at(zeile).todo == "Format anlegen"
        dialog._auf_doppelklick(zeile, 0)
        assert gerufen == ["spanisch"]

    def test_ohne_offene_handlung_fuehrt_er_zur_fundstelle(self, dialog, monkeypatch) -> None:
        gerufen = []
        monkeypatch.setattr(dialog, "_fundstelle_oeffnen", lambda row: gerufen.append(row.name))
        monkeypatch.setattr(dialog, "_layout_oeffnen", lambda row: gerufen.append("LAYOUT"))
        zeile = self._zeile_von(dialog, "prompt")
        assert dialog._row_at(zeile).todo == ""
        dialog._auf_doppelklick(zeile, 0)
        assert gerufen == ["prompt"]

    def test_doppelklick_ohne_fundstelle_geht_ins_layout(self, dialog, monkeypatch) -> None:
        karteileichen = [r for r in dialog.inventory.rows if not r.files]
        if not karteileichen:
            pytest.skip("Keine Karteileiche im Testbuch")
        gerufen = []
        monkeypatch.setattr(dialog, "_fundstelle_oeffnen", lambda row: gerufen.append("DATEI"))
        monkeypatch.setattr(dialog, "_layout_oeffnen", lambda row: gerufen.append(row.name))
        dialog._auf_doppelklick(self._zeile_von(dialog, karteileichen[0].name), 0)
        assert gerufen == [karteileichen[0].name]

    def test_namen_kopieren_setzt_die_zwischenablage(self, dialog, qapp) -> None:
        zeile = self._zeile_von(dialog, "spanisch")
        dialog._namen_kopieren(dialog._row_at(zeile))
        assert qapp.clipboard().text() == ".spanisch"

    def test_fehlende_datei_meldet_statt_zu_stuerzen(self, dialog, monkeypatch) -> None:
        from ui_qt.dialogs import doclayout_markup_inventory_dialog as modul

        gewarnt = []
        monkeypatch.setattr(
            modul.QMessageBox, "warning",
            lambda *a, **k: gewarnt.append(a[2] if len(a) > 2 else ""),
        )
        zeile = dialog._row_at(self._zeile_von(dialog, "spanisch"))
        (dialog._book_path / zeile.files[0]).unlink()
        dialog._fundstelle_oeffnen(zeile)
        assert gewarnt and "nicht gefunden" in gewarnt[0]
