"""Kastentitel, Zwischentitel und Farbfreiheit -- aus dem Absatzformat, nie aus dem Inhalt.

Nutzer, 2026-10-01: Die Kästen „Am Schalter auf Spanisch“ und „Key Takeaway“
bekommen ihre Überschrift samt einfarbigem Symbol aus der Layout-Definition;
Disclaimer und Transparenzhinweis im Impressum werden Zwischentitel (fett);
im Inhalt bleiben keine Farben (Hintergründe hellgrau, Text dunkelgrau).
Dasselbe gilt für den Typst-Satz (Fallback).
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from tools.doclayout.classmap import build_lua_filter, write_lua_filter
from tools.doclayout.schema import (
    SYMBOL_FONT_DEFAULT,
    Kastentitel,
    LayoutDefinition,
    ParagraphStyle,
)
from tools.doclayout.targets.docx import find_pandoc

LIBRARY = Path(__file__).resolve().parents[1] / "tools" / "doclayout" / "library"


def _andalusien() -> LayoutDefinition:
    return LayoutDefinition.load(LIBRARY / "Reisefuehrer_Andalusien.yaml")


# -- Schema ---------------------------------------------------------------------


def test_kastentitel_rundlauf_und_nur_bei_gebrauch_gespeichert() -> None:
    stil = ParagraphStyle.from_dict("Box", {
        "shading": "F2F2F2",
        "kastentitel": {"text": "Am Schalter", "icon": "🗨", "format": "Box-Titel"},
        "zwischentitel": "Box-Zwischen",
    })
    assert stil.kastentitel == Kastentitel("Am Schalter", "🗨", "Box-Titel")
    assert ParagraphStyle.from_dict("Box", stil.to_dict()) == stil
    ohne = ParagraphStyle.from_dict("Box", {"shading": "F2F2F2"})
    assert "kastentitel" not in ohne.to_dict() and "zwischentitel" not in ohne.to_dict()


def test_symbolschrift_nur_wenn_abweichend_gespeichert() -> None:
    d = _andalusien()
    assert d.typography.symbol_font == SYMBOL_FONT_DEFAULT
    assert "symbol_font" not in d.typography.to_dict()


def test_validierung_meldet_unbekannte_titelformate() -> None:
    d = LayoutDefinition.from_dict({
        "name": "T",
        "styles": {"Box": {"kastentitel": {"text": "X", "format": "Fehlt"}, "zwischentitel": "AuchFehlt"}},
    })
    probleme = " ".join(d.validate())
    assert "Fehlt" in probleme and "AuchFehlt" in probleme


def test_andalusien_ist_farbfrei_und_gueltig() -> None:
    d = _andalusien()
    assert d.validate() == []
    for sid, stil in d.styles.items():
        for wert in (stil.color, stil.shading, *(b.color for b in stil.borders.values())):
            hexwert = d.resolve_color(wert)
            if hexwert in (None, "auto"):
                continue
            r, g, b = (int(hexwert[i:i + 2], 16) for i in (0, 2, 4))
            assert r == g == b, f"{sid}: {wert} = {hexwert} ist nicht grau"
    assert d.styles["Spanisch"].kastentitel.text == "Am Schalter auf Spanisch"
    assert d.styles["KeyTakeaway"].kastentitel.text == "Key Takeaway"
    assert d.styles["Impressum"].zwischentitel == "Impressum-Zwischentitel"


# -- Filter ---------------------------------------------------------------------


def test_filter_traegt_titel_aus_der_definition() -> None:
    lua = build_lua_filter(_andalusien())
    assert '["Spanisch"] = {text = "Am Schalter auf Spanisch", icon = "🗨", format = "Spanisch-Titel"}' in lua
    assert '["Impressum"] = "Impressum-Zwischentitel"' in lua
    assert 'local symbol_font = "Segoe UI Symbol"' in lua
    assert 'fill = "F2F2F2"' in lua


_MD = """\
::: {.impressum}
Text davor.

*Transparenzhinweis zum Einsatz von KI*

Text danach.
:::

::: {.buch_spanisch}
**urgencias** — Notaufnahme
:::
"""


def _pandoc_oder_skip() -> str:
    pandoc = find_pandoc()
    if not pandoc:
        pytest.skip("Pandoc nicht gefunden")
    return pandoc


def test_docx_bekommt_kastentitel_und_zwischentitel(tmp_path: Path) -> None:
    pandoc = _pandoc_oder_skip()
    lua = write_lua_filter(_andalusien(), tmp_path / "classmap.lua")
    (tmp_path / "t.md").write_text(_MD, encoding="utf-8")
    subprocess.run([pandoc, str(tmp_path / "t.md"), "-o", str(tmp_path / "t.docx"),
                    f"--lua-filter={lua}"], check=True, capture_output=True)
    xml = zipfile.ZipFile(tmp_path / "t.docx").read("word/document.xml").decode("utf-8")
    assert "Am Schalter auf Spanisch" in xml
    titel = xml[: xml.index("Am Schalter auf Spanisch")]
    assert 'w:val="SpanischTitel"' in titel or 'w:val="Spanisch-Titel"' in titel
    assert "Segoe UI Symbol" in xml and "🗨" in xml
    vor_hinweis = xml[: xml.index("Transparenzhinweis")]
    assert vor_hinweis.rfind("Impressum-Zwischentitel") > vor_hinweis.rfind("<w:p>")


def test_typst_kasten_mit_titel_ohne_farbe(tmp_path: Path) -> None:
    pandoc = _pandoc_oder_skip()
    lua = write_lua_filter(_andalusien(), tmp_path / "classmap.lua")
    (tmp_path / "t.md").write_text(_MD, encoding="utf-8")
    typ = subprocess.run([pandoc, str(tmp_path / "t.md"), "-t", "typst", f"--lua-filter={lua}"],
                         check=True, capture_output=True).stdout.decode("utf-8")
    assert '#block(width: 100%, breakable: true, inset: 7pt, fill: rgb("#F2F2F2")' in typ
    assert "Am Schalter auf Spanisch" in typ and 'font: "Segoe UI Symbol"' in typ
    assert "#block(sticky: true)[" in typ
    # Zwischentitel fett (Strong) um die Hervorhebung
    assert "#strong[#emph[Transparenzhinweis zum Einsatz von KI]]" in typ


# -- Eintragung und Linkfarbe ---------------------------------------------------


def _buch_mit_filter(tmp_path: Path, filtertext: str) -> Path:
    buch = tmp_path / "buch"
    (buch / "bookconfig" / "doclayout").mkdir(parents=True)
    (buch / "bookconfig" / "doclayout" / "classmap.lua").write_text(filtertext, encoding="utf-8")
    (buch / "_quarto.yml").write_text(
        "project:\n  type: book\nformat:\n  typst:\n    toc: false\n    filters:\n      - eigen.lua\n",
        encoding="utf-8",
    )
    return buch


def test_render_klon_traegt_den_filter_fuer_typst_ein(tmp_path: Path) -> None:
    """Nur im Render-Klon -- das doclayout-Werkzeug fasst den Typst-Pfad nicht an."""
    import yaml

    from render_klon import ensure_typst_layout_filter

    buch = _buch_mit_filter(tmp_path, build_lua_filter(_andalusien()))
    meldungen: list[str] = []
    ensure_typst_layout_filter(buch, meldungen.append)
    typst = yaml.safe_load((buch / "_quarto.yml").read_text(encoding="utf-8"))["format"]["typst"]
    assert typst["filters"] == ["eigen.lua", "bookconfig/doclayout/classmap.lua"]
    assert typst["toc"] is False
    vorher = (buch / "_quarto.yml").read_text(encoding="utf-8")
    ensure_typst_layout_filter(buch, meldungen.append)
    assert (buch / "_quarto.yml").read_text(encoding="utf-8") == vorher  # idempotent


def test_alter_filter_ohne_typst_teil_bleibt_draussen(tmp_path: Path) -> None:
    from render_klon import ensure_typst_layout_filter

    buch = _buch_mit_filter(tmp_path, "-- alter Filter, nur DOCX\n")
    vorher = (buch / "_quarto.yml").read_text(encoding="utf-8")
    meldungen: list[str] = []
    ensure_typst_layout_filter(buch, meldungen.append)
    assert (buch / "_quarto.yml").read_text(encoding="utf-8") == vorher
    assert any("neu anwenden" in m for m in meldungen)


def test_linkfarbe_aus_dem_token(tmp_path: Path) -> None:
    import xml.etree.ElementTree as ET

    from tools.doclayout.ooxml import qn
    from tools.doclayout.targets.docx import _patch_link_color

    root = ET.fromstring(
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="character" w:styleId="Hyperlink"><w:rPr>'
        '<w:color w:val="4F81BD" w:themeColor="accent1"/></w:rPr></w:style></w:styles>'
    )
    _patch_link_color(_andalusien(), root)
    farbe = root.find(f"{qn('style')}/{qn('rPr')}/{qn('color')}")
    assert farbe.get(qn("val")) == "404040" and farbe.get(qn("themeColor")) is None
