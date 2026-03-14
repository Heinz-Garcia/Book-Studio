from __future__ import annotations

import re
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


def test_prepare_render_environment_converts_bracket_citations_with_locators_to_endnotes(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text mit Verweis [@DiamantiKandarakisDunaif2012, S. 331] und [vgl. @NestlerCharney2008].\n\n"
        "[@DiamantiKandarakisDunaif2012, S. 331]: Diamanti-Kandarakis & Dunaif (2012), S. 331.\n"
        "[@NestlerCharney2008]: Nestler (2008), S. 1878.\n",
    )

    processor = PreProcessor(book)
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")
    endnotes = (book / "processed" / "Endnoten.md").read_text(encoding="utf-8")

    assert "@DiamantiKandarakisDunaif2012" not in processed_content
    assert "@NestlerCharney2008" not in processed_content
    # Typst-native forward links (default output_format="typst")
    assert "`#super[#link(<fn-1>)[1]]`{=typst}" in processed_content
    assert "`#super[#link(<fn-2>)[2]]`{=typst}" in processed_content
    assert "Diamanti-Kandarakis & Dunaif" in endnotes
    assert "Nestler (2008)" in endnotes
    # Typst labels for link targets in endnotes chapter
    assert '`#label("fn-1")`{=typst}' in endnotes
    assert '`#label("fn-2")`{=typst}' in endnotes


def test_prepare_render_environment_preserves_regular_footnotes_semantics_in_footnotes_mode(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text mit Fussnote[^local-note].\n\n"
        "[^local-note]: Lokale Fussnote bleibt unveraendert.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes")
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processed_tree = processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")
    original_content = source.read_text(encoding="utf-8")

    assert "Text mit Fussnote" in processed_content
    assert "Lokale Fussnote bleibt unveraendert." in processed_content
    assert "[^local-note]" in original_content
    assert "[^local-note]: Lokale Fussnote bleibt unveraendert." in original_content
    assert not (book / "processed" / "Endnoten.md").exists()
    assert all(item["path"] != "processed/Endnoten.md" for item in processed_tree)


def test_prepare_render_environment_namespaces_duplicate_footnote_labels_in_footnotes_mode(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source_a = book / "content" / "a.md"
    source_b = book / "content" / "b.md"
    _write(
        source_a,
        "---\n"
        "title: \"A\"\n"
        "description: \"A\"\n"
        "---\n\n"
        "Text A[^1].\n\n"
        "[^1]: Fussnote A.\n",
    )
    _write(
        source_b,
        "---\n"
        "title: \"B\"\n"
        "description: \"B\"\n"
        "---\n\n"
        "Text B[^1].\n\n"
        "[^1]: Fussnote B.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes")
    tree_data = [
        {"title": "A", "path": "content/a.md", "children": []},
        {"title": "B", "path": "content/b.md", "children": []},
    ]

    processor.prepare_render_environment(tree_data)

    processed_a = (book / "processed" / "content" / "a.md").read_text(encoding="utf-8")
    processed_b = (book / "processed" / "content" / "b.md").read_text(encoding="utf-8")

    assert "[^1]" not in processed_a
    assert "[^1]" not in processed_b
    assert "Fussnote A." in processed_a
    assert "Fussnote B." in processed_b


def test_prepare_render_environment_adds_footnote_backlink_in_footnotes_mode(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text mit Fussnote[^local-note].\n\n"
        "[^local-note]: Lokale Fussnote.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes")
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")

    assert re.search(r"\[\]\{#fnref-[A-Za-z0-9_-]+-1\}\[\^[^\]]+\]", processed_content)
    assert re.search(r"\[↩\]\(#fnref-[A-Za-z0-9_-]+-1\)", processed_content)


def test_prepare_render_environment_adds_multiple_backlinks_for_reused_footnote(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Erster Verweis[^same-note]. Zweiter Verweis[^same-note].\n\n"
        "[^same-note]: Geteilte Fussnote.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes")
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")

    assert re.search(r"\[↩1\]\(#fnref-[A-Za-z0-9_-]+-1\)", processed_content)
    assert re.search(r"\[↩2\]\(#fnref-[A-Za-z0-9_-]+-2\)", processed_content)


def test_prepare_render_environment_can_disable_footnote_backlinks(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text mit Fussnote[^local-note].\n\n"
        "[^local-note]: Lokale Fussnote.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes", enable_footnote_backlinks=False)
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")

    assert "[↩]" not in processed_content
    assert "fnref-" not in processed_content
