"""Tests für Überschriften-Shift (Einrücken/Ausrücken)."""

from __future__ import annotations

from pathlib import Path

from ui_qt.book_workspace import StructureSession
from ui_qt.markdown_headings import (
    shift_body_headings,
    shift_markdown_file,
    shift_markdown_headings,
)


def test_shift_body_headings_basic():
    body = "# Titel\n\nText\n## Unter\n"
    assert "# Titel" in shift_body_headings(body, 0)
    up = shift_body_headings(body, 1)
    assert "## Titel" in up
    assert "### Unter" in up
    down = shift_body_headings(up, -1)
    assert "# Titel" in down
    assert "## Unter" in down


def test_shift_clamps_to_h1_h6():
    assert shift_body_headings("# A\n", -5).startswith("# A")
    assert shift_body_headings("###### Z\n", 2).startswith("###### Z")


def test_shift_skips_frontmatter_and_fences():
    content = (
        "---\ntitle: X\n---\n"
        "# Heading\n\n"
        "```bash\n"
        "# not a heading\n"
        "```\n"
        "## Sub\n"
    )
    out = shift_markdown_headings(content, 1)
    assert "---\ntitle: X\n---\n" in out
    assert "## Heading" in out
    assert "### Sub" in out
    assert "# not a heading" in out


def test_shift_markdown_file(tmp_path: Path):
    path = tmp_path / "ch.md"
    path.write_text("# Hello\n\nBody\n", encoding="utf-8")
    assert shift_markdown_file(path, 1) is True
    assert path.read_text(encoding="utf-8").startswith("## Hello")
    assert shift_markdown_file(path, -1) is True
    assert path.read_text(encoding="utf-8").startswith("# Hello")


def test_structure_session_indent_outdent_writes_markdown(tmp_path: Path):
    book = tmp_path / "Book"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  title: T\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("# Idx\n", encoding="utf-8")
    (book / "a.md").write_text("---\ntitle: A\n---\n\n# A\n\nText A\n", encoding="utf-8")
    (book / "b.md").write_text("---\ntitle: B\n---\n\n# B\n\nText B\n", encoding="utf-8")

    session = StructureSession(book)
    session.book_nodes = [
        {"path": "a.md", "title": "A", "children": []},
        {"path": "b.md", "title": "B", "children": []},
    ]
    session.avail = []

    assert session.indent(["b.md"]) is True
    text_b = (book / "b.md").read_text(encoding="utf-8")
    assert "## B" in text_b
    assert session.book_nodes[0]["children"][0]["path"] == "b.md"

    assert session.outdent(["b.md"]) is True
    text_b2 = (book / "b.md").read_text(encoding="utf-8")
    assert "# B" in text_b2
    assert "## B" not in text_b2.split("Text B")[0]


def test_structure_session_indent_by_two_levels(tmp_path: Path):
    book = tmp_path / "Book"
    book.mkdir()
    (book / "a.md").write_text("# A\n", encoding="utf-8")
    (book / "b.md").write_text("# B\n", encoding="utf-8")
    (book / "c.md").write_text("# C\n", encoding="utf-8")
    session = StructureSession(book)
    session.book_nodes = [
        {"path": "a.md", "title": "A", "children": []},
        {"path": "b.md", "title": "B", "children": []},
        {"path": "c.md", "title": "C", "children": []},
    ]
    session.avail = []

    # c unter b, dann unter b's letztem Kind — hier nur b als Parent möglich:
    # 1. Schritt: c → Kind von b; 2. Schritt: c hat idx 0 unter b → kein 2. Indent.
    # Mit a/b/c: erst b unter a, dann c ×2 → c unter b unter a.
    assert session.indent(["b.md"]) is True
    assert session.indent_by(["c.md"], levels=2) is True
    assert session._nesting_depth("c.md") == 2
    assert (book / "c.md").read_text(encoding="utf-8").startswith("### C")
    assert session.book_nodes[0]["children"][0]["path"] == "b.md"
    assert session.book_nodes[0]["children"][0]["children"][0]["path"] == "c.md"

    assert session.outdent_by(["c.md"], levels=2) is True
    assert session._nesting_depth("c.md") == 0
    assert (book / "c.md").read_text(encoding="utf-8").startswith("# C")


def test_structure_session_undo_restores_headings(tmp_path: Path):
    book = tmp_path / "Book"
    book.mkdir()
    (book / "a.md").write_text("# A\n", encoding="utf-8")
    (book / "b.md").write_text("# B\n", encoding="utf-8")
    session = StructureSession(book)
    session.book_nodes = [
        {"path": "a.md", "title": "A", "children": []},
        {"path": "b.md", "title": "B", "children": []},
    ]
    session.avail = []
    session.indent(["b.md"])
    assert (book / "b.md").read_text(encoding="utf-8").startswith("## B")
    assert session.undo() is True
    assert (book / "b.md").read_text(encoding="utf-8").startswith("# B")
    assert session.redo() is True
    assert (book / "b.md").read_text(encoding="utf-8").startswith("## B")
