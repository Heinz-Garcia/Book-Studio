"""Tests for Path Favorites junction sync + open_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.path_favorites.junction_sync import sync_junction_mirror
from tools.path_favorites.model import FavoriteNode, FavoritesTree
from tools.path_favorites.open_path import open_in_file_manager
from tools.path_favorites.placeholders import PlaceholderContext


def test_sync_creates_junctions(tmp_path: Path):
    real_a = tmp_path / "real" / "img"
    real_b = tmp_path / "real" / "cover"
    real_a.mkdir(parents=True)
    real_b.mkdir(parents=True)
    (real_a / "x.txt").write_text("a", encoding="utf-8")

    mirror = tmp_path / "mirror"
    tree = FavoritesTree(
        nodes=[
            FavoriteNode(
                id="bs",
                label="Book Studio",
                children=[
                    FavoriteNode(id="img", label="img", path=str(real_a)),
                    FavoriteNode(id="cover", label="kdp_cover", path=str(real_b)),
                    FavoriteNode(id="missing", label="fehlt", path=str(tmp_path / "nope")),
                ],
            )
        ]
    )
    ctx = PlaceholderContext(book_studio_root=tmp_path / "bs", userprofile=tmp_path)
    report = sync_junction_mirror(tree, ctx, mirror_root=mirror)
    assert not report.errors
    assert any("img" in c for c in report.created)
    link_img = mirror / "Book Studio" / "img"
    assert link_img.exists()
    assert (link_img / "x.txt").read_text(encoding="utf-8") == "a"
    assert any("fehlt" in s for s in report.skipped)


def test_sync_removes_stale_junction(tmp_path: Path):
    real = tmp_path / "real"
    real.mkdir()
    mirror = tmp_path / "mirror"
    ctx = PlaceholderContext(book_studio_root=tmp_path / "bs", userprofile=tmp_path)
    tree1 = FavoritesTree(
        nodes=[
            FavoriteNode(
                id="g",
                label="G",
                children=[FavoriteNode(id="a", label="A", path=str(real))],
            )
        ]
    )
    sync_junction_mirror(tree1, ctx, mirror_root=mirror)
    assert (mirror / "G" / "A").exists()

    tree2 = FavoritesTree(
        nodes=[
            FavoriteNode(
                id="g",
                label="G",
                children=[FavoriteNode(id="b", label="B", path=str(real))],
            )
        ]
    )
    report = sync_junction_mirror(tree2, ctx, mirror_root=mirror)
    assert (mirror / "G" / "B").exists()
    assert not (mirror / "G" / "A").exists()
    assert report.removed


def test_open_in_file_manager_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        open_in_file_manager(tmp_path / "missing")
