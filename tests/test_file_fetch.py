"""Tests for file-fetch across sibling book projects."""

from __future__ import annotations

from pathlib import Path

from ui_qt.dialogs.file_fetch_dialog import backup_then_copy, discover_file_candidates


def _book(root: Path, name: str, *, deckblatt: str) -> Path:
    book = root / name
    (book / "content").mkdir(parents=True)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters: [index.md]\n",
        encoding="utf-8",
    )
    (book / "index.md").write_text("---\ntitle: I\n---\n", encoding="utf-8")
    (book / "content" / "Deckblatt.md").write_text(deckblatt, encoding="utf-8")
    return book


def test_discover_file_candidates_skips_active(tmp_path: Path) -> None:
    active = _book(tmp_path, "Publish_Now", deckblatt="NOW")
    older = _book(tmp_path, "Publish_Old", deckblatt="OLD CUSTOM COVER")
    found = discover_file_candidates(active, "content/Deckblatt.md")
    assert len(found) == 1
    assert found[0].project_name == older.name
    assert "OLD CUSTOM" in found[0].source_path.read_text(encoding="utf-8")


def test_backup_then_copy(tmp_path: Path) -> None:
    src = tmp_path / "src.md"
    dst = tmp_path / "dst.md"
    src.write_text("NEW", encoding="utf-8")
    dst.write_text("OLD", encoding="utf-8")
    backup = backup_then_copy(src, dst, backup_root=tmp_path / ".backups")
    assert dst.read_text(encoding="utf-8") == "NEW"
    assert backup is not None
    assert backup.is_file()
    assert backup.read_text(encoding="utf-8") == "OLD"
