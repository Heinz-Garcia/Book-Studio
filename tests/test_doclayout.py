"""Tests der Formatvorlagen-Schicht (``tools/doclayout``).

Die Tests ohne Pandoc laufen ueberall; die Erzeugung der ``reference.docx``
braucht Pandoc (auch das von Quarto mitgelieferte) und wird sonst uebersprungen.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
import yaml

from tools.doclayout import units
from tools.doclayout.apply import apply_layout, quarto_snippet
from tools.doclayout.classmap import build_lua_filter, normalize_class
from tools.doclayout.library import LIBRARY_DIR, available_layouts, load_layout
from tools.doclayout.ooxml import W_NS, build_style_element, local_name, qn
from tools.doclayout.schema import LayoutDefinition, LayoutError, ParagraphStyle
from tools.doclayout.targets.docx import build_reference_docx, find_pandoc

pandoc_required = pytest.mark.skipif(
    find_pandoc() is None, reason="Pandoc (auch via Quarto) nicht gefunden"
)


@pytest.fixture()
def ifjn() -> LayoutDefinition:
    return load_layout("IFJN_layout")


# ---------------------------------------------------------------------------
# Bibliothek und Schema
# ---------------------------------------------------------------------------


def test_library_contains_ifjn_layout():
    names = [p.stem for p in available_layouts()]
    assert "IFJN_layout" in names, f"IFJN_layout fehlt in {LIBRARY_DIR}"


def test_ifjn_layout_validates(ifjn: LayoutDefinition):
    assert ifjn.validate() == []
    assert ifjn.name == "IFJN_layout"
    assert ifjn.classmap["prompt"] == "Prompt-Frage"


def test_load_layout_names_alternatives_on_typo():
    with pytest.raises(LayoutError) as excinfo:
        load_layout("gibt_es_nicht")
    assert "IFJN_layout" in str(excinfo.value)


def test_text_width_follows_from_page_and_margins(ifjn: LayoutDefinition):
    page = ifjn.page
    assert page.text_width_mm == pytest.approx(
        page.width_mm - page.margin.inner_mm - page.margin.outer_mm
    )


def test_margins_wider_than_page_are_rejected():
    with pytest.raises(LayoutError, match="Textbreite"):
        LayoutDefinition.from_dict(
            {
                "name": "kaputt",
                "page": {
                    "width_mm": 100,
                    "margin": {"inner_mm": 60, "outer_mm": 60},
                },
            }
        )


# ---------------------------------------------------------------------------
# Farbaufloesung
# ---------------------------------------------------------------------------


def test_resolve_color_accepts_token_and_hex(ifjn: LayoutDefinition):
    assert ifjn.resolve_color("accent") == "1F3864"
    assert ifjn.resolve_color("#ff8800") == "FF8800"
    assert ifjn.resolve_color("AABBCC") == "AABBCC"
    assert ifjn.resolve_color(None) is None


def test_unknown_color_token_is_an_error_not_a_default(ifjn: LayoutDefinition):
    """Ein Tippfehler im Editor soll auffallen, nicht schwarz gerendert werden."""
    with pytest.raises(LayoutError, match="weder ein Hex-Wert noch ein bekannter"):
        ifjn.resolve_color("akzent")


# ---------------------------------------------------------------------------
# Validierung findet Fehler, statt sie durchzureichen
# ---------------------------------------------------------------------------


def test_validate_reports_classmap_pointing_at_missing_style():
    definition = LayoutDefinition.from_dict(
        {"name": "x", "styles": {}, "classmap": {"prompt": "Gibt-Es-Nicht"}}
    )
    problems = definition.validate()
    assert any("Gibt-Es-Nicht" in p for p in problems)


def test_validate_reports_style_inheritance_cycle():
    definition = LayoutDefinition.from_dict(
        {
            "name": "x",
            "styles": {"A": {"based_on": "B"}, "B": {"based_on": "A"}},
        }
    )
    assert any("zyklisch" in p for p in definition.validate())


def test_validate_rejects_hanging_and_first_line_together():
    definition = LayoutDefinition.from_dict(
        {
            "name": "x",
            "styles": {"A": {"indent": {"hanging_mm": 5, "first_line_mm": 5}}},
        }
    )
    assert any("schliessen sich aus" in p for p in definition.validate())


def test_unknown_alignment_is_rejected():
    with pytest.raises(LayoutError, match="align="):
        LayoutDefinition.from_dict({"name": "x", "styles": {"A": {"align": "schraeg"}}})


# ---------------------------------------------------------------------------
# Einheiten
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "millimetres, twips",
    [(0, 0), (20, 1134), (25, 1417), (210, 11906)],
)
def test_mm_to_twips_matches_word(millimetres, twips):
    assert units.mm_to_twips(millimetres) == pytest.approx(twips, abs=1)


def test_point_conversions():
    assert units.pt_to_half_points(11) == 22
    assert units.pt_to_twips(6) == 120
    assert units.pt_to_eighth_points(2.25) == 18
    assert units.line_height_to_ooxml(1.15) == 276


def test_border_width_is_clamped_to_word_range():
    assert units.pt_to_eighth_points(0.0) == 2
    assert units.pt_to_eighth_points(1000.0) == 96


# ---------------------------------------------------------------------------
# OOXML: die Kindreihenfolge ist der teure Fehler
# ---------------------------------------------------------------------------


def _children(element: ET.Element, tag: str) -> list[str]:
    node = element.find(qn(tag))
    return [local_name(child.tag) for child in node] if node is not None else []


def test_paragraph_property_order_is_schema_conform(ifjn: LayoutDefinition):
    """``w:spacing`` hinter ``w:jc`` macht die Datei fuer Word ungueltig."""
    style = ifjn.styles["Prompt-Frage"]
    element = build_style_element(ifjn, style)
    order = _children(element, "pPr")
    expected = ["keepNext", "keepLines", "pBdr", "shd", "spacing", "ind", "outlineLvl"]
    assert order == expected


def test_run_property_order_is_schema_conform(ifjn: LayoutDefinition):
    element = build_style_element(ifjn, ifjn.styles["Prompt-Frage"])
    assert _children(element, "rPr") == ["b", "bCs", "color", "sz", "szCs"]


def test_style_element_order_is_schema_conform(ifjn: LayoutDefinition):
    element = build_style_element(ifjn, ifjn.styles["Prompt-Frage"])
    assert [local_name(c.tag) for c in element] == [
        "name", "basedOn", "next", "qFormat", "pPr", "rPr",
    ]


def test_page_break_before_lands_before_borders():
    """``pageBreakBefore`` steht laut CT_PPr vor ``pBdr`` -- Themenblock hat beides."""
    definition = load_layout("IFJN_layout")
    element = build_style_element(definition, definition.styles["Themenblock"])
    order = _children(element, "pPr")
    assert order.index("pageBreakBefore") < order.index("pBdr")


def test_style_values_are_converted_not_copied(ifjn: LayoutDefinition):
    element = build_style_element(ifjn, ifjn.styles["Prompt-Frage"])
    rpr = element.find(qn("rPr"))
    assert rpr.find(qn("sz")).get(qn("val")) == "26"  # 13 pt
    ppr = element.find(qn("pPr"))
    left = ppr.find(qn("pBdr")).find(qn("left"))
    assert left.get(qn("sz")) == "18"  # 2,25 pt in Achtelpunkten
    assert left.get(qn("color")) == "2E5C8A"  # Token accent2 aufgeloest


def test_style_without_properties_omits_empty_containers():
    definition = LayoutDefinition.from_dict({"name": "x", "styles": {"Leer": {}}})
    element = build_style_element(definition, definition.styles["Leer"])
    assert element.find(qn("pPr")) is None
    assert element.find(qn("rPr")) is None


# ---------------------------------------------------------------------------
# Klassen-Abbildung
# ---------------------------------------------------------------------------


def test_lua_filter_contains_every_classmap_entry(ifjn: LayoutDefinition):
    lua = build_lua_filter(ifjn)
    for cls, style in ifjn.classmap.items():
        assert f'["{cls}"] = "{style}"' in lua


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("prompt", "prompt"),
        ("{prompt}", "prompt"),       # Altform ohne Punkt aus bestehenden Exporten
        (".prompt", "prompt"),
        ("{fachtext}", "fachtext"),
    ],
)
def test_normalize_class_handles_legacy_form(raw, expected):
    assert normalize_class(raw) == expected


def test_lua_filter_is_valid_for_empty_classmap():
    definition = LayoutDefinition.from_dict({"name": "x", "classmap": {}})
    assert "local classmap = {}" in build_lua_filter(definition)


# ---------------------------------------------------------------------------
# DOCX-Erzeugung (braucht Pandoc)
# ---------------------------------------------------------------------------


@pandoc_required
def test_build_reference_docx_contains_all_styles(ifjn: LayoutDefinition, tmp_path: Path):
    out = build_reference_docx(ifjn, tmp_path / "reference.docx")
    with zipfile.ZipFile(out) as archive:
        root = ET.fromstring(archive.read("word/styles.xml"))
    present = {s.get(qn("styleId")) for s in root.findall(qn("style"))}
    assert set(ifjn.styles) <= present


@pandoc_required
def test_build_reference_docx_is_well_formed_everywhere(ifjn: LayoutDefinition, tmp_path: Path):
    out = build_reference_docx(ifjn, tmp_path / "reference.docx")
    with zipfile.ZipFile(out) as archive:
        for name in archive.namelist():
            if name.endswith((".xml", ".rels")):
                ET.fromstring(archive.read(name))


@pandoc_required
def test_build_reference_docx_sets_page_size(ifjn: LayoutDefinition, tmp_path: Path):
    out = build_reference_docx(ifjn, tmp_path / "reference.docx")
    with zipfile.ZipFile(out) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    sectpr = root.find(qn("body")).find(qn("sectPr"))
    assert sectpr.find(qn("pgSz")).get(qn("w")) == str(units.mm_to_twips(210))
    assert sectpr.find(qn("pgMar")).get(qn("left")) == str(units.mm_to_twips(25))


@pandoc_required
def test_build_reference_docx_adds_footer_part(ifjn: LayoutDefinition, tmp_path: Path):
    out = build_reference_docx(ifjn, tmp_path / "reference.docx")
    with zipfile.ZipFile(out) as archive:
        assert "word/footer1.xml" in archive.namelist()
        footer = archive.read("word/footer1.xml").decode("utf-8")
    assert "PAGE" in footer


@pandoc_required
def test_invalid_layout_refuses_to_build(tmp_path: Path):
    definition = LayoutDefinition.from_dict(
        {"name": "x", "classmap": {"prompt": "Fehlt"}}
    )
    with pytest.raises(LayoutError, match="nicht erzeugbar"):
        build_reference_docx(definition, tmp_path / "reference.docx")


# ---------------------------------------------------------------------------
# Anwendung auf ein Buchprojekt
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path) -> Path:
    book = tmp_path / "buch"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n"
        "  type: book\n"
        "  output-dir: export/_book\n"
        "book:\n"
        "  title: Testband\n"
        "  chapters:\n"
        "  - index.md\n"
        "  - content/kapitel.md\n"
        "format:\n"
        "  typst:\n"
        "    toc: true\n"
        "    papersize: a4\n",
        encoding="utf-8",
    )
    return book


@pandoc_required
def test_apply_writes_artifacts_and_wires_quarto_yml(ifjn: LayoutDefinition, tmp_path: Path):
    book = _make_book(tmp_path)
    result = apply_layout(ifjn, book)

    assert result.reference_docx.is_file()
    assert result.lua_filter.is_file()
    assert result.quarto_changed

    data = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    docx = data["format"]["docx"]
    assert docx["reference-doc"] == "bookconfig/doclayout/reference.docx"
    assert docx["filters"] == ["bookconfig/doclayout/classmap.lua"]


@pandoc_required
def test_apply_leaves_the_typst_pipeline_untouched(ifjn: LayoutDefinition, tmp_path: Path):
    """Anforderung 2 aus .doc/ebook-epub-autonomes-tool.md: der Print-Pfad
    darf sich durch dieses Tool nicht aendern -- auch nicht indirekt."""
    book = _make_book(tmp_path)
    before = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    apply_layout(ifjn, book)
    after = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))

    assert after["format"]["typst"] == before["format"]["typst"]
    assert after["book"] == before["book"]
    assert after["project"] == before["project"]
    assert "filters" not in after, "Filter darf nicht auf Projektebene landen"


@pandoc_required
def test_apply_is_idempotent(ifjn: LayoutDefinition, tmp_path: Path):
    book = _make_book(tmp_path)
    apply_layout(ifjn, book)
    text_after_first = (book / "_quarto.yml").read_text(encoding="utf-8")

    second = apply_layout(ifjn, book)
    assert not second.quarto_changed
    assert (book / "_quarto.yml").read_text(encoding="utf-8") == text_after_first


@pandoc_required
def test_apply_backs_up_quarto_yml_before_changing_it(ifjn: LayoutDefinition, tmp_path: Path):
    book = _make_book(tmp_path)
    original = (book / "_quarto.yml").read_text(encoding="utf-8")
    result = apply_layout(ifjn, book)
    assert result.quarto_backup is not None
    assert result.quarto_backup.read_text(encoding="utf-8") == original


@pandoc_required
def test_apply_can_skip_quarto_yml(ifjn: LayoutDefinition, tmp_path: Path):
    book = _make_book(tmp_path)
    original = (book / "_quarto.yml").read_text(encoding="utf-8")
    result = apply_layout(ifjn, book, write_quarto_yml=False)
    assert result.reference_docx.is_file()
    assert (book / "_quarto.yml").read_text(encoding="utf-8") == original


@pandoc_required
def test_apply_refuses_when_format_is_not_a_mapping(ifjn: LayoutDefinition, tmp_path: Path):
    book = tmp_path / "buch"
    book.mkdir()
    (book / "_quarto.yml").write_text("format: docx\n", encoding="utf-8")
    with pytest.raises(LayoutError, match="format"):
        apply_layout(ifjn, book)


def test_apply_rejects_missing_book(ifjn: LayoutDefinition, tmp_path: Path):
    with pytest.raises(LayoutError, match="Buchprojekt nicht gefunden"):
        apply_layout(ifjn, tmp_path / "gibt_es_nicht")


def test_quarto_snippet_uses_forward_slashes(ifjn: LayoutDefinition):
    """Quarto-Pfade sind POSIX, auch unter Windows."""
    snippet = quarto_snippet(ifjn)
    assert "bookconfig/doclayout/reference.docx" in snippet
    assert "\\" not in snippet


# ---------------------------------------------------------------------------
# Rundlauf durch YAML
# ---------------------------------------------------------------------------


def test_definition_survives_save_and_load(ifjn: LayoutDefinition, tmp_path: Path):
    path = ifjn.save(tmp_path / "kopie.yaml")
    again = LayoutDefinition.load(path)
    assert again.to_dict() == ifjn.to_dict()


def test_with_style_returns_a_copy(ifjn: LayoutDefinition):
    changed = ifjn.with_style(ParagraphStyle(style_id="Prompt-Frage", size_pt=99.0))
    assert changed.styles["Prompt-Frage"].size_pt == 99.0
    assert ifjn.styles["Prompt-Frage"].size_pt == 13.0, "Original wurde veraendert"


def test_namespace_constant_matches_ooxml():
    assert W_NS.endswith("wordprocessingml/2006/main")
