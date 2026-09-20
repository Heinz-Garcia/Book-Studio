"""Tests for structure finder + keep-structure refresh after external files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_session_load_wipes_unsaved_structure_empty_yml(tmp_path: Path) -> None:
    """Regression: volles load() nach Import mit chapters:[] zerstört GUI-Baum.

    Render-Prep rief früher refresh_ui_titles → session.load() und speicherte
    danach den leeren Baum — leeres PDF trotz Kapitel rechts in der GUI.
    """
    book = _make_book(tmp_path, "Band_EmptyChapters", with_struct=False)
    # Nur index — wie nach altem Import ohne Payload in chapters
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    payload = "Prosa_Demo.md"
    (book / payload).write_text("---\ntitle: Demo\n---\nText\n", encoding="utf-8")
    session = StructureSession(book)
    session.load()
    session.book_nodes = [
        {"path": "index.md", "title": "Index", "children": []},
        {"path": payload, "title": "Demo", "children": []},
    ]
    session.dirty = True
    # Was refresh_ui_titles früher tat:
    session.load()
    paths = [n.get("path") for n in session.book_nodes]
    assert payload not in paths

    # Korrektes Verhalten (wie refresh_ui_titles jetzt):
    session.book_nodes = [
        {"path": "index.md", "title": "Index", "children": []},
        {"path": payload, "title": "Demo", "children": []},
    ]
    session.dirty = True
    session.refresh_from_disk_keep_structure()
    paths = [n.get("path") for n in session.book_nodes]
    assert payload in paths


def test_refresh_titles_updates_required_icon_in_avail(tmp_path: Path) -> None:
    """Nach Frontmatter-Änderung (required) muss das Pool-📌 neu gelesen werden."""
    book = _make_book(tmp_path, "Band_RequiredIcon", with_struct=False)
    md = book / "content" / "A.md"
    md.write_text("---\ntitle: A\nrequired: true\n---\n# A\n", encoding="utf-8")
    session = StructureSession(book)
    session.load()
    titles = dict(session.avail)
    assert "content/A.md" in titles
    assert titles["content/A.md"].startswith("📌")

    md.write_text("---\ntitle: A\nrequired: false\n---\n# A\n", encoding="utf-8")
    session.refresh_titles_and_markers()
    titles = dict(session.avail)
    assert not titles["content/A.md"].startswith("📌")
    # display_title bevorzugt Registry — stale node-Titel werden überschrieben
    assert not session.display_title("content/A.md", "📌 A").startswith("📌")


def test_add_all_required_only_picks_required_pool_pages(tmp_path: Path) -> None:
    """„Hinzufügen (all required)“ nimmt nur required-Seiten aus dem Pool."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from ui_qt.widgets.structure_panel import StructurePanel

    book = _make_book(tmp_path, "Band_AddReq", with_struct=False)
    (book / "content" / "Rahmen.md").write_text(
        "---\ntitle: Rahmen\nrequired: true\norder: \"10\"\n---\n",
        encoding="utf-8",
    )
    (book / "content" / "Kapitel.md").write_text(
        "---\ntitle: Kapitel\nrequired: false\n---\n# Text\n",
        encoding="utf-8",
    )
    session = StructureSession(book)
    session.load()
    app = QApplication.instance() or QApplication([])
    panel = StructurePanel()
    panel.set_session(session)
    assert panel._required_avail_paths() == ["content/Rahmen.md"]
    panel._on_add_all_required()
    paths = [n.get("path") for n in session.book_nodes]
    assert "content/Rahmen.md" in paths
    assert "content/Kapitel.md" not in paths
    panel.close()
    app.processEvents()
