"""Pure search/match helpers for structure trees and left-list pool."""

from __future__ import annotations

import re
from typing import Any


def normalize_search_term(value: Any, *, case_sensitive: bool = False) -> str:
    text = str(value or "").strip()
    if not case_sensitive:
        return text.lower()
    return text


def _prepare_haystack(text: Any, *, case_sensitive: bool) -> str:
    hay = str(text or "")
    if not case_sensitive:
        return hay.lower()
    return hay


def _text_matches(
    haystack: Any,
    needle: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> bool:
    if not needle:
        return True
    text = _prepare_haystack(haystack, case_sensitive=case_sensitive)
    if not whole_word:
        return needle in text
    # Explicit Unicode word chars: Python ``\\b`` is ASCII-only for ``\\w``.
    # Needle must already match haystack casing (via normalize_search_term).
    pattern = rf"(?<![\w]){re.escape(needle)}(?![\w])"
    return re.search(pattern, text, flags=re.UNICODE) is not None


def matches_title_path(
    search_term: str,
    title: Any,
    path: Any,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> bool:
    if not search_term:
        return True
    return _text_matches(
        title, search_term, case_sensitive=case_sensitive, whole_word=whole_word
    ) or _text_matches(
        path, search_term, case_sensitive=case_sensitive, whole_word=whole_word
    )


def matches_tree_node(
    search_term: str,
    node_text: Any,
    path_text: Any,
    raw_title: Any,
    content_text: Any,
    is_fulltext: bool,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> bool:
    if not search_term:
        return True

    if is_fulltext:
        return (
            _text_matches(
                raw_title,
                search_term,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
            )
            or _text_matches(
                path_text,
                search_term,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
            )
            or _text_matches(
                content_text,
                search_term,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
            )
        )

    return _text_matches(
        node_text, search_term, case_sensitive=case_sensitive, whole_word=whole_word
    ) or _text_matches(
        path_text, search_term, case_sensitive=case_sensitive, whole_word=whole_word
    )


def should_include_available_item(
    search_term: str,
    apply_left_search: bool,
    is_fulltext: bool,
    title: Any,
    path: Any,
    content_text: Any,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> bool:
    if not apply_left_search or not search_term:
        return True

    if is_fulltext:
        return matches_title_path(
            search_term,
            title,
            path,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        ) or _text_matches(
            content_text,
            search_term,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        )

    return matches_title_path(
        search_term,
        title,
        path,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
    )
