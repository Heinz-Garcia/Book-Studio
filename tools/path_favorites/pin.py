"""Pin absolute paths into the Path Manager (user favorites.json)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tools.path_favorites.model import (
    USER_FAVORITES_PATH,
    FavoriteNode,
    FavoritesTree,
    add_group,
    add_leaf,
    ensure_user_favorites,
    load_favorites,
    save_favorites,
)

RECENT_EXPORT_GROUP_ID = "zuletzt-exportiert"
RECENT_EXPORT_GROUP_LABEL = "Zuletzt exportiert"


@dataclass(frozen=True)
class PinResult:
    """Outcome of pinning a path into favorites."""

    node: FavoriteNode
    created: bool
    group_id: str
    favorites_path: Path


def _normalize_path(path: Path | str) -> Path:
    p = Path(path).expanduser()
    try:
        return p.resolve()
    except OSError:
        return p.absolute()


def _paths_equal(a: Path | str, b: Path | str) -> bool:
    try:
        return _normalize_path(a) == _normalize_path(b)
    except OSError:
        return Path(a).as_posix().lower() == Path(b).as_posix().lower()


def ensure_recent_export_group(
    tree: FavoritesTree,
    *,
    group_id: str = RECENT_EXPORT_GROUP_ID,
    group_label: str = RECENT_EXPORT_GROUP_LABEL,
) -> FavoriteNode:
    """Return the „Zuletzt exportiert“ group, creating it at top level if missing."""
    existing = tree.find_by_id(group_id)
    if existing is not None:
        if existing.is_leaf:
            raise ValueError(
                f"Knoten „{group_id}“ ist ein Pfad, keine Gruppe — "
                "bitte im Pfad-Manager umbenennen oder löschen."
            )
        if group_label and existing.label != group_label:
            existing.label = group_label
        return existing
    return add_group(
        tree,
        parent_id=None,
        label=group_label,
        node_id=group_id,
    )


def find_leaf_by_path(
    tree: FavoritesTree,
    path: Path | str,
    *,
    parent_id: str | None = None,
) -> FavoriteNode | None:
    """First leaf whose stored path matches ``path`` (optionally under ``parent_id``)."""
    want = _normalize_path(path)
    scope: list[FavoriteNode]
    if parent_id:
        parent = tree.find_by_id(parent_id)
        if parent is None or parent.is_leaf:
            return None
        scope = list(parent.children)
    else:
        scope = list(tree.iter_leaves())

    def walk(nodes: list[FavoriteNode]) -> FavoriteNode | None:
        for node in nodes:
            if node.is_leaf and _paths_equal(node.path, want):
                return node
            if node.children:
                found = walk(node.children)
                if found is not None:
                    return found
        return None

    return walk(scope)


def pin_path(
    *,
    label: str,
    path: Path | str,
    favorites_path: Path | None = None,
    group_id: str = RECENT_EXPORT_GROUP_ID,
    group_label: str = RECENT_EXPORT_GROUP_LABEL,
) -> PinResult:
    """Add or update a leaf under „Zuletzt exportiert“ and save favorites.json.

    Idempotent: same resolved path under the group updates the label only.
    """
    label_s = str(label or "").strip()
    if not label_s:
        raise ValueError("Label ist Pflicht.")
    target = _normalize_path(path)
    path_s = str(target)
    if not path_s:
        raise ValueError("Pfad ist Pflicht.")

    dest = Path(favorites_path or USER_FAVORITES_PATH)
    ensure_user_favorites(user_path=dest)
    tree = load_favorites(dest)
    group = ensure_recent_export_group(
        tree, group_id=group_id, group_label=group_label
    )
    existing = find_leaf_by_path(tree, target, parent_id=group.id)
    if existing is not None:
        existing.label = label_s
        existing.path = path_s
        save_favorites(tree, path=dest)
        return PinResult(
            node=existing,
            created=False,
            group_id=group.id,
            favorites_path=dest,
        )
    leaf = add_leaf(
        tree,
        parent_id=group.id,
        label=label_s,
        path=path_s,
    )
    save_favorites(tree, path=dest)
    return PinResult(
        node=leaf,
        created=True,
        group_id=group.id,
        favorites_path=dest,
    )


__all__ = [
    "RECENT_EXPORT_GROUP_ID",
    "RECENT_EXPORT_GROUP_LABEL",
    "PinResult",
    "ensure_recent_export_group",
    "find_leaf_by_path",
    "pin_path",
]
