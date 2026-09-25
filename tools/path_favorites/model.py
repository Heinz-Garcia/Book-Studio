"""Load / save / resolve Path Favorites JSON (SSOT)."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from tools.path_favorites.placeholders import (
    PlaceholderContext,
    build_placeholder_context,
)

TOOL_DIR = Path(__file__).resolve().parent
DEFAULTS_PATH = TOOL_DIR / "favorites.defaults.json"
USER_FAVORITES_PATH = TOOL_DIR / "favorites.json"
SESSION_PATH = TOOL_DIR / "last_session.json"

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ENV_PERCENT_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")


@dataclass
class FavoriteNode:
    """One tree node: group (children only) or leaf (path template)."""

    id: str
    label: str
    path: str = ""
    children: list[FavoriteNode] = field(default_factory=list)

    @property
    def is_group(self) -> bool:
        return bool(self.children) and not str(self.path or "").strip()

    @property
    def is_leaf(self) -> bool:
        return bool(str(self.path or "").strip())

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
        }
        if str(self.path or "").strip():
            data["path"] = str(self.path).strip()
        if self.children:
            data["children"] = [c.to_dict() for c in self.children]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FavoriteNode:
        if not isinstance(data, dict):
            raise ValueError("Favoriten-Knoten muss ein Objekt sein.")
        nid = str(data.get("id") or "").strip()
        label = str(data.get("label") or "").strip()
        if not nid or not label:
            raise ValueError("Favoriten-Knoten braucht id und label.")
        kids_raw = data.get("children") or []
        children: list[FavoriteNode] = []
        if isinstance(kids_raw, list):
            for item in kids_raw:
                if isinstance(item, dict):
                    children.append(cls.from_dict(item))
        return cls(
            id=nid,
            label=label,
            path=str(data.get("path") or "").strip(),
            children=children,
        )


@dataclass
class FavoritesTree:
    version: int = 1
    mirror_root: str = "%USERPROFILE%/StudioFavoriten"
    nodes: list[FavoriteNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": int(self.version),
            "mirror_root": self.mirror_root,
            "nodes": [n.to_dict() for n in self.nodes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FavoritesTree:
        if not isinstance(data, dict):
            raise ValueError("favorites.json muss ein Objekt sein.")
        try:
            version = int(data.get("version", 1))
        except (TypeError, ValueError):
            version = 1
        mirror = str(
            data.get("mirror_root") or "%USERPROFILE%/StudioFavoriten"
        ).strip()
        nodes_raw = data.get("nodes") or []
        nodes: list[FavoriteNode] = []
        if isinstance(nodes_raw, list):
            for item in nodes_raw:
                if isinstance(item, dict):
                    nodes.append(FavoriteNode.from_dict(item))
        return cls(version=version, mirror_root=mirror, nodes=nodes)

    def iter_leaves(self) -> Iterable[FavoriteNode]:
        def walk(nodes: list[FavoriteNode]) -> Iterable[FavoriteNode]:
            for node in nodes:
                if node.is_leaf:
                    yield node
                if node.children:
                    yield from walk(node.children)

        yield from walk(self.nodes)

    def iter_groups(self) -> Iterable[FavoriteNode]:
        """Top-level and nested group nodes (no path)."""

        def walk(nodes: list[FavoriteNode]) -> Iterable[FavoriteNode]:
            for node in nodes:
                if not node.is_leaf:
                    yield node
                if node.children:
                    yield from walk(node.children)

        yield from walk(self.nodes)

    def find_by_id(self, node_id: str) -> FavoriteNode | None:
        want = str(node_id or "").strip()
        if not want:
            return None

        def walk(nodes: list[FavoriteNode]) -> FavoriteNode | None:
            for node in nodes:
                if node.id == want:
                    return node
                found = walk(node.children)
                if found is not None:
                    return found
            return None

        return walk(self.nodes)

    def all_ids(self) -> set[str]:
        out: set[str] = set()

        def walk(nodes: list[FavoriteNode]) -> None:
            for node in nodes:
                out.add(node.id)
                walk(node.children)

        walk(self.nodes)
        return out


def make_unique_id(base: str, existing: set[str]) -> str:
    """Slug id from label; append -2, -3, … if needed."""
    raw = (base or "eintrag").strip().lower()
    chars: list[str] = []
    for ch in raw:
        if ch.isalnum():
            chars.append(ch)
        elif ch in "-_ ":
            chars.append("-")
    stem = "".join(chars).strip("-") or "eintrag"
    stem = stem[:48]
    candidate = stem
    n = 2
    while candidate in existing:
        candidate = f"{stem}-{n}"
        n += 1
    return candidate


def path_as_template(path: Path, ctx: PlaceholderContext) -> str:
    """Prefer a placeholder form when the path sits under a known root."""
    resolved = Path(path).expanduser().resolve()
    mapping = ctx.as_mapping()
    # Longest root first so active_book wins over content_root etc.
    candidates: list[tuple[str, Path]] = []
    for key, value in mapping.items():
        if key in ("userprofile", "USERPROFILE"):
            continue
        try:
            root = Path(value).expanduser().resolve()
        except OSError:
            continue
        candidates.append((key, root))
    candidates.sort(key=lambda kv: len(str(kv[1])), reverse=True)
    for key, root in candidates:
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        rel_s = rel.as_posix()
        return f"{{{key}}}/{rel_s}" if rel_s and rel_s != "." else f"{{{key}}}"
    return str(resolved)


def add_leaf(
    tree: FavoritesTree,
    *,
    parent_id: str | None,
    label: str,
    path: str,
    node_id: str | None = None,
) -> FavoriteNode:
    """Append a leaf under ``parent_id`` (or as top-level if None)."""
    label_s = str(label or "").strip()
    path_s = str(path or "").strip()
    if not label_s or not path_s:
        raise ValueError("Label und Pfad sind Pflicht.")
    existing = tree.all_ids()
    nid = str(node_id or "").strip() or make_unique_id(label_s, existing)
    if nid in existing:
        nid = make_unique_id(nid, existing)
    leaf = FavoriteNode(id=nid, label=label_s, path=path_s)
    if parent_id:
        parent = tree.find_by_id(parent_id)
        if parent is None:
            raise ValueError(f"Gruppe nicht gefunden: {parent_id}")
        if parent.is_leaf:
            raise ValueError("Ziel ist kein Gruppenknoten.")
        parent.children.append(leaf)
    else:
        tree.nodes.append(leaf)
    return leaf


def add_group(
    tree: FavoritesTree,
    *,
    parent_id: str | None,
    label: str,
    node_id: str | None = None,
) -> FavoriteNode:
    label_s = str(label or "").strip()
    if not label_s:
        raise ValueError("Gruppenname ist Pflicht.")
    existing = tree.all_ids()
    nid = str(node_id or "").strip() or make_unique_id(label_s, existing)
    if nid in existing:
        nid = make_unique_id(nid, existing)
    group = FavoriteNode(id=nid, label=label_s, children=[])
    if parent_id:
        parent = tree.find_by_id(parent_id)
        if parent is None:
            raise ValueError(f"Gruppe nicht gefunden: {parent_id}")
        if parent.is_leaf:
            raise ValueError("Ziel ist kein Gruppenknoten.")
        parent.children.append(group)
    else:
        tree.nodes.append(group)
    return group


def remove_by_id(tree: FavoritesTree, node_id: str) -> bool:
    """Remove node (and subtree). Returns True if found."""
    want = str(node_id or "").strip()
    if not want:
        return False

    def walk(nodes: list[FavoriteNode]) -> bool:
        for i, node in enumerate(nodes):
            if node.id == want:
                del nodes[i]
                return True
            if walk(node.children):
                return True
        return False

    return walk(tree.nodes)


def rename_node(tree: FavoritesTree, node_id: str, new_label: str) -> bool:
    """Change display label; returns False if missing or empty label."""
    label = str(new_label or "").strip()
    if not label:
        return False
    node = tree.find_by_id(node_id)
    if node is None:
        return False
    node.label = label
    return True


def _sibling_list(
    tree: FavoritesTree, node_id: str
) -> tuple[list[FavoriteNode], int] | None:
    """Return (sibling list, index) for ``node_id``, or None."""
    want = str(node_id or "").strip()
    if not want:
        return None

    def walk(nodes: list[FavoriteNode]) -> tuple[list[FavoriteNode], int] | None:
        for i, node in enumerate(nodes):
            if node.id == want:
                return nodes, i
            found = walk(node.children)
            if found is not None:
                return found
        return None

    return walk(tree.nodes)


def move_node(tree: FavoritesTree, node_id: str, delta: int) -> bool:
    """Move a node among its siblings by ``delta`` (−1 up, +1 down).

    Returns True if the order changed.
    """
    if delta == 0:
        return False
    found = _sibling_list(tree, node_id)
    if found is None:
        return False
    siblings, index = found
    new_index = index + int(delta)
    if new_index < 0 or new_index >= len(siblings):
        return False
    siblings[index], siblings[new_index] = siblings[new_index], siblings[index]
    return True


def can_move_node(tree: FavoritesTree, node_id: str, delta: int) -> bool:
    """True if ``move_node`` would succeed without mutating."""
    if delta == 0:
        return False
    found = _sibling_list(tree, node_id)
    if found is None:
        return False
    siblings, index = found
    new_index = index + int(delta)
    return 0 <= new_index < len(siblings)


_BARE_PLACEHOLDER_RE = re.compile(r"^\{[^{}]+\}$")


def suggest_group_root_path(
    tree: FavoritesTree,
    group_id: str,
    ctx: PlaceholderContext | Mapping[str, str],
) -> Path | None:
    """Resolved folder to prefill when adding a path under ``group_id``.

    Prefers a direct leaf whose template is a bare ``{placeholder}`` (group
    root), then the shortest resolvable leaf path under the group.
    """
    group = tree.find_by_id(group_id)
    if group is None or group.is_leaf:
        return None

    bare: list[tuple[int, Path]] = []
    others: list[tuple[int, Path]] = []
    for child in group.children:
        if not child.is_leaf:
            continue
        resolved = resolve_node_path(child, ctx)
        if resolved is None:
            continue
        entry = (len(str(resolved)), resolved)
        if _BARE_PLACEHOLDER_RE.match(str(child.path or "").strip()):
            bare.append(entry)
        else:
            others.append(entry)
    if bare:
        bare.sort(key=lambda t: t[0])
        return bare[0][1]
    if others:
        others.sort(key=lambda t: t[0])
        return others[0][1]
    for child in group.children:
        if child.is_leaf:
            continue
        nested = suggest_group_root_path(tree, child.id, ctx)
        if nested is not None:
            return nested
    return None


def node_chain(tree: FavoritesTree, node_id: str) -> list[FavoriteNode] | None:
    """Root→…→node inclusive, or None if not found."""
    want = str(node_id or "").strip()
    if not want:
        return None

    def walk(
        nodes: list[FavoriteNode], trail: list[FavoriteNode]
    ) -> list[FavoriteNode] | None:
        for node in nodes:
            here = trail + [node]
            if node.id == want:
                return here
            found = walk(node.children, here)
            if found is not None:
                return found
        return None

    return walk(tree.nodes, [])


def expand_env_and_placeholders(
    template: str,
    ctx: PlaceholderContext | Mapping[str, str],
) -> str:
    """Expand ``%ENV%`` and ``{placeholder}``; unknown tokens stay empty."""
    text = str(template or "").strip()
    if not text:
        return ""
    mapping = ctx.as_mapping() if isinstance(ctx, PlaceholderContext) else dict(ctx)

    def env_sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in mapping and str(mapping[key]).strip():
            return mapping[key]
        env_val = os.environ.get(key, "")
        return env_val if str(env_val).strip() else match.group(0)

    text = _ENV_PERCENT_RE.sub(env_sub, text)

    def ph_sub(match: re.Match[str]) -> str:
        key = match.group(1)
        val = mapping.get(key, "")
        # Keep token if unknown/empty so resolve_path_template can reject it.
        return str(val) if str(val).strip() else match.group(0)

    text = _PLACEHOLDER_RE.sub(ph_sub, text)
    return text.strip()


def resolve_path_template(
    template: str,
    ctx: PlaceholderContext | Mapping[str, str],
) -> Path | None:
    """Return resolved Path, or None if template empty / unresolved."""
    expanded = expand_env_and_placeholders(template, ctx)
    if not expanded:
        return None
    # Unresolved leftover placeholders → invalid
    if "{" in expanded and "}" in expanded:
        return None
    if "%" in expanded and _ENV_PERCENT_RE.search(expanded):
        return None
    return Path(expanded).expanduser()


def resolve_node_path(
    node: FavoriteNode,
    ctx: PlaceholderContext | Mapping[str, str],
) -> Path | None:
    if not node.is_leaf:
        return None
    return resolve_path_template(node.path, ctx)


def resolve_mirror_root(
    tree: FavoritesTree,
    ctx: PlaceholderContext | Mapping[str, str],
) -> Path:
    resolved = resolve_path_template(tree.mirror_root, ctx)
    if resolved is None:
        return Path(os.path.expanduser("~")) / "StudioFavoriten"
    return resolved


def load_favorites(path: Path | None = None) -> FavoritesTree:
    target = path or USER_FAVORITES_PATH
    raw = json.loads(Path(target).read_text(encoding="utf-8"))
    return FavoritesTree.from_dict(raw)


def save_favorites(tree: FavoritesTree, path: Path | None = None) -> Path:
    target = Path(path or USER_FAVORITES_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(tree.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def ensure_user_favorites(
    *,
    user_path: Path | None = None,
    defaults_path: Path | None = None,
) -> Path:
    """Copy defaults to user favorites.json on first run; return user path."""
    dest = Path(user_path or USER_FAVORITES_PATH)
    if dest.is_file():
        return dest
    src = Path(defaults_path or DEFAULTS_PATH)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        shutil.copyfile(src, dest)
    else:
        save_favorites(FavoritesTree(), path=dest)
    return dest


def load_or_init_favorites(
    *,
    user_path: Path | None = None,
    defaults_path: Path | None = None,
) -> FavoritesTree:
    path = ensure_user_favorites(user_path=user_path, defaults_path=defaults_path)
    return load_favorites(path)


def load_session(path: Path | None = None) -> dict[str, Any]:
    target = Path(path or SESSION_PATH)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_session(data: dict[str, Any], path: Path | None = None) -> None:
    target = Path(path or SESSION_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# Re-export for callers that only import model
build_context = build_placeholder_context


__all__ = [
    "DEFAULTS_PATH",
    "SESSION_PATH",
    "TOOL_DIR",
    "USER_FAVORITES_PATH",
    "FavoriteNode",
    "FavoritesTree",
    "add_group",
    "add_leaf",
    "build_context",
    "can_move_node",
    "ensure_user_favorites",
    "expand_env_and_placeholders",
    "load_favorites",
    "load_or_init_favorites",
    "load_session",
    "make_unique_id",
    "move_node",
    "node_chain",
    "path_as_template",
    "remove_by_id",
    "rename_node",
    "resolve_mirror_root",
    "resolve_node_path",
    "resolve_path_template",
    "save_favorites",
    "save_session",
    "suggest_group_root_path",
]
