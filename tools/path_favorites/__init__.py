"""Path Favorites — JSON-driven folder shortcuts with optional junction mirror."""

from __future__ import annotations

from tools.path_favorites.actions import (
    ActionId,
    ActionPlan,
    FavoriteAction,
    resolve_favorite_actions,
)
from tools.path_favorites.badges import BadgeKind, FavoriteBadge, resolve_favorite_badge
from tools.path_favorites.drop_copy import (
    DropConflictPolicy,
    DropCopyResult,
    copy_paths_into_folder,
    unique_destination,
)
from tools.path_favorites.model import (
    FavoriteNode,
    FavoritesTree,
    ensure_user_favorites,
    load_favorites,
    resolve_node_path,
    save_favorites,
)
from tools.path_favorites.placeholders import PlaceholderContext, build_placeholder_context
from tools.path_favorites.pin import (
    RECENT_EXPORT_GROUP_ID,
    RECENT_EXPORT_GROUP_LABEL,
    PinResult,
    pin_path,
)

__all__ = [
    "ActionId",
    "ActionPlan",
    "BadgeKind",
    "DropConflictPolicy",
    "DropCopyResult",
    "FavoriteAction",
    "FavoriteBadge",
    "FavoriteNode",
    "FavoritesTree",
    "PinResult",
    "PlaceholderContext",
    "RECENT_EXPORT_GROUP_ID",
    "RECENT_EXPORT_GROUP_LABEL",
    "build_placeholder_context",
    "copy_paths_into_folder",
    "ensure_user_favorites",
    "load_favorites",
    "pin_path",
    "resolve_favorite_actions",
    "resolve_favorite_badge",
    "resolve_node_path",
    "save_favorites",
    "unique_destination",
]
