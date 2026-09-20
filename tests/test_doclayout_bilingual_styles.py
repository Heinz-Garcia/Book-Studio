"""Style language (DE/ES) and callout classmap fallback."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from tools.doclayout.apply import apply_layout
from tools.doclayout.classmap import write_lua_filter
from tools.doclayout.library import load_layout
from tools.doclayout.schema import LayoutDefinition, Page, PageMargin, ParagraphStyle, Typography


def test_paragraph_style_language_roundtrip() -> None:
    style = ParagraphStyle(style_id="Spanisch", language="es-ES", align="left")
    assert style.to_dict()["language"] == "es-ES"
    back = ParagraphStyle.from_dict("Spanisch", style.to_dict())
    assert back.language == "es-ES"


def test_reference_docx_writes_style_language(tmp_path: Path) -> None:
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nformat:\n  docx: {}\n",
        encoding="utf-8",
    )
    definition = LayoutDefinition(
        name="Solo",
        page=Page(width_mm=135.0, height_mm=215.0, margin=PageMargin(20, 20, 20, 16)),
        typography=Typography(body_font="Cambria", base_size_pt=11.0, language="de-DE"),
        styles={
            "BodyText": ParagraphStyle(
                style_id="BodyText", name="Fließtext", align="justify", language="de-DE"
            ),
            "Spanisch": ParagraphStyle(
                style_id="Spanisch", name="Spanisch", align="left", language="es-ES"
            ),
        },
    )
    result = apply_layout(definition, book)
    with ZipFile(result.reference_docx) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    idx = styles.find('styleId="Spanisch"')
    assert idx >= 0
    chunk = styles[idx : idx + 1800]
    assert 'w:val="es-ES"' in chunk or 'w:val="es-ES"' in chunk.replace(" ", "")


def test_classmap_lua_has_callout_fallback(tmp_path: Path) -> None:
    definition = load_layout("Reisefuehrer_Andalusien")
    path = write_lua_filter(definition, tmp_path / "classmap.lua")
    text = path.read_text(encoding="utf-8")
    assert '["spanisch"]' in text or '["spanisch"] =' in text.replace(" ", "")
    assert "callout" in text
    assert 'string.sub(name, 1, 7) == "callout"' in text


def test_reisefuehrer_maps_spanisch_and_callouts() -> None:
    definition = load_layout("Reisefuehrer_Andalusien")
    assert definition.classmap.get("spanisch") == "Spanisch"
    assert definition.classmap.get("key-takeaway") == "KeyTakeaway"
    assert definition.classmap.get("callout-tip") == "Callout"
    assert "Spanisch" in definition.styles
    assert definition.styles["Spanisch"].language == "es-ES"
    assert definition.styles["Spanisch"].align == "left"
    assert definition.styles["Prompt-Frage"].align == "left"
    assert definition.styles["BodyText"].align == "justify"
