"""Tests fuer Phase 4 / Import-Helper.

Deckt die aus `book_studio.py` extrahierten Funktionen ab:

- `extract_inline_svgs_from_md`: extrahiert <svg>-Bloecke,
  repariert alte images/svg_*.svg-Referenzen
- `extract_all_inline_svgs`: iteriert ueber publish_dir, entfernt
  alte images/svg_*.svg-Reste
- `generate_quarto_yml_for_import`: legt _quarto.yml + index.md an,
  liest Metadaten aus _book_studio.toml, cleant gui_state.json
"""

from __future__ import annotations

from pathlib import Path

from import_helpers import (
    extract_all_inline_svgs,
    extract_inline_svgs_from_md,
    generate_quarto_yml_for_import,
)


# --- extract_inline_svgs_from_md --------------------------------------------


def test_extract_inline_svgs_no_svg_returns_zero(tmp_path):
    md = tmp_path / "a.md"
    md.write_text("Hello world.", encoding="utf-8")
    assert extract_inline_svgs_from_md(md) == 0
    assert md.read_text(encoding="utf-8") == "Hello world."


def test_extract_inline_svgs_single_block(tmp_path):
    md = tmp_path / "a.md"
    md.write_text(
        "Vorher\n<svg viewBox='0 0 10 10'></svg>\nNachher",
        encoding="utf-8",
    )
    count = extract_inline_svgs_from_md(md)
    assert count == 1
    assert (tmp_path / "svg_1.svg").is_file()
    text = md.read_text(encoding="utf-8")
    assert "![Visualisierung](svg_1.svg)" in text
    assert "<svg" not in text


def test_extract_inline_svgs_with_figure_wrapper(tmp_path):
    md = tmp_path / "a.md"
    md.write_text(
        "<figure><svg viewBox='0 0 1 1'></svg></figure>",
        encoding="utf-8",
    )
    count = extract_inline_svgs_from_md(md)
    assert count == 1
    assert (tmp_path / "svg_1.svg").is_file()
    text = md.read_text(encoding="utf-8")
    assert "![Visualisierung](svg_1.svg)" in text
    assert "<figure>" not in text


def test_extract_inline_svgs_old_images_references(tmp_path):
    """Alte images/svg_N.svg-Referenzen werden zu svg_N.svg."""
    md = tmp_path / "a.md"
    md.write_text(
        "Vorher ![alt](images/svg_3.svg) Nachher",
        encoding="utf-8",
    )
    images = tmp_path / "images"
    images.mkdir()
    (images / "svg_3.svg").write_text("<svg/>", encoding="utf-8")

    count = extract_inline_svgs_from_md(md)
    assert count == 1
    text = md.read_text(encoding="utf-8")
    assert "![Visualisierung](svg_3.svg)" in text
    # SVG wurde von images/ nach md_dir/ verschoben
    assert not (images / "svg_3.svg").exists()
    assert (tmp_path / "svg_3.svg").is_file()


# --- extract_all_inline_svgs -----------------------------------------------


def test_extract_all_inline_svgs_iterates_md_files(tmp_path):
    (tmp_path / "a.md").write_text("<svg viewBox='0 0 1 1'></svg>", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.md").write_text("<svg viewBox='0 0 1 1'></svg>", encoding="utf-8")
    total = extract_all_inline_svgs(tmp_path)
    assert total == 2
    assert (tmp_path / "svg_1.svg").is_file()
    assert (sub / "svg_1.svg").is_file()


def test_extract_all_inline_svgs_cleans_old_images_dir(tmp_path):
    md = tmp_path / "a.md"
    md.write_text("Text ohne svg", encoding="utf-8")
    images = tmp_path / "images"
    images.mkdir()
    (images / "svg_1.svg").write_text("<svg/>", encoding="utf-8")
    extract_all_inline_svgs(tmp_path)
    # images/ ist leer und wird aufgeraeumt.
    assert not images.exists()


def test_extract_all_inline_svgs_keeps_non_svg_images(tmp_path):
    md = tmp_path / "a.md"
    md.write_text("Text ohne svg", encoding="utf-8")
    images = tmp_path / "images"
    images.mkdir()
    (images / "logo.png").write_text("png", encoding="utf-8")
    extract_all_inline_svgs(tmp_path)
    # images/ enthaelt logo.png und bleibt erhalten.
    assert images.is_dir()
    assert (images / "logo.png").is_file()


# --- generate_quarto_yml_for_import ---------------------------------------


def test_generate_quarto_yml_creates_minimal_file(tmp_path):
    result = generate_quarto_yml_for_import(tmp_path)
    assert result is not None
    assert result == tmp_path / "_quarto.yml"
    text = (tmp_path / "_quarto.yml").read_text(encoding="utf-8")
    assert "project:" in text
    assert "type: book" in text
    assert "chapters: []" in text


def test_generate_quarto_yml_reads_toml_metadata(tmp_path):
    toml = tmp_path / "_book_studio.toml"
    toml.write_text(
        'book = { title = "Mein Buch", author = "Ich Selbst" }\n',
        encoding="utf-8",
    )
    generate_quarto_yml_for_import(tmp_path)
    text = (tmp_path / "_quarto.yml").read_text(encoding="utf-8")
    assert 'title: "Mein Buch"' in text
    assert 'author: "Ich Selbst"' in text


def test_generate_quarto_yml_cli_overrides(tmp_path):
    toml = tmp_path / "_book_studio.toml"
    toml.write_text(
        'book = { title = "TOML Title", author = "TOML Author" }\n',
        encoding="utf-8",
    )
    generate_quarto_yml_for_import(
        tmp_path,
        index_title="CLI Title",
        index_author="CLI Author",
        index_description="CLI Desc",
    )
    text = (tmp_path / "_quarto.yml").read_text(encoding="utf-8")
    assert 'title: "CLI Title"' in text
    assert 'author: "CLI Author"' in text
    index = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert 'description: "CLI Desc"' in index


def test_generate_quarto_yml_creates_index_md(tmp_path):
    generate_quarto_yml_for_import(tmp_path, index_title="X", index_author="Y")
    index = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert 'title: "X"' in index
    assert 'author: "Y"' in index
    assert "# X" in index


def test_generate_quarto_yml_removes_gui_state(tmp_path):
    bookconfig = tmp_path / "bookconfig"
    bookconfig.mkdir()
    gui_state = bookconfig / ".gui_state.json"
    gui_state.write_text("{}", encoding="utf-8")
    generate_quarto_yml_for_import(tmp_path)
    assert not gui_state.exists()
    # Leeres bookconfig/ wird mit aufgeraeumt
    assert not bookconfig.exists()


def test_generate_quarto_yml_keeps_populated_bookconfig(tmp_path):
    bookconfig = tmp_path / "bookconfig"
    bookconfig.mkdir()
    gui_state = bookconfig / ".gui_state.json"
    gui_state.write_text("{}", encoding="utf-8")
    # Zweites File in bookconfig, das erhalten bleibt
    (bookconfig / "other.txt").write_text("keep", encoding="utf-8")
    generate_quarto_yml_for_import(tmp_path)
    assert not gui_state.exists()
    assert bookconfig.is_dir()
    assert (bookconfig / "other.txt").is_file()


def test_generate_quarto_yml_description_optional(tmp_path):
    """Ohne index_description wird keine description-Zeile geschrieben."""
    generate_quarto_yml_for_import(tmp_path, index_title="T")
    index = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert "description:" not in index
