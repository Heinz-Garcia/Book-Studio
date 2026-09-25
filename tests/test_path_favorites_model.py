"""Unit tests for Path Favorites model + placeholders."""

from __future__ import annotations

import json
from pathlib import Path


from tools.path_favorites.model import (
    FavoriteNode,
    FavoritesTree,
    ensure_user_favorites,
    expand_env_and_placeholders,
    load_favorites,
    resolve_mirror_root,
    resolve_node_path,
    resolve_path_template,
    save_favorites,
)
from tools.path_favorites.placeholders import (
    PlaceholderContext,
    discover_grammargraph_root,
)


def test_expand_placeholders_and_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    ctx = PlaceholderContext(
        book_studio_root=tmp_path / "bs",
        grammargraph_root=tmp_path / "gg",
        active_book=tmp_path / "book",
        userprofile=tmp_path / "user",
    )
    mirror = expand_env_and_placeholders("%USERPROFILE%/StudioFavoriten", ctx)
    assert Path(mirror) == tmp_path / "user" / "StudioFavoriten"
    book_img = expand_env_and_placeholders("{active_book}/img", ctx)
    assert Path(book_img) == tmp_path / "book" / "img"


def test_resolve_path_template_missing_placeholder():
    ctx = PlaceholderContext(book_studio_root=Path("C:/bs"))
    assert resolve_path_template("{active_book}/img", ctx) is None


def test_favorites_roundtrip(tmp_path: Path):
    tree = FavoritesTree(
        mirror_root="%USERPROFILE%/StudioFavoriten",
        nodes=[
            FavoriteNode(
                id="bs",
                label="Book Studio",
                children=[
                    FavoriteNode(
                        id="img",
                        label="img",
                        path="{active_book}/img",
                    )
                ],
            )
        ],
    )
    path = tmp_path / "favorites.json"
    save_favorites(tree, path)
    loaded = load_favorites(path)
    assert loaded.nodes[0].label == "Book Studio"
    assert list(loaded.iter_leaves())[0].path == "{active_book}/img"


def test_ensure_user_favorites_copies_defaults(tmp_path: Path):
    defaults = tmp_path / "defaults.json"
    defaults.write_text(
        json.dumps(
            {
                "version": 1,
                "mirror_root": "%USERPROFILE%/X",
                "nodes": [{"id": "a", "label": "A", "path": "{book_studio_root}"}],
            }
        ),
        encoding="utf-8",
    )
    user = tmp_path / "favorites.json"
    got = ensure_user_favorites(user_path=user, defaults_path=defaults)
    assert got == user
    assert user.is_file()
    # second call does not overwrite
    user.write_text('{"version":1,"mirror_root":"keep","nodes":[]}\n', encoding="utf-8")
    ensure_user_favorites(user_path=user, defaults_path=defaults)
    assert "keep" in user.read_text(encoding="utf-8")


def test_resolve_node_and_mirror(tmp_path: Path):
    ctx = PlaceholderContext(
        book_studio_root=tmp_path / "bs",
        active_book=tmp_path / "Band",
        userprofile=tmp_path / "home",
    )
    (tmp_path / "Band" / "img").mkdir(parents=True)
    node = FavoriteNode(id="i", label="img", path="{active_book}/img")
    resolved = resolve_node_path(node, ctx)
    assert resolved == (tmp_path / "Band" / "img")
    tree = FavoritesTree(mirror_root="%USERPROFILE%/StudioFavoriten")
    mirror = resolve_mirror_root(tree, ctx)
    assert mirror == tmp_path / "home" / "StudioFavoriten"


def test_discover_grammargraph_sibling(tmp_path: Path):
    bs = tmp_path / "Book_Studio_Unleashed"
    gg = tmp_path / "GrammarGraph"
    bs.mkdir()
    gg.mkdir()
    assert discover_grammargraph_root(book_studio_root=bs) == gg.resolve()


def test_add_leaf_remove_and_path_template(tmp_path: Path):
    from tools.path_favorites.model import (
        add_group,
        add_leaf,
        can_move_node,
        move_node,
        path_as_template,
        remove_by_id,
        rename_node,
        suggest_group_root_path,
    )
    from tools.path_favorites.junction_sync import mirror_path_for_node

    bs = tmp_path / "bs"
    book = bs / "Band"
    img = book / "img"
    img.mkdir(parents=True)
    ctx = PlaceholderContext(
        book_studio_root=bs,
        active_book=book,
        userprofile=tmp_path / "home",
    )
    assert path_as_template(img, ctx) == "{active_book}/img"

    tree = FavoritesTree()
    g = add_group(tree, parent_id=None, label="Book Studio")
    g2 = add_group(tree, parent_id=None, label="Andere")
    assert can_move_node(tree, g2.id, -1)
    assert move_node(tree, g2.id, -1)
    assert [n.id for n in tree.nodes] == [g2.id, g.id]
    assert not can_move_node(tree, g2.id, -1)
    assert move_node(tree, g2.id, 1)
    assert [n.id for n in tree.nodes] == [g.id, g2.id]

    add_leaf(
        tree,
        parent_id=g.id,
        label="Repo",
        path="{book_studio_root}",
    )
    leaf = add_leaf(
        tree,
        parent_id=g.id,
        label="img",
        path="{active_book}/img",
    )
    assert leaf.id
    assert suggest_group_root_path(tree, g.id, ctx) == bs
    assert list(tree.iter_leaves())[0].path == "{book_studio_root}"
    assert rename_node(tree, leaf.id, "Cover-img")
    assert tree.find_by_id(leaf.id).label == "Cover-img"
    mirror = mirror_path_for_node(tree, ctx, leaf.id, mirror_root=tmp_path / "m")
    assert mirror == tmp_path / "m" / "Book Studio" / "Cover-img"
    assert remove_by_id(tree, leaf.id)
    assert len(list(tree.iter_leaves())) == 1
