"""Tests für frontmatter_bool_toggles (YAML-Toggles im Markdown-Editor)."""

from __future__ import annotations

from frontmatter_bool_toggles import (
    apply_bool_to_content,
    discover_extra_bool_keys,
    effective_bool,
    list_bool_toggle_specs,
    toggle_bool_in_content,
    toggle_keys_signature,
)


def test_known_toggles_always_listed():
    keys = [s.key for s in list_bool_toggle_specs("---\ntitle: X\n---\n\n")]
    assert keys[:4] == ["required", "print_title", "unnumbered", "unlisted"]


def test_discovers_extra_bool_keys():
    content = "---\ntitle: X\ncustom_flag: true\nother: false\n---\n\n"
    assert discover_extra_bool_keys(content) == ["custom_flag", "other"]
    keys = [s.key for s in list_bool_toggle_specs(content)]
    assert "custom_flag" in keys
    assert "other" in keys


def test_toggle_required_and_print_title():
    base = "---\ntitle: Vakanz\n---\n\nBody\n"
    text, state = toggle_bool_in_content(base, "required")
    assert state is True
    assert "required: true" in text
    text2, state2 = toggle_bool_in_content(text, "print_title")
    assert state2 is True  # was false (required → silent), now on
    assert "print_title: true" in text2


def test_toggle_unnumbered_unlisted_explicit():
    base = "---\ntitle: Kap\n---\n\n"
    text, state = toggle_bool_in_content(base, "unnumbered")
    assert state is True
    assert "unnumbered: true" in text
    text2, state2 = toggle_bool_in_content(text, "unnumbered")
    assert state2 is False
    assert "unnumbered: false" in text2


def test_apply_extra_bool():
    base = "---\ntitle: X\n---\n\n"
    out = apply_bool_to_content(base, "draft", True)
    assert "draft: true" in out
    assert effective_bool(out, "draft") is True


def test_toggle_keys_signature_stable_for_known_only():
    a = toggle_keys_signature("---\ntitle: A\n---\n")
    b = toggle_keys_signature("---\ntitle: B\nrequired: true\n---\n")
    assert a == b  # known set identical; extras none
