"""Tests für die lesernahe Markdown-Vorschau."""

from __future__ import annotations

from pathlib import Path

from ui_qt.markdown_preview import (
    body_for_preview,
    markdown_to_preview_html,
    strip_inline_markdown,
)


def test_strip_inline_markdown():
    assert strip_inline_markdown("**fett** und *kursiv*") == "fett und kursiv"
    assert "🖼" in strip_inline_markdown("![Alt](a.png)")


def test_body_strips_frontmatter():
    md = (
        '---\n'
        'title: "Klappentext (hinten)"\n'
        'description: "Klappentext (hinten)"\n'
        "status: bookstudio\n"
        'order: "END-20"\n'
        "---\n\n"
        "# Klappentext\n\n"
        "Inhalt hier.\n"
    )
    body = body_for_preview(md)
    assert "status: bookstudio" not in body
    assert "order:" not in body
    assert "# Klappentext" in body


def test_preview_hides_frontmatter_and_pagebreak_code():
    md = (
        '---\n'
        'title: "Klappentext (hinten)"\n'
        "status: bookstudio\n"
        "---\n\n"
        "# Klappentext\n\n"
        "Text.\n\n"
        "```{=typst}\n"
        "#pagebreak()\n"
        "```\n"
    )
    html_doc = markdown_to_preview_html(md)
    assert "status: bookstudio" not in html_doc
    assert "order:" not in html_doc
    assert "#pagebreak()" not in html_doc
    assert "```" not in html_doc
    assert "Seitenumbruch" in html_doc
    assert "Klappentext" in html_doc


def test_preview_html_headings_and_lists():
    md = "# Titel\n\n- Punkt\n\n> Zitat\n\n```\ncode\n```\n"
    html_doc = markdown_to_preview_html(md)
    assert "Titel" in html_doc
    assert "• Punkt" in html_doc
    assert "▌ Zitat" in html_doc
    assert "<pre" in html_doc
    assert "code" in html_doc


def test_preview_renders_local_image(tmp_path: Path) -> None:
    book = tmp_path / "book"
    img_dir = book / "img"
    img_dir.mkdir(parents=True)
    image = img_dir / "cover.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    md_path = book / "content" / "page.md"
    md_path.parent.mkdir(parents=True)

    html_doc = markdown_to_preview_html(
        "![Deckblatt](/img/cover.png)\n",
        book_root=book,
        markdown_file=md_path,
    )
    assert "<img" in html_doc
    assert image.resolve().as_uri() in html_doc
    assert "🖼" not in html_doc


def test_preview_renders_typst_cover_image(tmp_path: Path) -> None:
    book = tmp_path / "book"
    img_dir = book / "img"
    img_dir.mkdir(parents=True)
    image = img_dir / "Deckblatt_IFJN_Brustkrebs.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    md_path = book / "content" / "Deckblatt.md"
    md_path.parent.mkdir(parents=True)
    md = (
        "```{=typst}\n"
        "#page(margin: 0pt)[\n"
        '  #image("/img/Deckblatt_IFJN_Brustkrebs.png", width: 100%, height: 100%, fit: "cover")\n'
        "]\n"
        "#past-cover.update(true)\n"
        "```\n"
    )

    html_doc = markdown_to_preview_html(md, book_root=book, markdown_file=md_path)
    assert "<img" in html_doc
    assert image.resolve().as_uri() in html_doc
    assert "object-fit:cover" in html_doc
    assert "aspect-ratio:148 / 210" in html_doc
    assert "Vollseiten-Vorschau" in html_doc
    assert "print_title" in html_doc
    assert "Layout-Block" not in html_doc


def test_preview_typst_image_without_cover_uses_normal_frame(tmp_path: Path) -> None:
    book = tmp_path / "book"
    img_dir = book / "img"
    img_dir.mkdir(parents=True)
    image = img_dir / "diagram.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    md_path = book / "content" / "page.md"
    md_path.parent.mkdir(parents=True)
    md = (
        "```{=typst}\n"
        '#image("/img/diagram.png", width: 80%)\n'
        "```\n"
    )

    html_doc = markdown_to_preview_html(md, book_root=book, markdown_file=md_path)
    assert "<img" in html_doc
    assert "object-fit:cover" not in html_doc
    assert "Vollseiten-Vorschau" not in html_doc
