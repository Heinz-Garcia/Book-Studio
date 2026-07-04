"""Tests für frontmatter_requirements (Config + Platzhalter)."""

from __future__ import annotations

from pathlib import Path

from frontmatter_requirements import (
    extract_h1_from_body,
    load_frontmatter_settings,
    resolve_frontmatter_placeholder,
)


def test_extract_h1_from_body() -> None:
    body = "# Mein Buchtitel\n\nInhalt.\n"
    assert extract_h1_from_body(body) == "Mein Buchtitel"


def test_resolve_h1_falls_back_to_filename(tmp_path: Path) -> None:
    filepath = tmp_path / "book-master.md"
    val = resolve_frontmatter_placeholder(
        "<h1>",
        filepath=filepath,
        body="Nur Text ohne Überschrift.\n",
        parsed_yaml={},
        value_map={},
        fallback_title=None,
    )
    assert val == "book-master"


def test_resolve_title_uses_value_map(tmp_path: Path) -> None:
    filepath = tmp_path / "kapitel.md"
    val = resolve_frontmatter_placeholder(
        "<title>",
        filepath=filepath,
        body="# T\n",
        parsed_yaml={},
        value_map={"title": "Aus Karte"},
        fallback_title="Fallback",
    )
    assert val == "Aus Karte"


def test_load_frontmatter_settings_reads_app_config(tmp_path: Path) -> None:
    cfg = tmp_path / "app_config.json"
    cfg.write_text(
        '{"frontmatter_requirements":{"title":"<h1>","description":"<title>","status":"draft"},'
        '"frontmatter_update_mode":"append_only"}',
        encoding="utf-8",
    )
    fields, mode = load_frontmatter_settings(cfg)
    assert fields["title"] == "<h1>"
    assert fields["status"] == "draft"
    assert mode == "append_only"
