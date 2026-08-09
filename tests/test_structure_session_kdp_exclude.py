"""Tests für StructureSession-Integration von KDP-Interior-Kapitelausschlüssen."""

from __future__ import annotations

from pathlib import Path

from tools.distribution.book_store import set_kdp_paperback
from ui_qt.book_workspace import StructureSession


def _write_book(book: Path) -> None:
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n"
        "  chapters:\n    - index.md\n    - content/Deckblatt.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")
    (book / "content").mkdir()
    (book / "content" / "Deckblatt.md").write_text(
        "---\ntitle: Deckblatt\n---\n\n# Deckblatt\n", encoding="utf-8"
    )


def test_kdp_channel_inactive_by_default(tmp_path: Path):
    book = tmp_path / "Book"
    _write_book(book)
    session = StructureSession(book)
    session.load()
    assert session.is_kdp_channel_active() is False
    assert session.is_kdp_chapter_excluded("content/Deckblatt.md") is False


def test_set_and_query_excluded_chapter(tmp_path: Path):
    book = tmp_path / "Book"
    _write_book(book)
    set_kdp_paperback(book, True)
    session = StructureSession(book)
    session.load()

    assert session.is_kdp_channel_active() is True
    assert session.is_kdp_chapter_excluded("content/Deckblatt.md") is False

    session.set_kdp_chapter_excluded("content/Deckblatt.md", True)
    assert session.is_kdp_chapter_excluded("content/Deckblatt.md") is True

    session.set_kdp_chapter_excluded("content/Deckblatt.md", False)
    assert session.is_kdp_chapter_excluded("content/Deckblatt.md") is False


def test_display_title_shows_marker_after_exclude(tmp_path: Path):
    book = tmp_path / "Book"
    _write_book(book)
    set_kdp_paperback(book, True)
    session = StructureSession(book)
    session.load()

    before = session.display_title("content/Deckblatt.md")
    assert "🚫K" not in before

    session.set_kdp_chapter_excluded("content/Deckblatt.md", True)
    after = session.display_title("content/Deckblatt.md")
    assert "🚫K" in after


def test_registry_cleared_when_channel_disabled_after_load(tmp_path: Path):
    """Wird der Kanal nach dem initialen `load()` deaktiviert, muss ein
    Refresh (z. B. `refresh_from_disk_keep_structure`) das Registry leeren."""
    book = tmp_path / "Book"
    _write_book(book)
    set_kdp_paperback(book, True)
    session = StructureSession(book)
    session.load()
    session.set_kdp_chapter_excluded("content/Deckblatt.md", True)
    assert session.kdp_excluded_registry == {"content/Deckblatt.md"}

    set_kdp_paperback(book, False)
    session.refresh_from_disk_keep_structure()
    assert session.kdp_excluded_registry == set()
