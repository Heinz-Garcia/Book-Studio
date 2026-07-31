"""Tests für Struktur laden (Ersetzen / Ergänzen)."""

from __future__ import annotations

from pathlib import Path

from ui_qt.book_workspace import StructureSession
from ui_qt.structure_snapshot import write_snapshot_file


def _write_snapshot(book: Path, label: str, tree: list) -> Path:
    backup_dir = book / ".backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"struct_test_{label.replace(' ', '_')}.json"
    write_snapshot_file(path, tree, label=label)
    return path


def test_replace_structure_from_snapshot(tmp_path: Path):
    book = tmp_path / "Book"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")
    (book / "content").mkdir()
    (book / "content" / "a.md").write_text("---\ntitle: A\n---\n\n# A\n", encoding="utf-8")
    (book / "content" / "b.md").write_text("---\ntitle: B\n---\n\n# B\n", encoding="utf-8")

    session = StructureSession(book)
    session.load()
    session.book_nodes = [
        {"path": "content/a.md", "title": "A", "children": []},
    ]
    session._refresh_avail()

    snapshot_tree = [
        {"path": "content/b.md", "title": "B", "children": []},
    ]
    assert session.replace_structure_from_snapshot(snapshot_tree)
    paths = [n["path"] for n in session.book_nodes]
    assert paths == ["content/b.md"]
    assert session.dirty is True


def test_merge_paths_skips_existing(tmp_path: Path):
    book = tmp_path / "Book"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")
    (book / "content").mkdir()
    (book / "content" / "a.md").write_text("---\ntitle: A\n---\n\n# A\n", encoding="utf-8")
    (book / "content" / "b.md").write_text("---\ntitle: B\n---\n\n# B\n", encoding="utf-8")
    (book / "content" / "c.md").write_text("---\ntitle: C\n---\n\n# C\n", encoding="utf-8")

    session = StructureSession(book)
    session.load()
    session.book_nodes = [
        {"path": "content/a.md", "title": "A", "children": []},
    ]
    session.avail = [
        ("content/b.md", "B"),
        ("content/c.md", "C"),
    ]
    session.title_registry = {
        "content/a.md": "A",
        "content/b.md": "B",
        "content/c.md": "C",
    }

    added, skipped = session.merge_paths_from_snapshot(
        ["content/a.md", "content/b.md", "content/c.md"]
    )
    assert added == 2
    assert skipped == 1
    paths = [n["path"] for n in session.book_nodes]
    assert paths == ["content/a.md", "content/b.md", "content/c.md"]


def test_list_backups_and_envelope_label(tmp_path: Path):
    from ui_qt.structure_snapshot import (
        format_backup_label,
        format_snapshot_list_item_multiline,
        list_structure_backups,
    )

    book = tmp_path / "Book"
    book.mkdir()
    tree = [{"path": "content/x.md", "title": "X", "children": []}]
    path = _write_snapshot(book, "vor TOC-Fix", tree)
    backups = list_structure_backups(book)
    assert path in backups
    label = format_backup_label(path)
    assert "vor TOC-Fix" in label or "TOC" in label
    multiline, tooltip = format_snapshot_list_item_multiline(path)
    assert "\n" in multiline
    assert "Kapitel" in multiline
    assert "X" in multiline or "x.md" in tooltip.lower()


def test_save_writes_named_snapshot_label(tmp_path: Path):
    from ui_qt.structure_snapshot import list_structure_backups, load_snapshot_file

    book = tmp_path / "Book"
    book.mkdir()
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")
    session = StructureSession(book)
    session.load()
    assert session.save(snapshot_label="rev.5 vor Skeleton")
    backups = list_structure_backups(book)
    assert backups
    _tree, meta = load_snapshot_file(backups[0])
    assert meta.label == "rev.5 vor Skeleton"


def test_format_snapshot_multiline_no_horizontal_breadcrumb(tmp_path: Path):
    from ui_qt.structure_snapshot import format_snapshot_list_item_multiline, write_snapshot_file

    book = tmp_path / "Book"
    book.mkdir()
    titles = [f"Kapitel_{i}" for i in range(8)]
    tree = [
        {"path": f"content/{t}.md", "title": t, "children": []} for t in titles
    ]
    path = book / ".backups" / "struct_demo.json"
    write_snapshot_file(path, tree, label="Lang")
    text, tooltip = format_snapshot_list_item_multiline(path)
    assert "→" not in text.split("\n")[0]
    assert "Kapitel_0" in text
    assert "(+6)" in text or "…" in text
    assert "Kapitel_0" in tooltip and "Kapitel_7" in tooltip


def test_compare_structure_paths_merge_and_replace():
    from ui_qt.structure_snapshot import (
        compare_structure_paths,
        format_structure_diff_summary,
    )

    snapshot = [
        {"path": "content/a.md", "title": "A", "children": []},
        {"path": "content/b.md", "title": "B", "children": []},
        {"path": "content/c.md", "title": "C", "children": []},
    ]
    current = ["content/a.md", "content/x.md", "content/b.md"]
    diff = compare_structure_paths(snapshot, current)
    assert diff.only_in_snapshot == ("content/c.md",)
    assert diff.only_in_current == ("content/x.md",)
    assert diff.in_both == ("content/a.md", "content/b.md")
    assert diff.order_changed is False

    reorder_current = ["content/b.md", "content/a.md", "content/c.md"]
    diff_reorder = compare_structure_paths(snapshot, reorder_current)
    assert diff_reorder.order_changed is True

    merge_summary, tooltip = format_structure_diff_summary(diff, merge_mode=True)
    assert "➕ 1" in merge_summary
    assert "✓ 2" in merge_summary
    assert "content/x.md" in tooltip

    merge_reorder, _ = format_structure_diff_summary(diff_reorder, merge_mode=True)
    assert "Reihenfolge" in merge_reorder

    replace_summary, _ = format_structure_diff_summary(diff, merge_mode=False)
    assert "⚠ 1" in replace_summary
    assert "verschwinden" in replace_summary


def test_structure_load_dialog_peek_is_modal_dialog(tmp_path: Path):
    """Doppelklick öffnet ChapterPeekDialog; Snapshot-Dialog ändert Größe nicht."""
    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.structure_load_dialog import (
        ChapterPeekDialog,
        StructureLoadDialog,
        _DIALOG_SIZE,
    )
    from ui_qt.structure_snapshot import write_snapshot_file

    _app = QApplication.instance() or QApplication([])

    book = tmp_path / "Book"
    book.mkdir()
    (book / "content").mkdir()
    (book / "content" / "a.md").write_text("# A\n\nHallo\n", encoding="utf-8")
    backup_dir = book / ".backups"
    backup_dir.mkdir()
    write_snapshot_file(
        backup_dir / "struct_demo.json",
        [{"path": "content/a.md", "title": "A", "children": []}],
        label="demo",
    )

    dlg = StructureLoadDialog(
        None,
        book,
        current_paths_ordered=["content/a.md"],
        on_preview=lambda _tree: None,
        on_restore=lambda: None,
        live_preview_default=True,
    )
    try:
        assert dlg.size().width() <= _DIALOG_SIZE[0] + 20
        assert not hasattr(dlg, "_right_pane")
        assert not hasattr(dlg, "_peek_open")

        item = dlg._chapters.item(0)
        assert item is not None
        # Ohne exec: Dialog-Objekt prüfen
        peek = ChapterPeekDialog(dlg, book, "content/a.md", chapter_title="A")
        try:
            assert "Leservorschau" in peek.windowTitle()
            assert peek.isModal()
        finally:
            peek.close()
            peek.deleteLater()
    finally:
        dlg.close()
        dlg.deleteLater()


def test_structure_load_dialog_delete_snapshot(tmp_path: Path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ui_qt.dialogs import structure_load_dialog as sld
    from ui_qt.structure_snapshot import write_snapshot_file

    _app = QApplication.instance() or QApplication([])

    book = tmp_path / "Book"
    book.mkdir()
    backup_dir = book / ".backups"
    backup_dir.mkdir()
    keep = backup_dir / "struct_keep.json"
    gone = backup_dir / "struct_gone.json"
    write_snapshot_file(
        keep, [{"path": "content/a.md", "title": "A", "children": []}], label="keep"
    )
    write_snapshot_file(
        gone, [{"path": "content/b.md", "title": "B", "children": []}], label="gone"
    )

    monkeypatch.setattr(
        sld.QMessageBox,
        "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )

    dlg = sld.StructureLoadDialog(None, book, current_paths_ordered=[])
    try:
        assert dlg._snapshots.count() == 2
        target_row = None
        for row in range(dlg._snapshots.count()):
            item = dlg._snapshots.item(row)
            raw = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if raw.endswith("struct_gone.json"):
                target_row = row
                break
        assert target_row is not None
        dlg._snapshots.clearSelection()
        dlg._snapshots.setCurrentRow(target_row)
        dlg._snapshots.item(target_row).setSelected(True)
        dlg._delete_selected_snapshots()
        assert not gone.exists()
        assert keep.exists()
        assert dlg._snapshots.count() == 1
    finally:
        dlg.close()
        dlg.deleteLater()
