"""Tests für tools.distribution.book_store."""

from __future__ import annotations

import json
from pathlib import Path

from tools.distribution.book_store import (
    CHANNEL_KDP_PAPERBACK,
    DISTRIBUTION_FILENAME,
    distribution_path,
    is_kdp_paperback,
    read_distribution,
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
