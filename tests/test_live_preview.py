"""Tests für tools.live_preview.preview_render."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from tools.live_preview.preview_render import (
    find_book_root,
    is_aggregator_content,
    newest_output_pdf,
    render_preview,
    render_single_chapter_preview,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_FIXTURE = PROJECT_ROOT / "Band_Dummy"


def test_find_book_root_from_nested_file(tmp_path):
    book = tmp_path / "Band_Test"
    (book / "content").mkdir(parents=True)
    (book / "_quarto.yml").write_text("book:\n  title: X\n", encoding="utf-8")
    md_file = book / "content" / "Kapitel.md"
    md_file.write_text("# Kapitel\n", encoding="utf-8")

    assert find_book_root(md_file) == book


def test_find_book_root_returns_none_without_quarto_yml(tmp_path):
    md_file = tmp_path / "lonely.md"
    md_file.write_text("# X\n", encoding="utf-8")

    assert find_book_root(md_file) is None


def test_newest_output_pdf_picks_latest_mtime(tmp_path):
    book = tmp_path / "Band_Test"
    out_dir = book / "export" / "_book"
    out_dir.mkdir(parents=True)
    (book / "_quarto.yml").write_text("book:\n  title: X\n", encoding="utf-8")

    older = out_dir / "old.pdf"
    older.write_bytes(b"%PDF-1.4")
    newer = out_dir / "new.pdf"
    newer.write_bytes(b"%PDF-1.4")
    import os
    import time

    now = time.time()
    os.utime(older, (now - 100, now - 100))
    os.utime(newer, (now, now))

    assert newest_output_pdf(book) == newer


def test_newest_output_pdf_none_when_dir_missing(tmp_path):
    book = tmp_path / "Band_Test"
    book.mkdir()
    assert newest_output_pdf(book) is None


def test_render_preview_reports_missing_book_root(tmp_path):
    md_file = tmp_path / "orphan.md"
    md_file.write_text("# X\n", encoding="utf-8")

    result = render_preview(md_file)
    assert result.success is False
    assert result.book_root is None
    assert result.pdf_path is None
    assert result.returncode == 2


def test_is_aggregator_content_detects_outline_call():
    assert is_aggregator_content('```{=typst}\n#outline(indent: 1em)\n```') is True
    assert is_aggregator_content("# Normales Kapitel\n\nEin Absatz.") is False


def test_render_single_chapter_preview_reports_missing_book_root(tmp_path):
    md_file = tmp_path / "orphan.md"
    md_file.write_text("# X\n", encoding="utf-8")

    result = render_single_chapter_preview(md_file)
    assert result.success is False
    assert result.book_root is None
    assert result.cleanup_dir is None


def _copy_fixture_to_tmp() -> Path:
    if not SMOKE_FIXTURE.exists():
        pytest.skip(f"Test-Fixture fehlt: {SMOKE_FIXTURE}")
    tmp_root = Path(tempfile.mkdtemp(prefix="bs_livepreview_"))
    book_copy = tmp_root / SMOKE_FIXTURE.name
    shutil.copytree(SMOKE_FIXTURE, book_copy)
    for stale in ("processed", "export", ".quarto"):
        target = book_copy / stale
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    return book_copy


@pytest.mark.slow
def test_render_preview_end_to_end_produces_pdf():
    """Echter Render (Band_Dummy): PDF entsteht, publish_map bekommt KEINEN
    neuen Eintrag (Vorschau ist kein registriertes Release)."""
    book = _copy_fixture_to_tmp()
    # Fixture kann von früheren lokalen Testläufen bereits eine
    # bookconfig/publish_map.json mitbringen (gitignored Buch-Ordner,
    # kein sauberer Repo-Zustand) — für die Isolation entfernen.
    publish_map = book / "bookconfig" / "publish_map.json"
    if publish_map.exists():
        publish_map.unlink()

    md_file = book / "content" / "book-master.md"
    if not md_file.is_file():
        candidates = list((book / "content").glob("*.md"))
        assert candidates, f"Keine Markdown-Datei in {book / 'content'} gefunden."
        md_file = candidates[0]

    result = render_preview(md_file, output_format="typst")
    assert result.success, f"rc={result.returncode} log={result.log_tail}"
    assert result.pdf_path is not None
    assert result.pdf_path.is_file()

    assert not publish_map.exists(), (
        "render_preview darf keine publish_map.json anlegen — reine Arbeitsvorschau, "
        "kein Eintrag im Mapping Manager."
    )


@pytest.mark.slow
def test_render_single_chapter_preview_uses_isolated_temp_book():
    """Echter Render (Band_Dummy, ein Kapitel): eigener cleanup_dir statt
    des festen Convenience-Pfads im echten Buch — darf export/_book/ dort
    NICHT anfassen (sonst würde eine unvollständige Einzelkapitel-PDF den
    normalen Export-Convenience-Pfad verfälschen)."""
    book = _copy_fixture_to_tmp()
    md_file = book / "content" / "required" / "Titel.md"
    if not md_file.is_file():
        candidates = [
            p for p in book.rglob("*.md") if p.name.lower() not in {"ivz.md", "index.md"}
        ]
        assert candidates, f"Keine geeignete Markdown-Datei unter {book} gefunden."
        md_file = candidates[0]

    result = render_single_chapter_preview(md_file, output_format="typst")
    try:
        assert result.success, f"rc={result.returncode} log={result.log_tail}"
        assert result.cleanup_dir is not None
        assert result.pdf_path is not None
        assert result.pdf_path.is_file()
        assert result.cleanup_dir in result.pdf_path.parents

        real_out_dir = book / "export" / "_book"
        assert not real_out_dir.exists() or not list(real_out_dir.glob("*.pdf")), (
            "Einzelkapitel-Vorschau darf export/_book/ im echten Buch nicht befüllen."
        )
    finally:
        if result.cleanup_dir is not None:
            shutil.rmtree(result.cleanup_dir, ignore_errors=True)


@pytest.mark.slow
def test_render_single_chapter_preview_falls_back_for_aggregator_page():
    """Eine Seite mit #outline() zieht das ganze Buch — Fallback auf
    Vollbuch-Render, PDF landet im echten Convenience-Pfad (kein
    cleanup_dir). Inhalt wird bewusst überschrieben (statt auf Band_Dummys
    aktuelle IVZ.md-Fassung zu vertrauen), damit der Test unabhängig von
    deren Content bleibt."""
    book = _copy_fixture_to_tmp()
    md_file = book / "content" / "required" / "IVZ.md"
    if not md_file.is_file():
        pytest.skip(f"Keine IVZ.md in {book} gefunden.")
    md_file.write_text(
        "---\ntitle: Inhaltsverzeichnis\nprint_title: false\n---\n\n"
        '```{=typst}\n#outline(indent: 1em)\n```\n',
        encoding="utf-8",
    )

    result = render_single_chapter_preview(md_file, output_format="typst")
    assert result.success, f"rc={result.returncode} log={result.log_tail}"
    assert result.cleanup_dir is None
    assert result.pdf_path is not None
    assert result.pdf_path.is_file()
