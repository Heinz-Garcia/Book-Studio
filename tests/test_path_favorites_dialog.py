"""Offscreen smoke for Path Favorites dialog."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.path_favorites.model import FavoriteNode, FavoritesTree, load_favorites, save_favorites
from tools.path_favorites.placeholders import PlaceholderContext


def test_path_favorites_dialog_smoke(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    fav = tmp_path / "favorites.json"
    save_favorites(
        FavoritesTree(
            nodes=[
                FavoriteNode(
                    id="bs",
                    label="Book Studio",
                    children=[
                        FavoriteNode(
                            id="root",
                            label="Repo",
                            path=str(tmp_path),
                        )
                    ],
                )
            ]
        ),
        fav,
    )
    monkeypatch.setattr(
        "ui_qt.dialogs.path_favorites_dialog.USER_FAVORITES_PATH",
        fav,
    )
    monkeypatch.setattr(
        "ui_qt.dialogs.path_favorites_dialog.ensure_user_favorites",
        lambda **_k: fav,
    )
    monkeypatch.setattr(
        "ui_qt.dialogs.path_favorites_dialog.load_favorites",
        lambda path=None: load_favorites(path or fav),
    )

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.path_favorites_dialog import PathFavoritesDialog
    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    ctx = PlaceholderContext(book_studio_root=tmp_path, userprofile=tmp_path)
    dlg = PathFavoritesDialog(None, placeholder_context=ctx)
    try:
        assert dlg.tree.topLevelItemCount() == 1
        root = dlg.tree.topLevelItem(0)
        assert root is not None
        assert root.childCount() == 1
        leaf = root.child(0)
        assert leaf is not None
        assert "Repo" in leaf.text(0)
    finally:
        dlg.close()


def test_path_favorites_suggest_root_and_group_move(monkeypatch, tmp_path: Path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    bs = tmp_path / "BookStudio"
    bs.mkdir()
    fav = tmp_path / "favorites.json"
    save_favorites(
        FavoritesTree(
            nodes=[
                FavoriteNode(
                    id="g1",
                    label="Erste",
                    children=[
                        FavoriteNode(id="root1", label="Root", path="{book_studio_root}"),
                    ],
                ),
                FavoriteNode(
                    id="g2",
                    label="Zweite",
                    children=[],
                ),
            ]
        ),
        fav,
    )
    monkeypatch.setattr(
        "ui_qt.dialogs.path_favorites_dialog.USER_FAVORITES_PATH",
        fav,
    )
    monkeypatch.setattr(
        "ui_qt.dialogs.path_favorites_dialog.ensure_user_favorites",
        lambda **_k: fav,
    )
    monkeypatch.setattr(
        "ui_qt.dialogs.path_favorites_dialog.load_favorites",
        lambda path=None: load_favorites(path or fav),
    )
    monkeypatch.setattr(
        "ui_qt.dialogs.path_favorites_dialog.save_favorites",
        lambda tree, path=None: save_favorites(tree, path or fav),
    )

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.path_favorites_dialog import PathFavoritesDialog
    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    ctx = PlaceholderContext(book_studio_root=bs, userprofile=tmp_path)
    dlg = PathFavoritesDialog(None, placeholder_context=ctx)
    try:
        assert dlg._suggest_path_for_parent("g1") == str(bs)
        assert dlg.tree.topLevelItem(0).text(0) == "Erste"
        dlg.tree.setCurrentItem(dlg.tree.topLevelItem(1))
        assert dlg.btn_group_up.isEnabled()
        dlg._move_selected_group(-1)
        assert dlg.tree.topLevelItem(0).text(0) == "Zweite"
        loaded = load_favorites(fav)
        assert [n.id for n in loaded.nodes] == ["g2", "g1"]
    finally:
        dlg.close()
