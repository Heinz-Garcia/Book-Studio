"""Tests for md-übergreifende Buchstruktur-Suche (structure_search)."""

from __future__ import annotations

from ui_qt.structure_search import (
    DEFAULT_STRUCTURE_SEARCH_MODE,
    DEFAULT_STRUCTURE_SEARCH_SCOPE,
    SEARCH_MODE_FULLTEXT,
    SEARCH_SCOPE_BOTH,
    SEARCH_SCOPE_LEFT,
    SEARCH_SCOPE_RIGHT,
    applies_to_left,
    applies_to_right,
    filter_structure_nodes,
    is_fulltext_mode,
    path_matches_search,
)


def test_defaults_are_fulltext_both() -> None:
    assert DEFAULT_STRUCTURE_SEARCH_MODE == SEARCH_MODE_FULLTEXT
    assert DEFAULT_STRUCTURE_SEARCH_SCOPE == SEARCH_SCOPE_BOTH


def test_scope_helpers() -> None:
    assert applies_to_left(SEARCH_SCOPE_LEFT) is True
    assert applies_to_left(SEARCH_SCOPE_BOTH) is True
    assert applies_to_left(SEARCH_SCOPE_RIGHT) is False
    assert applies_to_right(SEARCH_SCOPE_RIGHT) is True
    assert applies_to_right(SEARCH_SCOPE_BOTH) is True
    assert applies_to_right(SEARCH_SCOPE_LEFT) is False


def test_fulltext_matches_content_not_title() -> None:
    assert (
        path_matches_search(
            search_term="Chemotherapie",
            title="Die Operation",
            path="content/op.md",
            is_fulltext=True,
            content_text="hier kommt chemotherapie vor",
        )
        is True
    )
    assert (
        path_matches_search(
            search_term="Chemotherapie",
            title="Die Operation",
            path="content/op.md",
            is_fulltext=False,
            content_text="hier kommt chemotherapie vor",
        )
        is False
    )


def test_filter_keeps_parent_when_child_matches() -> None:
    nodes = [
        {
            "path": "content/ch1.md",
            "title": "Kapitel 1",
            "children": [
                {
                    "path": "content/ch1_sub.md",
                    "title": "Unterkapitel",
                    "children": [],
                }
            ],
        },
        {
            "path": "content/other.md",
            "title": "Andere",
            "children": [],
        },
    ]
    contents = {
        "content/ch1.md": "lorem",
        "content/ch1_sub.md": "wichtiges schlüsselwort hier",
        "content/other.md": "nichts",
    }
    filtered = filter_structure_nodes(
        nodes,
        "schlüsselwort",
        is_fulltext=True,
        content_lookup=lambda p: contents.get(p, ""),
    )
    assert len(filtered) == 1
    assert filtered[0]["path"] == "content/ch1.md"
    assert len(filtered[0]["children"]) == 1
    assert filtered[0]["children"][0]["path"] == "content/ch1_sub.md"


def test_filter_empty_term_returns_all() -> None:
    nodes = [{"path": "a.md", "title": "A", "children": []}]
    assert filter_structure_nodes(nodes, "", is_fulltext=True) == nodes


def test_is_fulltext_mode() -> None:
    assert is_fulltext_mode(SEARCH_MODE_FULLTEXT) is True
    assert is_fulltext_mode("Titel/Pfad") is False


def test_case_sensitive_content_match() -> None:
    assert (
        path_matches_search(
            search_term="Du",
            title="Kapitel",
            path="content/a.md",
            is_fulltext=True,
            content_text="Nur du klein geschrieben.",
            case_sensitive=True,
        )
        is False
    )
    assert (
        path_matches_search(
            search_term="Du",
            title="Kapitel",
            path="content/a.md",
            is_fulltext=True,
            content_text="Ansprache an Du und Sie.",
            case_sensitive=True,
        )
        is True
    )


def test_whole_word_content_match() -> None:
    assert (
        path_matches_search(
            search_term="Du",
            title="Kapitel",
            path="content/a.md",
            is_fulltext=True,
            content_text="Durch die Nacht.",
            whole_word=True,
        )
        is False
    )
    assert (
        path_matches_search(
            search_term="Du",
            title="Kapitel",
            path="content/a.md",
            is_fulltext=True,
            content_text="Du, lies weiter.",
            whole_word=True,
        )
        is True
    )


def test_filter_respects_whole_word() -> None:
    nodes = [
        {"path": "a.md", "title": "Durch", "children": []},
        {"path": "b.md", "title": "Du", "children": []},
    ]
    filtered = filter_structure_nodes(
        nodes, "Du", is_fulltext=False, whole_word=True
    )
    assert len(filtered) == 1
    assert filtered[0]["path"] == "b.md"
