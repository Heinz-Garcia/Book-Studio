"""Pure helpers for structure-panel search (title/path + fulltext)."""

from __future__ import annotations

from typing import Any, Callable

from search_filter import matches_tree_node, normalize_search_term
from services.constants import FilterValue
from services.ui_state_service import UiStateService

SEARCH_MODE_TITLE_PATH = FilterValue.TITLE_PATH.value
SEARCH_MODE_FULLTEXT = FilterValue.FULLTEXT.value
SEARCH_SCOPE_LEFT = FilterValue.LEFT.value
SEARCH_SCOPE_RIGHT = FilterValue.RIGHT.value
SEARCH_SCOPE_BOTH = FilterValue.BOTH.value

DEFAULT_STRUCTURE_SEARCH_MODE = SEARCH_MODE_FULLTEXT
DEFAULT_STRUCTURE_SEARCH_SCOPE = SEARCH_SCOPE_BOTH


def is_fulltext_mode(search_mode: str | None) -> bool:
    return UiStateService.is_fulltext_search_enabled(search_mode)


def applies_to_left(search_scope: str | None) -> bool:
    return search_scope in (SEARCH_SCOPE_LEFT, SEARCH_SCOPE_BOTH)


def applies_to_right(search_scope: str | None) -> bool:
    return UiStateService.is_right_side_search_scope(search_scope)


def path_matches_search(
    *,
    search_term: str,
    title: str,
    path: str,
    is_fulltext: bool,
    content_text: str = "",
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> bool:
    """True if a single file/node matches the active search."""
    term = normalize_search_term(search_term, case_sensitive=case_sensitive)
    if not term:
        return True
    return matches_tree_node(
        term,
        title,
        path,
        title,
        content_text if is_fulltext else "",
        is_fulltext,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
    )


def filter_structure_nodes(
    nodes: list[dict[str, Any]],
    search_term: str,
    *,
    is_fulltext: bool,
    content_lookup: Callable[[str], str] | None = None,
    display_title: Callable[[str, str], str] | None = None,
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> list[dict[str, Any]]:
    """Return a pruned copy of ``nodes`` keeping matches and ancestors of matches."""
    term = normalize_search_term(search_term, case_sensitive=case_sensitive)
    if not term:
        return list(nodes)

    def _title(path: str, raw: str) -> str:
        if callable(display_title):
            return display_title(path, raw)
        return raw

    def _content(path: str) -> str:
        if not is_fulltext or not callable(content_lookup):
            return ""
        try:
            return str(content_lookup(path) or "")
        except (OSError, TypeError, ValueError):
            return ""

    def walk(node_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        for node in node_list:
            if not isinstance(node, dict):
                continue
            path = str(node.get("path") or "")
            raw_title = str(node.get("title") or path)
            title = _title(path, raw_title)
            children = walk(list(node.get("children") or []))
            self_match = path_matches_search(
                search_term=term,
                title=title,
                path=path,
                is_fulltext=is_fulltext,
                content_text=_content(path),
                case_sensitive=case_sensitive,
                whole_word=whole_word,
            )
            if self_match or children:
                copy = dict(node)
                copy["children"] = children
                kept.append(copy)
        return kept

    return walk(nodes)


def count_leafish_nodes(nodes: list[dict[str, Any]]) -> int:
    """Count nodes in a (possibly filtered) structure tree."""
    total = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        total += 1
        total += count_leafish_nodes(list(node.get("children") or []))
    return total
