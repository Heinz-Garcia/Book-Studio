from __future__ import annotations

from pathlib import Path

from pre_processor import PreProcessor


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_book(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    book.mkdir(parents=True, exist_ok=True)
    return book


def test_prepare_render_environment_strips_non_numeric_order_from_processed_frontmatter(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "required" / "Literaturverzeichnis.md"
    _write(
        source,
        "---\n"
        "title: \"Quellenverzeichnis\"\n"
        "order: END-50\n"
        "---\n\n"
        "# Quellenverzeichnis\n",
    )

    processor = PreProcessor(book)
    tree_data = [{"title": "Quellenverzeichnis", "path": "content/required/Literaturverzeichnis.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed = (book / "processed" / "content" / "required" / "Literaturverzeichnis.md").read_text(encoding="utf-8")
    original = source.read_text(encoding="utf-8")

    assert "order: END-50" in original
    assert "order:" not in processed
    assert "title: Quellenverzeichnis" in processed


def test_prepare_render_environment_keeps_numeric_order_in_processed_frontmatter(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "required" / "Vorwort.md"
    _write(
        source,
        "---\n"
        "title: \"Vorwort\"\n"
        "order: 5\n"
        "---\n\n"
        "# Vorwort\n",
    )

    processor = PreProcessor(book)
    tree_data = [{"title": "Vorwort", "path": "content/required/Vorwort.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed = (book / "processed" / "content" / "required" / "Vorwort.md").read_text(encoding="utf-8")

    assert "order: 5" in processed


# B4: Die folgenden Footnote-spezifischen Tests wurden entfernt, weil das
# komplette Fußnoten-System (FootnoteHarvester, Modus, Backlinks, Endnoten-
# Generierung) abgeschaltet ist. Pandoc-konforme `[^1]`-Marker werden
# unverändert weitergereicht — die zugehörigen Tests sind obsolet.
