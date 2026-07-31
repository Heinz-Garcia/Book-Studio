"""Tests for page_outline SSOT and StructureSession registration."""

from __future__ import annotations

from pathlib import Path

from page_outline import (
    OUTLINE_CONTENT_ROLE,
    build_outline_markdown,
    suggest_outline_rel_path,
    write_outline_page,
)
from ui_qt.book_workspace import StructureSession
from yaml_engine import QuartoYamlEngine


def test_build_outline_markdown_has_content_role():
    text = build_outline_markdown('Teil I "Alpha"')
    assert f"content_role: {OUTLINE_CONTENT_ROLE}" in text
    assert 'title: "Teil I \\"Alpha\\""' in text
    assert "# Teil I \"Alpha\"" in text


def test_suggest_and_unique_write(tmp_path: Path):
    book = tmp_path / "Book"
    book.mkdir()
    assert suggest_outline_rel_path("Teil I") == "content/Teil_I.md"
    rel1 = write_outline_page(book, "Teil I")
    assert rel1 == "content/Teil_I.md"
    assert (book / rel1).is_file()
    rel2 = write_outline_page(book, "Teil I")
    assert rel2 == "content/Teil_I_2.md"
    content = (book / rel1).read_text(encoding="utf-8")
    assert "content_role: outline" in content


def test_session_register_and_add_outline(tmp_path: Path):
    book = tmp_path / "Book"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")
    (book / "content").mkdir()
    (book / "content" / "kap.md").write_text(
        "---\ntitle: Kap\n---\n\n# Kap\n", encoding="utf-8"
    )

    session = StructureSession(book)
    session.load()
    rel = write_outline_page(book, "Teil A")
    session.register_new_file(rel)
    assert any(p == rel for p, _t in session.avail)

    assert session.add_paths([rel], after_path=None)
    paths = [n["path"] for n in session.book_nodes]
    assert rel in paths
    title = session.title_registry[rel]
    assert "🧭" in title

    engine = QuartoYamlEngine(book)
    assert engine.extract_content_role_from_md(book / rel) == "outline"
