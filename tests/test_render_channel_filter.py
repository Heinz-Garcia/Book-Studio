"""Tests für tools.distribution.render_filter.filter_tree_for_channel."""

from __future__ import annotations

from tools.distribution.render_filter import filter_tree_for_channel


def _leaf(path: str) -> dict:
    return {"path": path, "title": path, "children": []}


def test_no_excluded_paths_returns_same_tree():
    tree = [_leaf("index.md"), _leaf("content/chapter.md")]
    assert filter_tree_for_channel(tree, []) == tree
    assert filter_tree_for_channel(tree, set()) == tree


def test_excludes_top_level_leaf():
    tree = [_leaf("index.md"), _leaf("content/Deckblatt.md"), _leaf("content/chapter.md")]
    result = filter_tree_for_channel(tree, ["content/Deckblatt.md"])
    assert [n["path"] for n in result] == ["index.md", "content/chapter.md"]


def test_excludes_nested_leaf_and_prunes_empty_part():
    tree = [
        _leaf("index.md"),
        {
            "path": "PART:Vorspann",
            "title": "Vorspann",
            "children": [_leaf("content/Deckblatt.md")],
        },
        _leaf("content/chapter.md"),
    ]
    result = filter_tree_for_channel(tree, ["content/Deckblatt.md"])
    assert [n["path"] for n in result] == ["index.md", "content/chapter.md"]


def test_keeps_part_with_remaining_children():
    tree = [
        {
            "path": "PART:Vorspann",
            "title": "Vorspann",
            "children": [_leaf("content/Deckblatt.md"), _leaf("content/Vorwort.md")],
        },
    ]
    result = filter_tree_for_channel(tree, ["content/Deckblatt.md"])
    assert len(result) == 1
    assert [n["path"] for n in result[0]["children"]] == ["content/Vorwort.md"]


def test_backslash_paths_normalized():
    tree = [_leaf("content/Deckblatt.md")]
    result = filter_tree_for_channel(tree, ["content\\Deckblatt.md"])
    assert result == []


def test_no_op_when_path_not_present():
    tree = [_leaf("index.md")]
    result = filter_tree_for_channel(tree, ["content/does_not_exist.md"])
    assert result == tree
