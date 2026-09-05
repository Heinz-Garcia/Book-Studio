"""Die Schriftwahl muss bis in die erzeugte ``reference.docx`` durchschlagen.

Regression: ``body_font``, ``heading_font`` und ``mono_font`` waren lange ein
Leerlauf. Der Editor bot drei Felder an, das Schema speicherte sie, der
Importer las sie aus einer bestehenden ``.docx`` sogar zurueck -- nur das
Zielformat schrieb nie ein ``w:rFonts``. Wer die Grundschrift auf Garamond
stellte, bekam eine Vorlage in Pandocs Themenschrift, ohne Hinweis.

Zwei Wege muessen dafuer zusammenkommen, und beide werden hier geprueft:

* ``docDefaults`` traegt die Grundschrift -- sie gilt fuer alles, was nichts
  eigenes sagt.
* Das **Thema** traegt das Schriftpaar. Pandocs Basisformate benennen naemlich
  keine Schrift, sondern verweisen darauf (``w:asciiTheme="majorHAnsi"``), und
  so ein Verweis schlaegt die Dokumentvorgaben. Ohne diesen zweiten Schritt
  blieben ausgerechnet die ``Heading1..9`` in der alten Schrift stehen.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from tools.doclayout.library import load_layout
from tools.doclayout.ooxml import (
    HEADING_STYLE_IDS,
    MONOSPACE_STYLE_IDS,
    build_style_element,
    font_for,
    local_name,
    qn,
)
from tools.doclayout.schema import LayoutDefinition, ParagraphStyle, Typography
from tools.doclayout.targets.docx import (
    DocxTargetError,
    build_reference_docx,
    find_pandoc,
)

pandoc_required = pytest.mark.skipif(
    find_pandoc() is None, reason="Pandoc (auch via Quarto) nicht gefunden"
)

_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


@pytest.fixture()
def dreischriftig() -> LayoutDefinition:
    """Ein Layout, dessen drei Schriften sich eindeutig unterscheiden."""
    return replace(
        load_layout("IFJN_layout"),
        typography=replace(
            load_layout("IFJN_layout").typography,
            body_font="Garamond",
            heading_font="Futura",
            mono_font="Fira Code",
        ),
    )


# ---------------------------------------------------------------------------
# Die Zuordnung Format -> Schrift (ohne Pandoc)
# ---------------------------------------------------------------------------


def _typografie(**kwargs) -> LayoutDefinition:
    return LayoutDefinition(name="T", typography=Typography(**kwargs))


def test_fliesstext_bekommt_keine_eigene_schrift():
    """Er erbt aus den Dokumentvorgaben -- sonst stuende sie vierzigmal da."""
    definition = _typografie(body_font="Garamond", heading_font="Futura")
    assert font_for(definition, ParagraphStyle(style_id="BodyText")) is None


@pytest.mark.parametrize("style_id", sorted(HEADING_STYLE_IDS))
def test_ueberschriften_bekommen_die_ueberschriftenschrift(style_id: str):
    definition = _typografie(body_font="Garamond", heading_font="Futura")
    assert font_for(definition, ParagraphStyle(style_id=style_id)) == "Futura"


@pytest.mark.parametrize("style_id", sorted(MONOSPACE_STYLE_IDS))
def test_codeformate_bekommen_die_feste_breite(style_id: str):
    definition = _typografie(body_font="Garamond", mono_font="Fira Code")
    assert font_for(definition, ParagraphStyle(style_id=style_id)) == "Fira Code"


def test_ein_eigenes_format_mit_gliederungsebene_zaehlt_als_ueberschrift():
    """Ein »Kapitelkopf« ist eine Ueberschrift, auch wenn er nicht so heisst."""
    definition = _typografie(heading_font="Futura")
    eigen = ParagraphStyle(style_id="Kapitelkopf", outline_level=0)
    assert font_for(definition, eigen) == "Futura"


def test_leere_ueberschriftenschrift_heisst_wie_die_grundschrift():
    """Das Feld sagt "leer = wie Grundschrift" -- dann eben kein Eintrag."""
    definition = _typografie(body_font="Garamond", heading_font="")
    assert font_for(definition, ParagraphStyle(style_id="Heading1")) is None


def test_die_schrift_steht_im_erzeugten_format():
    definition = _typografie(heading_font="Futura")
    element = build_style_element(definition, ParagraphStyle(style_id="Heading1"))
    fonts = element.find(qn("rPr")).find(qn("rFonts"))
    assert fonts is not None
    assert fonts.get(qn("ascii")) == "Futura"
    assert fonts.get(qn("hAnsi")) == "Futura"


def test_rfonts_steht_an_schemakonformer_stelle():
    """CT_RPr verlangt ``rFonts`` vor ``b``, ``color`` und ``sz``.

    Falsch einsortiert oeffnet Word die Vorlage ohne Formate -- ein Fehler,
    den man der Datei nicht ansieht.
    """
    definition = _typografie(heading_font="Futura")
    style = ParagraphStyle(
        style_id="Heading1", bold=True, italic=True, size_pt=18.0, color="1F3864"
    )
    rpr = build_style_element(definition, style).find(qn("rPr"))
    namen = [local_name(child.tag) for child in rpr]
    assert namen[0] == "rFonts", namen


def test_ohne_eigene_schrift_bleibt_das_format_unberuehrt():
    """Kein leeres ``w:rFonts`` -- das naehme der Basisvorlage ihre Schrift."""
    definition = _typografie(body_font="Garamond", heading_font="")
    rpr = build_style_element(
        definition, ParagraphStyle(style_id="Heading1")
    ).find(qn("rPr"))
    assert rpr is None or rpr.find(qn("rFonts")) is None


# ---------------------------------------------------------------------------
# Die erzeugte Datei (mit Pandoc)
# ---------------------------------------------------------------------------


def _theme_fonts(docx: Path) -> dict[str, str]:
    theme = zipfile.ZipFile(docx).read("word/theme/theme1.xml").decode("utf-8")
    root = ET.fromstring(theme)
    scheme = root.find(f".//{{{_A_NS}}}fontScheme")
    return {
        local_name(gruppe.tag): gruppe.find(f"{{{_A_NS}}}latin").get("typeface")
        for gruppe in scheme
        if gruppe.find(f"{{{_A_NS}}}latin") is not None
    }


def _doc_default_font(docx: Path) -> str | None:
    styles = zipfile.ZipFile(docx).read("word/styles.xml")
    root = ET.fromstring(styles)
    rpr = root.find(qn("docDefaults")).find(qn("rPrDefault")).find(qn("rPr"))
    fonts = rpr.find(qn("rFonts"))
    return None if fonts is None else fonts.get(qn("ascii"))


@pandoc_required
def test_die_grundschrift_steht_in_den_dokumentvorgaben(
    dreischriftig: LayoutDefinition, tmp_path: Path
):
    out = build_reference_docx(dreischriftig, tmp_path / "reference.docx")
    assert _doc_default_font(out) == "Garamond"


@pandoc_required
def test_die_dokumentvorgaben_verlieren_den_themenverweis(
    dreischriftig: LayoutDefinition, tmp_path: Path
):
    """``w:asciiTheme`` neben ``w:ascii`` machte die Schrift zum Vorschlag."""
    out = build_reference_docx(dreischriftig, tmp_path / "reference.docx")
    styles = zipfile.ZipFile(out).read("word/styles.xml")
    rpr = (
        ET.fromstring(styles)
        .find(qn("docDefaults"))
        .find(qn("rPrDefault"))
        .find(qn("rPr"))
    )
    assert rpr.find(qn("rFonts")).get(qn("asciiTheme")) is None


@pandoc_required
def test_das_thema_traegt_beide_schriften(
    dreischriftig: LayoutDefinition, tmp_path: Path
):
    out = build_reference_docx(dreischriftig, tmp_path / "reference.docx")
    fonts = _theme_fonts(out)
    assert fonts["majorFont"] == "Futura"
    assert fonts["minorFont"] == "Garamond"


@pandoc_required
def test_ohne_ueberschriftenschrift_folgt_das_thema_der_grundschrift(
    tmp_path: Path,
):
    definition = replace(
        load_layout("IFJN_layout"),
        typography=replace(
            load_layout("IFJN_layout").typography,
            body_font="Garamond",
            heading_font="",
        ),
    )
    fonts = _theme_fonts(
        build_reference_docx(definition, tmp_path / "reference.docx")
    )
    assert fonts["majorFont"] == "Garamond"
    assert fonts["minorFont"] == "Garamond"


@pandoc_required
def test_nicht_erklaerte_ueberschriften_folgen_ueber_das_thema(
    dreischriftig: LayoutDefinition, tmp_path: Path
):
    """Der eigentliche Grund fuer den Umweg ueber das Thema.

    ``IFJN_layout`` erklaert kein ``Heading1``; es kommt aus Pandocs
    Basisvorlage und verweist auf die Themenschrift. Vor der Korrektur blieb
    genau dieses Format in der alten Schrift stehen.
    """
    out = build_reference_docx(dreischriftig, tmp_path / "reference.docx")
    assert "Heading1" not in dreischriftig.styles
    root = ET.fromstring(zipfile.ZipFile(out).read("word/styles.xml"))
    heading = next(
        s for s in root.findall(qn("style")) if s.get(qn("styleId")) == "Heading1"
    )
    fonts = heading.find(qn("rPr")).find(qn("rFonts"))
    assert fonts.get(qn("asciiTheme")) == "majorHAnsi"
    assert _theme_fonts(out)["majorFont"] == "Futura"


@pandoc_required
def test_die_panose_kennung_der_alten_schrift_verschwindet(
    dreischriftig: LayoutDefinition, tmp_path: Path
):
    """Sonst suchte ein Ersatz nach den Merkmalen der falschen Schrift."""
    out = build_reference_docx(dreischriftig, tmp_path / "reference.docx")
    theme = zipfile.ZipFile(out).read("word/theme/theme1.xml").decode("utf-8")
    for gruppe in ("majorFont", "minorFont"):
        treffer = re.search(rf"<a:{gruppe}>\s*<a:latin[^/]*/>", theme)
        assert treffer is not None
        assert "panose" not in treffer.group(0)


@pandoc_required
def test_eine_verschluckte_grundschrift_faellt_auf(
    dreischriftig: LayoutDefinition, tmp_path: Path, monkeypatch
):
    """Die Rueckpruefung ist der Grund, warum das nicht wieder still ausfaellt."""
    import tools.doclayout.targets.docx as ziel

    monkeypatch.setattr(ziel, "_patch_doc_defaults", lambda definition, root: None)
    with pytest.raises(DocxTargetError, match="Grundschrift"):
        build_reference_docx(dreischriftig, tmp_path / "reference.docx")


@pandoc_required
def test_die_vorlage_bleibt_ein_lesbares_docx(
    dreischriftig: LayoutDefinition, tmp_path: Path
):
    """Alle Teile muessen gueltiges XML bleiben -- auch das angefasste Thema."""
    out = build_reference_docx(dreischriftig, tmp_path / "reference.docx")
    with zipfile.ZipFile(out) as archiv:
        for name in archiv.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                ET.fromstring(archiv.read(name))
