"""Textauszeichnungs-Inventar: Herkunft, Benutzung und Vorlage in einer Zeile.

Die drei Auskuenfte lagen bisher getrennt vor. Erst zusammengelegt beantworten
sie die Fragen, die in der Praxis auftauchen: Warum bleibt ein Abschnitt im
.docx Fliesstext (Auszeichnung ohne Vorlage) und wo kommt eine Vorlage her,
die niemand kennt (Vorlage ohne Auszeichnung).
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tools.doclayout.library import load_layout
from tools.doclayout.markup_inventory import (
    Verdict,
    build_markup_inventory,
)
from tools.doclayout.usage import GENERATOR_CLASSES_FILE


@pytest.fixture()
def bibliothek(tmp_path: Path) -> Path:
    """Zwei Layouts: beide kennen ``fachtext``, nur eines ``themenblock``."""
    ordner = tmp_path / "library"
    ordner.mkdir()
    basis = load_layout("IFJN_layout")
    replace(basis, name="Alpha", classmap={"fachtext": "Fachtext"}).save(
        ordner / "Alpha.yaml"
    )
    replace(
        basis,
        name="Beta",
        classmap={"fachtext": "Fachtext", "themenblock": "Themenblock"},
    ).save(ordner / "Beta.yaml")
    return ordner


@pytest.fixture()
def buch(tmp_path: Path) -> Path:
    """Buchprojekt mit einem Kapitel: fachtext 2x, spanisch 1x."""
    root = tmp_path / "buch"
    (root / "content").mkdir(parents=True)
    (root / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (root / "content" / "kapitel.qmd").write_text(
        "\n".join(
            [
                "::: {.fachtext}",
                "Erster Text.",
                ":::",
                "",
                "::: {.fachtext}",
                "Zweiter Text.",
                ":::",
                "",
                "::: {.spanisch}",
                "Urgencias",
                ":::",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return root


def _generator_meldung(buch: Path, counts: dict[str, int]) -> None:
    ziel = buch / GENERATOR_CLASSES_FILE
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "names": list(counts),
                "counts": counts,
                "malformed": {},
                "source": "Publish_Test",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class TestBefunde:
    def test_benutzt_ohne_vorlage(self, buch: Path, bibliothek: Path) -> None:
        inv = build_markup_inventory(buch, library_dir=bibliothek)
        namen = [row.name for row in inv.without_template]
        assert namen == ["spanisch"]

    def test_vorlage_ohne_benutzung_ist_karteileiche(self, buch, bibliothek) -> None:
        inv = build_markup_inventory(buch, library_dir=bibliothek)
        assert [row.name for row in inv.orphans] == ["themenblock"]

    def test_benutzt_und_zugeordnet_ist_ok(self, buch: Path, bibliothek: Path) -> None:
        zeile = next(r for r in build_markup_inventory(buch, library_dir=bibliothek).rows
                     if r.name == "fachtext")
        assert zeile.verdict is Verdict.OK
        assert zeile.book_count == 2
        assert zeile.styles == ("Fachtext",)

    def test_probleme_stehen_oben(self, buch: Path, bibliothek: Path) -> None:
        """Wer die Tabelle oeffnet, soll nicht scrollen muessen."""
        inv = build_markup_inventory(buch, library_dir=bibliothek)
        assert inv.rows[0].verdict is Verdict.OHNE_VORLAGE
        assert inv.rows[1].verdict is Verdict.KARTEILEICHE

    def test_sauberes_buch(self, tmp_path: Path, bibliothek: Path) -> None:
        root = tmp_path / "sauber"
        (root / "content").mkdir(parents=True)
        (root / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
        (root / "content" / "k.qmd").write_text(
            "::: {.fachtext}\nText.\n:::\n", encoding="utf-8"
        )
        inv = build_markup_inventory(root, library_dir=bibliothek)
        assert inv.is_clean
        assert "themenblock" in [row.name for row in inv.orphans]


class TestHerkunft:
    def test_ohne_generator_meldung_gilt_der_buchtext(self, buch, bibliothek) -> None:
        inv = build_markup_inventory(buch, library_dir=bibliothek)
        zeile = next(r for r in inv.rows if r.name == "spanisch")
        assert zeile.origin == "Buchtext"
        assert not zeile.from_generator

    def test_generator_wird_als_herkunft_genannt(self, buch, bibliothek) -> None:
        _generator_meldung(buch, {"spanisch": 4})
        inv = build_markup_inventory(buch, library_dir=bibliothek)
        zeile = next(r for r in inv.rows if r.name == "spanisch")
        assert zeile.origin == "Generator"
        assert zeile.generator_count == 4

    def test_layouts_werden_gezaehlt(self, buch: Path, bibliothek: Path) -> None:
        zeile = next(r for r in build_markup_inventory(buch, library_dir=bibliothek).rows
                     if r.name == "fachtext")
        assert zeile.origin == "Buchtext + 2 Layouts"

    def test_einzelnes_layout_im_singular(self, buch: Path, bibliothek: Path) -> None:
        zeile = next(r for r in build_markup_inventory(buch, library_dir=bibliothek).rows
                     if r.name == "themenblock")
        assert zeile.origin == "1 Layout"

    def test_vom_generator_gemeldet_aber_nicht_im_buch(self, buch, bibliothek) -> None:
        """Der Export kann melden, was inzwischen aus dem Buch verschwand."""
        _generator_meldung(buch, {"weg": 3})
        zeile = next(r for r in build_markup_inventory(buch, library_dir=bibliothek).rows
                     if r.name == "weg")
        assert zeile.verdict is Verdict.OHNE_VORLAGE
        assert zeile.book_count == 0


class TestZusammenfassung:
    def test_nennt_beide_gruppen(self, buch: Path, bibliothek: Path) -> None:
        text = build_markup_inventory(buch, library_dir=bibliothek).summary()
        assert ".spanisch" in text
        assert ".themenblock" in text

    def test_sauber_meldet_vollstaendigkeit(self, tmp_path: Path) -> None:
        leer = tmp_path / "leer"
        (leer / "content").mkdir(parents=True)
        (leer / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
        leere_bib = tmp_path / "keine_layouts"
        leere_bib.mkdir()
        inv = build_markup_inventory(leer, library_dir=leere_bib)
        assert inv.summary() == "Keine Textauszeichnungen gefunden."


class TestRobustheit:
    def test_fehlendes_buch_wirft_nicht(self, tmp_path: Path, bibliothek: Path) -> None:
        inv = build_markup_inventory(tmp_path / "gibt_es_nicht", library_dir=bibliothek)
        # Die Layouts kennt es trotzdem -- sie haengen nicht am Buch.
        assert [row.name for row in inv.orphans] == ["fachtext", "themenblock"]

    def test_leere_bibliothek_macht_alles_zur_luecke(self, buch, tmp_path) -> None:
        leer = tmp_path / "ohne_layouts"
        leer.mkdir()
        inv = build_markup_inventory(buch, library_dir=leer)
        assert {row.name for row in inv.without_template} == {"fachtext", "spanisch"}


class TestGestaltungUndHandlung:
    """„ok" reicht nicht: Ein Format kann existieren und trotzdem nichts tun.

    ``Fehlende Formate anlegen`` erzeugt Absatzformate, die von ``BodyText``
    erben und sonst nichts tragen -- ausdruecklich so gewollt. Danach meldet
    das Inventar „ok", waehrend der Abschnitt im Satz weiter aussieht wie
    Fliesstext. Genau diese Luecke schliessen die Spalten „gestaltet?" und
    „Zu tun".
    """

    def _bibliothek_mit(self, ordner: Path, classmap: dict, styles: list) -> Path:
        from tools.doclayout.schema import LayoutDefinition

        basis = load_layout("IFJN_layout")
        definition = replace(basis, name="Solo", classmap=classmap)
        for style in styles:
            definition = definition.with_style(style)
        ordner.mkdir(exist_ok=True)
        definition.save(ordner / "Solo.yaml")
        return ordner

    def test_leeres_format_gilt_als_ungestaltet(self, buch: Path, tmp_path: Path) -> None:
        from tools.doclayout.schema import ParagraphStyle

        bib = self._bibliothek_mit(
            tmp_path / "bib1",
            {"spanisch": "Spanisch"},
            [ParagraphStyle(style_id="Spanisch", name="Spanisch", based_on="BodyText")],
        )
        zeile = next(r for r in build_markup_inventory(buch, library_dir=bib).rows
                     if r.name == "spanisch")
        assert zeile.verdict is Verdict.OK
        assert zeile.styled is False
        assert zeile.todo == "Gestalten"

    def test_gestaltetes_format_verlangt_nichts(self, buch: Path, tmp_path: Path) -> None:
        from tools.doclayout.schema import ParagraphStyle

        bib = self._bibliothek_mit(
            tmp_path / "bib2",
            {"spanisch": "Spanisch"},
            [ParagraphStyle(style_id="Spanisch", name="Spanisch", italic=True, size_pt=10.5)],
        )
        zeile = next(r for r in build_markup_inventory(buch, library_dir=bib).rows
                     if r.name == "spanisch")
        assert zeile.styled is True
        assert zeile.todo == ""
        assert "kursiv" in zeile.appearance
        assert "10.5 pt" in zeile.appearance

    def test_ohne_vorlage_heisst_anlegen(self, buch: Path, tmp_path: Path) -> None:
        leer = tmp_path / "leer"
        leer.mkdir()
        zeile = next(r for r in build_markup_inventory(buch, library_dir=leer).rows
                     if r.name == "spanisch")
        assert zeile.todo == "Format anlegen"
        assert zeile.styled is None

    def test_karteileiche_heisst_pruefen(self, buch: Path, bibliothek: Path) -> None:
        zeile = next(r for r in build_markup_inventory(buch, library_dir=bibliothek).rows
                     if r.name == "themenblock")
        assert zeile.todo.startswith("Prüfen")

    def test_uneinige_layouts_sagen_es(self, buch: Path, tmp_path: Path) -> None:
        """Zwei Layouts, zwei Fassungen -- keine davon ist die Wahrheit."""
        from tools.doclayout.markup_inventory import UNEINHEITLICH
        from tools.doclayout.schema import ParagraphStyle

        ordner = tmp_path / "uneinig"
        ordner.mkdir()
        basis = load_layout("IFJN_layout")
        for name, style in (
            ("A", ParagraphStyle(style_id="Spanisch", name="Spanisch", italic=True)),
            ("B", ParagraphStyle(style_id="Spanisch", name="Spanisch", bold=True)),
        ):
            replace(basis, name=name, classmap={"spanisch": "Spanisch"}).with_style(
                style
            ).save(ordner / f"{name}.yaml")
        zeile = next(r for r in build_markup_inventory(buch, library_dir=ordner).rows
                     if r.name == "spanisch")
        assert zeile.appearance == UNEINHEITLICH
        assert zeile.styled is None

    def test_beschreibung_nennt_nur_sichtbares(self) -> None:
        """``based_on`` sagt nichts darueber, wie etwas aussieht."""
        from tools.doclayout.markup_inventory import (
            OHNE_GESTALTUNG,
            describe_paragraph_style,
        )
        from tools.doclayout.schema import ParagraphStyle

        nur_name = ParagraphStyle(style_id="X", name="X", based_on="BodyText",
                                  next_style="BodyText")
        assert describe_paragraph_style(nur_name) == OHNE_GESTALTUNG
        bunt = ParagraphStyle(style_id="Y", name="Y", bold=True, color="accent",
                              shading="f0f0f0", space_after_pt=6.0)
        assert describe_paragraph_style(bunt) == "fett, Farbe accent, hinterlegt, Abstände"
