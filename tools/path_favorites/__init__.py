"""Path Favorites — JSON-driven folder shortcuts with optional junction mirror."""

from __future__ import annotations

from tools.path_favorites.model import (
    FavoriteNode,
    FavoritesTree,
    ensure_user_favorites,
    load_favorites,
    resolve_node_path,
    save_favorites,
)
from tools.path_favorites.placeholders import PlaceholderContext, build_placeholder_context

__all__ = [
    "FavoriteNode",
    "FavoritesTree",
    "PlaceholderContext",
    "build_placeholder_context",
    "ensure_user_favorites",
    "load_favorites",
    "resolve_node_path",
    "save_favorites",
]
