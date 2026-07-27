"""Tests: ui_qt/markdown_formatting.py (reine Text-Transformationslogik für
die Formatier-Buttons im Markdown-Editor, kein Qt nötig)."""

from __future__ import annotations

from ui_qt.markdown_formatting import (
    apply_line_prefix,
    next_footnote_index,
    set_heading_level,
    table_skeleton,
    wrap_selection,
)


def test_wrap_selection_wraps_existing_selection():
    result = wrap_selection("Hallo", "**", "**")
    assert result.replacement == "**Hallo**"
    assert result.select_from == 2
    assert result.select_to == 7


def test_wrap_selection_inserts_placeholder_when_empty():
    result = wrap_selection("", "*", "*", placeholder="Text")
    assert result.replacement == "*Text*"
    assert result.select_from == 1
    assert result.select_to == 5


def test_set_heading_level_on_plain_line():
    assert set_heading_level("Kapitel eins", 2) == "## Kapitel eins"


def test_set_heading_level_replaces_existing_level():
    assert set_heading_level("### Kapitel eins", 1) == "# Kapitel eins"


def test_apply_line_prefix_bullet_list():
    lines = ["Erstens", "Zweitens", "", "Drittens"]
    result = apply_line_prefix(lines, lambda _i: "- ")
    assert result == ["- Erstens", "- Zweitens", "", "- Drittens"]


def test_apply_line_prefix_ordered_list_numbers_only_nonempty_lines():
    lines = ["Erstens", "", "Zweitens", "Drittens"]
    result = apply_line_prefix(lines, lambda i: f"{i}. ")
    assert result == ["1. Erstens", "", "2. Zweitens", "3. Drittens"]


def test_apply_line_prefix_switches_marker_type_without_stacking():
    """Regression: eine bestehende Zitat-Zeile per Listen-Button in eine Liste
    umwandeln darf nicht "- > Text" ergeben, sondern muss das alte Präfix
    zuerst entfernen."""
    lines = ["> Zitat-Zeile"]
    result = apply_line_prefix(lines, lambda _i: "- ")
    assert result == ["- Zitat-Zeile"]


def test_table_skeleton_shape():
    text = table_skeleton(columns=3, rows=1)
    lines = text.split("\n")
    assert len(lines) == 3
    assert lines[0].count("|") == 4
    assert lines[1] == "| --- | --- | --- |"


def test_next_footnote_index_starts_at_one():
    assert next_footnote_index("Kein Fußnote hier.") == 1


def test_next_footnote_index_skips_used_numbers():
    text = "Text[^1] mit[^2] Fußnoten.\n\n[^1]: eins\n[^2]: zwei\n"
    assert next_footnote_index(text) == 3


def test_next_footnote_index_fills_gap():
    text = "Nur[^2] verwendet."
    assert next_footnote_index(text) == 1
