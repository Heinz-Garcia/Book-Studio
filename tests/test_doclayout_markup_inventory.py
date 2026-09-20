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

    def test_zeile_traegt_buchzitate_als_snippets(self, buch: Path, bibliothek: Path) -> None:
        """Hover/Tooltip braucht echte Textproben, nicht nur die Zaehlung."""
        zeile = next(
            r
            for r in build_markup_inventory(buch, library_dir=bibliothek).rows
            if r.name == "fachtext"
        )
        assert len(zeile.snippets) == 2
        assert any("Erster Text" in s for s in zeile.snippets)
        assert any("Zweiter Text" in s for s in zeile.snippets)
        assert all("content/" in s or s.startswith("content/") for s in zeile.snippets)

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
        # Im Buch UND auf dem Import-Lieferschein -- beides nennen.
        assert zeile.origin == "Buchtext + Import-Meldung"
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
        assert zeile.origin == "Import-Meldung"


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

    def test_ungleiche_fassungen_desselben_formats_sind_kein_fehler(
        self, buch: Path, tmp_path: Path
    ) -> None:
        """Gleiches Absatzformat in zwei Layouts, abweichende Gestaltung.

        Die Bibliothek darf Varianten halten -- das ist kein Buchfehler.
        ``uneinheitlich`` gilt nur, wenn eine Klasse auf mehrere Style-IDs zeigt.
        """
        from tools.doclayout.markup_inventory import UNEINHEITLICH
        from tools.doclayout.schema import ParagraphStyle

        ordner = tmp_path / "varianten"
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
        assert zeile.appearance != UNEINHEITLICH
        assert zeile.styled is True
        assert zeile.todo == ""
        assert zeile.appearance in {"kursiv", "fett"}

    def test_zwei_absatzformate_fuer_eine_klasse_sind_uneinheitlich(
        self, buch: Path, tmp_path: Path
    ) -> None:
        """Eine Auszeichnung → zwei Style-IDs: das ist der Buchfehler."""
        from tools.doclayout.markup_inventory import UNEINHEITLICH
        from tools.doclayout.schema import ParagraphStyle

        ordner = tmp_path / "uneinig"
        ordner.mkdir()
        basis = load_layout("IFJN_layout")
        replace(
            basis, name="A", classmap={"spanisch": "Spanisch"}
        ).with_style(
            ParagraphStyle(style_id="Spanisch", name="Spanisch", italic=True)
        ).save(ordner / "A.yaml")
        replace(
            basis, name="B", classmap={"spanisch": "SpanischFett"}
        ).with_style(
            ParagraphStyle(style_id="SpanischFett", name="Spanisch Fett", bold=True)
        ).save(ordner / "B.yaml")
        zeile = next(r for r in build_markup_inventory(buch, library_dir=ordner).rows
                     if r.name == "spanisch")
        assert zeile.appearance == UNEINHEITLICH
        assert zeile.styled is None
        assert zeile.todo == "Vorlage vereinheitlichen"

    def test_angewandtes_layout_entscheidet_aussehen(
        self, buch: Path, tmp_path: Path
    ) -> None:
        """Nach apply zaehlt nur das Layout aus classmap.lua -- nicht die Bibliothek."""
        from tools.doclayout.classmap import write_lua_filter
        from tools.doclayout.library import book_output_dir
        from tools.doclayout.markup_inventory import UNEINHEITLICH
        from tools.doclayout.schema import ParagraphStyle

        ordner = tmp_path / "mit_apply"
        ordner.mkdir()
        basis = load_layout("IFJN_layout")
        layout_a = replace(
            basis, name="A", classmap={"spanisch": "Spanisch"}
        ).with_style(
            ParagraphStyle(style_id="Spanisch", name="Spanisch", italic=True, size_pt=10.5)
        )
        layout_a.save(ordner / "A.yaml")
        replace(
            basis, name="B", classmap={"spanisch": "SpanischFett"}
        ).with_style(
            ParagraphStyle(style_id="SpanischFett", name="Spanisch Fett", bold=True)
        ).save(ordner / "B.yaml")

        ziel = book_output_dir(buch)
        ziel.mkdir(parents=True, exist_ok=True)
        write_lua_filter(layout_a, ziel / "classmap.lua")

        zeile = next(r for r in build_markup_inventory(buch, library_dir=ordner).rows
                     if r.name == "spanisch")
        assert zeile.appearance != UNEINHEITLICH
        assert "kursiv" in zeile.appearance
        assert "10.5 pt" in zeile.appearance
        assert zeile.todo == ""

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


class TestErbfolgeUndProbe:
    """Erbfolge und wirksames Aussehen -- nicht nur die eigenen Merkmale."""

    def test_erbfolge_und_wirksames_aussehen(self, buch: Path, tmp_path: Path) -> None:
        from tools.doclayout.schema import LayoutDefinition, ParagraphStyle, Typography

        bib = tmp_path / "erb"
        bib.mkdir()
        LayoutDefinition(
            name="Solo",
            label="Solo",
            typography=Typography(body_font="Calibri", base_size_pt=11.0),
            styles={
                "BodyText": ParagraphStyle(
                    style_id="BodyText",
                    name="Fließtext",
                    based_on="Normal",
                    align="justify",
                    space_after_pt=3.0,
                    line_height=1.2,
                ),
                "Fachtext": ParagraphStyle(
                    style_id="Fachtext",
                    name="Fachtext",
                    based_on="BodyText",
                    space_before_pt=0.0,
                    space_after_pt=7.0,
                ),
            },
            classmap={"fachtext": "Fachtext"},
        ).save(bib / "Solo.yaml")

        zeile = next(
            r
            for r in build_markup_inventory(buch, library_dir=bib).rows
            if r.name == "fachtext"
        )
        assert zeile.appearance == "Abstände"
        assert zeile.preview is not None
        assert zeile.preview.inheritance == "Normal → BodyText → Fachtext"
        assert "Blocksatz" in zeile.preview.effective_appearance
        assert "Abstände" in zeile.preview.effective_appearance
        assert "Zeilenabstand" in zeile.preview.effective_appearance
        assert zeile.preview.size_pt == 11.0
        assert zeile.preview.align == "justify"
        assert "Lorem ipsum" in zeile.preview.sample_text
        assert "11 pt" in zeile.preview.layout_comment
        assert "Taschenbuch" in zeile.preview.layout_comment or "KDP" in zeile.preview.layout_comment
        # Fixture nutzt Calibri → Bewertung soll Serifen empfehlen.
        assert "Calibri" in zeile.preview.layout_comment or "Serifen" in zeile.preview.layout_comment

    def test_eigenstaendiges_format_ohne_based_on(self) -> None:
        """Prompt-Trenner hat kein based_on — Erbfolge muss das sagen, nicht nur den Namen."""
        from tools.doclayout.library import load_layout
        from tools.doclayout.markup_inventory import _preview_for

        definition = load_layout("Reisefuehrer_Andalusien")
        vorschau = _preview_for(definition, "Prompt-Trenner")
        assert vorschau is not None
        assert "eigenständig" in vorschau.inheritance
        assert "based_on" in vorschau.inheritance
        assert "Folgeformat" in vorschau.inheritance
        assert "Prompt-Frage" in vorschau.inheritance
        assert "→" not in vorschau.inheritance.split("—")[0]

    def test_layout_comment_zu_klein(self) -> None:
        from tools.doclayout.markup_inventory import assess_layout_comment

        text = assess_layout_comment(size_pt=8.0, align="justify")
        assert "zu klein" in text
        text_ok = assess_layout_comment(
            size_pt=11.0, line_height=1.2, align="justify", font_family="Cambria"
        )
        assert "normale Grundschrift" in text_ok
        assert "Serifen" in text_ok or "Cambria" in text_ok

    def test_layout_comment_sans_fuer_fliesstext(self) -> None:
        from tools.doclayout.markup_inventory import assess_layout_comment

        text = assess_layout_comment(
            size_pt=11.0, align="justify", font_family="Calibri"
        )
        assert "ohne Serifen" in text or "Grotesk" in text
        assert "Serifenschrift" in text or "Cambria" in text

    def test_resolve_style_auf_layoutdefinition(self) -> None:
        from tools.doclayout.schema import LayoutDefinition, ParagraphStyle, Typography

        definition = LayoutDefinition(
            name="T",
            label="T",
            typography=Typography(base_size_pt=12.0),
            styles={
                "BodyText": ParagraphStyle(
                    style_id="BodyText", bold=True, size_pt=12.0
                ),
                "Kind": ParagraphStyle(
                    style_id="Kind", based_on="BodyText", italic=True
                ),
            },
        )
        assert definition.inheritance_chain("Kind") == ("Kind", "BodyText")
        wirksam = definition.resolve_style("Kind")
        assert wirksam is not None
        assert wirksam.bold is True
        assert wirksam.italic is True
        assert wirksam.size_pt == 12.0


def test_remove_unused_class_from_library_streicht_karteileiche(tmp_path: Path) -> None:
    from tools.doclayout.markup_inventory import (
        build_markup_inventory,
        remove_unused_class_from_library,
    )
    from tools.doclayout.schema import LayoutDefinition, ParagraphStyle

    bib = tmp_path / "bib"
    bib.mkdir()
    LayoutDefinition(
        name="Solo",
        label="Solo",
        styles={
            "BodyText": ParagraphStyle(style_id="BodyText", name="Body Text"),
            "Themenblock": ParagraphStyle(
                style_id="Themenblock", name="Themenblock", bold=True, size_pt=20
            ),
        },
        classmap={"themenblock": "Themenblock"},
    ).save(bib / "Solo.yaml")

    buch = tmp_path / "Buch"
    buch.mkdir()
    (buch / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    (buch / "index.md").write_text("# Hi\n", encoding="utf-8")

    vor = build_markup_inventory(buch, library_dir=bib)
    assert any(r.name == "themenblock" for r in vor.rows)

    ok, msg = remove_unused_class_from_library(
        "themenblock", library_dir=bib, layout_names=("Solo",)
    )
    assert ok, msg
    nach = build_markup_inventory(buch, library_dir=bib)
    assert not any(r.name == "themenblock" for r in nach.rows)
