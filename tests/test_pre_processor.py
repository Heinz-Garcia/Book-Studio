"""Regressionstests fuer die Baum-Semantik in pre_processor.py
(Code-Review 2026-07-03).

Vorher entschied `root_node.get("children")` allein, ob ein Knoten als
"Part" behandelt wurde. Echte Parts erkennt man am virtuellen Pfad
`"PART:<Titel>"` (siehe `yaml_engine._tree_to_quarto_list`). Ein
reguläres Kapitel MIT eigenen Unterkapiteln hat einen echten Datei-Pfad
und darf NICHT ueber die Part-Logik laufen (H1 wuerde entfernt, und die
Unterkapitel wuerden als eigenstaendige Chapters statt inline
amalgamiert eingefuegt).
"""

from __future__ import annotations

from pathlib import Path

from pre_processor import PreProcessor


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_real_part_node_uses_part_logic_and_strips_h1(tmp_path):
    """Ein echter PART-Knoten (path == 'PART:...') wird ueber
    `_process_part_file` behandelt: seine Chapters bleiben eigenstaendige
    Dateien im processed_tree."""
    book = tmp_path / "Book"
    _write(book / "index.md", "# Book\n\nHi\n")
    _write(book / "ch1.md", "# Chapter 1\n\nInhalt 1\n")
    _write(book / "ch2.md", "# Chapter 2\n\nInhalt 2\n")

    tree = [
        {
            "title": "Teil 1",
            "path": "PART:Teil 1",
            "children": [
                {"title": "Chapter 1", "path": "ch1.md", "children": []},
                {"title": "Chapter 2", "path": "ch2.md", "children": []},
            ],
        }
    ]

    proc = PreProcessor(book, output_format="typst")
    processed_tree = proc.prepare_render_environment(tree)

    assert len(processed_tree) == 1
    part_node = processed_tree[0]
    assert part_node["path"] == "processed/PART:Teil 1"
    assert [c["path"] for c in part_node["children"]] == [
        "processed/ch1.md",
        "processed/ch2.md",
    ]
    # Chapter-Dateien bleiben eigenstaendig und existieren separat.
    assert (book / "processed" / "ch1.md").is_file()
    assert (book / "processed" / "ch2.md").is_file()


def test_regular_chapter_with_subchapters_is_not_treated_as_part(tmp_path):
    """B-Fix: ein normales Kapitel mit eigenen Unterkapiteln (kein
    PART-Knoten) amalgamiert die Unterkapitel INLINE in dieselbe Datei,
    statt sie als separate Chapters aufzufuehren."""
    book = tmp_path / "Book"
    _write(book / "index.md", "# Book\n\nHi\n")
    _write(book / "main.md", "# Hauptkapitel\n\nHaupttext\n")
    _write(book / "sub.md", "# Unterkapitel\n\nUntertext\n")

    tree = [
        {
            "title": "Hauptkapitel",
            "path": "main.md",
            "children": [
                {"title": "Unterkapitel", "path": "sub.md", "children": []},
            ],
        }
    ]

    proc = PreProcessor(book, output_format="typst")
    processed_tree = proc.prepare_render_environment(tree)

    # Nur EIN Knoten im Ergebnisbaum - das Unterkapitel wird nicht als
    # eigenstaendiges Chapter gefuehrt.
    assert len(processed_tree) == 1
    assert processed_tree[0]["path"] == "processed/main.md"
    assert processed_tree[0]["children"] == []

    processed_main = (book / "processed" / "main.md").read_text(encoding="utf-8")
    assert "Haupttext" in processed_main
    # Der Text des Unterkapitels wurde inline amalgamiert, seine
    # Ueberschrift wurde dabei um eine Ebene tiefer eingerueckt (H1 -> H2).
    assert "## Unterkapitel" in processed_main
    assert "Untertext" in processed_main
    # Es wird keine separate sub.md unter processed/ angelegt.
    assert not (book / "processed" / "sub.md").exists()


def test_flat_chapter_without_children_is_processed_as_host_file(tmp_path):
    book = tmp_path / "Book"
    _write(book / "index.md", "# Book\n\nHi\n")
    _write(book / "solo.md", "# Solo\n\nText\n")

    tree = [{"title": "Solo", "path": "solo.md", "children": []}]

    proc = PreProcessor(book, output_format="typst")
    processed_tree = proc.prepare_render_environment(tree)

    assert len(processed_tree) == 1
    text = (book / "processed" / "solo.md").read_text(encoding="utf-8")
    assert "Text" in text
