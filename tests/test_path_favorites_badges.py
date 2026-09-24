"""Tests for Path Favorites Werkbank status badges (SSOT)."""

from __future__ import annotations

from pathlib import Path

from tools.path_favorites.badges import BadgeKind, resolve_favorite_badge
from tools.path_favorites.placeholders import PlaceholderContext


def _ctx(tmp_path: Path, *, with_book: bool = True) -> PlaceholderContext:
    book = tmp_path / "books" / "MeinBuch" if with_book else None
    if book is not None:
        book.mkdir(parents=True, exist_ok=True)
        (book / "export" / "kdp_cover").mkdir(parents=True, exist_ok=True)
        (book / "img").mkdir(exist_ok=True)
    return PlaceholderContext(
        book_studio_root=tmp_path / "bs",
        grammargraph_root=tmp_path / "gg",
        active_book=book,
        active_project=None,
        userprofile=tmp_path / "user",
    )


def test_group_badge(tmp_path: Path):
    ctx = _ctx(tmp_path)
    badge = resolve_favorite_badge(None, ctx, is_group=True)
    assert badge.kind == BadgeKind.GROUP
    assert badge.label == "Gruppe"


def test_missing_unresolved(tmp_path: Path):
    ctx = _ctx(tmp_path)
    badge = resolve_favorite_badge(None, ctx)
    assert badge.kind == BadgeKind.MISSING
    assert badge.label == "fehlt"


def test_missing_path(tmp_path: Path):
    ctx = _ctx(tmp_path)
    ghost = tmp_path / "nope"
    badge = resolve_favorite_badge(ghost, ctx, path_exists=False)
    assert badge.kind == BadgeKind.MISSING


def test_empty_folder(tmp_path: Path):
    ctx = _ctx(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    badge = resolve_favorite_badge(empty, ctx, path_exists=True)
    assert badge.kind == BadgeKind.EMPTY
    assert badge.label == "leer"


def test_ok_nonempty(tmp_path: Path):
    ctx = _ctx(tmp_path)
    folder = tmp_path / "stuff"
    folder.mkdir()
    (folder / "a.txt").write_text("x", encoding="utf-8")
    badge = resolve_favorite_badge(folder, ctx, path_exists=True)
    assert badge.kind == BadgeKind.OK
    assert badge.label == "ok"


def test_kdp_no_layout(tmp_path: Path):
    ctx = _ctx(tmp_path)
    assert ctx.active_book is not None
    kdp = ctx.active_book / "export" / "kdp_cover"
    badge = resolve_favorite_badge(kdp, ctx, path_exists=True)
    assert badge.kind == BadgeKind.NO_LAYOUT
    assert badge.label == "kein Layout"


def test_kdp_with_layout(tmp_path: Path):
    ctx = _ctx(tmp_path)
    assert ctx.active_book is not None
    kdp = ctx.active_book / "export" / "kdp_cover"
    (kdp / "cover_kdp_cover.json").write_text("{}", encoding="utf-8")
    badge = resolve_favorite_badge(kdp, ctx, path_exists=True)
    assert badge.kind == BadgeKind.LAYOUT
    assert badge.label == "Layout"


def test_application_badge(tmp_path: Path):
    ctx = _ctx(tmp_path)
    exe = tmp_path / "gimp.exe"
    exe.write_bytes(b"")
    badge = resolve_favorite_badge(exe, ctx, path_exists=True)
    assert badge.kind == BadgeKind.APP
    assert badge.label == "App"
