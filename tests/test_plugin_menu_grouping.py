"""Gliederung des Plugin-Menues: Gruppen statt Sammelbecken.

Frueher standen drei feste Namenslisten im Menuebauer, alles uebrige fiel in
einen Rest am Ende. Neue Werkzeuge landeten dadurch neben Unverwandtem -- der
Layout-Assistent etwa neben dem Datei-Indexer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ui_qt.menu_builder import _PLUGIN_GROUPS

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"


class TestGruppendefinition:
    def test_keine_doppelten_eintraege(self) -> None:
        alle = [name for gruppe in _PLUGIN_GROUPS for name in gruppe]
        assert len(alle) == len(set(alle)), "Ein Plugin steht in zwei Gruppen"

    def test_keine_leeren_gruppen(self) -> None:
        assert all(_PLUGIN_GROUPS)

    def test_jedes_sichtbare_plugin_hat_seinen_platz(self) -> None:
        """Sonst rutscht es in die Restgruppe -- sichtbar, aber am falschen Ort."""
        from services.plugin_loader import PluginLoader

        sichtbar = {
            p.name
            for p in PluginLoader(PLUGIN_DIR).discover()
            if p.menu_section == "Plugins" and p.show_in_menu and p.load_error is None
        }
        einsortiert = {name for gruppe in _PLUGIN_GROUPS for name in gruppe}
        assert sichtbar <= einsortiert, f"ohne Gruppe: {sorted(sichtbar - einsortiert)}"

    def test_layoutwerkzeuge_stehen_beisammen(self) -> None:
        """Editor, Assistent und Inventar sind drei Sichten auf dieselbe Sache."""
        gruppe = next(
            g for g in _PLUGIN_GROUPS if "doclayout_editor" in g
        )
        assert {"doclayout_wizard", "markup_inventory"} <= set(gruppe)


@pytest.mark.gui
class TestMenueaufbau:
    @pytest.fixture(scope="class")
    def qapp(self):
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication

        yield QApplication.instance() or QApplication([])

    @pytest.fixture()
    def menu(self, qapp):
        from PySide6.QtWidgets import QMenu

        from ui_qt.menu_builder import _populate_plugins

        m = QMenu()
        _populate_plugins(m, resolve=lambda _name: None, plugins_dir=PLUGIN_DIR)
        return m

    def test_trennstriche_trennen_gruppen(self, menu) -> None:
        aktionen = menu.actions()
        assert sum(1 for a in aktionen if a.isSeparator()) >= 4

    def test_kein_strich_am_anfang_oder_ende(self, menu) -> None:
        aktionen = menu.actions()
        assert not aktionen[0].isSeparator()
        assert not aktionen[-1].isSeparator()

    def test_keine_zwei_striche_hintereinander(self, menu) -> None:
        """Eine leere Gruppe darf keinen doppelten Strich hinterlassen."""
        aktionen = menu.actions()
        paare = zip(aktionen, aktionen[1:])
        assert not [1 for a, b in paare if a.isSeparator() and b.isSeparator()]

    def test_reihenfolge_innerhalb_der_gruppe_folgt_der_definition(self, menu) -> None:
        """Nicht die order-Zahl entscheidet, sondern der Arbeitsweg."""
        texte = [a.text() for a in menu.actions() if not a.isSeparator()]
        buecher = next(i for i, t in enumerate(texte) if "Bücher verwalten" in t)
        skeleton = next(i for i, t in enumerate(texte) if "Skeleton ins Buch" in t)
        assert buecher < skeleton
