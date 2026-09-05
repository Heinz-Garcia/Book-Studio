"""Tests fuer den Abgleich zwischen Buchtext und Klassen-Abbildung (Stufe 1).

Der Anlass war messbar: Im echten Buchprojekt hatte **keine** der benutzten
Klassen eine Zuordnung -- rund 640 Absaetze waeren in der ``.docx``
unformatiert herausgekommen, ohne dass irgendetwas darauf hingewiesen haette.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tools.doclayout.library import load_layout
from tools.doclayout.schema import LayoutDefinition
from tools.doclayout.usage import (
    GENERATOR_CLASSES_FILE,
    QUARTO_BUILTIN_CLASSES,
    compare,
    markdown_files,
    read_generator_classes,
    scan_book,
    scan_book_detailed,
    scan_text,
    scan_text_detailed,
    suggested_style_id,
    write_generator_classes,
)


@pytest.fixture()
def layout() -> LayoutDefinition:
    return load_layout("IFJN_layout")


def _book(root: Path, **dateien: str) -> Path:
    (root / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (root / "content").mkdir(exist_ok=True)
    for name, text in dateien.items():
        (root / "content" / f"{name}.md").write_text(text, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Textanalyse
# ---------------------------------------------------------------------------


def test_a_class_is_found_in_the_attribute_form():
    assert scan_text("::: {.merksatz}\nText\n:::\n") == ["merksatz"]


def test_the_short_form_without_braces_counts_too():
    assert scan_text("::: merksatz\nText\n:::\n") == ["merksatz"]


def test_several_classes_in_one_block_all_count():
    assert scan_text('::: {.a .b #id key="x"}\nText\n:::\n') == ["a", "b"]


def test_the_closing_line_is_not_a_class():
    assert scan_text("::: {.a}\nText\n:::\n") == ["a"]


def test_four_colons_open_a_div_as_well():
    assert scan_text(":::: {.aussen}\nText\n::::\n") == ["aussen"]


def test_a_class_inside_a_code_fence_is_ignored():
    """Ein Beispiel in der Dokumentation fordert keine Vorlage an."""
    text = "```\n::: {.nurbeispiel}\n```\n\n::: {.echt}\nText\n:::\n"
    assert scan_text(text) == ["echt"]


def test_the_braced_form_without_a_dot_counts_as_a_usage():
    """Die Altform funktioniert -- ``classmap.lua`` streift die Klammern ab.

    Frueher stand sie hier als Textfehler: nicht mitgezaehlt, dafuer rot
    gemeldet. Das war doppelt falsch. Im echten Buch hiess das: 240 Bloecke,
    die ihr Absatzformat sehr wohl bekommen, wurden als "keine Vorlage kann
    sie ansprechen" ausgewiesen -- und tauchten zugleich in keiner Zaehlung
    auf, sodass der Assistent gar keine Vorlage dafuer anbot.
    """
    valid, legacy = scan_text_detailed("::: {beruf}\nText\n:::\n")
    assert valid == ["beruf"]
    assert legacy == ["beruf"]


def test_the_legacy_form_stands_beside_the_correct_one():
    valid, legacy = scan_text_detailed("::: {.gut}\nA\n:::\n\n::: {alt}\nB\n:::\n")
    assert valid == ["gut", "alt"]
    assert legacy == ["alt"]


# ---------------------------------------------------------------------------
# Dateiauswahl
# ---------------------------------------------------------------------------


def test_generated_directories_are_skipped(tmp_path: Path):
    book = _book(tmp_path, kapitel="::: {.a}\nX\n:::\n")
    for ordner in ("export", "_book", ".quarto"):
        (book / ordner).mkdir()
        (book / ordner / "kopie.md").write_text("::: {.b}\nX\n:::\n", encoding="utf-8")
    namen = {p.name for p in markdown_files(book)}
    assert namen == {"kapitel.md"}


def test_processed_is_skipped_when_content_exists(tmp_path: Path):
    """Sonst zaehlte jede Klasse doppelt -- Quelle und Vorverarbeitung."""
    book = _book(tmp_path, kapitel="::: {.a}\nX\n:::\n")
    (book / "processed").mkdir()
    (book / "processed" / "kapitel.md").write_text("::: {.a}\nX\n:::\n", encoding="utf-8")
    assert scan_book(book)["a"].count == 1


def test_processed_is_read_when_there_is_no_content(tmp_path: Path):
    """Ohne content/ waere Ueberspringen schlimmer als Doppelzaehlen."""
    (tmp_path / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (tmp_path / "processed").mkdir()
    (tmp_path / "processed" / "k.md").write_text("::: {.a}\nX\n:::\n", encoding="utf-8")
    assert "a" in scan_book(tmp_path)


def test_a_missing_book_yields_nothing(tmp_path: Path):
    assert scan_book(tmp_path / "gibtsnicht") == {}


# ---------------------------------------------------------------------------
# Zaehlung
# ---------------------------------------------------------------------------


def test_occurrences_and_files_are_counted(tmp_path: Path):
    book = _book(
        tmp_path,
        eins="::: {.a}\nX\n:::\n\n::: {.a}\nY\n:::\n",
        zwei="::: {.a}\nZ\n:::\n",
    )
    entry = scan_book(book)["a"]
    assert entry.count == 3
    assert entry.files == ("content/eins.md", "content/zwei.md")


# ---------------------------------------------------------------------------
# Vergleich
# ---------------------------------------------------------------------------


def test_a_class_without_a_mapping_is_reported(tmp_path: Path, layout: LayoutDefinition):
    book = _book(tmp_path, k="::: {.merksatz}\nX\n:::\n")
    result = compare(scan_book(book), layout)
    assert [u.name for u in result.unmapped] == ["merksatz"]
    assert result.is_complete is False


def test_a_mapped_class_is_not_a_gap(tmp_path: Path, layout: LayoutDefinition):
    book = _book(tmp_path, k="::: {.prompt}\nX\n:::\n")
    result = compare(scan_book(book), layout)
    assert [m.name for m in result.mapped] == ["prompt"]
    assert result.is_complete is True


def test_quarto_classes_are_not_reported_as_a_gap(tmp_path: Path, layout: LayoutDefinition):
    """Ein Fehlalarm hier deckte die echten Funde zu."""
    assert "callout-note" in QUARTO_BUILTIN_CLASSES
    book = _book(tmp_path, k="::: {.callout-note}\nX\n:::\n")
    result = compare(scan_book(book), layout)
    assert result.unmapped == ()
    assert [b.name for b in result.builtin] == ["callout-note"]


def test_quarto_classes_can_be_demanded_explicitly(tmp_path: Path, layout: LayoutDefinition):
    book = _book(tmp_path, k="::: {.callout-note}\nX\n:::\n")
    result = compare(scan_book(book), layout, ignore_builtins=False)
    assert [u.name for u in result.unmapped] == ["callout-note"]


def test_mappings_without_a_use_are_listed(tmp_path: Path, layout: LayoutDefinition):
    book = _book(tmp_path, k="Nur Text.\n")
    result = compare(scan_book(book), layout)
    assert set(result.unused) == set(layout.classmap)


def test_gaps_are_sorted_by_frequency(tmp_path: Path, layout: LayoutDefinition):
    book = _book(
        tmp_path,
        k="::: {.selten}\nX\n:::\n" + "::: {.oft}\nY\n:::\n" * 3,
    )
    result = compare(scan_book(book), layout)
    assert [u.name for u in result.unmapped] == ["oft", "selten"]


def test_the_legacy_form_reaches_the_comparison(tmp_path: Path, layout: LayoutDefinition):
    """Sie steht in ``legacy_form`` **und** in der normalen Einordnung."""
    book = _book(tmp_path, k="::: {beruf}\nX\n:::\n")
    gueltig, altform = scan_book_detailed(book)
    result = compare(gueltig, layout, legacy_form=altform)
    assert [m.name for m in result.legacy_form] == ["beruf"]
    assert [u.name for u in result.unmapped] == ["beruf"]


def test_a_mapped_class_in_the_legacy_form_is_no_gap(tmp_path: Path, layout: LayoutDefinition):
    """Der Fehlalarm, wortwoertlich: ``.prompt`` hat eine Vorlage, so oder so."""
    book = _book(tmp_path, k="::: {prompt}\nX\n:::\n")
    gueltig, altform = scan_book_detailed(book)
    result = compare(gueltig, layout, legacy_form=altform)
    assert [m.name for m in result.mapped] == ["prompt"]
    assert result.unmapped == ()
    assert result.is_complete is True


def test_the_summary_names_the_legacy_form_too(tmp_path: Path, layout: LayoutDefinition):
    book = _book(tmp_path, k="::: {.prompt}\nX\n:::\n\n::: {prompt}\nY\n:::\n")
    gueltig, altform = scan_book_detailed(book)
    text = compare(gueltig, layout, legacy_form=altform).summary()
    assert "Altform" in text


# ---------------------------------------------------------------------------
# Namensvorschlag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("klasse", "erwartet"),
    [
        ("merksatz", "Merksatz"),
        ("prompt-separator", "PromptSeparator"),
        ("eof_spacer", "EofSpacer"),
        ("a", "A"),
    ],
)
def test_a_style_id_is_suggested_from_the_class(klasse: str, erwartet: str):
    assert suggested_style_id(klasse) == erwartet


def test_an_existing_style_is_never_overwritten():
    """Der teuerste denkbare Nebeneffekt waere, eine Vorlage zu ueberschreiben."""
    assert suggested_style_id("merksatz", {"Merksatz"}) == "Merksatz2"
    assert suggested_style_id("merksatz", {"Merksatz", "Merksatz2"}) == "Merksatz3"


# ---------------------------------------------------------------------------
# Auskunft des Generators (Stufe 2)
# ---------------------------------------------------------------------------


def test_the_generator_report_survives_writing_and_reading(tmp_path: Path):
    payload = {
        "names": ["prompt", "merksatz"],
        "counts": {"prompt": 5, "merksatz": 2},
        "malformed": {"beruf": 1},
    }
    write_generator_classes(tmp_path, payload, source="Publish_X")
    gelesen = read_generator_classes(tmp_path)
    assert gelesen.names == ("prompt", "merksatz")
    assert gelesen.counts == {"prompt": 5, "merksatz": 2}
    assert gelesen.malformed == {"beruf": 1}
    assert gelesen.source == "Publish_X"


def test_the_report_lands_in_bookconfig(tmp_path: Path):
    target = write_generator_classes(tmp_path, {"names": [], "counts": {}})
    assert target == tmp_path / GENERATOR_CLASSES_FILE


def test_a_missing_report_is_not_an_error(tmp_path: Path):
    assert read_generator_classes(tmp_path) is None


def test_a_broken_report_is_not_an_error(tmp_path: Path):
    path = tmp_path / GENERATOR_CLASSES_FILE
    path.parent.mkdir(parents=True)
    path.write_text("{kein json", encoding="utf-8")
    assert read_generator_classes(tmp_path) is None


def test_names_are_derived_when_the_report_omits_them(tmp_path: Path):
    """Aeltere oder fremde Schreiber muessen nicht alles liefern."""
    path = tmp_path / GENERATOR_CLASSES_FILE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"counts": {"a": 1, "b": 9}}), encoding="utf-8")
    assert read_generator_classes(tmp_path).names == ("b", "a")


# ---------------------------------------------------------------------------
# Der Fund, der das Ganze ausgeloest hat
# ---------------------------------------------------------------------------


def test_a_layout_from_another_band_matches_nothing(tmp_path: Path):
    """Genau der gemessene Ausgangszustand: kein einziger Treffer."""
    fremd = replace(
        load_layout("IFJN_layout"),
        classmap={"prompt": "Prompt-Frage", "fachtext": "Fachtext"},
    )
    book = _book(
        tmp_path,
        k="::: {.answer}\nA\n:::\n\n::: {.monospace}\nB\n:::\n",
    )
    result = compare(scan_book(book), fremd)
    assert [u.name for u in result.unmapped] == ["answer", "monospace"]
    assert result.mapped == ()
    assert set(result.unused) == {"prompt", "fachtext"}
