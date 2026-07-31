"""Tests for structure finder + keep-structure refresh after external files."""

from __future__ import annotations

import json
from pathlib import Path

from ui_qt.book_workspace import StructureSession
from ui_qt.dialogs.structure_finder_dialog import (
    discover_structure_snapshots,
    _count_nodes,
)


def _make_book(root: Path, name: str, *, with_struct: bool = True) -> Path:
    book = root / name
    book.mkdir(parents=True)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")
    (book / "content").mkdir()
    (book / "content" / "A.md").write_text("---\ntitle: A\n---\n# A\n", encoding="utf-8")
    if with_struct:
        backups = book / ".backups"
        backups.mkdir()
        tree = [{"path": "content/A.md", "title": "A", "children": []}]
        (backups / "struct_20260720_120000.json").write_text(
            json.dumps(tree, indent=2), encoding="utf-8"
        )
        bookconfig = book / "bookconfig"
        bookconfig.mkdir()
        (bookconfig / "Publish_Demo_rev.5.json").write_text(
            json.dumps(tree, indent=2), encoding="utf-8"
        )
        (bookconfig / "publish_map.json").write_text("{}", encoding="utf-8")
    return book


def test_count_nodes_nested() -> None:
    data = [
        {
            "path": "a.md",
            "title": "A",
            "children": [{"path": "b.md", "title": "B", "children": []}],
        }
    ]
    assert _count_nodes(data) == 2


def test_discover_structure_snapshots_finds_siblings(tmp_path: Path) -> None:
    active = _make_book(tmp_path, "Publish_Active")
    sibling = _make_book(tmp_path, "Publish_Sibling_rev")
    snaps = discover_structure_snapshots(active)
    paths = {s.path.name for s in snaps}
    assert "struct_20260720_120000.json" in paths
    assert "Publish_Demo_rev.5.json" in paths
    # publish_map is not a structure tree
    assert "publish_map.json" not in paths
    projects = {s.project_name for s in snaps}
    assert "Publish_Active" in projects
    assert "Publish_Sibling_rev" in projects
    assert sibling.is_dir()


def test_refresh_from_disk_keep_structure(tmp_path: Path) -> None:
    book = _make_book(tmp_path, "Band_Keep", with_struct=False)
    session = StructureSession(book)
    session.load()
    session.book_nodes = [
        {"path": "content/A.md", "title": "Handgebaut", "children": []},
    ]
    session.dirty = True
    # Neue Datei auf Disk (wie nach Skeleton-Populate)
    (book / "content" / "Widmung.md").write_text(
        "---\ntitle: Widmung\n---\n", encoding="utf-8"
    )
    session.refresh_from_disk_keep_structure()
    assert session.book_nodes[0]["title"] == "Handgebaut"
    assert any(p == "content/Widmung.md" for p, _t in session.avail)
