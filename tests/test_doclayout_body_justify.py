"""apply_layout setzt BodyText-Blocksatz, wenn Ausrichtung fehlt."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from tools.doclayout.apply import apply_layout
from tools.doclayout.schema import LayoutDefinition, Page, PageMargin, ParagraphStyle, Typography


def test_apply_layout_fills_bodytext_justify(tmp_path: Path) -> None:
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nformat:\n  docx: {}\n",
        encoding="utf-8",
    )
    definition = LayoutDefinition(
        name="Solo",
        page=Page(
            width_mm=135.0,
            height_mm=215.0,
            margin=PageMargin(20, 20, 20, 16),
        ),
        typography=Typography(body_font="Cambria", base_size_pt=11.0),
        styles={
            "BodyText": ParagraphStyle(
                style_id="BodyText",
                name="Fließtext",
                # absichtlich ohne align
            ),
        },
    )
    result = apply_layout(definition, book)
    assert result.reference_docx.is_file()
    with ZipFile(result.reference_docx) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    idx = styles.find('styleId="BodyText"')
    assert idx >= 0
    chunk = styles[idx : idx + 1500]
    assert 'w:val="both"' in chunk  # OOXML: justify == both
