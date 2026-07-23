"""Toolkit-agnostische Buchstruktur-Operationen (Phase 2).

Arbeitet auf Listen von Knoten-Dicts im Engine-Format::

    {"path": "content/…", "title": "…", "children": [...]}

Entspricht der Logik von ``tree_book.move`` / Indent / Outdent in der Tk-UI,
ohne Tk-Abhängigkeit.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Iterable, Optional

Node = dict[str, Any]
Tree = list[Node]
# (sibling_list, index, parent_node)
Location = tuple[Tree, int, Optional[Node]]


def is_technical_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").strip()
    return normalized in {"content", "content/"}


def chapters_to_display_tree(
    chapters: Iterable[dict[str, Any]],
    title_registry: Optional[dict[str, str]] = None,
) -> Tree:
    """Filtert ``index.md`` und technische Knoten; Titel aus Registry wenn möglich."""
    registry = title_registry or {}
    result: Tree = []
    for item in chapters:
        path = str(item.get("path") or "")
        children_raw = item.get("children") or []
        if path == "index.md":
            continue
        if is_technical_path(path):
            result.extend(chapters_to_display_tree(children_raw, registry))
            continue
        title = registry.get(path) or item.get("title") or path
        result.append(
            {
                "path": path,
                "title": title,
                "children": chapters_to_display_tree(children_raw, registry),
            }
        )
    return result


def collect_paths(nodes: Tree) -> list[str]:
    found: list[str] = []

    def walk(items: Tree) -> None:
        for node in items:
            path = str(node.get("path") or "")
            if path:
                found.append(path)
            walk(list(node.get("children") or []))

    walk(nodes)
    return found


def locate(roots: Tree, path: str) -> Optional[Location]:
    """Findet ``(sibling_list, index, parent_node)``; Parent ist ``None`` auf Root-Ebene.

    Wichtig: ``sibling_list`` ist die echte Liste am Parent (nicht ``list(...)``),
    damit Indent/Outdent/Move/Remove per ``pop``/``insert`` den Baum mutieren.
    """

    def _walk(siblings: Tree, parent: Optional[Node]) -> Optional[Location]:
        for idx, node in enumerate(siblings):
            if str(node.get("path") or "") == path:
                return siblings, idx, parent
            hit = _walk(_ensure_children(node), node)
            if hit is not None:
                return hit
        return None

    return _walk(roots, None)


def _ensure_children(node: Node) -> Tree:
    children = node.get("children")
    if not isinstance(children, list):
        children = []
        node["children"] = children
    return children


def is_ancestor(roots: Tree, ancestor_path: str, descendant_path: str) -> bool:
    hit = locate(roots, descendant_path)
    while hit is not None:
        _sib, _idx, parent = hit
        if parent is None:
            return False
        parent_path = str(parent.get("path") or "")
        if parent_path == ancestor_path:
            return True
        hit = locate(roots, parent_path)
    return False


def move_up(roots: Tree, paths: Iterable[str]) -> bool:
    changed = False
    for path in paths:
        hit = locate(roots, path)
        if hit is None:
            continue
        siblings, idx, _parent = hit
        if idx > 0:
            siblings[idx - 1], siblings[idx] = siblings[idx], siblings[idx - 1]
            changed = True
    return changed


def move_down(roots: Tree, paths: Iterable[str]) -> bool:
    changed = False
    for path in reversed(list(paths)):
        hit = locate(roots, path)
        if hit is None:
            continue
        siblings, idx, _parent = hit
        if idx < len(siblings) - 1:
            siblings[idx + 1], siblings[idx] = siblings[idx], siblings[idx + 1]
            changed = True
    return changed


def indent(roots: Tree, paths: Iterable[str]) -> bool:
    changed = False
    for path in paths:
        hit = locate(roots, path)
        if hit is None:
            continue
        siblings, idx, _parent = hit
        if idx == 0:
            continue
        node = siblings.pop(idx)
        prev = siblings[idx - 1]
        _ensure_children(prev).append(node)
        changed = True
    return changed


def outdent(roots: Tree, paths: Iterable[str]) -> bool:
    changed = False
    for path in reversed(list(paths)):
        hit = locate(roots, path)
        if hit is None:
            continue
        siblings, idx, parent = hit
        if parent is None:
            continue
        parent_path = str(parent.get("path") or "")
        parent_hit = locate(roots, parent_path)
        if parent_hit is None:
            continue
        parent_siblings, parent_idx, _gp = parent_hit
        node = siblings.pop(idx)
        parent_siblings.insert(parent_idx + 1, node)
        changed = True
    return changed


def reorder_among_siblings(roots: Tree, drag_path: str, target_path: str, *, after: bool) -> bool:
    """Tk-Parität: Drag landet unter dem Parent des Targets (kein Reparent via DnD)."""
    if drag_path == target_path:
        return False
    if is_ancestor(roots, drag_path, target_path):
        return False
    drag_hit = locate(roots, drag_path)
    target_hit = locate(roots, target_path)
    if drag_hit is None or target_hit is None:
        return False
    drag_siblings, drag_idx, _ = drag_hit
    target_siblings, target_idx, _ = target_hit

    node = drag_siblings.pop(drag_idx)
    if drag_siblings is target_siblings and drag_idx < target_idx:
        target_idx -= 1
    insert_at = target_idx + 1 if after else target_idx
    target_siblings.insert(insert_at, node)
    return True


def remove_paths(roots: Tree, paths: Iterable[str]) -> list[Node]:
    """Entfernt selektierte Knoten (Unterbaum bleibt am Knoten hängen)."""
    removed: list[Node] = []
    for path in list(paths):
        hit = locate(roots, path)
        if hit is None:
            continue
        siblings, idx, _p = hit
        removed.append(siblings.pop(idx))
    return removed


def insert_nodes(
    roots: Tree,
    nodes: list[Node],
    *,
    after_path: Optional[str] = None,
) -> None:
    """Fügt Knoten ein: nach ``after_path`` (gleicher Parent) oder ans Root-Ende."""
    if after_path:
        hit = locate(roots, after_path)
        if hit is not None:
            siblings, idx, _p = hit
            for offset, node in enumerate(nodes):
                siblings.insert(idx + 1 + offset, copy.deepcopy(node))
            return
    roots.extend(copy.deepcopy(n) for n in nodes)


def insert_node_by_order(
    roots: Tree,
    node: Node,
    *,
    order_meta_for_path: Callable[[str], tuple[Any, Any]],
) -> bool:
    """Fügt einen Knoten root-level nach Frontmatter-``order`` ein.

    Entspricht Tk ``insert_required_by_order`` / ``populate._insert_node_by_order``:
    - ``front``: nach ``index.md`` (falls vorhanden), aufsteigend nach sort_key
    - ``end``: Endblock, höhere END-Zahl weiter vorn (``END-1`` ganz hinten)
    - sonst: False (Aufrufer soll cursor-basiert einfügen)

    ``order_meta_for_path(path) -> (sort_key, group)`` wie
    ``yaml_engine.get_required_order``.
    """
    path = str(node.get("path") or "").replace("\\", "/")
    try:
        sort_key, group = order_meta_for_path(path)
    except (TypeError, ValueError, OSError, AttributeError):
        return False

    def meta(item: Node) -> tuple[Any, Any]:
        p = str(item.get("path") or "").replace("\\", "/")
        if not p or p.startswith("PART:"):
            return None, None
        try:
            return order_meta_for_path(p)
        except (TypeError, ValueError, OSError, AttributeError):
            return None, None

    fresh = copy.deepcopy(node)

    if group == "front" and sort_key is not None:
        insert_at = 0
        for idx, item in enumerate(roots):
            if str(item.get("path") or "").replace("\\", "/") == "index.md":
                insert_at = idx + 1
                break
        idx = insert_at
        while idx < len(roots):
            other_key, other_group = meta(roots[idx])
            if other_group != "front":
                break
            if other_key is not None and int(other_key) <= int(sort_key):
                idx += 1
                continue
            break
        roots.insert(idx, fresh)
        return True

    if group == "end" and sort_key is not None:
        first_end = len(roots)
        for idx, item in enumerate(roots):
            _other_key, other_group = meta(item)
            if other_group == "end":
                first_end = idx
                break
        idx = first_end
        while idx < len(roots):
            other_key, other_group = meta(roots[idx])
            if other_group != "end":
                idx += 1
                continue
            if other_key is not None and int(other_key) > int(sort_key):
                idx += 1
                continue
            break
        roots.insert(idx, fresh)
        return True

    return False


def flatten_nodes_for_avail(nodes: list[Node]) -> list[tuple[str, str]]:
    """Alle Pfade eines entfernten Teilbaums als Avail-Einträge."""
    out: list[tuple[str, str]] = []

    def walk(items: list[Node]) -> None:
        for node in items:
            path = str(node.get("path") or "")
            title = str(node.get("title") or path)
            if path and not path.startswith("PART:"):
                out.append((path, title))
            walk(list(node.get("children") or []))

    walk(nodes)
    return out


def snapshot(book: Tree, avail: list[tuple[str, str]]) -> dict[str, Any]:
    return {"book": copy.deepcopy(book), "avail": list(avail)}


def restore_snapshot(state: dict[str, Any]) -> tuple[Tree, list[tuple[str, str]]]:
    book = copy.deepcopy(state.get("book") or [])
    avail = [tuple(x) for x in (state.get("avail") or [])]  # type: ignore[misc]
    return book, avail  # type: ignore[return-value]
