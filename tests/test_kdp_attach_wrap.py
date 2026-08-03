"""Tests: Wrap-PDF am Buch hinterlegen (kein Quarto-Kapitel)."""

from __future__ import annotations

from pathlib import Path

from tools.kdp_cover.attach_wrap import attach_wrap_pdf_to_book, wrap_pdf_relpath
from tools.kdp_cover.model import CoverLayout, default_wrap_pdf_path, load_layout, save_layout


def test_attach_wrap_pdf_copies_to_canonical(tmp_path: Path) -> None:
    book = tmp_path / "Mein_Buch"
    book.mkdir()
    src = tmp_path / "elsewhere" / "custom.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF-1.4 fake")

    dest = attach_wrap_pdf_to_book(book, src)
    assert dest == default_wrap_pdf_path(book)
    assert dest.is_file()
    assert dest.read_bytes() == src.read_bytes()
    assert wrap_pdf_relpath(book, dest) == f"export/kdp_cover/{book.name}_kdp_wrap.pdf"


def test_attach_wrap_pdf_idempotent_same_path(tmp_path: Path) -> None:
    book = tmp_path / "Buch"
    book.mkdir()
    dest = default_wrap_pdf_path(book)
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"%PDF-1.4 already")
    out = attach_wrap_pdf_to_book(book, dest)
    assert out == dest
    assert out.read_bytes() == b"%PDF-1.4 already"


def test_wrap_pdf_roundtrip_in_layout(tmp_path: Path) -> None:
    layout = CoverLayout(
        page_count=100,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        wrap_pdf="export/kdp_cover/Buch_kdp_wrap.pdf",
    )
    path = tmp_path / "cover.json"
    save_layout(layout, path)
    loaded = load_layout(path)
    assert loaded.wrap_pdf == "export/kdp_cover/Buch_kdp_wrap.pdf"
    plain = CoverLayout(
        page_count=100,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
    )
    assert "wrap_pdf" not in plain.to_dict()
