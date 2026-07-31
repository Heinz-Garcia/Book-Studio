"""Regression: Bulk-Hinzufügen sortiert nach Frontmatter-order (drei Zonen)."""

from __future__ import annotations

from pathlib import Path

from ui_qt.book_workspace import StructureSession
from yaml_engine import QuartoYamlEngine


class _FakeEngine:
    def __init__(self, book_path: Path, orders: dict[str, tuple[int | None, str | None]]):
        self.book_path = book_path
        self._orders = orders

    def get_required_order(self, rel_path: str):
        key = str(rel_path).replace("\\", "/")
        return self._orders.get(key, (None, None))


def test_add_paths_places_required_by_frontmatter_order(tmp_path: Path):
    book = tmp_path / "Book"
    book.mkdir()
    session = StructureSession(book)
    session.engine = _FakeEngine(
        book,
        {
            "content/required/Titel.md": (10, "front"),
            "content/required/Impressum.md": (30, "front"),
            "content/required/Rueckseite.md": (1, "end"),
            "content/required/Klappentext_hinten.md": (10, "end"),
        },
    )
    session.book_nodes = [
        {"path": "content/chapter.md", "title": "Kapitel", "children": []},
    ]
    session.avail = [
        ("content/required/Impressum.md", "Impressum"),
        ("content/required/Titel.md", "Titel"),
        ("content/required/Rueckseite.md", "Rückseite"),
        ("content/required/Klappentext_hinten.md", "Klappentext hinten"),
        ("content/free.md", "Frei"),
    ]
    session.title_registry = {p: t for p, t in session.avail}

    # Cursor auf Kapitel — ordered Dateien ignorieren den Cursor.
    assert session.add_paths(
        [
            "content/required/Impressum.md",
            "content/required/Titel.md",
            "content/free.md",
            "content/required/Klappentext_hinten.md",
            "content/required/Rueckseite.md",
        ],
        after_path="content/chapter.md",
    )

    paths = [n["path"] for n in session.book_nodes]
    assert paths == [
        "content/required/Titel.md",
        "content/required/Impressum.md",
        "content/chapter.md",
        "content/free.md",
        "content/required/Klappentext_hinten.md",
        "content/required/Rueckseite.md",
    ]


def _write_md(path: Path, *, title: str, order: str | None = None, required: bool | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", f'title: "{title}"', f'description: "{title}"']
    if required is not None:
        lines.append(f"required: {'true' if required else 'false'}")
    if order is not None:
        lines.append(f'order: "{order}"')
    lines.extend(["---", "", f"# {title}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def test_add_paths_honors_order_even_when_required_false(tmp_path: Path):
    """Skeleton-Optionals: order + required:false müssen trotzdem Vorspann/Nachspann bilden."""
    book = tmp_path / "Book"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")

    _write_md(book / "content" / "Widmung.md", title="Widmung", order="4", required=False)
    _write_md(book / "content" / "Impressum.md", title="Impressum", order="6", required=True)
    _write_md(book / "content" / "Kapitel_A.md", title="A")
    _write_md(book / "content" / "Kapitel_B.md", title="B")
    _write_md(book / "content" / "Glossar.md", title="Glossar", order="END-35", required=False)
    _write_md(book / "content" / "Rueckseite.md", title="Rueckseite", order="END-10", required=True)

    session = StructureSession(book)
    session.engine = QuartoYamlEngine(book)
    session.book_nodes = []
    session.avail = [
        ("content/Glossar.md", "Glossar"),
        ("content/Kapitel_B.md", "B"),
        ("content/Impressum.md", "Impressum"),
        ("content/Kapitel_A.md", "A"),
        ("content/Widmung.md", "Widmung"),
        ("content/Rueckseite.md", "Rueckseite"),
    ]
    session.title_registry = {p: t for p, t in session.avail}

    # Absichtlich „falsche“ Übergabe-Reihenfolge — Autosort muss Zonen herstellen.
    # Mittelzone: A vor B wie in dieser Liste (entspricht linker Reihenfolge nach Filter).
    assert session.add_paths(
        [
            "content/Rueckseite.md",
            "content/Kapitel_A.md",
            "content/Glossar.md",
            "content/Kapitel_B.md",
            "content/Impressum.md",
            "content/Widmung.md",
        ]
    )

    paths = [n["path"] for n in session.book_nodes]
    assert paths == [
        "content/Widmung.md",
        "content/Impressum.md",
        "content/Kapitel_A.md",
        "content/Kapitel_B.md",
        "content/Glossar.md",
        "content/Rueckseite.md",
    ]


def test_add_paths_middle_stays_between_front_and_end(tmp_path: Path):
    book = tmp_path / "Book"
    book.mkdir()
    session = StructureSession(book)
    session.engine = _FakeEngine(
        book,
        {
            "content/front.md": (10, "front"),
            "content/back.md": (1, "end"),
        },
    )
    session.book_nodes = [
        {"path": "content/front.md", "title": "Front", "children": []},
        {"path": "content/back.md", "title": "Back", "children": []},
    ]
    session.avail = [
        ("content/m1.md", "M1"),
        ("content/m2.md", "M2"),
    ]
    session.title_registry = {p: t for p, t in session.avail}

    # Cursor auf Vorspann — Mitte trotzdem vor Nachspann.
    assert session.add_paths(
        ["content/m1.md", "content/m2.md"],
        after_path="content/front.md",
    )
    assert [n["path"] for n in session.book_nodes] == [
        "content/front.md",
        "content/m1.md",
        "content/m2.md",
        "content/back.md",
    ]
