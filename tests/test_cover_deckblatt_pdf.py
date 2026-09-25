"""Tests: Innenwerk-PDF + Cover-Deckblatt Bundle."""

from __future__ import annotations


import pytest


def test_build_interior_with_cover_deckblatt(tmp_path, monkeypatch):
    pytest.importorskip("fitz")

    import fitz

    from services.cover_deckblatt_pdf import build_interior_with_cover_deckblatt
    from tools.distribution.book_store import set_kdp_paperback
    from tools.kdp_cover.model import CoverLayout, default_project_path

    book = tmp_path / "Band"
    book.mkdir()
    set_kdp_paperback(book, True)
    layout = CoverLayout(
        page_count=100,
        paper_type_id="white_bw",
        trim_width_mm=135.0,
        trim_height_mm=215.0,
        title="T",
        author="A",
        front_color="#123456",
    )
    cover_json = default_project_path(book)
    cover_json.parent.mkdir(parents=True, exist_ok=True)
    cover_json.write_text(
        __import__("json").dumps(layout.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Mini-Innenwerk-PDF
    interior = book / "export" / "_book" / "innen.pdf"
    interior.parent.mkdir(parents=True)
    doc = fitz.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((40, 80), "Innenwerk")
    doc.save(interior)
    doc.close()

    logs: list[tuple[str, str]] = []
    out = build_interior_with_cover_deckblatt(
        book, interior, log=lambda m, lv="info": logs.append((lv, m))
    )
    assert out is not None
    assert out.name.endswith("_mit_Deckblatt.pdf")
    assert out.is_file()
    with fitz.open(out) as merged:
        assert merged.page_count == 2
    assert any("Deckblatt" in m for _, m in logs)


def test_export_dialog_shows_format_warn_for_typst(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    import ui_qt.dialogs.export_dialog as E

    app = QApplication.instance() or QApplication([])
    book = tmp_path / "Band"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    dlg = E.ExportDialog(None, ["Standard"], initial={"format": "typst"}, book_path=book)
    try:
        assert dlg.format_warn.isVisibleTo(dlg) is True
        assert "ACHTUNG" in dlg.format_warn.text()
        dlg.format_combo.setCurrentText("docx")
        dlg._sync_format_rows()
        assert dlg.format_warn.isVisibleTo(dlg) is False
    finally:
        dlg.close()
        app.processEvents()
