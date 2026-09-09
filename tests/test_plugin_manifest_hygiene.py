"""Manifest-Hygiene der echten Plugins -- nicht der Testfixtures.

Zwei Befunde aus der Plugin-Pruefung (Q3/Q4, siehe
``.doc/plugin-bugpruefung.md``) waren keine Fehler im Ablauf, sondern
Unstimmigkeiten in den Manifesten selbst. Genau die faellt in einem normalen
Test nicht auf, weil jeder einzelne Aufruf funktioniert -- deshalb pruefen wir
den Bestand hier als Ganzes.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGINS = REPO / "plugins"


def _manifeste() -> dict[str, dict]:
    return {
        pfad.parent.name: json.loads(pfad.read_text(encoding="utf-8"))
        for pfad in sorted(PLUGINS.glob("*/plugin.json"))
    }


def test_jede_order_ist_nur_einmal_vergeben() -> None:
    """Doppelte ``order``-Werte machen die Reihenfolge zur Entdeckungsfrage.

    Vorher teilten sich ``book_projects``, ``doclayout_wizard`` und
    ``provenance`` die 5, ``asset_manager`` und ``gg_content_swap`` die 28.
    Damit haing die Menuereihenfolge innerhalb einer Gruppe daran, in welcher
    Reihenfolge der Lader die Ordner findet -- an nichts Entschiedenem.
    """
    orders = [(daten.get("order"), name) for name, daten in _manifeste().items()]
    doppelt = {
        wert
        for wert, _ in orders
        if [w for w, _ in orders].count(wert) > 1
    }
    assert not doppelt, f"mehrfach vergebene order-Werte: {sorted(doppelt)}"


def test_order_folgt_der_menuegruppierung() -> None:
    """``order`` sagt dasselbe wie ``_PLUGIN_GROUPS``, keine zweite Meinung."""
    from ui_qt.menu_builder import _PLUGIN_GROUPS

    manifeste = _manifeste()
    erwartet = [name for gruppe in _PLUGIN_GROUPS for name in gruppe]
    assert sorted(erwartet) == sorted(manifeste), "Gruppen und Manifeste driften"
    tatsaechlich = sorted(manifeste, key=lambda n: manifeste[n].get("order", 0))
    assert tatsaechlich == erwartet


def test_jedes_plugin_beantwortet_is_available() -> None:
    """Der Lader kommt ohne aus -- wer die Liste prueft, nicht.

    ``provenance`` und ``publish_record`` fielen als einzige aus dem Muster;
    fuer zwei von 23 Eintraegen musste man eine Ausnahme kennen.
    """
    fehlend = []
    for name in _manifeste():
        modul = importlib.import_module(f"plugins.{name}")
        if not callable(getattr(modul, "is_available", None)):
            fehlend.append(name)
    assert not fehlend, f"ohne is_available(): {fehlend}"
