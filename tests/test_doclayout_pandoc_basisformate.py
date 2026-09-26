"""Verwerfen auf ein Pandoc-Basisformat (BodyText, Normal, FirstParagraph).

Bis 2026-09-26: Das Markup-Inventar erlaubte „Verwerfen“ auf ``BodyText``,
auch wenn das Layout das Format nicht selbst definiert (z. B.
``Prosa_Layout``). ``validate()`` verlangte aber jedes Klassen-Ziel in
``styles`` -- Setzen und Vorschau verweigerten danach das Layout. Und der
Lua-Filter schrieb die Kennung als ``custom-style``: Pandoc legte damit ein
zweites Format ``BodyText`` an, statt „Body Text“ zu treffen.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from tools.doclayout import library
from tools.doclayout import markup_inventory as mi
from tools.doclayout.classmap import build_lua_filter
from tools.doclayout.schema import PANDOC_BASISFORMATE


@pytest.fixture
def bibliothek(tmp_path: Path) -> Path:
    kopie = tmp_path / "library"
    shutil.copytree(library.LIBRARY_DIR, kopie)
    return kopie


def _prosa(bibliothek: Path):
    return library.load_layout("Prosa_Layout", bibliothek)


def test_prosa_layout_definiert_keine_basisformate(bibliothek: Path):
    """Voraussetzung des Tests: sonst prüfte er nichts."""
    assert not set(PANDOC_BASISFORMATE) & set(_prosa(bibliothek).styles)


@pytest.mark.parametrize("ziel", sorted(PANDOC_BASISFORMATE))
def test_verwerfen_laesst_das_layout_gueltig(bibliothek: Path, ziel: str):
    ok, meldung = mi.remap_class_to_style(
        "fachtext", ziel, library_dir=bibliothek, layout_names=("Prosa_Layout",)
    )
    assert ok, meldung
    layout = _prosa(bibliothek)
    assert layout.classmap["fachtext"] == ziel
    assert layout.validate() == []


def test_unbekanntes_ziel_bleibt_ein_fehler(bibliothek: Path):
    from dataclasses import replace

    layout = _prosa(bibliothek)
    kaputt = replace(layout, classmap={**layout.classmap, "fachtext": "GibtEsNicht"})
    assert any("GibtEsNicht" in p for p in kaputt.validate())


def test_filter_schreibt_den_word_namen(bibliothek: Path):
    mi.remap_class_to_style(
        "fachtext", "BodyText", library_dir=bibliothek, layout_names=("Prosa_Layout",)
    )
    lua = build_lua_filter(_prosa(bibliothek))
    assert '["fachtext"] = "Body Text"' in lua
    # Eigene Formate behalten ihre Kennung.
    eigenes = next(k for k, v in _prosa(bibliothek).classmap.items() if v != "BodyText")
    assert f'["{eigenes}"] = "{_prosa(bibliothek).classmap[eigenes]}"' in lua


def _pandoc() -> str:
    for kandidat in (
        shutil.which("pandoc"),
        r"C:\Program Files\Quarto\bin\tools\pandoc.exe",
    ):
        if kandidat and Path(kandidat).is_file():
            return kandidat
    pytest.skip("pandoc nicht gefunden")


def test_pandoc_trifft_das_echte_body_text(bibliothek: Path, tmp_path: Path):
    """Ende zu Ende: Klasse → Filter → Pandoc → genau ein Format „BodyText“."""
    mi.remap_class_to_style(
        "fachtext", "BodyText", library_dir=bibliothek, layout_names=("Prosa_Layout",)
    )
    filter_datei = tmp_path / "classmap.lua"
    filter_datei.write_text(build_lua_filter(_prosa(bibliothek)), encoding="utf-8")
    quelle = tmp_path / "probe.md"
    quelle.write_text("::: {.fachtext}\nText.\n:::\n", encoding="utf-8")
    ziel = tmp_path / "probe.docx"
    subprocess.run(
        [_pandoc(), str(quelle), "--lua-filter", str(filter_datei), "-o", str(ziel)],
        check=True, capture_output=True, timeout=120,
    )
    with zipfile.ZipFile(ziel) as z:
        dokument = z.read("word/document.xml").decode("utf-8")
        stile = z.read("word/styles.xml").decode("utf-8")
    assert re.search(r'<w:pStyle w:val="BodyText"\s*/>', dokument)
    assert stile.count('w:styleId="BodyText"') == 1, "doppeltes Format BodyText"


def test_eigenes_format_erbt_vom_bisherigen_ziel(bibliothek: Path):
    """Nach „Verwerfen → Normal“ erbt das eigene Format von Normal (bis
    2026-09-26 still von BodyText)."""
    mi.remap_class_to_style(
        "fachtext", "Normal", library_dir=bibliothek, layout_names=("Prosa_Layout",)
    )
    ok, meldung = mi.detach_class_to_own_style(
        "fachtext", library_dir=bibliothek, layout_names=("Prosa_Layout",)
    )
    assert ok, meldung
    layout = _prosa(bibliothek)
    neues = layout.styles[layout.classmap["fachtext"]]
    assert neues.based_on == "Normal"
    assert layout.validate() == []


def _datei(bibliothek: Path, name: str) -> Path:
    return next(p for p in (bibliothek / f"{name}.yaml", bibliothek / f"{name}.yml") if p.is_file())


@pytest.mark.parametrize("aktion", ["verwerfen", "eigenes_format"])
def test_speichern_ganz_oder_gar_nicht(bibliothek: Path, monkeypatch, aktion: str):
    """Scheitert das zweite Layout beim Speichern, bleibt auch das erste, wie
    es war -- bis 2026-09-26 war es schon umgebaut, und die Meldung
    verschwieg das."""
    from tools.doclayout.schema import LayoutDefinition

    namen = ("IFJN_layout", "Reisefuehrer_Andalusien")
    betroffen = [n for n in namen if "fachtext" in library.load_layout(n, bibliothek).classmap]
    if len(betroffen) < 2:
        pytest.skip("braucht zwei Layouts mit der Klasse .fachtext")
    if aktion == "eigenes_format":
        assert mi.remap_class_to_style("fachtext", "Normal", library_dir=bibliothek,
                                       layout_names=namen)[0]
    vorher = {n: _datei(bibliothek, n).read_bytes() for n in namen}

    echtes_speichern = LayoutDefinition.save
    aufrufe = []

    def zweites_scheitert(self, path):
        aufrufe.append(path)
        if len(aufrufe) == 2:
            raise OSError("Platte voll")
        return echtes_speichern(self, path)

    monkeypatch.setattr(LayoutDefinition, "save", zweites_scheitert)
    if aktion == "verwerfen":
        ok, meldung = mi.remap_class_to_style("fachtext", "BodyText", library_dir=bibliothek,
                                              layout_names=namen)
    else:
        ok, meldung = mi.detach_class_to_own_style("fachtext", library_dir=bibliothek,
                                                   layout_names=namen)
    assert not ok and "nichts geändert" in meldung
    assert {n: _datei(bibliothek, n).read_bytes() for n in namen} == vorher
