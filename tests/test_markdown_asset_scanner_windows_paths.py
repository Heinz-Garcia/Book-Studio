"""Regression: Windows-Laufwerkspfade in markdown_asset_scanner."""

from __future__ import annotations

from pathlib import Path

from markdown_asset_scanner import (
    _is_local_asset_target,
    _is_windows_drive_path,
    find_missing_image_refs,
)


def test_windows_drive_path_detection():
    assert _is_windows_drive_path("C:/Bilder/test.png")
    assert _is_windows_drive_path("D:\\Bilder\\test.png")
    assert not _is_windows_drive_path("https://example.com/x.png")
    assert not _is_windows_drive_path("bilder/foo.png")


def test_windows_drive_paths_are_local_assets():
    assert _is_local_asset_target("C:/Bilder/test.png") is True
    assert _is_local_asset_target("D:\\Bilder\\test.png") is True
    assert _is_local_asset_target("https://example.com/x.png") is False


def test_find_missing_image_refs_windows_absolute_path(tmp_path):
    md_file = tmp_path / "chapter.md"
    missing_png = "C:/Bilder/fehlt.png"
    md_file.write_text(f"![Alt]({missing_png})\n", encoding="utf-8")
    missing = find_missing_image_refs(md_file.read_text(encoding="utf-8"), md_file, tmp_path)
    assert missing == [(1, missing_png)]


def test_find_missing_image_refs_relative_still_works(tmp_path):
    md_file = tmp_path / "chapter.md"
    (tmp_path / "bilder").mkdir()
    md_file.write_text("![Alt](bilder/fehlt.png)\n", encoding="utf-8")
    missing = find_missing_image_refs(md_file.read_text(encoding="utf-8"), md_file, tmp_path)
    assert missing == [(1, "bilder/fehlt.png")]
