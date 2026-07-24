"""Tests für tools.generated_books.discovery."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tools.generated_books.discovery import (
    GeneratedPdf,
    delete_generated_pdf,
    find_generated_pdfs,
    load_settings,
    sort_generated_pdfs,
)


def _make_book_with_pdf(root: Path, name: str, pdf_name: str = "book.pdf") -> Path:
    book = root / name
    (book / "export" / "_book").mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (book / "export" / "_book" / pdf_name).write_bytes(b"%PDF-1.4\n")
    return book


def test_find_generated_pdfs_sorts_newest_first(tmp_path: Path):
    older = _make_book_with_pdf(tmp_path, "Band_Old", "old.pdf")
    newer = _make_book_with_pdf(tmp_path, "Band_New", "new.pdf")
    # mtime: newer file younger
    import os
    import time

    old_pdf = older / "export" / "_book" / "old.pdf"
    new_pdf = newer / "export" / "_book" / "new.pdf"
    now = time.time()
    os.utime(old_pdf, (now - 100, now - 100))
    os.utime(new_pdf, (now, now))

    found = find_generated_pdfs([older, newer], max_entries=10)
    assert [f.path.name for f in found] == ["new.pdf", "old.pdf"]


def test_find_generated_pdfs_includes_profile_export_dirs(tmp_path: Path):
    book = tmp_path / "Band_A"
    (book / "export" / "_book_draft").mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    pdf = book / "export" / "_book_draft" / "Band_A.pdf"
    pdf.write_bytes(b"%PDF")

    found = find_generated_pdfs([book], max_entries=5)
    assert len(found) == 1
    assert found[0].path == pdf


def test_find_generated_pdfs_respects_max_entries(tmp_path: Path):
    books = [_make_book_with_pdf(tmp_path, f"B{i}", f"{i}.pdf") for i in range(5)]
    found = find_generated_pdfs(books, max_entries=2)
    assert len(found) == 2


def test_find_generated_pdfs_includes_publish_renders_archive_dirs(tmp_path: Path):
    """Dauerhaft archivierte Renders (siehe tools.publish_map.store.
    snapshot_render_dir) müssen auch ohne intakte publish_map.json per
    Disk-Scan wiedergefunden werden können."""
    book = tmp_path / "Band_A"
    snapshot_dir = book / "export" / "publish_renders" / "snap-123"
    snapshot_dir.mkdir(parents=True)
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    pdf = snapshot_dir / "Buch_20260721_234150.pdf"
    pdf.write_bytes(b"%PDF")

    found = find_generated_pdfs([book], max_entries=5)
    assert len(found) == 1
    assert found[0].path == pdf


def test_load_settings_defaults_and_file(tmp_path: Path):
    cfg = tmp_path / "config.json"
    cfg.write_text(
        '{"display": {"max_entries": 7}, "scan": {"recent_only": false}}',
        encoding="utf-8",
    )
    settings = load_settings(cfg)
    assert settings["max_entries"] == 7
    assert settings["recent_only"] is False


def test_generated_pdf_display_fields(tmp_path: Path):
    book = _make_book_with_pdf(tmp_path, "Band_A", "out.pdf")
    pdf = book / "export" / "_book" / "out.pdf"
    import os
    import time

    now = time.time()
    os.utime(pdf, (now, now))
    entry = find_generated_pdfs([book], max_entries=1)[0]
    assert entry.display_name == "out.pdf · Band_A"
    assert entry.date_str == entry.date_str  # format smoke
    assert "out.pdf" in entry.label


def test_sort_generated_pdfs_by_name_and_date(tmp_path: Path):
    a = GeneratedPdf(Path("a.pdf"), "B1", tmp_path / "B1", 100.0)
    b = GeneratedPdf(Path("b.pdf"), "B2", tmp_path / "B2", 200.0)
    by_name = sort_generated_pdfs([b, a], "name", reverse=False)
    assert [x.path.name for x in by_name] == ["a.pdf", "b.pdf"]
    by_date = sort_generated_pdfs([a, b], "date", reverse=True)
    assert [x.path.name for x in by_date] == ["b.pdf", "a.pdf"]


def test_delete_generated_pdf(tmp_path: Path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF")
    delete_generated_pdf(pdf)
    assert not pdf.exists()


def test_delete_generated_pdf_rejects_non_pdf(tmp_path: Path):
    txt = tmp_path / "notes.txt"
    txt.write_text("x", encoding="utf-8")
    try:
        delete_generated_pdf(txt)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
