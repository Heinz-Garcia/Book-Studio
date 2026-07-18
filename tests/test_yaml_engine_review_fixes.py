"""Regressionstests fuer yaml_engine.py-Fixes (Code-Review 2026-07-03).

Deckt ab:
- `ensure_required_frontmatter` liest `app_config.json` statt der
  veralteten `studio_config.json`.
- `parse_chapters` bevorzugt einen veralteten `.gui_state.json`-Cache
  nicht mehr gegenueber einer neueren `_quarto.yml`.
- `save_chapters` wirft keinen KeyError, wenn `_quarto.yml` die
  Top-Level-Schluessel `project`/`book` nicht enthaelt.
- `parse_chapters` zieht bei Dict-Chapter-Eintraegen bekannte Schluessel
  (`file`/`href`) statt sich auf die Dict-Reihenfolge zu verlassen.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import yaml

from yaml_engine import QuartoYamlEngine


def _make_book(tmp_path: Path) -> Path:
    book = tmp_path / "Book"
    book.mkdir()
    (book / "index.md").write_text("# Book\n", encoding="utf-8")
    return book


# --- ensure_required_frontmatter liest app_config.json ---------------------


def test_ensure_required_frontmatter_reads_app_config_json(tmp_path, monkeypatch):
    """Test für Cluster 3.1: `ensure_required_frontmatter` liest
    `app_config.json` über `frontmatter_requirements` (nicht `yaml_engine`).

    Dieser Test wurde repariert: Monkeypatch-Ziel ist jetzt korrekt auf
    `frontmatter_requirements._app_config_service` (nicht `yaml_engine._app_config_service`,
    die nicht existiert).
    """
    book = _make_book(tmp_path)
    md = book / "chapter.md"
    md.write_text("Kein Frontmatter hier.\n", encoding="utf-8")

    # `ensure_required_frontmatter` liest die app_config.json über
    # `frontmatter_requirements.load_frontmatter_settings()`, die wiederum
    # `frontmatter_requirements._app_config_service` nutzt.
    calls = []

    def fake_load_validated_config(path):
        calls.append(Path(path).name)
        return {
            "frontmatter_requirements": {"status": "custom-status"},
            "frontmatter_update_mode": "append_only",
        }

    import frontmatter_requirements as fr

    # Korrekt: Monkeypatch auf frontmatter_requirements._app_config_service
    monkeypatch.setattr(fr._app_config_service, "load_validated_config", fake_load_validated_config)

    engine = QuartoYamlEngine(book)
    ok = engine.ensure_required_frontmatter(md)

    assert ok is True
    assert calls == ["app_config.json"]
    text = md.read_text(encoding="utf-8")
    assert "status:" in text
    assert "custom-status" in text


# --- gui_state Frische / Invalidierung --------------------------------------


def test_parse_chapters_prefers_fresh_gui_state(tmp_path):
    book = _make_book(tmp_path)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters: [ch1.md]\n",
        encoding="utf-8",
    )
    engine = QuartoYamlEngine(book)
    engine._save_gui_state([{"path": "cached.md", "children": []}])

    result = engine.parse_chapters()
    assert result == [{"path": "cached.md", "children": []}]


def test_parse_chapters_ignores_stale_gui_state(tmp_path):
    """B-Fix: eine NACH dem GUI-State-Cache geaenderte `_quarto.yml`
    (z. B. manuell bearbeitet oder frisch importiert) muss den Cache
    ueberstimmen."""
    book = _make_book(tmp_path)
    (book / "ch1.md").write_text("# Chapter 1\n", encoding="utf-8")
    yaml_path = book / "_quarto.yml"
    yaml_path.write_text(
        "project:\n  type: book\nbook:\n  chapters: [ch1.md]\n",
        encoding="utf-8",
    )
    engine = QuartoYamlEngine(book)
    engine._save_gui_state([{"path": "cached.md", "children": []}])

    # gui_state.json aelter machen als _quarto.yml.
    old_time = time.time() - 3600
    os.utime(engine.gui_state_path, (old_time, old_time))

    result = engine.parse_chapters()
    assert result == [{"path": "ch1.md", "title": "Chapter 1", "children": []}]


def test_parse_chapters_falls_back_when_no_gui_state(tmp_path):
    book = _make_book(tmp_path)
    (book / "ch1.md").write_text("# Chapter 1\n", encoding="utf-8")
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters: [ch1.md]\n",
        encoding="utf-8",
    )
    engine = QuartoYamlEngine(book)
    result = engine.parse_chapters()
    assert result == [{"path": "ch1.md", "title": "Chapter 1", "children": []}]


def test_parse_chapters_fallback_always_includes_title(tmp_path):
    """B-Fix: `convert()` muss IMMER ein `title`-Feld liefern, sonst
    stuerzt `pre_processor.prepare_render_environment` mit KeyError('title')
    ab (betrifft insbesondere den CLI-Pfad `quarto_render_safe.py`, der
    `parse_chapters()` direkt aufruft)."""
    book = _make_book(tmp_path)
    (book / "no_frontmatter.md").write_text("Kein Titel hier.\n", encoding="utf-8")
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  chapters: [no_frontmatter.md]\n",
        encoding="utf-8",
    )
    engine = QuartoYamlEngine(book)
    result = engine.parse_chapters()
    assert result[0]["title"] == "no_frontmatter"


# --- save_chapters KeyError-Absicherung -------------------------------------


def test_save_chapters_handles_missing_project_and_book_keys(tmp_path):
    """B-Fix: eine `_quarto.yml` ohne `project`/`book`-Keys darf keinen
    KeyError auslösen."""
    book = _make_book(tmp_path)
    yaml_path = book / "_quarto.yml"
    yaml_path.write_text("format:\n  typst:\n    toc: true\n", encoding="utf-8")

    engine = QuartoYamlEngine(book)
    engine.save_chapters([{"path": "index.md", "children": []}], save_gui_state=False)

    saved = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert saved["book"]["chapters"] == ["index.md"]
    assert saved["project"]["output-dir"] == "export/_book"


# --- Dict-zu-Pfad-Konverter --------------------------------------------------


def test_parse_chapters_dict_entry_prefers_href_key_regardless_of_order(tmp_path):
    """B-Fix: bei einer beliebigen fuehrenden Meta-Angabe vor `href`
    darf nicht der Deko-Wert als Pfad interpretiert werden (vorher:
    `list(item.values())[0]`, abhaengig von der Dict-Reihenfolge)."""
    book = _make_book(tmp_path)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\n"
        "book:\n"
        "  chapters:\n"
        "    - number-depth: 2\n"
        "      href: real_chapter.md\n",
        encoding="utf-8",
    )
    engine = QuartoYamlEngine(book)
    result = engine.parse_chapters()
    assert result[0]["path"] == "real_chapter.md"


def test_parse_chapters_dict_entry_with_file_key(tmp_path):
    book = _make_book(tmp_path)
    (book / "_quarto.yml").write_text(
        "project:\n  type: book\n"
        "book:\n"
        "  chapters:\n"
        "    - number-depth: 2\n"
        "      file: real_chapter.md\n",
        encoding="utf-8",
    )
    engine = QuartoYamlEngine(book)
    result = engine.parse_chapters()
    assert result[0]["path"] == "real_chapter.md"
