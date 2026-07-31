"""Tests für Buchprojekt-Anzeigenamen und Katalog-Feld."""

from __future__ import annotations

from pathlib import Path

from tools.book_projects.label import read_display_name, write_display_name
from tools.book_projects.catalog import BookInfo, list_books, write_content_root_config


def test_display_name_roundtrip_and_clear(tmp_path: Path) -> None:
    book = tmp_path / "Publish_Demo"
    book.mkdir()
    assert read_display_name(book) == ""
    write_display_name(book, "  IFJN Probe  ")
    assert read_display_name(book) == "IFJN Probe"
    assert (book / "bookconfig" / "project_label.json").is_file()
    write_display_name(book, "")
    assert read_display_name(book) == ""
    assert not (book / "bookconfig" / "project_label.json").is_file()


def test_list_books_includes_empty_display_name(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app_config.json").write_text("{}", encoding="utf-8")
    root = tmp_path / "books"
    root.mkdir()
    book = root / "Band_A"
    book.mkdir()
    (book / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    write_content_root_config([str(root)], repo=repo)
    books = list_books(repo)
    assert len(books) == 1
    assert isinstance(books[0], BookInfo)
    assert books[0].name == "Band_A"
    assert books[0].display_name == ""
    write_display_name(book, "Mein Band")
    books2 = list_books(repo)
    assert books2[0].display_name == "Mein Band"
