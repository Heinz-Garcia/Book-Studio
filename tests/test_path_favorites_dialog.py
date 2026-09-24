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

    from PySide6.QtWidgets import QApplication, QToolButton

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
        assert hasattr(dlg, "werkbank_panel")
        assert dlg.werkbank_panel.objectName() == "pathFavoritesWerkbank"
        assert any(
            b.objectName() == "handbookInfoButton"
            for b in dlg.findChildren(QToolButton)
        )
        dlg.tree.setCurrentItem(leaf)
        assert dlg._action_plan is not None
        assert dlg._action_buttons
        assert any(
            b.property("action_id") == "open_explorer" for b in dlg._action_buttons
        )
    finally:
        dlg.close()


def test_path_favorites_werkbank_kdp_primary(monkeypatch, tmp_path: Path):
    """Auswahl von export/kdp_cover → Cover-Designer als Primäraktion."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    book = tmp_path / "book"
    kdp = book / "export" / "kdp_cover"
    kdp.mkdir(parents=True)
    fav = tmp_path / "favorites.json"
    save_favorites(
        FavoritesTree(
            nodes=[
                FavoriteNode(
                    id="kdp",
                    label="KDP Cover",
                    path=str(kdp),
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

    from tools.path_favorites.actions import ActionId
    from ui_qt.dialogs.path_favorites_dialog import PathFavoritesDialog
    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    ctx = PlaceholderContext(
        book_studio_root=tmp_path,
        active_book=book,
        userprofile=tmp_path,
    )
    dlg = PathFavoritesDialog(None, placeholder_context=ctx)
    try:
        leaf = dlg.tree.topLevelItem(0)
        assert leaf is not None
        dlg.tree.setCurrentItem(leaf)
        plan = dlg._action_plan
        assert plan is not None
        assert plan.rule == "kdp_cover"
        assert plan.primary is not None
        assert plan.primary.id == ActionId.OPEN_KDP_COVER
        ids = [b.property("action_id") for b in dlg._action_buttons]
        assert "open_kdp_cover" in ids
        assert "open_explorer" in ids

        opened: list[str] = []
        monkeypatch.setattr(
            dlg,
            "_open_kdp_cover_tool",
            lambda: opened.append("kdp"),
        )
        dlg._execute_action(ActionId.OPEN_KDP_COVER)
        assert opened == ["kdp"]
        assert "kein Layout" in dlg.werkbank_badge.text() or "Layout" in dlg.werkbank_badge.text()
        assert "●" in leaf.text(0)
    finally:
        dlg.close()


def test_path_favorites_drop_copies_into_folder(monkeypatch, tmp_path: Path):
    """Drop auf Blatt → Copy in Zielordner (ohne Konflikt-Dialog)."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    dest = tmp_path / "dest_folder"
    dest.mkdir()
    fav = tmp_path / "favorites.json"
    save_favorites(
        FavoritesTree(
            nodes=[
                FavoriteNode(
                    id="dest",
                    label="Ablage",
                    path=str(dest),
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
        leaf = dlg.tree.topLevelItem(0)
        assert leaf is not None
        dlg.tree.setCurrentItem(leaf)
        src = tmp_path / "drop_me.txt"
        src.write_text("payload", encoding="utf-8")
        dlg._on_paths_dropped(leaf, [src])
        assert (dest / "drop_me.txt").read_text(encoding="utf-8") == "payload"
        assert "ok" in dlg.werkbank_badge.text().lower() or "●" in dlg.werkbank_badge.text()
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


def test_path_favorites_expand_state_persists(monkeypatch, tmp_path: Path):
    """Auf-/Zuklappstand der Gruppen bleibt in last_session.json."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    fav = tmp_path / "favorites.json"
    session = tmp_path / "last_session.json"
    save_favorites(
        FavoritesTree(
            nodes=[
                FavoriteNode(
                    id="outer",
                    label="Aussen",
                    children=[
                        FavoriteNode(
                            id="inner",
                            label="Innen",
                            children=[
                                FavoriteNode(
                                    id="leaf",
                                    label="Repo",
                                    path=str(tmp_path),
                                )
                            ],
                        )
                    ],
                ),
                FavoriteNode(
                    id="other",
                    label="Andere",
                    children=[
                        FavoriteNode(
                            id="leaf2",
                            label="Tmp",
                            path=str(tmp_path),
                        )
                    ],
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

    def _load_sess(path=None):
        if not session.is_file():
            return {}
        import json

        data = json.loads(session.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _save_sess(data, path=None):
        import json

        session.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "ui_qt.dialogs.path_favorites_dialog.load_session",
        _load_sess,
    )
    monkeypatch.setattr(
        "ui_qt.dialogs.path_favorites_dialog.save_session",
        _save_sess,
    )

    from PySide6.QtWidgets import QApplication

    from ui_qt.dialogs.path_favorites_dialog import PathFavoritesDialog
    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    ctx = PlaceholderContext(book_studio_root=tmp_path, userprofile=tmp_path)
    dlg = PathFavoritesDialog(None, placeholder_context=ctx)
    try:
        outer = dlg.tree.topLevelItem(0)
        other = dlg.tree.topLevelItem(1)
        assert outer is not None and other is not None
        inner = outer.child(0)
        assert inner is not None
        # User-Stand: Andere zu, Aussen + Innen auf.
        other.setExpanded(False)
        outer.setExpanded(True)
        inner.setExpanded(True)
        ids = dlg._collect_expanded_ids()
        assert "outer" in ids
        assert "inner" in ids
        assert "other" not in ids
    finally:
        dlg.close()

    import json

    raw = json.loads(session.read_text(encoding="utf-8"))
    assert "outer" in raw["expanded_ids"]
    assert "inner" in raw["expanded_ids"]
    assert "other" not in raw["expanded_ids"]

    dlg2 = PathFavoritesDialog(None, placeholder_context=ctx)
    try:
        outer2 = dlg2.tree.topLevelItem(0)
        other2 = dlg2.tree.topLevelItem(1)
        assert outer2 is not None and other2 is not None
        assert outer2.isExpanded()
        assert not other2.isExpanded()
        assert outer2.child(0) is not None
        assert outer2.child(0).isExpanded()
    finally:
        dlg2.close()
