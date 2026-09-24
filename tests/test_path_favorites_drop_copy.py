"""Tests for Path Favorites drop-copy (SSOT)."""

from __future__ import annotations

from pathlib import Path

from tools.path_favorites.drop_copy import (
    DropConflictPolicy,
    copy_paths_into_folder,
    unique_destination,
)


def test_unique_destination(tmp_path: Path):
    dest = tmp_path / "file.txt"
    dest.write_text("a", encoding="utf-8")
    assert unique_destination(dest) == tmp_path / "file_1.txt"
    (tmp_path / "file_1.txt").write_text("b", encoding="utf-8")
    assert unique_destination(dest) == tmp_path / "file_2.txt"


def test_copy_into_empty(tmp_path: Path):
    dest = tmp_path / "dest"
    dest.mkdir()
    src = tmp_path / "src.txt"
    src.write_text("hello", encoding="utf-8")
    result = copy_paths_into_folder([src], dest)
    assert len(result.copied) == 1
    assert (dest / "src.txt").read_text(encoding="utf-8") == "hello"
    assert not result.errors


def test_rename_on_conflict(tmp_path: Path):
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "src.txt").write_text("old", encoding="utf-8")
    src = tmp_path / "src.txt"
    src.write_text("new", encoding="utf-8")
    result = copy_paths_into_folder(
        [src], dest, on_conflict=DropConflictPolicy.RENAME
    )
    assert len(result.copied) == 1
    assert result.copied[0].name == "src_1.txt"
    assert (dest / "src.txt").read_text(encoding="utf-8") == "old"
    assert (dest / "src_1.txt").read_text(encoding="utf-8") == "new"


def test_overwrite_on_conflict(tmp_path: Path):
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "src.txt").write_text("old", encoding="utf-8")
    src = tmp_path / "src.txt"
    src.write_text("new", encoding="utf-8")
    result = copy_paths_into_folder(
        [src], dest, on_conflict=DropConflictPolicy.OVERWRITE
    )
    assert len(result.copied) == 1
    assert (dest / "src.txt").read_text(encoding="utf-8") == "new"


def test_skip_on_conflict(tmp_path: Path):
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "src.txt").write_text("old", encoding="utf-8")
    src = tmp_path / "src.txt"
    src.write_text("new", encoding="utf-8")
    result = copy_paths_into_folder(
        [src], dest, on_conflict=DropConflictPolicy.SKIP
    )
    assert not result.copied
    assert len(result.skipped) == 1
    assert (dest / "src.txt").read_text(encoding="utf-8") == "old"


def test_copy_folder(tmp_path: Path):
    dest = tmp_path / "dest"
    dest.mkdir()
    src_dir = tmp_path / "folder"
    src_dir.mkdir()
    (src_dir / "inner.txt").write_text("x", encoding="utf-8")
    result = copy_paths_into_folder([src_dir], dest)
    assert len(result.copied) == 1
    assert (dest / "folder" / "inner.txt").read_text(encoding="utf-8") == "x"


def test_dest_not_dir(tmp_path: Path):
    not_dir = tmp_path / "file"
    not_dir.write_text("x", encoding="utf-8")
    src = tmp_path / "a.txt"
    src.write_text("a", encoding="utf-8")
    result = copy_paths_into_folder([src], not_dir)
    assert not result.copied
    assert result.errors


def test_overwrite_onto_own_folder_keeps_the_source(tmp_path: Path):
    """Regression: Quelle == Ziel -> "Überschreiben" löschte die Quelle."""
    src = tmp_path / "wichtig.txt"
    src.write_text("inhalt", encoding="utf-8")
    result = copy_paths_into_folder(
        [src], tmp_path, on_conflict=DropConflictPolicy.OVERWRITE
    )
    assert src.read_text(encoding="utf-8") == "inhalt"
    assert result.skipped == (src,)
    assert not result.errors


def test_folder_into_its_own_subfolder_is_refused(tmp_path: Path):
    src = tmp_path / "ordner"
    sub = src / "unter"
    sub.mkdir(parents=True)
    result = copy_paths_into_folder([src], sub)
    assert result.errors
    assert not (sub / "ordner").exists()
