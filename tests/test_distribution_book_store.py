"""Tests für tools.distribution.book_store."""

from __future__ import annotations

import json
from pathlib import Path

from tools.distribution.book_store import (
    CHANNEL_KDP_PAPERBACK,
    DISTRIBUTION_FILENAME,
    distribution_path,
    is_chapter_excluded,
    is_kdp_paperback,
    list_excluded_chapters,
    read_distribution,
    set_chapter_excluded,
    set_kdp_paperback,
    write_distribution,
)


def test_read_missing_file_defaults_false(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    data = read_distribution(book)
    assert data["channels"] == {}
    assert is_kdp_paperback(book) is False


def test_write_roundtrip_kdp_flag(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    out = set_kdp_paperback(book, True)
    assert out == distribution_path(book)
    assert out.name == DISTRIBUTION_FILENAME
    assert is_kdp_paperback(book) is True
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert raw["channels"][CHANNEL_KDP_PAPERBACK] is True

    set_kdp_paperback(book, False)
    assert is_kdp_paperback(book) is False
    raw2 = json.loads(out.read_text(encoding="utf-8"))
    assert raw2["channels"][CHANNEL_KDP_PAPERBACK] is False


def test_write_distribution_creates_bookconfig(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    write_distribution(
        book,
        {"schema_version": 1, "channels": {CHANNEL_KDP_PAPERBACK: True}},
    )
    assert (book / "bookconfig" / DISTRIBUTION_FILENAME).is_file()


def test_corrupt_json_treated_as_empty(tmp_path: Path) -> None:
    book = tmp_path / "book"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    (cfg / DISTRIBUTION_FILENAME).write_text("{not-json", encoding="utf-8")
    assert is_kdp_paperback(book) is False


def test_chapter_overrides_empty_for_missing_file(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    assert list_excluded_chapters(book, CHANNEL_KDP_PAPERBACK) == []
    assert is_chapter_excluded(book, CHANNEL_KDP_PAPERBACK, "content/Deckblatt.md") is False


def test_set_chapter_excluded_roundtrip(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    set_chapter_excluded(book, CHANNEL_KDP_PAPERBACK, "content/Deckblatt.md", True)
    assert list_excluded_chapters(book, CHANNEL_KDP_PAPERBACK) == ["content/Deckblatt.md"]
    assert is_chapter_excluded(book, CHANNEL_KDP_PAPERBACK, "content/Deckblatt.md") is True
    # schema_version bleibt unveraendert (rein additiv, kein Version-Bump)
    raw = json.loads(distribution_path(book).read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert raw["chapter_overrides"][CHANNEL_KDP_PAPERBACK]["exclude_paths"] == [
        "content/Deckblatt.md"
    ]

    set_chapter_excluded(book, CHANNEL_KDP_PAPERBACK, "content/Deckblatt.md", False)
    assert list_excluded_chapters(book, CHANNEL_KDP_PAPERBACK) == []
    assert is_chapter_excluded(book, CHANNEL_KDP_PAPERBACK, "content/Deckblatt.md") is False


def test_chapter_overrides_independent_per_channel(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    set_chapter_excluded(book, "kdp_paperback", "content/Deckblatt.md", True)
    set_chapter_excluded(book, "other_channel", "content/Bonus.md", True)
    assert list_excluded_chapters(book, "kdp_paperback") == ["content/Deckblatt.md"]
    assert list_excluded_chapters(book, "other_channel") == ["content/Bonus.md"]


def test_old_file_without_chapter_overrides_still_reads(tmp_path: Path) -> None:
    book = tmp_path / "book"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    (cfg / DISTRIBUTION_FILENAME).write_text(
        json.dumps({"schema_version": 1, "channels": {CHANNEL_KDP_PAPERBACK: True}}),
        encoding="utf-8",
    )
    assert list_excluded_chapters(book, CHANNEL_KDP_PAPERBACK) == []
    assert is_kdp_paperback(book) is True
