"""Tests fuer das Inventar: woraus ein Buch besteht.

Die Zuordnung Bauteil -> Absatzformat wurde gemessen, nicht abgeschrieben:
Musterdokument je Bauteil setzen, ``word/document.xml`` auslesen. Diese Tests
halten das Ergebnis fest, damit es nicht unbemerkt verrutscht.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tools.doclayout.inventory import (
    CLASS_PREFIX,
    ELEMENT_BY_KEY,
    ELEMENT_TYPES,
    STATUS_LABELS,
    Inventory,
    missing_styles,
    open_findings,
    scan_file,
    scan_inventory,
    steps_by_chapter,
    steps_by_type,
)
from tools.doclayout.library import load_layout
from tools.doclayout.schema import LayoutDefinition


@pytest.fixture()
def layout() -> LayoutDefinition:
    return load_layout("IFJN_Referenz")


def _book(root: Path, **dateien: str) -> Path:
    (root / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (root / "content").mkdir(exist_ok=True)
    for name, text in dateien.items():
        (root / "content" / f"{name}.md").write_text(text, encoding="utf-8")
    return root


def _keys(inv: Inventory) -> set[str]:
    return {f.element.key for f in inv.findings}


# ---------------------------------------------------------------------------
# Erkennung der Bauteile
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("markdown", "key"),
    [
        ("# Kapitel\n", "heading1"),
        ("## Abschnitt\n", "heading2"),
        ("###### Tief\n", "heading6"),
        ("Ein Absatz.\n", "body"),
        ("- Punkt\n", "bullet_list"),
        ("1. Erstens\n", "ordered_list"),
        ("> Zitat\n", "blockquote"),
        ("| A | B |\n", "table"),
        ("![Bild](b.png)\n", "image"),
        ("Oben.\n\n---\n\nUnten.\n", "horizontal_rule"),
        ("[^1]: Die Note.\n", "footnote"),
        (":   Erklaerung\n", "definition_list"),
    ],
)
def test_each_building_block_is_recognised(tmp_path: Path, markdown: str, key: str):
    book = _book(tmp_path, k=markdown)
    assert key in _keys(scan_inventory(book))


def test_a_code_block_counts_once_not_per_line(tmp_path: Path):
    """Zwanzig Zeilen Code sind ein Codeblock, keine zwanzig."""
    book = _book(tmp_path, k="```\n" + "x = 1\n" * 20 + "```\n")
    treffer = {f.element.key: f.count for f in scan_inventory(book).findings}
    assert treffer["code_block"] == 1


def test_frontmatter_is_not_mistaken_for_content(tmp_path: Path):
    """Regression: ``---`` im Frontmatter sah wie eine Trennlinie aus.

    Bei 116 Dateien waren das ueber zweihundert Fehltreffer -- und die
    ``- eintrag``-Zeilen einer YAML-Liste wurden als Aufzaehlung gezaehlt.
    """
    book = _book(
        tmp_path,
        k="---\ntitle: Test\nkeywords:\n  - eins\n  - zwei\n---\n\nEin Absatz.\n",
    )
    gefunden = _keys(scan_inventory(book))
    assert "horizontal_rule" not in gefunden
    assert "bullet_list" not in gefunden
    assert "body" in gefunden


def test_a_block_inside_a_code_fence_is_not_content(tmp_path: Path):
    book = _book(tmp_path, k="```\n# Keine Ueberschrift\n- keine Liste\n```\n")
    gefunden = _keys(scan_inventory(book))
    assert "heading1" not in gefunden
    assert "bullet_list" not in gefunden
    assert "code_block" in gefunden


def test_fenced_div_classes_become_their_own_building_block(tmp_path: Path):
    book = _book(tmp_path, k="::: {.merksatz}\nText\n:::\n")
    assert f"{CLASS_PREFIX}merksatz" in _keys(scan_inventory(book))


def test_occurrences_carry_a_real_excerpt(tmp_path: Path):
    """Eine Attrappe hilft niemandem beim Wiedererkennen."""
    book = _book(tmp_path, k="# Die echte Ueberschrift\n")
    finding = next(
        f for f in scan_inventory(book).findings if f.element.key == "heading1"
    )
    assert finding.samples[0].excerpt == "Die echte Ueberschrift"
    assert finding.samples[0].file == "content/k.md"


def test_only_a_few_samples_are_kept(tmp_path: Path):
    book = _book(tmp_path, k="# A\n\n# B\n\n# C\n\n# D\n\n# E\n")
    finding = next(
        f for f in scan_inventory(book).findings if f.element.key == "heading1"
    )
    assert finding.count == 5
    assert len(finding.samples) == 3


def test_an_empty_book_yields_nothing(tmp_path: Path):
    book = _book(tmp_path)
    assert scan_inventory(book).is_empty


def test_an_unreadable_file_does_not_stop_the_scan(tmp_path: Path):
    book = _book(tmp_path, gut="# Kapitel\n")
    assert scan_file(book / "content" / "fehlt.md", book) == {}
    assert "heading1" in _keys(scan_inventory(book))


# ---------------------------------------------------------------------------
# Die gemessene Zuordnung
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "erwartet"),
    [
        ("heading1", ("Heading1",)),
        ("heading3", ("Heading3",)),
        ("body", ("BodyText", "FirstParagraph")),
        ("bullet_list", ("Compact",)),
        ("ordered_list", ("Compact",)),
        ("blockquote", ("BlockText",)),
        ("code_block", ("SourceCode",)),
        ("image", ("ImageCaption",)),
        ("footnote", ("FootnoteText",)),
        ("definition_list", ("DefinitionTerm", "Definition")),
    ],
)
def test_the_measured_mapping_holds(key: str, erwartet: tuple[str, ...]):
    assert ELEMENT_BY_KEY[key].style_ids == erwartet


def test_a_horizontal_rule_has_no_style():
    """Pandoc setzt sie ohne eigenes Format -- da ist nichts einzustellen."""
    element = ELEMENT_BY_KEY["horizontal_rule"]
    assert element.style_ids == ()
    assert element.reachable is False


def test_every_element_type_has_an_explanation():
    for element in ELEMENT_TYPES:
        assert element.note.strip(), f"{element.key} erklaert sich nicht"


# ---------------------------------------------------------------------------
# Zustand
# ---------------------------------------------------------------------------


def test_a_missing_style_is_reported_as_missing(tmp_path: Path, layout):
    """SourceCode fehlt selbst in Pandocs Basisvorlage."""
    book = _book(tmp_path, k="```\nx\n```\n")
    finding = next(
        f for f in scan_inventory(book, layout).findings if f.element.key == "code_block"
    )
    assert finding.status(layout) == "missing"
    assert finding.missing_styles(layout) == ("SourceCode",)


def test_an_unmapped_class_is_not_reported_as_ok(tmp_path: Path, layout):
    """Regression: eine Klasse ohne Zuordnung galt faelschlich als fertig."""
    book = _book(tmp_path, k="::: {.merksatz}\nText\n:::\n")
    finding = next(
        f
        for f in scan_inventory(book, layout).findings
        if f.element.key == f"{CLASS_PREFIX}merksatz"
    )
    assert finding.status(layout) == "unmapped"
    assert finding.has_style(layout) is False


def test_a_mapped_class_is_ok(tmp_path: Path, layout):
    book = _book(tmp_path, k="::: {.prompt}\nText\n:::\n")
    finding = next(
        f
        for f in scan_inventory(book, layout).findings
        if f.element.key == f"{CLASS_PREFIX}prompt"
    )
    assert finding.status(layout) == "ok"


def test_a_quarto_class_needs_nothing(tmp_path: Path, layout):
    book = _book(tmp_path, k="::: {.callout-note}\nText\n:::\n")
    finding = next(
        f
        for f in scan_inventory(book, layout).findings
        if f.element.key == f"{CLASS_PREFIX}callout-note"
    )
    assert finding.status(layout) == "nothing"


def test_every_status_has_a_label():
    for zustand in ("ok", "missing", "unmapped", "nothing"):
        assert STATUS_LABELS[zustand]


def test_open_findings_lists_only_what_is_left(tmp_path: Path, layout):
    book = _book(
        tmp_path,
        k="# Kapitel\n\nText.\n\n::: {.merksatz}\nX\n:::\n\n```\ncode\n```\n",
    )
    inventar = scan_inventory(book, layout)
    offen = {f.element.key for f in open_findings(inventar, layout)}
    assert offen == {"code_block", f"{CLASS_PREFIX}merksatz"}


def test_missing_styles_are_collected_without_duplicates(tmp_path: Path, layout):
    book = _book(tmp_path, a="```\nx\n```\n", b="```\ny\n```\n")
    assert missing_styles(scan_inventory(book, layout), layout) == ["SourceCode"]


# ---------------------------------------------------------------------------
# Die zwei Ansichten
# ---------------------------------------------------------------------------


def test_the_type_view_has_one_step_per_building_block(tmp_path: Path, layout):
    book = _book(tmp_path, a="# A\n\nText.\n", b="# B\n\n- Punkt\n")
    inventar = scan_inventory(book, layout)
    schritte = steps_by_type(inventar)
    assert len(schritte) == len(inventar.findings)
    assert len({s.key for s in schritte}) == len(schritte)


def test_the_chapter_view_has_one_step_per_file(tmp_path: Path, layout):
    book = _book(tmp_path, a="# A\n", b="# B\n", c="# C\n")
    schritte = steps_by_chapter(scan_inventory(book, layout))
    assert [s.title for s in schritte] == [
        "content/a.md",
        "content/b.md",
        "content/c.md",
    ]


def test_both_views_cover_the_same_material(tmp_path: Path, layout):
    """Zwei Wege durch dasselbe -- keiner darf etwas auslassen."""
    book = _book(
        tmp_path,
        a="# A\n\nText.\n\n- Punkt\n",
        b="## B\n\n> Zitat\n\n::: {.merksatz}\nX\n:::\n",
    )
    inventar = scan_inventory(book, layout)
    per_typ = {f.element.key for s in steps_by_type(inventar) for f in s.findings}
    per_kapitel = {f.element.key for s in steps_by_chapter(inventar) for f in s.findings}
    assert per_typ == per_kapitel


def test_the_type_view_starts_with_the_body_text(tmp_path: Path, layout):
    """Erst das Grundgeruest, dann die Feinheiten."""
    book = _book(tmp_path, a="# A\n\nText.\n\n::: {.merksatz}\nX\n:::\n")
    schritte = steps_by_type(scan_inventory(book, layout))
    assert schritte[0].title == "Fließtext"
    assert schritte[-1].title.startswith("Klasse ")


def test_a_step_knows_whether_anything_can_be_set(tmp_path: Path, layout):
    book = _book(tmp_path, a="Text.\n\n---\n\nMehr.\n")
    schritte = {s.title: s for s in steps_by_type(scan_inventory(book, layout))}
    assert schritte["Trennlinie"].is_actionable is False
    assert schritte["Fließtext"].is_actionable is True


def test_files_without_findings_do_not_become_steps(tmp_path: Path, layout):
    book = _book(tmp_path, voll="# A\n", leer="")
    titel = [s.title for s in steps_by_chapter(scan_inventory(book, layout))]
    assert titel == ["content/voll.md"]


# ---------------------------------------------------------------------------
# Reales Buch
# ---------------------------------------------------------------------------


def test_the_real_book_is_covered_completely(layout):
    """Am echten Band gemessen -- das war der Anlass fuer den Assistenten."""
    buch = Path(__file__).resolve().parent.parent / "Band_Stoffwechselgesundheit"
    if not (buch / "_quarto.yml").is_file():
        pytest.skip("Band_Stoffwechselgesundheit ist nicht vorhanden")
    inventar = scan_inventory(buch, layout)
    assert not inventar.is_empty
    keys = _keys(inventar)
    assert "body" in keys and "heading1" in keys
    # Jeder Fund landet in beiden Ansichten.
    assert len(steps_by_type(inventar)) == len(inventar.findings)
    assert len(steps_by_chapter(inventar)) == len(inventar.per_file)


def test_a_definition_stays_untouched_by_a_scan(tmp_path: Path, layout):
    """Das Inventar liest nur -- es aendert das Layout nicht."""
    book = _book(tmp_path, k="```\nx\n```\n")
    vorher = replace(layout)
    scan_inventory(book, layout)
    assert layout.styles == vorher.styles
    assert layout.classmap == vorher.classmap

def test_a_rule_at_the_very_top_of_a_file_is_frontmatter(tmp_path: Path):
    """Bekannte Grenze, bewusst so.

    ``---`` in der ersten Zeile eroeffnet in einem Quarto-Projekt YAML-
    Frontmatter -- der SSOT-Parser entfernt es, auch ohne schliessendes
    Gegenstueck. Eine Trennlinie ganz oben ist damit nicht erkennbar. In einem
    echten Buch ist das der seltenere Fall; ihn zu retten hiesse, das
    Frontmatter jeder Datei falsch zu lesen.
    """
    book = _book(tmp_path, k="---\n\nText.\n")
    gefunden = _keys(scan_inventory(book))
    assert "horizontal_rule" not in gefunden
    assert "body" in gefunden


# ---------------------------------------------------------------------------
# «fertig» war gelogen
# ---------------------------------------------------------------------------


def test_an_empty_style_is_not_reported_as_finished(tmp_path: Path, layout):
    """Regression: «fertig» hiess nur, dass ein Format dieses Namens existiert.

    Wer den Assistenten benutzt und ein Format anlegen laesst, sah danach
    «fertig» -- ohne je etwas gestaltet zu haben.
    """
    from dataclasses import replace as _replace

    from tools.doclayout.schema import ParagraphStyle

    leer = _replace(
        layout,
        styles={
            **layout.styles,
            "Heading1": ParagraphStyle(style_id="Heading1", based_on="BodyText"),
        },
    )
    book = _book(tmp_path, k="# Kapitel\n")
    finding = next(
        f for f in scan_inventory(book, leer).findings if f.element.key == "heading1"
    )
    assert finding.status(leer) == "plain"


def test_a_designed_style_is_reported_as_present(tmp_path: Path, layout):
    book = _book(tmp_path, k="# Kapitel\n")
    finding = next(
        f for f in scan_inventory(book, layout).findings if f.element.key == "heading1"
    )
    assert layout.styles["Heading1"].carries_formatting() is True
    assert finding.status(layout) == "ok"


def test_the_label_no_longer_claims_completion():
    """«fertig» hat genau die Frage aufgeworfen, die es beantworten sollte."""
    assert STATUS_LABELS["ok"] == "Vorlage vorhanden"
    assert "fertig" not in STATUS_LABELS.values()


def test_an_ungestylt_template_is_not_an_open_item(tmp_path: Path, layout):
    """Gestalten ist Arbeit des Benutzers, kein offener Posten des Werkzeugs."""
    from dataclasses import replace as _replace

    from tools.doclayout.schema import ParagraphStyle

    leer = _replace(
        layout,
        styles={
            **layout.styles,
            "Heading1": ParagraphStyle(style_id="Heading1", based_on="BodyText"),
        },
    )
    book = _book(tmp_path, k="# Kapitel\n")
    inventar = scan_inventory(book, leer)
    assert open_findings(inventar, leer) == ()
    finding = next(f for f in inventar.findings if f.element.key == "heading1")
    assert finding.has_style(leer) is True


def test_every_status_including_plain_has_a_label():
    for zustand in ("ok", "plain", "missing", "unmapped", "nothing"):
        assert STATUS_LABELS[zustand]
