"""Tests für Skeleton-Sync von End-Befehlen."""

from __future__ import annotations

from pathlib import Path

import yaml

from ui_qt.end_commands import DEFAULT_PAGEBREAK_COMMAND
from ui_qt.skeleton_sync import (
    apply_end_command_to_skeleton_file,
    resolve_skeleton_counterpart,
)


def _make_skeleton_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    book = tmp_path / "book"
    profile = repo / "tools" / "skeleton" / "library" / "standard"
    required = profile / "content" / "required"
    required.mkdir(parents=True)
    book_required = book / "content" / "required"
    book_required.mkdir(parents=True)

    skel_md = required / "Titel.md"
    book_md = book_required / "Titel.md"
    body = "---\ntitle: Titel\n---\n\n# Titel\n\nText.\n"
    skel_md.write_text(body, encoding="utf-8")
    book_md.write_text(body, encoding="utf-8")

    manifest = {
        "name": "standard",
        "label": "Standard",
        "description": "Test",
        "files": [{"path": "content/required/Titel.md", "title": "Titel"}],
    }
    (profile / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True),
        encoding="utf-8",
    )
    (repo / "app_config.json").write_text(
        '{"skeleton_library_path": "tools/skeleton/library", '
        '"skeleton_default_profile": "standard"}',
        encoding="utf-8",
    )
    return repo, book, book_md


def test_resolve_skeleton_counterpart(tmp_path: Path):
    repo, book, book_md = _make_skeleton_repo(tmp_path)
    hit = resolve_skeleton_counterpart(book, book_md, repo)
    assert hit is not None
    assert hit.profile == "standard"
    assert hit.rel_path == "content/required/Titel.md"
    assert hit.library_path.is_file()


def test_resolve_skips_non_manifest_file(tmp_path: Path):
    repo, book, _ = _make_skeleton_repo(tmp_path)
    other = book / "content" / "kap.md"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("# X\n", encoding="utf-8")
    assert resolve_skeleton_counterpart(book, other, repo) is None


def test_apply_end_command_to_skeleton(tmp_path: Path):
    repo, book, book_md = _make_skeleton_repo(tmp_path)
    hit = resolve_skeleton_counterpart(book, book_md, repo)
    assert hit is not None
    ok, message = apply_end_command_to_skeleton_file(hit.library_path, DEFAULT_PAGEBREAK_COMMAND)
    assert ok is True
    text = hit.library_path.read_text(encoding="utf-8")
    assert "#pagebreak()" in text
    assert "eingefügt" in message

    ok2, message2 = apply_end_command_to_skeleton_file(hit.library_path, DEFAULT_PAGEBREAK_COMMAND)
    assert ok2 is False
    assert "bereits vorhanden" in message2
