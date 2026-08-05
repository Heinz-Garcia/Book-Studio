"""Unit tests for search_filter match options."""

from __future__ import annotations

from search_filter import (
    matches_title_path,
    matches_tree_node,
    normalize_search_term,
    should_include_available_item,
)


def test_normalize_default_lowers() -> None:
    assert normalize_search_term("  Du  ") == "du"
    assert normalize_search_term("Du", case_sensitive=True) == "Du"


def test_substring_case_insensitive_default() -> None:
    assert matches_title_path("du", "Durchatmen", "a.md") is True
    assert matches_title_path("Du", "Durchatmen", "a.md") is False  # already lowered expected


def test_case_sensitive_title() -> None:
    assert (
        matches_title_path(
            "Du", "Du und ich", "a.md", case_sensitive=True
        )
        is True
    )
    assert (
        matches_title_path(
            "Du", "du und ich", "a.md", case_sensitive=True
        )
        is False
    )


def test_whole_word_rejects_prefix() -> None:
    assert (
        matches_title_path("du", "Durchatmen", "a.md", whole_word=True) is False
    )
    assert matches_title_path("du", "Du, bitte", "a.md", whole_word=True) is True
    assert matches_title_path("du", "„Du“", "a.md", whole_word=True) is True


def test_whole_word_umlaut() -> None:
    assert (
        matches_title_path(
            "größe", "Die Größe stimmt", "a.md", whole_word=True
        )
        is True
    )
    assert (
        matches_title_path(
            "größe", "Größenordnung", "a.md", whole_word=True
        )
        is False
    )


def test_fulltext_content_case_and_word() -> None:
    content = "Hier kommt Chemotherapie vor. Und Du."
    assert (
        matches_tree_node(
            "chemotherapie",
            "Op",
            "op.md",
            "Op",
            content,
            True,
        )
        is True
    )
    assert (
        matches_tree_node(
            "Chemotherapie",
            "Op",
            "op.md",
            "Op",
            content,
            True,
            case_sensitive=True,
        )
        is True
    )
    assert (
        matches_tree_node(
            "chemotherapie",
            "Op",
            "op.md",
            "Op",
            content,
            True,
            case_sensitive=True,
        )
        is False
    )
    assert (
        matches_tree_node(
            "du",
            "Op",
            "op.md",
            "Op",
            content,
            True,
            whole_word=True,
        )
        is True
    )
    assert (
        matches_tree_node(
            "chemo",
            "Op",
            "op.md",
            "Op",
            content,
            True,
            whole_word=True,
        )
        is False
    )


def test_should_include_available_item_flags() -> None:
    assert (
        should_include_available_item(
            "du",
            True,
            False,
            "Durch",
            "x.md",
            "",
            whole_word=True,
        )
        is False
    )
    assert (
        should_include_available_item(
            "Du",
            True,
            True,
            "Andere",
            "x.md",
            "Hallo Du!",
            case_sensitive=True,
            whole_word=True,
        )
        is True
    )
