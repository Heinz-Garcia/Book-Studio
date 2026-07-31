"""Tests für Bild-Einfügen im Markdown-Editor."""

from __future__ import annotations

from pathlib import Path

from markdown_asset_scanner import resolve_local_image_file
from ui_qt.editor_image import (
    build_image_markdown_snippet,
    build_image_typst_snippet,
    convert_markdown_images_to_typst,
    import_image_for_markdown,
    infer_book_root_from_markdown,
    markdown_ref_for_existing_book_image,
)


def test_infer_book_root_from_markdown(tmp_path: Path) -> None:
    book = tmp_path / "MyBook"
    content = book / "content"
    content.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    md = content / "Kapitel.md"
    md.write_text("# Test\n", encoding="utf-8")
    assert infer_book_root_from_markdown(md) == book.resolve()


def test_import_image_copies_external_file(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    external = tmp_path / "photo.png"
    external.write_bytes(b"\x89PNG\r\n\x1a\n")

    markdown_ref, dest = import_image_for_markdown(external, book)
    assert markdown_ref == "/img/photo.png"
    assert dest == book / "img" / "photo.png"
    assert dest.is_file()


def test_import_image_reuses_existing_book_file(tmp_path: Path) -> None:
    book = tmp_path / "book"
    img_dir = book / "img"
    img_dir.mkdir(parents=True)
    existing = img_dir / "logo.png"
    existing.write_bytes(b"png")

    markdown_ref, dest = import_image_for_markdown(existing, book)
    assert markdown_ref == "/img/logo.png"
    assert dest.resolve() == existing.resolve()


def test_import_image_unique_name_on_collision(tmp_path: Path) -> None:
    book = tmp_path / "book"
    img_dir = book / "img"
    img_dir.mkdir(parents=True)
    (img_dir / "shot.png").write_bytes(b"old")

    external = tmp_path / "shot.png"
    external.write_bytes(b"new")

    markdown_ref, dest = import_image_for_markdown(external, book)
    assert markdown_ref == "/img/shot_1.png"
    assert dest.name == "shot_1.png"
    assert dest.read_bytes() == b"new"


def test_build_image_markdown_snippet_uses_stem_when_alt_empty() -> None:
    assert build_image_markdown_snippet("", "/img/Deckblatt.png") == "![Deckblatt](/img/Deckblatt.png)"


def test_convert_markdown_images_to_typst() -> None:
    assert (
        convert_markdown_images_to_typst("![DSC](/img/DSC_3595.jpg)")
        == '#image("/img/DSC_3595.jpg", width: 80%)'
    )


def test_normalize_typst_width() -> None:
    from ui_qt.editor_image import normalize_typst_width

    assert normalize_typst_width(80) == "80%"
    assert normalize_typst_width("100") == "100%"
    assert normalize_typst_width("50%") == "50%"
    assert normalize_typst_width(0) == "1%"
    assert normalize_typst_width(150) == "100%"


def test_build_image_typst_snippet_centered() -> None:
    snip = build_image_typst_snippet("/img/DSC_3595.jpg")
    assert "```{=typst}" in snip
    assert '#image("/img/DSC_3595.jpg", width: 80%)' in snip
    assert "center + horizon" in snip


def test_resolve_local_image_file_root_relative(tmp_path: Path) -> None:
    book = tmp_path / "book"
    img_dir = book / "img"
    img_dir.mkdir(parents=True)
    image = img_dir / "foo.png"
    image.write_bytes(b"x")
    md = book / "content" / "chapter.md"
    md.parent.mkdir(parents=True)
    md.write_text("![x](/img/foo.png)\n", encoding="utf-8")

    resolved = resolve_local_image_file("/img/foo.png", md, book)
    assert resolved == image


def test_markdown_ref_for_existing_book_image(tmp_path: Path) -> None:
    book = tmp_path / "book"
    image = book / "img" / "a.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"j")
    assert markdown_ref_for_existing_book_image(image, book) == "/img/a.jpg"
