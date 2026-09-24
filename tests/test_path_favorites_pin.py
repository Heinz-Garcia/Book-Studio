"""Tests for Path Manager pin helper (Zuletzt exportiert)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.path_favorites.model import FavoritesTree, load_favorites, save_favorites
from tools.path_favorites.pin import (
    RECENT_EXPORT_GROUP_ID,
    RECENT_EXPORT_GROUP_LABEL,
    find_leaf_by_path,
    pin_path,
)


def test_pin_path_creates_group_and_leaf(tmp_path: Path) -> None:
    fav = tmp_path / "favorites.json"
    save_favorites(FavoritesTree(), path=fav)
    target = tmp_path / "covers" / "book_kdp_wrap.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"%PDF")

    result = pin_path(
        label="KDP Druck · book",
        path=target,
        favorites_path=fav,
    )
    assert result.created is True
    assert result.group_id == RECENT_EXPORT_GROUP_ID
    tree = load_favorites(fav)
    group = tree.find_by_id(RECENT_EXPORT_GROUP_ID)
    assert group is not None
    assert group.label == RECENT_EXPORT_GROUP_LABEL
    assert not group.is_leaf
    assert len(group.children) == 1
    assert group.children[0].label == "KDP Druck · book"
    assert Path(group.children[0].path).resolve() == target.resolve()


def test_pin_path_idempotent_updates_label(tmp_path: Path) -> None:
    fav = tmp_path / "favorites.json"
    save_favorites(FavoritesTree(), path=fav)
    target = tmp_path / "out" / "layout.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

    first = pin_path(label="Alt", path=target, favorites_path=fav)
    second = pin_path(label="Neu · Label", path=target, favorites_path=fav)
    assert first.created is True
    assert second.created is False
    assert second.node.id == first.node.id
    tree = load_favorites(fav)
    group = tree.find_by_id(RECENT_EXPORT_GROUP_ID)
    assert group is not None
    assert len(group.children) == 1
    assert group.children[0].label == "Neu · Label"
    found = find_leaf_by_path(tree, target, parent_id=RECENT_EXPORT_GROUP_ID)
    assert found is not None
    assert found.label == "Neu · Label"


def test_pin_path_rejects_empty_label(tmp_path: Path) -> None:
    fav = tmp_path / "favorites.json"
    save_favorites(FavoritesTree(), path=fav)
    with pytest.raises(ValueError, match="Label"):
        pin_path(label="  ", path=tmp_path / "x", favorites_path=fav)
