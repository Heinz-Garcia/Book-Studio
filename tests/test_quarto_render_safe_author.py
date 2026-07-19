"""Regression: Typst/orange-book braucht book.author als nicht-leeren String."""

from __future__ import annotations

from pathlib import Path

import yaml

from quarto_render_safe import _ensure_typst_book_author


def _write_yml(book: Path, book_block: dict) -> None:
    book.mkdir(parents=True, exist_ok=True)
    data = {
        "project": {"type": "book", "output-dir": "export/_book"},
        "book": book_block,
    }
    (book / "_quarto.yml").write_text(
        yaml.dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def test_ensure_typst_book_author_sets_placeholder_from_title(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write_yml(book, {"title": "Mein Buch", "chapters": ["index.md"]})

    _ensure_typst_book_author(book)

    data = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    assert data["book"]["author"] == "Mein Buch"


def test_ensure_typst_book_author_joins_list(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write_yml(
        book,
        {
            "title": "X",
            "author": [{"name": "Ada"}, {"name": "Grace"}],
            "chapters": ["index.md"],
        },
    )

    _ensure_typst_book_author(book)

    data = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    assert data["book"]["author"] == "Ada, Grace"


def test_ensure_typst_book_author_keeps_existing_string(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write_yml(book, {"title": "X", "author": "Bestehend", "chapters": ["index.md"]})

    _ensure_typst_book_author(book)

    data = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    assert data["book"]["author"] == "Bestehend"
