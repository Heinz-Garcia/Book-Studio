"""Tests der Formatvorlagen-Schicht (``tools/doclayout``).

Die Tests ohne Pandoc laufen ueberall; die Erzeugung der ``reference.docx``
braucht Pandoc (auch das von Quarto mitgelieferte) und wird sonst uebersprungen.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
import yaml

from tools.doclayout import units
from tools.doclayout.apply import apply_layout, quarto_snippet
from tools.doclayout.classmap import build_lua_filter, lua_string, normalize_class
from tools.doclayout.library import LIBRARY_DIR, available_layouts, load_layout
from tools.doclayout.ooxml import W_NS, build_style_element, local_name, qn
from tools.doclayout.process import NO_WINDOW, run_hidden
from tools.doclayout.origins import (
    PANDOC_STYLE_IDS,
    StyleOrigin,
    counts,
    is_standard,
    origin_of,
    origins,
)
from tools.doclayout.requirements import (
    check_requirements,
    is_blocked,
    missing,
    summary,
)
from tools.doclayout.preview import (
    PreviewError,
    build_sample_markdown,
    find_soffice,
    render_preview,
    toc_title_for,
)
from tools.doclayout.schema import LayoutDefinition, LayoutError, ParagraphStyle
from tools.doclayout.targets.docx import build_reference_docx, find_pandoc

pandoc_required = pytest.mark.skipif(
    find_pandoc() is None, reason="Pandoc (auch via Quarto) nicht gefunden"
)

soffice_required = pytest.mark.skipif(
    find_soffice() is None, reason="LibreOffice nicht gefunden"
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


# --- Umlaute im Lua-Filter -------------------------------------------------
#
# Regression: Der Filter wurde mit ``json.dumps`` gebaut, also mit
# ``ensure_ascii=True``. Jedes Nicht-ASCII-Zeichen wurde damit zu ``\uXXXX`` --
# einer Schreibweise, die Lua nicht kennt (dort ``\u{XXXX}``). Der Filter war
# syntaktisch kaputt, und Pandoc brach den ganzen Lauf ab:
#
#     …/classmap.lua:7: missing '{' near '"begr\u0'
#
# Ein einziger Umlaut in einem Klassennamen oder Absatzformat machte damit
# jeden DOCX-Export des Buches unmoeglich. Der Weg dorthin ist der vorgesehene
# Ablauf: Generator schreibt ``::: {.begrüßung}`` -> "Fehlende Klassen anlegen"
# -> ``suggested_style_id`` macht daraus ``Begrüßung``.


@pytest.mark.parametrize(
    "roh, erwartet",
    [
        ("prompt", '"prompt"'),
        ("Begrüßung", '"Begrüßung"'),  # woertlich, nicht ü
        ("Fußnote", '"Fußnote"'),
        ('mit"quote', '"mit\\"quote"'),
        ("back\\slash", '"back\\\\slash"'),
        ("zeile\numbruch", '"zeile\\numbruch"'),
        ("tab\there", '"tab\\there"'),
        ("steuer\x01zeichen", '"steuer\\001zeichen"'),
    ],
)
def test_lua_string_escapes_only_what_lua_needs(roh, erwartet):
    assert lua_string(roh) == erwartet


def test_lua_filter_keeps_umlauts_verbatim():
    """Der Kern des Fehlers: kein ``\\u`` im erzeugten Filter."""
    definition = LayoutDefinition.from_dict(
        {
            "name": "x",
            "styles": {"Begrüßung": {"name": "Begrüßung"}},
            "classmap": {"begrüßung": "Begrüßung"},
        }
    )
    lua = build_lua_filter(definition)
    assert '["begrüßung"] = "Begrüßung"' in lua
    assert "\\u" not in lua


@pytest.mark.slow
def test_lua_filter_with_umlauts_survives_real_pandoc(tmp_path: Path):
    """Gegenprobe am echten Pandoc -- der Filter muss geladen werden koennen.

    Ohne diesen Test faellt die Regression erst im fertigen Buch auf, und dort
    sieht sie aus wie ein Pandoc-Problem.
    """
    from tools.doclayout.targets.docx import find_pandoc

    pandoc = find_pandoc(None)
    if not pandoc:
        pytest.skip("Pandoc nicht gefunden")

    definition = LayoutDefinition.from_dict(
        {
            "name": "x",
            "styles": {"Begrüßung": {"name": "Begrüßung"}},
            "classmap": {"begrüßung": "Begrüßung"},
        }
    )
    (tmp_path / "f.lua").write_text(build_lua_filter(definition), encoding="utf-8")
    (tmp_path / "t.md").write_text("::: {.begrüßung}\nHallo\n:::\n", encoding="utf-8")
    ergebnis = subprocess.run(
        [
            pandoc,
            "-f",
            "markdown",
            "-t",
            "docx",
            "--lua-filter",
            str(tmp_path / "f.lua"),
            str(tmp_path / "t.md"),
            "-o",
            str(tmp_path / "o.docx"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert (tmp_path / "o.docx").is_file()


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


# ---------------------------------------------------------------------------
# Bruecke zu tools/layout_profiles -- die Masse duerfen nicht auseinanderlaufen
# ---------------------------------------------------------------------------


def _profile_ids() -> list[str]:
    from tools.layout_profiles.catalog import LAYOUT_PROFILES

    return [p.id for p in LAYOUT_PROFILES]


def test_every_layout_profile_yields_a_page(ifjn: LayoutDefinition):
    from tools.doclayout.profiles import page_from_profile

    for profile_id in _profile_ids():
        page = page_from_profile(profile_id)
        assert page.width_mm > 0 and page.height_mm > 0
        assert page.text_width_mm > 0, f"{profile_id}: keine Textbreite uebrig"


@pytest.mark.parametrize("profile_id", _profile_ids())
def test_page_geometry_matches_the_profile(ifjn: LayoutDefinition, profile_id: str):
    """Profil -> Definition -> Typst-Metadaten muss wieder beim Profil landen.

    Das ist die eigentliche Zusage der Bruecke: Word-Fassung und PDF duerfen
    nicht unterschiedlich gross werden.
    """
    from tools.doclayout.profiles import definition_from_profile, typst_format_options
    from tools.layout_profiles.catalog import get_profile

    expected = get_profile(profile_id).format_options()
    actual = typst_format_options(definition_from_profile(ifjn, profile_id))

    assert actual["fontsize"] == expected["fontsize"]
    assert actual["linestretch"] == pytest.approx(expected["linestretch"])
    assert _geometry_mm(actual) == pytest.approx(_geometry_mm(expected), abs=0.05)


def _geometry_mm(options: dict) -> tuple[float, float]:
    from tools.doclayout.profiles import PAPER_SIZES_MM
    from tools.layout_profiles.units import parse_length_mm

    width = parse_length_mm(str(options.get("typst-page-width") or ""))
    height = parse_length_mm(str(options.get("typst-page-height") or ""))
    if width and height:
        return width, height
    return PAPER_SIZES_MM[str(options.get("papersize", "a4")).lower()]


def test_bleed_profile_is_larger_than_its_unbled_twin(ifjn: LayoutDefinition):
    """Regression: die Rohfelder des Profils enthalten den Bleed NICHT.

    ``page_from_profile`` muss ueber ``format_options()`` lesen, sonst waere
    eine Vorlage fuer ``paperback-bleed`` 3,2 mm zu schmal -- ein Fehler, der
    erst auf gedrucktem Papier auffaellt.
    """
    from tools.doclayout.profiles import page_from_profile

    plain = page_from_profile("paperback")
    bled = page_from_profile("paperback-bleed")
    assert bled.width_mm > plain.width_mm
    assert bled.height_mm > plain.height_mm


def test_profile_without_margins_uses_the_page_typ_fallback():
    """``standard`` setzt kein page-margin; page.typ nimmt dann 1.25in."""
    from tools.doclayout.profiles import PAGE_TYP_DEFAULT_MARGIN_MM, page_from_profile

    page = page_from_profile("standard")
    assert page.margin.top_mm == pytest.approx(PAGE_TYP_DEFAULT_MARGIN_MM)
    assert page.margin.inner_mm == pytest.approx(PAGE_TYP_DEFAULT_MARGIN_MM)


def test_mirrored_margins_are_detected_for_bound_books(ifjn: LayoutDefinition):
    from tools.doclayout.profiles import page_from_profile, typst_format_options
    from dataclasses import replace

    page = page_from_profile("paperback")
    assert page.mirrored, "Bundsteg-Profil muss gespiegelt sein"
    options = typst_format_options(replace(ifjn, page=page))
    assert set(options["page-margin"]) == {"inside", "outside", "top", "bottom"}


def test_unmirrored_margins_use_left_right(ifjn: LayoutDefinition):
    options = typst_format_options_for(ifjn)
    assert set(options["page-margin"]) == {"left", "right", "top", "bottom"}


def typst_format_options_for(definition: LayoutDefinition) -> dict:
    from tools.doclayout.profiles import typst_format_options

    return typst_format_options(definition)


def test_unknown_profile_names_alternatives():
    from tools.doclayout.profiles import page_from_profile

    with pytest.raises(LayoutError, match="unbekannt"):
        page_from_profile("gibt_es_nicht")


# ---------------------------------------------------------------------------
# Import: bestehende .docx -> Definition
# ---------------------------------------------------------------------------


@pandoc_required
def test_import_reads_back_every_generated_style(ifjn: LayoutDefinition, tmp_path: Path):
    from tools.doclayout.importer import import_docx

    built = build_reference_docx(ifjn, tmp_path / "reference.docx")
    imported = import_docx(built, name="zurueck")

    missing = sorted(set(ifjn.styles) - set(imported.styles))
    assert not missing, f"nicht zurueckgelesen: {missing}"


@pandoc_required
def test_import_preserves_style_values(ifjn: LayoutDefinition, tmp_path: Path):
    from tools.doclayout.importer import import_docx

    built = build_reference_docx(ifjn, tmp_path / "reference.docx")
    back = import_docx(built, name="zurueck").styles["Prompt-Frage"]
    original = ifjn.styles["Prompt-Frage"]

    assert back.size_pt == original.size_pt
    assert back.bold == original.bold
    assert back.space_after_pt == original.space_after_pt
    assert back.line_height == original.line_height
    assert back.outline_level == original.outline_level
    assert back.keep_next == original.keep_next
    assert set(back.borders) == set(original.borders)
    assert back.indent.left_mm == pytest.approx(original.indent.left_mm, abs=0.05)
    assert back.indent.hanging_mm == pytest.approx(original.indent.hanging_mm, abs=0.05)


@pandoc_required
def test_import_preserves_page_and_typography(ifjn: LayoutDefinition, tmp_path: Path):
    from tools.doclayout.importer import import_docx

    built = build_reference_docx(ifjn, tmp_path / "reference.docx")
    back = import_docx(built, name="zurueck")

    assert back.page.width_mm == pytest.approx(ifjn.page.width_mm, abs=0.05)
    assert back.page.margin.inner_mm == pytest.approx(ifjn.page.margin.inner_mm, abs=0.05)
    assert back.typography.base_size_pt == pytest.approx(ifjn.typography.base_size_pt)
    assert back.typography.line_height == pytest.approx(ifjn.typography.line_height)
    assert back.typography.language == ifjn.typography.language


@pandoc_required
def test_import_build_import_is_stable(ifjn: LayoutDefinition, tmp_path: Path):
    """Zweimal durch die Muehle muss dasselbe ergeben.

    Ohne diese Eigenschaft wanderten Werte bei jedem Bearbeiten im Editor ein
    Stueck -- Rundungsfehler, die sich aufaddieren.
    """
    from tools.doclayout.importer import import_docx

    build_reference_docx(ifjn, tmp_path / "a.docx")
    first = import_docx(tmp_path / "a.docx", name="rt")
    build_reference_docx(first, tmp_path / "b.docx")
    second = import_docx(tmp_path / "b.docx", name="rt")

    for key in ("page", "typography", "colors", "styles"):
        assert first.to_dict()[key] == second.to_dict()[key], f"{key} driftet"


@pandoc_required
def test_import_names_colours_by_role(ifjn: LayoutDefinition, tmp_path: Path):
    """Ein Token soll etwas bedeuten -- 'accent' ist die Ueberschriftenfarbe.

    Die Farben werden aus den **Ueberschriften** abgeleitet. Das Layout aus der
    Bibliothek darf jederzeit umgebaut werden -- auch so, dass es gar keine
    Ueberschriften mehr enthaelt. Deshalb stellt dieser Test sie sich selbst,
    statt sich auf eine Datei zu verlassen, die dem Benutzer gehoert.
    """
    from dataclasses import replace as _replace

    from tools.doclayout.importer import import_docx

    styles = dict(ifjn.styles)
    styles["Heading1"] = ParagraphStyle(
        style_id="Heading1", name="Heading 1", size_pt=18.0, bold=True, color="accent"
    )
    # Zwei Ueberschriften je Farbe: Der Importer vergibt einen Namen nur fuer
    # Farben, die mehrfach vorkommen -- ein Token fuer ein Einzelvorkommen waere
    # nur ein zweiter Name fuer dasselbe.
    styles["Heading2"] = ParagraphStyle(
        style_id="Heading2", name="Heading 2", size_pt=15.0, bold=True, color="accent"
    )
    styles["Heading3"] = ParagraphStyle(
        style_id="Heading3", name="Heading 3", size_pt=13.0, bold=True, color="accent2"
    )
    styles["Heading4"] = ParagraphStyle(
        style_id="Heading4", name="Heading 4", size_pt=12.0, bold=True, color="accent2"
    )
    quelle = _replace(ifjn, styles=styles)

    built = build_reference_docx(quelle, tmp_path / "reference.docx")
    back = import_docx(built, name="zurueck")

    assert back.colors.get("accent") == quelle.colors["accent"]
    assert back.colors.get("accent2") == quelle.colors["accent2"]
    assert back.colors.get("rule") == quelle.colors["rule"]


@pandoc_required
def test_import_skips_styles_that_carry_no_formatting(ifjn: LayoutDefinition, tmp_path: Path):
    """Die Pandoc-Basis bringt ~50 Formate mit, die meisten nur Namen."""
    from tools.doclayout.importer import import_docx

    built = build_reference_docx(ifjn, tmp_path / "reference.docx")
    lean = import_docx(built, name="schlank")
    fat = import_docx(built, name="voll", keep_all_styles=True)
    assert len(lean.styles) < len(fat.styles)


@pandoc_required
def test_imported_definition_can_be_built_again(ifjn: LayoutDefinition, tmp_path: Path):
    """Der Import muss etwas Erzeugbares liefern, nicht nur etwas Lesbares."""
    from tools.doclayout.importer import import_docx

    built = build_reference_docx(ifjn, tmp_path / "reference.docx")
    back = import_docx(built, name="zurueck")
    assert back.validate() == []
    again = build_reference_docx(back, tmp_path / "wieder.docx")
    assert again.is_file()


def test_import_rejects_a_non_docx(tmp_path: Path):
    from tools.doclayout.importer import DocxImportError, import_docx

    bogus = tmp_path / "kein.docx"
    bogus.write_text("das ist kein zip", encoding="utf-8")
    with pytest.raises(DocxImportError, match="kein lesbares DOCX"):
        import_docx(bogus)


def test_import_rejects_a_zip_without_styles(tmp_path: Path):
    from tools.doclayout.importer import DocxImportError, import_docx

    bogus = tmp_path / "leer.docx"
    with zipfile.ZipFile(bogus, "w") as archive:
        archive.writestr("hallo.txt", "nichts")
    with pytest.raises(DocxImportError, match="keine word/styles.xml"):
        import_docx(bogus)


def test_import_rejects_a_missing_file(tmp_path: Path):
    from tools.doclayout.importer import DocxImportError, import_docx

    with pytest.raises(DocxImportError, match="nicht gefunden"):
        import_docx(tmp_path / "gibt_es_nicht.docx")


@pandoc_required
def test_import_reproduces_every_style_value_exactly(ifjn: LayoutDefinition, tmp_path: Path):
    """Erzeugen und Zurueckimportieren darf keinen einzigen Wert veraendern.

    Millimeter werden dabei auf 0,1 mm gerundet: Twips loesen 0,0176 mm auf,
    feiner zu runden erzeugt nur Artefakte (210 mm kaeme als 210,01 zurueck).
    """
    from tools.doclayout.importer import import_docx

    built = build_reference_docx(ifjn, tmp_path / "reference.docx")
    back = import_docx(built, name=ifjn.name)

    fields = (
        "size_pt", "bold", "italic", "align", "space_before_pt", "space_after_pt",
        "line_height", "keep_next", "keep_lines", "page_break_before", "outline_level",
    )
    differences = []
    for style_id, original in ifjn.styles.items():
        imported = back.styles[style_id]
        for field_name in fields:
            if getattr(original, field_name) != getattr(imported, field_name):
                differences.append(
                    f"{style_id}.{field_name}: "
                    f"{getattr(original, field_name)} -> {getattr(imported, field_name)}"
                )
        if original.indent != imported.indent:
            differences.append(f"{style_id}.indent: {original.indent} -> {imported.indent}")

    assert not differences, "Werte veraendert:\n  " + "\n  ".join(differences)


@pandoc_required
def test_import_keeps_page_size_free_of_rounding_artefacts(
    ifjn: LayoutDefinition, tmp_path: Path
):
    from tools.doclayout.importer import import_docx

    built = build_reference_docx(ifjn, tmp_path / "reference.docx")
    page = import_docx(built, name="zurueck").page
    assert page.width_mm == ifjn.page.width_mm
    assert page.height_mm == ifjn.page.height_mm


# ---------------------------------------------------------------------------
# Vorschau
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("de-DE", "Inhaltsverzeichnis"),
        ("de", "Inhaltsverzeichnis"),
        ("DE_de", "Inhaltsverzeichnis"),
        ("en-GB", "Table of Contents"),
        ("nl", "Inhoudsopgave"),
    ],
)
def test_toc_title_follows_the_language(language: str, expected: str):
    assert toc_title_for(language) == expected


@pytest.mark.parametrize("language", ["", "   ", "kl-KL", "zz"])
def test_toc_title_stays_silent_for_unknown_languages(language: str):
    """Lieber Pandocs Vorgabe als eine erfundene Uebersetzung."""
    assert toc_title_for(language) is None


def test_sample_markdown_exercises_every_mapped_class(ifjn: LayoutDefinition):
    """Wer eine Klasse ergaenzt, muss sie in der Vorschau wiederfinden."""
    sample = build_sample_markdown(ifjn)
    for cls in ifjn.classmap:
        assert f"::: {{.{cls}}}" in sample, f"Klasse .{cls} fehlt im Musterinhalt"


def test_sample_markdown_reacts_to_a_new_class(ifjn: LayoutDefinition):
    from dataclasses import replace

    extended = ifjn.with_style(ParagraphStyle(style_id="Merksatz", name="Merksatz"))
    extended = replace(
        extended, classmap={**extended.classmap, "merksatz": "Merksatz"}
    )
    assert "::: {.merksatz}" in build_sample_markdown(extended)


def test_sample_markdown_carries_the_layout_label(ifjn: LayoutDefinition):
    assert ifjn.label in build_sample_markdown(ifjn)


@pandoc_required
def test_preview_without_pdf_still_yields_a_docx(ifjn: LayoutDefinition, tmp_path: Path):
    result = render_preview(ifjn, tmp_path, to_pdf=False)
    assert result.docx.is_file()
    assert result.pdf is None
    assert result.complete is False
    assert zipfile.is_zipfile(result.docx)


@pandoc_required
def test_preview_writes_the_reference_and_filter_beside_it(
    ifjn: LayoutDefinition, tmp_path: Path
):
    render_preview(ifjn, tmp_path, to_pdf=False)
    assert (tmp_path / "reference.docx").is_file()
    assert (tmp_path / "classmap.lua").is_file()
    assert (tmp_path / "vorschau.md").is_file()


@pandoc_required
def test_preview_translates_the_table_of_contents(ifjn: LayoutDefinition, tmp_path: Path):
    """Regression: ohne ``toc-title`` stand hier "Table of Contents"."""
    result = render_preview(ifjn, tmp_path, to_pdf=False)
    document = zipfile.ZipFile(result.docx).read("word/document.xml").decode("utf-8")
    texts = [
        node.text or ""
        for node in ET.fromstring(document).iter(qn("t"))
    ]
    assert "Inhaltsverzeichnis" in texts
    assert "Table of Contents" not in texts


@pandoc_required
def test_preview_applies_the_named_styles(ifjn: LayoutDefinition, tmp_path: Path):
    """Der Lua-Filter muss die Klassen wirklich auf Formate abbilden."""
    result = render_preview(ifjn, tmp_path, to_pdf=False)
    document = zipfile.ZipFile(result.docx).read("word/document.xml").decode("utf-8")
    used = {
        node.get(qn("val"))
        for node in ET.fromstring(document).iter(qn("pStyle"))
    }
    for style_id in ifjn.classmap.values():
        assert style_id in used, f"Format {style_id} taucht im Dokument nicht auf"


@pandoc_required
def test_preview_accepts_its_own_sample(ifjn: LayoutDefinition, tmp_path: Path):
    sample = "Nur ein Satz.\n"
    result = render_preview(ifjn, tmp_path, sample_markdown=sample, to_pdf=False)
    assert result.markdown.read_text(encoding="utf-8") == sample


@pandoc_required
def test_preview_reports_a_missing_libreoffice_instead_of_failing(
    ifjn: LayoutDefinition, tmp_path: Path
):
    """Ohne LibreOffice gibt es die .docx -- und einen Hinweis, keinen Absturz."""
    result = render_preview(ifjn, tmp_path, soffice="c:/gibt/es/nicht.exe")
    assert result.pdf is None
    assert result.docx.is_file()
    assert result.complete is False
    assert "c:/gibt/es/nicht.exe" in result.note


def test_an_explicit_pandoc_path_is_binding():
    """Ein Vertipper darf nicht heimlich ein anderes Pandoc benutzen."""
    assert find_pandoc("c:/gibt/es/nicht.exe") is None


def test_an_explicit_soffice_path_is_binding():
    assert find_soffice("c:/gibt/es/nicht.exe") is None


@pandoc_required
def test_a_wrong_pandoc_path_names_itself_in_the_error(
    ifjn: LayoutDefinition, tmp_path: Path
):
    with pytest.raises(PreviewError, match="gibt/es/nicht"):
        render_preview(ifjn, tmp_path, pandoc="c:/gibt/es/nicht.exe", to_pdf=False)


@pandoc_required
@soffice_required
@pytest.mark.slow
def test_preview_produces_a_real_pdf(ifjn: LayoutDefinition, tmp_path: Path):
    result = render_preview(ifjn, tmp_path)
    assert result.complete, result.note
    assert result.pdf is not None and result.pdf.stat().st_size > 1000
    assert result.pdf.read_bytes().startswith(b"%PDF")


# ---------------------------------------------------------------------------
# Voraussetzungen
# ---------------------------------------------------------------------------


def test_requirements_name_both_programs():
    names = [r.name for r in check_requirements()]
    assert names == ["Pandoc", "LibreOffice"]


def test_pandoc_is_essential_and_libreoffice_is_not():
    by_name = {r.name: r for r in check_requirements()}
    assert by_name["Pandoc"].essential is True
    assert by_name["LibreOffice"].essential is False


def test_a_missing_pandoc_blocks_but_a_missing_libreoffice_does_not():
    """Ohne Pandoc geht nichts; ohne LibreOffice fehlt nur das Bild."""
    assert is_blocked(check_requirements(pandoc="x/nein.exe")) is True
    assert is_blocked(check_requirements(soffice="x/nein.exe")) is False


def test_summary_is_empty_when_everything_is_there():
    found = [r for r in check_requirements() if r.ok]
    if len(found) == 2:
        assert summary(check_requirements()) == ""


def test_summary_explains_the_consequence_not_just_the_name():
    text = summary(check_requirements(pandoc="x/nein.exe", soffice="x/nein.exe"))
    assert "Pandoc fehlt." in text
    assert "LibreOffice fehlt." in text
    # Der Name allein hilft niemandem -- die Folge muss dastehen.
    assert "Vorschau" in text
    assert "Quarto" in text


def test_missing_lists_the_essential_one_first():
    gaps = missing(check_requirements(pandoc="x/nein.exe", soffice="x/nein.exe"))
    assert [r.name for r in gaps] == ["Pandoc", "LibreOffice"]


def test_missing_is_empty_when_nothing_is_missing():
    assert missing([r for r in check_requirements() if r.ok]) == []


# ---------------------------------------------------------------------------
# Herkunft der Absatzformate
# ---------------------------------------------------------------------------


def test_styles_used_by_the_classmap_count_as_content(ifjn: LayoutDefinition):
    by_style = origins(ifjn)
    for style_id in ifjn.classmap.values():
        assert by_style[style_id] is StyleOrigin.CONTENT


def test_pandoc_styles_count_as_standard(ifjn: LayoutDefinition):
    assert origin_of("BodyText", ifjn) is StyleOrigin.STANDARD
    assert origin_of("Heading1", ifjn) is StyleOrigin.STANDARD
    assert origin_of("Title", ifjn) is StyleOrigin.STANDARD


def test_word_builtins_count_as_standard_too(ifjn: LayoutDefinition):
    """Footer und die IVZ-Ebenen stehen nicht in Pandocs Basisvorlage."""
    assert "Footer" not in PANDOC_STYLE_IDS
    assert "TOC1" not in PANDOC_STYLE_IDS
    assert origin_of("Footer", ifjn) is StyleOrigin.STANDARD
    assert origin_of("TOC1", ifjn) is StyleOrigin.STANDARD


def test_an_own_style_without_a_class_is_flagged_as_unused(ifjn: LayoutDefinition):
    """Der eigentliche Gewinn: ein Format, auf das nichts zeigt."""
    extended = ifjn.with_style(ParagraphStyle(style_id="Merksatz", name="Merksatz"))
    assert origin_of("Merksatz", extended) is StyleOrigin.UNUSED


def test_a_mapped_class_turns_a_standard_style_into_a_content_style(
    ifjn: LayoutDefinition,
):
    """Wer BodyText an eine eigene Klasse haengt, macht es zu seinem Format."""
    from dataclasses import replace

    hooked = replace(ifjn, classmap={**ifjn.classmap, "flies": "BodyText"})
    assert origin_of("BodyText", hooked) is StyleOrigin.CONTENT


def test_every_style_gets_exactly_one_origin(ifjn: LayoutDefinition):
    by_style = origins(ifjn)
    assert set(by_style) == set(ifjn.styles)
    assert sum(counts(ifjn).values()) == len(ifjn.styles)


def test_is_standard_does_not_depend_on_a_definition():
    assert is_standard("BodyText") is True
    assert is_standard("Footer") is True
    assert is_standard("Prompt-Frage") is False


def test_ifjn_splits_into_four_own_and_the_rest_inherited(ifjn: LayoutDefinition):
    tally = counts(ifjn)
    assert tally[StyleOrigin.CONTENT] == 4
    assert tally[StyleOrigin.UNUSED] == 0
    assert tally[StyleOrigin.STANDARD] == len(ifjn.styles) - 4


# ---------------------------------------------------------------------------
# Unterprozesse ohne Konsolenfenster
# ---------------------------------------------------------------------------


def test_run_hidden_suppresses_the_console_window():
    """Regression: beim Oeffnen blitzten Terminalfenster auf."""
    from unittest import mock

    with mock.patch("tools.doclayout.process.subprocess.run") as fake:
        run_hidden(["irgendwas"], capture_output=True)
    assert fake.call_args.kwargs["creationflags"] & NO_WINDOW == NO_WINDOW


def test_run_hidden_adds_to_existing_flags_instead_of_replacing_them():
    """Ein Aufrufer, der eigene Flags mitgibt, darf sie nicht verlieren."""
    import subprocess as sp
    from unittest import mock

    own = getattr(sp, "CREATE_NEW_PROCESS_GROUP", 0x200)
    with mock.patch("tools.doclayout.process.subprocess.run") as fake:
        run_hidden(["irgendwas"], creationflags=own)
    flags = fake.call_args.kwargs["creationflags"]
    assert flags & own == own
    assert flags & NO_WINDOW == NO_WINDOW


def test_no_module_starts_a_process_without_the_helper():
    """Jeder neue subprocess-Aufruf muss ueber run_hidden laufen."""
    import re

    package = Path(__file__).resolve().parent.parent / "tools" / "doclayout"
    # ``_uno_worker.py`` ist die eine Ausnahme, und sie ist erzwungen: Der
    # Vorgang laeuft mit dem Python von LibreOffice und kann ``run_hidden``
    # deshalb gar nicht importieren. Er traegt die Regel stattdessen selbst --
    # nachgeprueft im Test darunter.
    ausnahmen = {"process.py", "_uno_worker.py"}
    offenders = []
    for source in package.rglob("*.py"):
        if source.name in ausnahmen:
            continue
        text = source.read_text(encoding="utf-8")
        if re.search(r"subprocess\.(run|Popen|call|check_output|check_call)\(", text):
            offenders.append(source.name)
    assert offenders == [], f"Prozessstart ohne run_hidden: {offenders}"


def test_the_uno_worker_hides_its_window_on_its_own():
    """Die Ausnahme darf nicht zum Schlupfloch werden.

    Der Vorgang startet LibreOffice selbst. Ohne ``CREATE_NO_WINDOW`` blitzte
    bei jeder Vorschau ein schwarzes Fenster auf -- genau das, wogegen
    ``run_hidden`` ueberhaupt gebaut wurde.
    """
    worker = (
        Path(__file__).resolve().parent.parent
        / "tools" / "doclayout" / "_uno_worker.py"
    )
    text = worker.read_text(encoding="utf-8")
    assert "CREATE_NO_WINDOW" in text
    assert "creationflags=NO_WINDOW" in text



# ---------------------------------------------------------------------------
# Rueckfallebene
# ---------------------------------------------------------------------------


def test_the_reference_layout_exists():
    """``IFJN_Referenz`` ist der Stand, auf den man immer zurueck kann."""
    assert "IFJN_Referenz" in {p.stem for p in available_layouts()}


def test_the_reference_layout_is_buildable():
    assert load_layout("IFJN_Referenz").validate() == []


def test_the_reference_layout_carries_every_pandoc_style():
    """Fehlt eines, waere die Rueckfallebene keine mehr.

    Die Liste stammt aus Pandocs Basisvorlage; wer im Referenz-Layout etwas
    loescht, soll das hier erfahren und nicht erst an einer .docx, in der ein
    Bildtitel oder ein Literaturverzeichnis unformatiert bleibt.
    """
    from tools.doclayout.origins import PANDOC_STYLE_IDS

    vorhanden = set(load_layout("IFJN_Referenz").styles)
    fehlend = sorted(PANDOC_STYLE_IDS - vorhanden)
    assert fehlend == [], f"im Referenz-Layout fehlen: {fehlend}"


def test_the_reference_layout_carries_the_word_builtins():
    """Fusszeile und Verzeichnisebenen schreibt doclayout selbst."""
    vorhanden = set(load_layout("IFJN_Referenz").styles)
    for style_id in ("Footer", "TOC1", "TOC2", "TOC3", "TOCHeading"):
        assert style_id in vorhanden, f"{style_id} fehlt im Referenz-Layout"


def test_the_reference_layout_keeps_the_content_styles():
    """Ohne sie waere es eine Vorlage fuer irgendein Buch, nicht fuer deines."""
    definition = load_layout("IFJN_Referenz")
    assert set(definition.classmap) >= {"prompt", "prompt-separator"}
    for style_id in definition.classmap.values():
        assert style_id in definition.styles


# ---------------------------------------------------------------------------
# Was «geerbt» bedeutet
# ---------------------------------------------------------------------------


def test_a_style_without_a_size_inherits_the_base_size(ifjn: LayoutDefinition):
    """«geerbt» allein ist eine Auskunft, die nichts sagt."""
    from dataclasses import replace as _replace

    d = _replace(
        ifjn,
        styles={**ifjn.styles, "Ohne": ParagraphStyle(style_id="Ohne")},
    )
    assert d.styles["Ohne"].size_pt is None
    assert d.resolve_size_pt("Ohne") == d.typography.base_size_pt
    assert d.size_origin("Ohne") is None


def test_a_size_is_inherited_through_the_chain(ifjn: LayoutDefinition):
    from dataclasses import replace as _replace

    d = _replace(
        ifjn,
        styles={
            **ifjn.styles,
            "Gross": ParagraphStyle(style_id="Gross", size_pt=22.0),
            "Erbe": ParagraphStyle(style_id="Erbe", based_on="Gross"),
            "Enkel": ParagraphStyle(style_id="Enkel", based_on="Erbe"),
        },
    )
    assert d.resolve_size_pt("Enkel") == 22.0
    assert d.size_origin("Enkel") == "Gross"


def test_an_own_size_wins_over_the_inherited_one(ifjn: LayoutDefinition):
    from dataclasses import replace as _replace

    d = _replace(
        ifjn,
        styles={
            **ifjn.styles,
            "Gross": ParagraphStyle(style_id="Gross", size_pt=22.0),
            "Eigen": ParagraphStyle(style_id="Eigen", based_on="Gross", size_pt=9.0),
        },
    )
    assert d.resolve_size_pt("Eigen") == 9.0
    assert d.size_origin("Eigen") == "Eigen"


def test_a_circular_inheritance_does_not_hang(ifjn: LayoutDefinition):
    """Eine kaputte Definition darf die Oberflaeche nicht einfrieren."""
    from dataclasses import replace as _replace

    d = _replace(
        ifjn,
        styles={
            **ifjn.styles,
            "A": ParagraphStyle(style_id="A", based_on="B"),
            "B": ParagraphStyle(style_id="B", based_on="A"),
        },
    )
    assert d.resolve_size_pt("A") == d.typography.base_size_pt
    assert d.size_origin("A") is None


def test_an_unknown_style_falls_back_to_the_base_size(ifjn: LayoutDefinition):
    assert ifjn.resolve_size_pt("GibtsNicht") == ifjn.typography.base_size_pt


# ---------------------------------------------------------------------------
# Welche Grundlage ein Format haben darf
# ---------------------------------------------------------------------------


def test_inheritance_is_followed_across_steps(ifjn: LayoutDefinition):
    from dataclasses import replace as _replace

    d = _replace(
        ifjn,
        styles={
            **ifjn.styles,
            "Opa": ParagraphStyle(style_id="Opa"),
            "Vater": ParagraphStyle(style_id="Vater", based_on="Opa"),
            "Kind": ParagraphStyle(style_id="Kind", based_on="Vater"),
        },
    )
    assert d.inherits_from("Kind", "Opa") is True
    assert d.inherits_from("Opa", "Kind") is False


def test_a_style_is_never_its_own_base(ifjn: LayoutDefinition):
    assert "BodyText" not in ifjn.possible_bases("BodyText")


def test_its_own_descendants_are_not_offered(ifjn: LayoutDefinition):
    """Regression: »BodyText basiert auf Fachtext« ergab einen Ringschluss.

    ``Fachtext`` baut selbst auf ``BodyText`` auf. Die Auswahl bot es
    trotzdem an, und der Kreis fiel erst hinterher als Warnung auf.
    """
    assert ifjn.styles["Fachtext"].based_on == "BodyText"
    assert "Fachtext" not in ifjn.possible_bases("BodyText")


def test_an_unrelated_style_stays_available(ifjn: LayoutDefinition):
    """Nur die Nachkommen fallen weg, nicht die halbe Bibliothek.

    Die Formate stellt der Test sich selbst: Das Layout aus der Bibliothek
    gehoert dem Benutzer und darf jederzeit anders aussehen.
    """
    from dataclasses import replace as _replace

    d = _replace(
        ifjn,
        styles={
            "Basis": ParagraphStyle(style_id="Basis"),
            "Kind": ParagraphStyle(style_id="Kind", based_on="Basis"),
            "Fremd": ParagraphStyle(style_id="Fremd"),
        },
        classmap={},
    )
    moeglich = d.possible_bases("Fremd")
    assert "Basis" in moeglich
    assert "Kind" in moeglich
    assert d.possible_bases("Basis") == ["Fremd"]


def test_no_offered_base_creates_a_cycle(ifjn: LayoutDefinition):
    """Die eigentliche Zusicherung: Was angeboten wird, ist unbedenklich."""
    from dataclasses import replace as _replace

    for style_id in sorted(ifjn.styles):
        for basis in ifjn.possible_bases(style_id):
            geaendert = _replace(
                ifjn,
                styles={
                    **ifjn.styles,
                    style_id: _replace(ifjn.styles[style_id], based_on=basis),
                },
            )
            zyklen = [p for p in geaendert.validate() if "zyklisch" in p]
            assert zyklen == [], f"{style_id} auf {basis} ergibt {zyklen}"


def test_an_existing_cycle_does_not_hang(ifjn: LayoutDefinition):
    """Eine schon kaputte Definition darf die Auswahl nicht einfrieren."""
    from dataclasses import replace as _replace

    d = _replace(
        ifjn,
        styles={
            **ifjn.styles,
            "A": ParagraphStyle(style_id="A", based_on="B"),
            "B": ParagraphStyle(style_id="B", based_on="A"),
        },
    )
    assert d.inherits_from("A", "GibtsNicht") is False
    assert isinstance(d.possible_bases("A"), list)


# ---------------------------------------------------------------------------
# Tabellensatz: der schmale Satzspiegel
# ---------------------------------------------------------------------------
#
# In einem 135-mm-Band bleiben fuer eine fuenfspaltige Tabelle rund 20 mm je
# Spalte. Im Grundgrad brach dort jede Telefonnummer um, und "Besonderheit"
# fiel senkrecht auseinander -- die Klinikliste des Reisefuehrers belegte drei
# Seiten statt einer. Der Schriftgrad muss deshalb getrennt einstellbar sein.


def test_the_table_size_is_optional():
    """Ohne Angabe bleibt alles wie bisher -- kein stiller Eingriff."""
    from tools.doclayout.schema import Typography

    assert Typography.from_dict({}).table_size_pt is None
    assert "table_size_pt" not in Typography.from_dict({}).to_dict()


def test_the_table_size_survives_a_round_trip():
    from tools.doclayout.schema import Typography

    typography = Typography.from_dict({"table_size_pt": 8.5})
    assert typography.table_size_pt == 8.5
    assert Typography.from_dict(typography.to_dict()).table_size_pt == 8.5


def test_an_absurd_table_size_is_rejected():
    from tools.doclayout.schema import Typography

    with pytest.raises(LayoutError, match="table_size_pt"):
        Typography.from_dict({"table_size_pt": 200})


@pandoc_required
def test_the_table_size_lands_in_the_table_style(tmp_path: Path, ifjn: LayoutDefinition):
    """Es muss die Tabellen-Formatvorlage sein, nicht ein Absatzformat.

    Pandoc legt Tabellenzellen **und** enggesetzte Aufzaehlungen in dasselbe
    ``Compact``. Wer dort den Grad senkt, schrumpft jede Liste des Buches mit.
    """
    from dataclasses import replace as _replace

    definition = _replace(
        ifjn, typography=_replace(ifjn.typography, table_size_pt=8.5)
    )
    ziel = build_reference_docx(definition, tmp_path / "ref.docx")
    styles = ET.fromstring(zipfile.ZipFile(ziel).read("word/styles.xml"))
    tabelle = next(
        s for s in styles.findall(qn("style")) if s.get(qn("styleId")) == "Table"
    )
    groessen = [
        c.get(qn("val"))
        for c in tabelle.find(qn("rPr"))
        if local_name(c.tag) in ("sz", "szCs")
    ]
    assert groessen == ["17", "17"], "8,5 pt sind 17 Halbpunkte"

    compact = next(
        (s for s in styles.findall(qn("style")) if s.get(qn("styleId")) == "Compact"),
        None,
    )
    if compact is not None and compact.find(qn("rPr")) is not None:
        assert not [
            c for c in compact.find(qn("rPr")) if local_name(c.tag) == "sz"
        ], "Compact darf keinen eigenen Grad bekommen -- sonst schrumpfen die Listen"


@pandoc_required
def test_the_table_style_keeps_its_schema_order(tmp_path: Path, ifjn: LayoutDefinition):
    """``w:rPr`` gehoert laut CT_Style vor ``w:tblPr``.

    Steht es dahinter, oeffnet Word die Vorlage ohne Formate -- derselbe
    Fehlermodus, der die Absatzeigenschaften schon einmal gekostet hat.
    """
    from dataclasses import replace as _replace

    definition = _replace(
        ifjn, typography=_replace(ifjn.typography, table_size_pt=9.0)
    )
    ziel = build_reference_docx(definition, tmp_path / "ref.docx")
    styles = ET.fromstring(zipfile.ZipFile(ziel).read("word/styles.xml"))
    tabelle = next(
        s for s in styles.findall(qn("style")) if s.get(qn("styleId")) == "Table"
    )
    namen = [local_name(c.tag) for c in tabelle]
    assert namen.index("rPr") < namen.index("tblPr")


@pandoc_required
def test_without_the_setting_the_table_style_stays_untouched(
    tmp_path: Path, ifjn: LayoutDefinition
):
    ziel = build_reference_docx(ifjn, tmp_path / "ref.docx")
    styles = ET.fromstring(zipfile.ZipFile(ziel).read("word/styles.xml"))
    tabelle = next(
        s for s in styles.findall(qn("style")) if s.get(qn("styleId")) == "Table"
    )
    assert tabelle.find(qn("rPr")) is None
