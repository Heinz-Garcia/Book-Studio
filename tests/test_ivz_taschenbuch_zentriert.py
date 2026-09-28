"""Taschenbuch statt A4, Zeichengrenze fuer Verzeichniseintraege, Zentrieren.

Nutzerentscheidungen 2026-09-28:

* Buecher nur im Taschenbuchformat („A4 mit Calibri ist unmoeglich“).
* Verzeichniseintraege sollen einzeilig bleiben; die Grenze kommt aus dem
  Layout und wird frueh gemeldet (Vorab-Pruefung in GG, Titel-Prompt) und
  spaet (Nacharbeit).
* ``style="text-align: center;"`` ist eine Formatieranweisung, kein
  Absatzformat: Hilfsformat „Zentriert“ im DOCX, ``#align(center)`` in Typst.
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from tools.doclayout import ivz
from tools.doclayout.classmap import write_lua_filter
from tools.doclayout.library import available_layouts, load_layout
from tools.doclayout.schema import ZENTRIERT, mit_hilfsformaten
from tools.doclayout.targets.docx import find_pandoc
from tools.doclayout.taschenbuch import pruefe_taschenbuch, taschenbuch_format

REPO = Path(__file__).resolve().parents[1]
LANG = "1. Medizinische Notfälle & Gesundheitsschäden (Fokus: Versorgung, Transport, Medikamente)"


@pytest.fixture()
def andalusien():
    return load_layout("Reisefuehrer_Andalusien")


def _a4(definition):
    return replace(definition, page=replace(definition.page, width_mm=210.0, height_mm=297.0))


# -- Taschenbuch -------------------------------------------------------------


@pytest.mark.parametrize("pfad", available_layouts(), ids=lambda p: p.stem)
def test_jede_mitgelieferte_vorlage_ist_ein_taschenbuch(pfad: Path) -> None:
    definition = load_layout(pfad.stem)
    assert taschenbuch_format(definition), definition.name
    assert not pruefe_taschenbuch(definition)


def test_a4_wird_abgewiesen(andalusien) -> None:
    probleme = pruefe_taschenbuch(_a4(andalusien))
    assert probleme and "kein Taschenbuchformat" in probleme[0] and "135" in probleme[0]


def test_vorab_pruefung_meldet_a4_als_luecke(andalusien, monkeypatch) -> None:
    from services.automatik import pruefe_bs

    monkeypatch.setattr("tools.doclayout.library.load_layout", lambda name, directory=None: _a4(andalusien))
    ergebnis = pruefe_bs({"bs": {"doclayout": "x", "skeleton_profil": ""}}, REPO)
    assert any("kein Taschenbuchformat" in z for z in ergebnis["luecken"])


# -- Zeichengrenze -----------------------------------------------------------


def test_grenze_aus_schrift_und_satzbreite(andalusien) -> None:
    g = ivz.grenzen(andalusien)
    assert g.satzbreite_mm == pytest.approx(99.0)
    ebene2 = g.ebenen[2]
    if ebene2.geschaetzt:
        pytest.skip("Cambria nicht installiert")
    # Gemessen am gedruckten IVZ: Einträge brechen nach gut 50 Zeichen um.
    assert 45 <= ebene2.zeichen <= 55
    assert g.ebenen[1].zeichen < ebene2.zeichen  # fett, 12 pt
    assert g.zeichen == g.ebenen[1].zeichen


def test_zu_lange_titel_werden_gemessen(andalusien) -> None:
    zu_lang = ivz.zu_lange_titel(andalusien, [(2, LANG), (2, "Kurz")])
    assert [e["titel"] for e in zu_lang] == [LANG]
    assert zu_lang[0]["breite_mm"] > zu_lang[0]["platz_mm"]


def test_breiter_satzspiegel_mehr_zeichen(andalusien) -> None:
    breit = replace(andalusien, page=replace(andalusien.page, width_mm=148.0))  # A5
    assert ivz.grenzen(breit).ebenen[2].zeichen > ivz.grenzen(andalusien).ebenen[2].zeichen


def test_buch_titel_wie_im_satz_ohne_callouts(tmp_path: Path) -> None:
    (tmp_path / "_quarto.yml").write_text(
        "book:\n  title: B\n  chapters:\n    - k.md\n", encoding="utf-8"
    )
    (tmp_path / "k.md").write_text(
        "---\ntitle: Kapitel\n---\n\n## Abschnitt\n\n::: {.callout-tip}\n## Kein Eintrag\n:::\n\n"
        "```\n## auch keiner\n```\n\n### zu tief\n",
        encoding="utf-8",
    )
    assert ivz.buch_titel(tmp_path) == [(1, "Kapitel"), (2, "Abschnitt")]


def test_cli_ivz(tmp_path: Path) -> None:
    titel = tmp_path / "t.json"
    titel.write_text(json.dumps([[2, LANG]], ensure_ascii=False), encoding="utf-8")
    erg = subprocess.run(
        [sys.executable, "-m", "tools.automatik", "ivz", "--doclayout", "Reisefuehrer_Andalusien",
         "--titel", str(titel)],
        cwd=REPO, capture_output=True, check=True,
    )
    daten = json.loads(erg.stdout.decode("utf-8"))
    assert daten["zeichen"] > 0 and daten["zu_lang"][0]["titel"] == LANG


def test_nacharbeit_listet_zu_lange_eintraege(tmp_path: Path) -> None:
    from services.nacharbeit import _ivz_zu_lang

    (tmp_path / "_quarto.yml").write_text("book:\n  chapters:\n    - k.md\n", encoding="utf-8")
    (tmp_path / "k.md").write_text(f"## {LANG}\n\n## Kurz\n", encoding="utf-8")
    eintraege = _ivz_zu_lang(tmp_path, load_layout("Reisefuehrer_Andalusien"))
    assert [e["titel"] for e in eintraege] == [LANG]


# -- Zentrieren ---------------------------------------------------------------


def test_jede_vorlage_bringt_zentriert_mit(andalusien) -> None:
    assert ZENTRIERT not in andalusien.styles
    ergaenzt = mit_hilfsformaten(andalusien)
    assert ergaenzt.styles[ZENTRIERT].align == "center"
    assert ZENTRIERT not in andalusien.styles  # Original unveraendert


def test_zentrierte_anweisung_bekommt_das_hilfsformat(tmp_path: Path) -> None:
    pandoc = find_pandoc(None)
    if not pandoc:
        pytest.skip("Pandoc nicht installiert")
    lua = write_lua_filter(load_layout("Prosa_Layout"), tmp_path / "f.lua")
    md = tmp_path / "t.md"
    md.write_text('::: {style="text-align: center;"}\nZeile eins\n\nZeile zwei\n:::\n', encoding="utf-8")
    out = tmp_path / "t.docx"
    subprocess.run(
        [pandoc, str(md), "-o", str(out), f"--lua-filter={lua}", "-M", "bs-typeset=true"],
        check=True, capture_output=True,
    )
    with zipfile.ZipFile(out) as archiv:
        xml = archiv.read("word/document.xml").decode("utf-8")
    assert xml.count(f'w:val="{ZENTRIERT}"') == 2


def test_typst_zentriert_auch_verschachtelt() -> None:
    from pre_processor import zentriere_fuer_typst

    text = (
        '::: {style="text-align: center;"}\nA\n\n::: {.fachtext}\nB\n:::\n\n```\n:::\n```\nC\n:::\n\nD\n'
    )
    ergebnis = zentriere_fuer_typst(text)
    assert ergebnis.count("#align(center)[") == 1
    # Die schliessende Klammer steht nach C, nicht nach dem inneren Div.
    assert ergebnis.index("C") < ergebnis.index("]\n```") < ergebnis.index("D")
    assert "::: {.fachtext}" in ergebnis


def test_formatinventur_nennt_anweisungen_als_erledigt(tmp_path: Path) -> None:
    from tools.doclayout.markup_inventory import build_markup_inventory

    (tmp_path / "_quarto.yml").write_text("book:\n  chapters:\n    - k.md\n", encoding="utf-8")
    (tmp_path / "k.md").write_text(
        '::: {style="text-align: center;"}\n◈\n:::\n\n::: {style="text-align: center;"}\nX\n:::\n',
        encoding="utf-8",
    )
    inventar = build_markup_inventory(tmp_path)
    assert inventar.directives == {"zentriert": 2}
    assert "2× zentriert (vom Satz erledigt)" in inventar.directives_summary()
    assert not inventar.without_template
