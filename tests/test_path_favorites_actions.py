"""Tests for Path Favorites Werkbank action rules (SSOT)."""

from __future__ import annotations

from pathlib import Path

from tools.path_favorites.actions import ActionId, resolve_favorite_actions
from tools.path_favorites.placeholders import PlaceholderContext


def _ctx(tmp_path: Path, *, with_book: bool = True, with_project: bool = False) -> PlaceholderContext:
    book = tmp_path / "books" / "MeinBuch" if with_book else None
    project = tmp_path / "gg" / "projects" / "P1" if with_project else None
    if book is not None:
        book.mkdir(parents=True, exist_ok=True)
        (book / "img").mkdir(exist_ok=True)
        (book / "export" / "kdp_cover").mkdir(parents=True, exist_ok=True)
        (book / "export" / "publish_renders").mkdir(parents=True, exist_ok=True)
    if project is not None:
        project.mkdir(parents=True, exist_ok=True)
    return PlaceholderContext(
        book_studio_root=tmp_path / "bs",
        grammargraph_root=tmp_path / "gg",
        active_book=book,
        active_project=project,
        userprofile=tmp_path / "user",
    )


def test_group_returns_group_info_only(tmp_path: Path):
    ctx = _ctx(tmp_path)
    plan = resolve_favorite_actions(ctx.active_book, ctx, is_group=True)
    assert plan.rule == "group"
    assert plan.action_ids == (ActionId.GROUP_INFO,)


def test_unresolved_and_missing(tmp_path: Path):
    ctx = _ctx(tmp_path)
    plan = resolve_favorite_actions(None, ctx)
    assert plan.rule == "missing_unresolved"
    assert plan.action_ids == (ActionId.MISSING_TARGET,)

    ghost = tmp_path / "nope"
    plan2 = resolve_favorite_actions(ghost, ctx, path_exists=False)
    assert plan2.rule == "missing_path"
    assert plan2.primary is not None
    assert plan2.primary.id == ActionId.MISSING_TARGET


def test_kdp_cover_rule(tmp_path: Path):
    ctx = _ctx(tmp_path)
    assert ctx.active_book is not None
    kdp = ctx.active_book / "export" / "kdp_cover"
    plan = resolve_favorite_actions(kdp, ctx, path_exists=True)
    assert plan.rule == "kdp_cover"
    assert plan.action_ids == (ActionId.OPEN_KDP_COVER, ActionId.OPEN_EXPLORER)
    assert plan.primary is not None
    assert plan.primary.id == ActionId.OPEN_KDP_COVER


def test_book_img_rule(tmp_path: Path):
    ctx = _ctx(tmp_path)
    assert ctx.active_book is not None
    img = ctx.active_book / "img"
    plan = resolve_favorite_actions(img, ctx, path_exists=True)
    assert plan.rule == "book_img"
    assert plan.action_ids[0] == ActionId.OPEN_STYLECLOUD


def test_active_book_rule(tmp_path: Path):
    ctx = _ctx(tmp_path)
    plan = resolve_favorite_actions(ctx.active_book, ctx, path_exists=True)
    assert plan.rule == "active_book"
    assert plan.action_ids[0] == ActionId.FOCUS_ACTIVE_BOOK


def test_export_and_publish_renders(tmp_path: Path):
    ctx = _ctx(tmp_path)
    assert ctx.active_book is not None
    export_dir = ctx.active_book / "export"
    renders = export_dir / "publish_renders"
    p1 = resolve_favorite_actions(export_dir, ctx, path_exists=True)
    p2 = resolve_favorite_actions(renders, ctx, path_exists=True)
    assert p1.rule == "export_archive"
    assert p2.rule == "export_archive"
    assert ActionId.OPEN_RENDER_ARCHIVE in p1.action_ids
    assert ActionId.OPEN_RENDER_ARCHIVE in p2.action_ids


def test_active_project_hint(tmp_path: Path):
    ctx = _ctx(tmp_path, with_project=True)
    plan = resolve_favorite_actions(ctx.active_project, ctx, path_exists=True)
    assert plan.rule == "active_project"
    assert plan.action_ids[0] == ActionId.HINT_PITUGRAFO


def test_generic_folder(tmp_path: Path):
    ctx = _ctx(tmp_path)
    other = tmp_path / "somewhere"
    other.mkdir()
    plan = resolve_favorite_actions(other, ctx, path_exists=True)
    assert plan.rule == "generic_folder"
    assert plan.action_ids == (ActionId.OPEN_EXPLORER, ActionId.COPY_PATH)


def test_application_rule(tmp_path: Path):
    ctx = _ctx(tmp_path)
    exe = tmp_path / "Paint.NET.exe"
    exe.write_bytes(b"")
    plan = resolve_favorite_actions(exe, ctx, path_exists=True)
    assert plan.rule == "application"
    assert plan.action_ids[0] == ActionId.OPEN_APPLICATION
    assert ActionId.OPEN_EXPLORER in plan.action_ids


def test_kdp_without_active_book_falls_through(tmp_path: Path):
    """Without active_book, a kdp_cover-named folder is only generic."""
    ctx = _ctx(tmp_path, with_book=False)
    fake = tmp_path / "export" / "kdp_cover"
    fake.mkdir(parents=True)
    plan = resolve_favorite_actions(fake, ctx, path_exists=True)
    assert plan.rule == "generic_folder"
    assert ActionId.OPEN_KDP_COVER not in plan.action_ids


def test_priority_kdp_over_export_parent(tmp_path: Path):
    """kdp_cover must win over the broader export/ rule."""
    ctx = _ctx(tmp_path)
    assert ctx.active_book is not None
    kdp = ctx.active_book / "export" / "kdp_cover"
    plan = resolve_favorite_actions(kdp, ctx, path_exists=True)
    assert plan.rule == "kdp_cover"
    assert ActionId.OPEN_RENDER_ARCHIVE not in plan.action_ids
