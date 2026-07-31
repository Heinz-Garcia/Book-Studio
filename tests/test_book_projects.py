"""Tests für tools/book_projects."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.book_projects.catalog import (
    add_content_root,
    create_empty_book,
    ensure_book_discoverable,
    list_books,
    list_content_roots,
    read_content_root_config,
    remove_content_root,
)
from tools.book_projects.scaffold import (
    create_empty_book as scaffold_create,
    is_quarto_book,
    sanitize_book_folder_name,
)


def test_sanitize_book_folder_name():
    assert sanitize_book_folder_name(" Mein Buch ") == "Mein_Buch"
    with pytest.raises(ValueError):
        sanitize_book_folder_name("...")
    with pytest.raises(ValueError):
        sanitize_book_folder_name("a/b")


def test_scaffold_create_empty_book(tmp_path: Path):
    book = scaffold_create(tmp_path, "Demo_Buch", title="Demo")
    assert is_quarto_book(book)
    assert (book / "index.md").is_file()
    assert (book / "bookconfig").is_dir()
    assert (book / "content").is_dir()
    yml = (book / "_quarto.yml").read_text(encoding="utf-8")
    assert "Demo" in yml
    with pytest.raises(ValueError):
        scaffold_create(tmp_path, "Demo_Buch")


def _write_app_config(repo: Path, content_root: object) -> None:
    (repo / "app_config.json").write_text(
        json.dumps({"content_root_path": content_root}),
        encoding="utf-8",
    )


def test_content_roots_and_list_books(tmp_path: Path):
    books_root = tmp_path / "books"
    books_root.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_app_config(repo, str(books_root))

    book = create_empty_book(books_root, "Alpha", title="Alpha", repo=repo)
    roots = list_content_roots(repo)
    assert books_root.resolve() in {r.resolve() for r in roots}
    found = list_books(repo)
    assert any(b.path.resolve() == book.resolve() for b in found)


def test_add_remove_content_root(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    _write_app_config(repo, str(root_a))

    add_content_root(root_b, repo=repo)
    entries = read_content_root_config(repo)
    assert any(Path(e).resolve() == root_b.resolve() for e in entries)

    remove_content_root(root_b, repo=repo)
    entries2 = read_content_root_config(repo)
    assert all(Path(e).resolve() != root_b.resolve() for e in entries2)


def test_ensure_book_discoverable_adds_parent(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    orphan_parent = tmp_path / "elsewhere"
    orphan_parent.mkdir()
    _write_app_config(repo, str(tmp_path / "empty_root"))
    (tmp_path / "empty_root").mkdir()

    book = scaffold_create(orphan_parent, "Orphan")
    ensure_book_discoverable(book, repo=repo)
    roots = list_content_roots(repo)
    assert orphan_parent.resolve() in {r.resolve() for r in roots}
    assert any(b.path.resolve() == book.resolve() for b in list_books(repo))
