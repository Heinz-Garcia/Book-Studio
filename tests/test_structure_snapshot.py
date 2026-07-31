"""Tests for named structure snapshot envelopes."""

from __future__ import annotations

import json
from pathlib import Path

from book_doctor import BackupManager
from ui_qt.structure_snapshot import (
    LEGACY_LABEL,
    build_envelope,
    format_snapshot_list_label,
    load_snapshot_file,
    parse_snapshot_data,
    peek_book_file,
    write_snapshot_file,
)


def test_parse_legacy_list() -> None:
    tree = [{"path": "content/A.md", "title": "Alpha", "children": []}]
    parsed, meta = parse_snapshot_data(tree)
    assert parsed == tree
    assert meta.is_legacy
    assert meta.label == LEGACY_LABEL
    assert meta.chapter_count == 1
    assert meta.chapter_titles == ["Alpha"]


def test_envelope_roundtrip(tmp_path: Path) -> None:
    tree = [
        {
            "path": "content/Deckblatt.md",
            "title": "Deckblatt",
            "children": [],
        },
        {"path": "content/IVZ.md", "title": "IVZ", "children": []},
    ]
    path = tmp_path / "struct_20260728_120000.json"
    write_snapshot_file(path, tree, label="rev.5 vor Skeleton")
    loaded, meta = load_snapshot_file(path)
    assert loaded == tree
    assert meta.label == "rev.5 vor Skeleton"
    assert meta.chapter_count == 2
    assert "Deckblatt" in meta.chapter_titles
    label = format_snapshot_list_label(path, meta)
    assert "rev.5 vor Skeleton" in label
    assert "2 Kapitel" in label


def test_backup_manager_writes_envelope(tmp_path: Path) -> None:
    book = tmp_path / "Band"
    book.mkdir()
    mgr = BackupManager(None, book)
    name = mgr.create_structure_backup(
        [{"path": "content/A.md", "title": "A", "children": []}],
        label="Mein Stand",
    )
    assert name
    data = json.loads((book / ".backups" / name).read_text(encoding="utf-8"))
    assert data["label"] == "Mein Stand"
    assert isinstance(data["tree"], list)


def test_backup_manager_default_label_is_timestamp(tmp_path: Path) -> None:
    import re

    book = tmp_path / "Band"
    book.mkdir()
    mgr = BackupManager(None, book)
    name = mgr.create_structure_backup([])
    data = json.loads((book / ".backups" / name).read_text(encoding="utf-8"))
    assert re.fullmatch(r"Band \d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}", data["label"])


def test_default_structure_snapshot_label_format() -> None:
    from datetime import datetime

    from ui_qt.structure_snapshot import default_structure_snapshot_label

    fixed = datetime(2026, 7, 28, 21, 41, 5)
    assert default_structure_snapshot_label(fixed) == "28.07.2026 21:41:05"
    assert (
        default_structure_snapshot_label(fixed, book_name="IFJN_Brustkrebs")
        == "IFJN_Brustkrebs 28.07.2026 21:41:05"
    )
    assert (
        default_structure_snapshot_label(
            fixed, book_name=Path(r"C:\books\IFJN_Brustkrebs")
        )
        == "IFJN_Brustkrebs 28.07.2026 21:41:05"
    )


def test_delete_structure_backup(tmp_path: Path) -> None:
    from ui_qt.structure_snapshot import delete_structure_backup, write_snapshot_file

    book = tmp_path / "Band"
    backups = book / ".backups"
    backups.mkdir(parents=True)
    path = backups / "struct_20260728_120000.json"
    write_snapshot_file(path, [{"path": "content/a.md", "title": "A", "children": []}], label="x")
    assert path.is_file()
    delete_structure_backup(path)
    assert not path.exists()

    bad = tmp_path / "other.json"
    bad.write_text("[]", encoding="utf-8")
    try:
        delete_structure_backup(bad)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_peek_book_file(tmp_path: Path) -> None:
    book = tmp_path / "Band"
    (book / "content").mkdir(parents=True)
    (book / "content" / "Deckblatt.md").write_text("COVER TEXT", encoding="utf-8")
    assert "COVER TEXT" in peek_book_file(book, "content/Deckblatt.md")
    assert "fehlt" in peek_book_file(book, "content/Missing.md")


def test_build_envelope_defaults() -> None:
    env = build_envelope([], label="  ")
    assert env["label"] == LEGACY_LABEL
    assert env["chapter_count"] == 0
