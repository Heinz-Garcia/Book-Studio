"""Tests für automatische Recto-Öffnung (recto_open / PreProcessor)."""

from __future__ import annotations

from pathlib import Path

from pre_processor import PreProcessor
from recto_open import (
    RECTO_MARKER,
    maybe_ensure_recto_open,
    should_open_on_recto,
    strip_manual_recto_breaks,
)


def test_should_open_content_yes_required_no():
    assert should_open_on_recto({"title": "Diagnose"}) is True
    assert should_open_on_recto({"title": "Vakanz", "required": True}) is False


def test_should_open_respects_explicit_open_recto():
    assert should_open_on_recto({"title": "Widmung", "open_recto": False}) is False
    assert should_open_on_recto(
        {"title": "Vakanz", "required": True, "open_recto": True}
    ) is True


def test_strip_removes_typst_odd_start_and_end():
    body = (
        "```{=typst}\n"
        '#pagebreak(weak: true, to: "odd")\n'
        "```\n\n"
        "Text.\n\n"
        "```{=typst}\n"
        '#pagebreak(to: "odd")\n'
        "```\n"
    )
    out = strip_manual_recto_breaks(body)
    assert "to: \"odd\"" not in out
    assert "Text." in out


def test_inject_typst_recto_and_dedup():
    fm = "---\ntitle: Diagnose\n---\n"
    body = (
        "```{=typst}\n"
        '#pagebreak(weak: true, to: "odd")\n'
        "```\n\n"
        "Hallo\n"
    )
    out = maybe_ensure_recto_open(fm, body, output_format="typst")
    assert out.count('to: "odd"') == 1
    assert RECTO_MARKER in out
    assert out.index(RECTO_MARKER) < out.index("Hallo")


def test_docx_body_gets_no_start_block():
    """DOCX: kein Abschnittsumbruch am Body-Anfang (stünde hinter der Überschrift)."""
    fm = "---\ntitle: Diagnose\n---\n"
    out = maybe_ensure_recto_open(fm, "Hallo\n", output_format="docx")
    assert out == "Hallo\n"


def test_strip_keeps_paragraphs_apart():
    body = (
        "Para A\n\n"
        "```{=typst}\n"
        '#pagebreak(to: "odd")\n'
        "```\n\n"
        "Para B\n\n\n\nPara C\n"
    )
    out = strip_manual_recto_breaks(body)
    # Mitten im Kapitel bleibt alles unangetastet (kein Verschmelzen von A/B).
    assert out == body


def test_strip_keeps_mid_chapter_openxml_page_break():
    body = (
        "Text\n\n"
        "```{=openxml}\n"
        '<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n'
        "```\n\n"
        "Tabelle\n"
    )
    assert strip_manual_recto_breaks(body) == body


def test_strip_removes_leading_openxml_page_break():
    body = (
        "```{=openxml}\n"
        '<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n'
        "```\n\n"
        "Text\n"
    )
    assert strip_manual_recto_breaks(body) == "Text\n"


def _docx_book(tmp_path: Path, chapters: list[tuple[str, str]], *, reference: bool = False):
    import zipfile

    book = tmp_path / "Book"
    (book / "content").mkdir(parents=True)
    (book / "index.md").write_text("---\ntitle: I\nunnumbered: true\n---\n\nVorwort\n", encoding="utf-8")
    if reference:
        ref = book / "ref.docx"
        with zipfile.ZipFile(ref, "w") as zf:
            zf.writestr(
                "word/document.xml",
                '<w:document><w:body><w:p/><w:sectPr><w:headerReference w:type="default" r:id="rId9"/><w:pgNumType w:start="1"/><w:pgSz w:w="8391" w:h="11906"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>'
                "</w:sectPr></w:body></w:document>",
            )
        (book / "_quarto.yml").write_text(
            "format:\n  docx:\n    reference-doc: ref.docx\n", encoding="utf-8"
        )
    tree = []
    for name, fm in chapters:
        (book / "content" / f"{name}.md").write_text(f"---\n{fm}\n---\n\nText {name}\n", encoding="utf-8")
        tree.append({"title": name, "path": f"content/{name}.md", "children": []})
    PreProcessor(book, output_format="docx").prepare_render_environment(tree)
    return book


def _read(book: Path, name: str) -> str:
    return (book / "processed" / "content" / f"{name}.md").read_text(encoding="utf-8")


def test_docx_sections_close_at_end_of_each_chapter(tmp_path: Path):
    book = _docx_book(
        tmp_path,
        [
            ("Widmung", "title: Widmung\nopen_recto: false"),
            ("Eins", "title: Eins"),
            ("Zwei", "title: Zwei"),
        ],
    )
    index = (book / "index.md").read_text(encoding="utf-8")
    assert index.rstrip().endswith("```")
    assert 'w:val="continuous"' in index
    widmung = _read(book, "Widmung")
    assert 'w:val="continuous"' in widmung
    eins = _read(book, "Eins")
    # Block am Ende, Text davor — Abschnitt umfasst Überschrift + Body
    assert eins.index("Text Eins") < eins.index('w:val="oddPage"')
    assert eins.rstrip().endswith("```")
    zwei = _read(book, "Zwei")
    assert 'w:val="oddPage"' in zwei  # letzte Einheit, recto → abgeschlossen


def test_docx_last_non_recto_unit_left_to_template(tmp_path: Path):
    book = _docx_book(
        tmp_path,
        [("Eins", "title: Eins"), ("Nachwort", "title: Nachwort\nopen_recto: false")],
    )
    assert "sectPr" not in _read(book, "Nachwort")


def test_docx_section_takes_page_setup_from_reference(tmp_path: Path):
    book = _docx_book(tmp_path, [("Eins", "title: Eins")], reference=True)
    eins = _read(book, "Eins")
    assert (
        '<w:sectPr><w:headerReference w:type="default" r:id="rId9"/>'
        '<w:type w:val="oddPage"/><w:pgSz w:w="8391" w:h="11906"/><w:pgMar'
    ) in eins
    assert "pgNumType" not in eins  # keine Neuzählung je Kapitel


def test_docx_index_close_is_idempotent(tmp_path: Path):
    book = _docx_book(tmp_path, [("Eins", "title: Eins")])
    tree = [{"title": "Eins", "path": "content/Eins.md", "children": []}]
    PreProcessor(book, output_format="docx").prepare_render_environment(tree)
    index = (book / "index.md").read_text(encoding="utf-8")
    assert index.count("<w:sectPr>") == 1


def _vorlage(book: Path, breite: int) -> None:
    import zipfile

    with zipfile.ZipFile(book / "ref.docx", "w") as zf:
        zf.writestr(
            "word/document.xml",
            f'<w:document><w:body><w:p/><w:sectPr><w:pgSz w:w="{breite}" w:h="11906"/>'
            "</w:sectPr></w:body></w:document>",
        )


def test_docx_index_folgt_einer_geaenderten_vorlage(tmp_path: Path):
    """prepare-only schreibt ins Original. Bis 2026-09-26 blieb der erste
    Block dort stehen, und jeder spätere Lauf übersprang das Anhängen: Nach
    einer Layout-Änderung behielt der erste Abschnitt die alte Seitengröße."""
    book = _docx_book(tmp_path, [("Eins", "title: Eins")], reference=True)
    tree = [{"title": "Eins", "path": "content/Eins.md", "children": []}]
    _vorlage(book, 9999)
    PreProcessor(book, output_format="docx").prepare_render_environment(tree)
    index = (book / "index.md").read_text(encoding="utf-8")
    assert index.count("<w:sectPr>") == 1
    assert 'w:w="9999"' in index and 'w:w="8391"' not in index


def test_docx_block_verschwindet_bei_anderem_format(tmp_path: Path):
    book = _docx_book(tmp_path, [("Eins", "title: Eins")])
    assert "<w:sectPr>" in (book / "index.md").read_text(encoding="utf-8")
    tree = [{"title": "Eins", "path": "content/Eins.md", "children": []}]
    PreProcessor(book, output_format="typst").prepare_render_environment(tree)
    index = (book / "index.md").read_text(encoding="utf-8")
    assert "sectPr" not in index and RECTO_MARKER not in index
    assert index.endswith("Vorwort\n\n")


def test_fremde_umbrueche_im_index_bleiben():
    from recto_open import ohne_eigenen_docx_abschnitt

    von_hand = "Vorwort\n\n```{=openxml}\n<w:p><w:pPr><w:sectPr/></w:pPr></w:p>\n```\n"
    assert ohne_eigenen_docx_abschnitt(von_hand) == von_hand


def test_no_recto_for_silent_page():
    fm = "---\ntitle: Vakanz\nrequired: true\n---\n"
    body = "```{=typst}\n#pagebreak()\n```\n"
    assert maybe_ensure_recto_open(fm, body, output_format="typst") == body


def test_preprocessor_injects_recto_before_title(tmp_path: Path):
    book = tmp_path / "Book"
    (book / "content").mkdir(parents=True)
    (book / "index.md").write_text("---\ntitle: I\nunnumbered: true\n---\n\n", encoding="utf-8")
    (book / "content" / "Kapitel.md").write_text(
        "---\ntitle: Echtes Kapitel\n---\n\n"
        "```{=typst}\n"
        '#pagebreak(to: "odd")\n'
        "```\n\n"
        "Hallo\n",
        encoding="utf-8",
    )
    tree = [{"title": "Echtes Kapitel", "path": "content/Kapitel.md", "children": []}]
    PreProcessor(book, output_format="typst").prepare_render_environment(tree)
    kap = (book / "processed" / "content" / "Kapitel.md").read_text(encoding="utf-8")

    assert kap.count('to: "odd"') == 1
    assert RECTO_MARKER in kap
    assert "#chapter-titles-visible.update(true)" in kap
    assert kap.index(RECTO_MARKER) < kap.index("#chapter-titles-visible.update(true)")
    assert kap.index("#chapter-titles-visible.update(true)") < kap.index("Hallo")


def test_preprocessor_docx_gets_odd_page(tmp_path: Path):
    book = tmp_path / "Book"
    (book / "content").mkdir(parents=True)
    (book / "index.md").write_text("---\ntitle: I\nunnumbered: true\n---\n\n", encoding="utf-8")
    (book / "content" / "Kapitel.md").write_text(
        "---\ntitle: Echtes Kapitel\n---\n\nHallo\n",
        encoding="utf-8",
    )
    tree = [{"title": "Echtes Kapitel", "path": "content/Kapitel.md", "children": []}]
    PreProcessor(book, output_format="docx").prepare_render_environment(tree)
    kap = (book / "processed" / "content" / "Kapitel.md").read_text(encoding="utf-8")
    assert 'w:val="oddPage"' in kap
    assert "chapter-titles-visible" not in kap  # Titel-Injection nur Typst


def test_unterkapitel_verliert_manuellen_rechtsumbruch(tmp_path: Path):
    """Amalgamierte Unterkapitel wurden nicht bereinigt: Ein manuelles
    #pagebreak(to: "odd") erzeugte eine Leerseite mitten im Kapitel."""
    book = tmp_path / "Book"
    (book / "content").mkdir(parents=True)
    (book / "index.md").write_text("---\ntitle: I\nunnumbered: true\n---\n\n", encoding="utf-8")
    (book / "content" / "Kapitel.md").write_text(
        "---\ntitle: Kapitel\n---\n\nEinleitung\n", encoding="utf-8"
    )
    (book / "content" / "Unter.md").write_text(
        "---\ntitle: Unter\n---\n\n"
        "```{=typst}\n#pagebreak(to: \"odd\")\n```\n\n"
        "## Unterkapitel\n\nMitte\n\n"
        "```{=typst}\n#pagebreak()\n```\n\nNach dem gewollten Umbruch\n",
        encoding="utf-8",
    )
    tree = [{
        "title": "Kapitel", "path": "content/Kapitel.md",
        "children": [{"title": "Unter", "path": "content/Unter.md", "children": []}],
    }]
    PreProcessor(book, output_format="typst").prepare_render_environment(tree)
    kap = (book / "processed" / "content" / "Kapitel.md").read_text(encoding="utf-8")
    assert kap.count('to: "odd"') == 1, "nur der kanonische Kapitelanfang"
    assert kap.index(RECTO_MARKER) < kap.index("Einleitung")
    assert "#pagebreak()" in kap, "gewollter Umbruch im Text bleibt"
    assert "Unterkapitel" in kap and "Mitte" in kap
