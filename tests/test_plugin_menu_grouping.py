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


def _group_names(gruppe: tuple[str, tuple[str, ...]]) -> tuple[str, ...]:
    return gruppe[1]


def _all_plugin_names() -> list[str]:
    return [name for _titel, namen in _PLUGIN_GROUPS for name in namen]


class TestGruppendefinition:
    def test_keine_doppelten_eintraege(self) -> None:
        alle = _all_plugin_names()
        assert len(alle) == len(set(alle)), "Ein Plugin steht in zwei Gruppen"

    def test_keine_leeren_gruppen(self) -> None:
        assert all(namen for _titel, namen in _PLUGIN_GROUPS)

    def test_jedes_sichtbare_plugin_hat_seinen_platz(self) -> None:
        """Sonst rutscht es in die Restgruppe -- sichtbar, aber am falschen Ort."""
        from services.plugin_loader import PluginLoader

        sichtbar = {
            p.name
            for p in PluginLoader(PLUGIN_DIR).discover()
            if p.menu_section == "Plugins" and p.show_in_menu and p.load_error is None
        }
        einsortiert = set(_all_plugin_names())
        assert sichtbar <= einsortiert, f"ohne Gruppe: {sorted(sichtbar - einsortiert)}"

    def test_layoutwerkzeuge_stehen_beisammen(self) -> None:
        """Editor, Assistent, Inventar und Satz gehören zum Layout-Arbeitsweg."""
        gruppe = next(
            _group_names(g) for g in _PLUGIN_GROUPS if "doclayout_editor" in g[1]
        )
        assert {
            "doclayout_wizard",
            "markup_inventory",
            "satz_werkzeuge",
        } <= set(gruppe)

    def test_kapitelliste_ist_eigene_gruppe(self) -> None:
        """Trennstrich oberhalb von Kapitelliste — getrennt von Notizen."""
        assert any(namen == ("file_indexer",) for _t, namen in _PLUGIN_GROUPS)
        notizen = next(_group_names(g) for g in _PLUGIN_GROUPS if "memo_pad" in g[1])
        assert "file_indexer" not in notizen
        assert "satz_werkzeuge" not in next(
            _group_names(g) for g in _PLUGIN_GROUPS if "gg_content_swap" in g[1]
        )

    def test_freigabe_und_archiv_tragen_stufenmarkierung(self) -> None:
        titel_map = {titel: namen for titel, namen in _PLUGIN_GROUPS}
        assert "publisher_compliance" in titel_map["I · Freigabe"]
        assert "publish_readiness" in titel_map["I · Freigabe (Erweitert)"]
        assert "mapping_manager" in titel_map["J · Archiv"]
        assert "book_projects" in titel_map["G · Struktur"]


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

    def test_keine_separatoren_zwischen_gruppen(self, menu) -> None:
        """Überschriften ersetzen die Trennstriche."""
        assert not any(a.isSeparator() for a in menu.actions())

    def test_gruppenkopf_vor_jeder_definierten_gruppe(self, menu) -> None:
        from PySide6.QtWidgets import QWidgetAction

        texte = [a.text() for a in menu.actions()]
        for titel, _namen in _PLUGIN_GROUPS:
            assert titel in texte

        koepfe = [
            a.text()
            for a in menu.actions()
            if isinstance(a, QWidgetAction) and not a.isEnabled()
        ]
        assert "G · Struktur" in koepfe
        assert "Kapitelliste" in koepfe

    def test_reihenfolge_innerhalb_der_gruppe_folgt_der_definition(self, menu) -> None:
        """Nicht die order-Zahl entscheidet, sondern der Arbeitsweg."""
        texte = [a.text() for a in menu.actions() if not a.isSeparator()]
        buecher = next(i for i, t in enumerate(texte) if "Bücher wählen" in t)
        skeleton = next(i for i, t in enumerate(texte) if "Skeleton ins Buch" in t)
        assert buecher < skeleton

    def test_satzpruefung_steht_bei_layout(self, menu) -> None:
        texte = [a.text() for a in menu.actions() if not a.isSeparator()]
        layout = next(i for i, t in enumerate(texte) if "Layout-Editor" in t)
        satz = next(i for i, t in enumerate(texte) if "Satzprüfung" in t)
        inventar = next(i for i, t in enumerate(texte) if "Textauszeichnungs" in t)
        assert layout < satz
        assert inventar < satz
        assert "&" not in texte[satz]
        assert "_" not in texte[satz].replace("…", "")
        assert "und Regelkreis" in texte[satz]

    def test_gruppenkoepfe_haben_hintergrund_label(self, menu) -> None:
        """Überschriften sind volle Zeilen (QWidgetAction), nicht grauer Text."""
        from PySide6.QtWidgets import QLabel, QWidgetAction

        koepfe = [
            a
            for a in menu.actions()
            if isinstance(a, QWidgetAction) and not a.isEnabled()
        ]
        assert koepfe, "mindestens ein Gruppenkopf erwartet"
        for action in koepfe:
            widget = action.defaultWidget()
            assert isinstance(widget, QLabel)
            assert widget.objectName() == "pluginMenuGroupHeader"
            assert action.text()
            assert widget.text() == action.text()

    def test_kapitelliste_folgt_auf_gruppenkopf(self, menu) -> None:
        from PySide6.QtWidgets import QWidgetAction

        aktionen = list(menu.actions())
        kap_kopf = next(
            i
            for i, a in enumerate(aktionen)
            if isinstance(a, QWidgetAction) and a.text() == "Kapitelliste"
        )
        assert kap_kopf > 0
        # Direkt danach der Plugin-Eintrag (Kapitelliste exportieren…)
        folge = aktionen[kap_kopf + 1]
        assert not isinstance(folge, QWidgetAction)
        assert "Kapitelliste" in folge.text()
        assert "exportieren" in folge.text().casefold()

    def test_plugin_aktionen_tragen_magenta_badge(self, menu) -> None:
        for action in menu.actions():
            if action.isSeparator() or not action.isEnabled():
                continue
            assert not action.icon().isNull(), action.text()
            assert "Autonomes Plugin" in (action.toolTip() or "")
