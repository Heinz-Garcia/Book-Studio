"""Regressionstests fuer markdown_asset_scanner.py (Code-Review 2026-07-03).

`collect_image_targets` warf zuvor einen AttributeError auf
Referenz-Bildsyntax (`![alt][ref]`), weil `_REF_IMAGE_PATTERN.findall()`
2-Tupel liefert und `.strip()` faelschlich direkt auf dem Tupel
aufgerufen wurde.
"""

from __future__ import annotations

from markdown_asset_scanner import collect_image_targets, find_missing_image_refs


def test_collect_image_targets_inline_image():
    text = "Hallo ![Alt](bilder/foo.png) Welt"
    assert collect_image_targets(text) == ["bilder/foo.png"]


def test_collect_image_targets_reference_style_by_ref_name():
    text = (
        "Hallo ![Alt][myref] Welt\n"
        "\n"
        "[myref]: bilder/bar.png\n"
    )
    assert collect_image_targets(text) == ["bilder/bar.png"]


def test_collect_image_targets_reference_style_falls_back_to_alt_text():
    """Leerer Referenzname (`![alt][]`) nutzt den Alt-Text als Referenz,
    analog zu `collect_image_refs`."""
    text = (
        "Hallo ![myref][] Welt\n"
        "\n"
        "[myref]: bilder/baz.png\n"
    )
    assert collect_image_targets(text) == ["bilder/baz.png"]


def test_collect_image_targets_mixed_inline_and_reference():
    text = (
        "![Inline](a.png)\n"
        "![Ref][x]\n"
        "\n"
        "[x]: b.png\n"
    )
    assert collect_image_targets(text) == ["a.png", "b.png"]


def test_find_missing_image_refs_reference_style(tmp_path):
    md_file = tmp_path / "chapter.md"
    md_file.write_text(
        "![Alt][missing]\n\n[missing]: does-not-exist.png\n",
        encoding="utf-8",
    )
    missing = find_missing_image_refs(md_file.read_text(encoding="utf-8"), md_file, tmp_path)
    assert missing == [(1, "does-not-exist.png")]
