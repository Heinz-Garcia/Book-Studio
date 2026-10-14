"""Neue Stufen: fehlende Absatzformate vor dem Lauf finden und gestalten (Nutzer, 14.10.2026)."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from tools.doclayout.library import load_layout
from tools.doclayout.neue_stufen import (
    Stufe,
    beispiel_markdown,
    beispieltext,
    fehlende_stufen,
    stufen_des_projekts,
    vorschlag,
    zuordnen,
)

LAYOUT = "Reisefuehrer_Andalusien"


def _manifest(ordner: Path, stufen: list[dict]) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / "manifest.json"
    pfad.write_text(json.dumps({"stages": stufen}), encoding="utf-8")
    return pfad


def _reise(ordner: Path, *, extra: list[dict] | None = None) -> Path:
    kopf = "ifjn_reise_v_2_"
    return _manifest(ordner, [
        {"id": kopf + "fachtext", "display_name": "Fachtext", "is_mandatory": True, "order": 10},
        {"id": kopf + "spanisch", "display_name": "Am Schalter auf Spanisch", "order": 20},
        {"id": kopf + "takeaway", "display_name": "Key Takeaway", "order": 30,
         "output": {"wrap_tags": {"x": {"tag": "key-takeaway"}}}},
        *(extra or []),
    ])


def test_stufen_mit_stufentyp_klasse_und_pflicht(tmp_path: Path) -> None:
    stufen = stufen_des_projekts(_reise(tmp_path / "Reise_Band2", extra=[
        {"id": "planung", "display_name": "Plan", "plans_prompts": True, "order": 5},
    ]))
    assert [(s.stufentyp, s.klasse, s.pflicht) for s in stufen] == [
        ("fachtext", "ifjn_reise_v_2_fachtext", True),
        ("spanisch", "ifjn_reise_v_2_spanisch", False),
        ("key-takeaway", "key-takeaway", False),  # Klasse aus dem wrap tag
    ]


def test_vorhandene_zuordnungen_gelten_auch_nach_umbenennen(tmp_path: Path) -> None:
    """Stufen heißen ``…_v_2_…``, das Projekt ``…_Band2`` -- die Zuordnung greift trotzdem."""
    definition = load_layout(LAYOUT)
    stufen = stufen_des_projekts(_reise(tmp_path / "Reise_Band2"))
    assert fehlende_stufen(definition, stufen) == []


def test_neue_stufe_fehlt_und_bekommt_ein_eigenes_format(tmp_path: Path) -> None:
    definition = load_layout(LAYOUT)
    stufen = stufen_des_projekts(_reise(tmp_path / "Reise", extra=[
        {"id": "ifjn_reise_v_2_notfallkarte", "display_name": "Notfallkarte", "order": 40},
    ]))
    offen = fehlende_stufen(definition, stufen)
    assert [s.stufentyp for s in offen] == ["notfallkarte"]
    ziel, gibt_es = vorschlag(definition, offen[0])
    assert (ziel, gibt_es) == ("Notfallkarte", False)

    neu = zuordnen(definition, offen[0], ziel)
    assert neu.classmap["notfallkarte"] == "Notfallkarte"
    assert neu.styles["Notfallkarte"].based_on == "BodyText"
    assert fehlende_stufen(neu, stufen) == []


def test_haupttext_wird_fliesstext(tmp_path: Path) -> None:
    definition = replace(load_layout(LAYOUT), classmap={})
    stufe = Stufe("produktion", "produktion", "produktion", "produktion", pflicht=True)
    assert vorschlag(definition, stufe) == ("BodyText", True)


def test_beispieltext_aus_dem_juengsten_lauf_sonst_platzhalter(tmp_path: Path) -> None:
    stufe = Stufe("ifjn_reise_v_2_spanisch", "Am Schalter auf Spanisch", "x", "spanisch")
    text, herkunft = beispieltext(stufe, tmp_path / "output")
    assert "noch nie gelaufen" in text and herkunft.startswith("Platzhalter")

    datei = tmp_path / "output" / "Reise_20261014_10.00" / "P_003" / "P_003_ifjn_reise_v_2_spanisch.md"
    datei.parent.mkdir(parents=True)
    datei.write_text("**la urgencia** — die Notaufnahme\n", encoding="utf-8")
    text, herkunft = beispieltext(stufe, tmp_path / "output")
    assert text.startswith("**la urgencia**") and "P_003" in herkunft


def test_beispiel_markdown_zeigt_jede_stufe_in_ihrem_block() -> None:
    definition = load_layout(LAYOUT)
    stufe = Stufe("a_notfallkarte", "Notfallkarte", "a_notfallkarte", "notfallkarte")
    md = beispiel_markdown(definition, [(stufe, "Text der Karte")])
    assert "## Notfallkarte" in md and "::: {.notfallkarte}\nText der Karte\n:::" in md


def test_vorab_pruefung_warnt_vor_stufen_ohne_format(tmp_path: Path) -> None:
    from services.automatik import pruefe_bs

    manifest = _reise(tmp_path / "Reise", extra=[
        {"id": "ifjn_reise_v_2_notfallkarte", "display_name": "Notfallkarte", "order": 40},
    ])
    profil = {"gg": {"projekt": str(manifest.parent)}, "bs": {"doclayout": LAYOUT}}
    warnungen = pruefe_bs(profil, Path(__file__).resolve().parents[1])["warnungen"]
    treffer = [w for w in warnungen if "Ohne Absatzformat" in w]
    assert len(treffer) == 1 and "»Notfallkarte«" in treffer[0] and "--fenster" in treffer[0]


def test_cli_stufen_json(tmp_path: Path, capsys) -> None:
    from tools.doclayout.__main__ import main

    manifest = _reise(tmp_path / "Reise", extra=[
        {"id": "ifjn_reise_v_2_notfallkarte", "display_name": "Notfallkarte", "order": 40},
    ])
    assert main(["stufen", LAYOUT, "-p", str(manifest.parent), "--json"]) == 0
    daten = json.loads(capsys.readouterr().out)
    assert [f["stufentyp"] for f in daten["fehlend"]] == ["notfallkarte"]
    assert daten["fehlend"][0]["vorschlag"] == "Notfallkarte"


def test_fenster_fuehrt_durch_die_offenen_stufen(tmp_path: Path, monkeypatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs import doclayout_neue_stufen as modul

    QApplication.instance() or QApplication([])
    gesetzt: list[str] = []
    monkeypatch.setattr(
        modul.PreviewRunner, "start",
        lambda self, definition, sample_markdown=None: gesetzt.append(sample_markdown or ""),
    )
    gespeichert: list = []
    definition = load_layout(LAYOUT)
    offen = [
        Stufe("a_notfallkarte", "Notfallkarte", "a_notfallkarte", "notfallkarte"),
        Stufe("a_merksatz", "Merksatz", "a_merksatz", "merksatz"),
    ]
    dlg = modul.NeueStufenDialog(
        None, definition, offen, save=lambda d: gespeichert.append(d) or True
    )
    try:
        assert "::: {.notfallkarte}" in gesetzt[-1]  # Vorschau mit den neuen Stufen
        assert dlg.format_wahl.currentData() == "neu:Notfallkarte"  # Vorschlag vorbelegt
        dlg._zuordnen_und_weiter()
        assert dlg.liste.currentRow() == 1  # weiter zur nächsten offenen Stufe
        assert dlg.definition.classmap["notfallkarte"] == "Notfallkarte"
        dlg._zuordnen_und_weiter()
        assert dlg.geaendert and not dlg.gespeichert
        dlg._speichern()
        assert gespeichert and gespeichert[-1].classmap["merksatz"] == "Merksatz"
        assert dlg.gespeichert
    finally:
        dlg._runner.release()
        dlg.close()
