"""Tests der Kapitelliste (``tools/chapter_list/``).

Die Abnahme des Plans ``.doc/kapitelliste-csv-export-plan.md``: Das alte
Werkzeug las einen Ordner alphabetisch aus und lieferte fuer ein echtes Buch
eine leere CSV ohne Fehlermeldung. Jeder Test hier haelt genau einen dieser
Befunde geschlossen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.chapter_list.builder import (
    CSV_HEADER,
    NO_TITLE,
    ChapterListError,
    build_chapter_list,
    build_chapter_list_detailed,
    count_body,
    write_chapter_list,
)


def _schreibe(pfad: Path, text: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")


def _kapitel(titel: str, rumpf: str = "Ein Satz mit fuenf Woertern.") -> str:
    return f"---\ntitle: {titel}\n---\n\n{rumpf}\n"


@pytest.fixture()
def buch(tmp_path: Path) -> Path:
    """Ein Buch, das alle Befunde des Plans auf einmal traegt.

    Die Kapitelfolge ist absichtlich **gegen** das Alphabet gesetzt
    (``zulaufen`` vor ``anfang``), ein Kapitel ist eine ``.qmd``, eines liegt
    im Unterordner, und daneben liegen eine nicht gelistete Datei sowie
    Renderausgaben, die nicht mitzaehlen duerfen.
    """
    root = tmp_path / "Band_Test"
    _schreibe(
        root / "_quarto.yml",
        "project:\n"
        "  type: book\n"
        "book:\n"
        "  title: Prüfband\n"
        "  chapters:\n"
        "  - index.md\n"
        "  - content/zulaufen.md\n"
        "  - content/anfang.qmd\n"
        "  - content/teil/tief.md\n",
    )
    _schreibe(root / "index.md", _kapitel("Vorwort"))
    _schreibe(root / "content" / "zulaufen.md", _kapitel("Zulaufen"))
    _schreibe(root / "content" / "anfang.qmd", _kapitel("Anfang"))
    _schreibe(root / "content" / "teil" / "tief.md", _kapitel("Tief im Ordner"))
    # Nicht gelistet, aber vorhanden -- gehoert ans Ende der Liste.
    _schreibe(root / "content" / "uebrig.md", _kapitel("Übriggeblieben"))
    # Renderausgaben: duerfen nicht als Manuskript gelten.
    _schreibe(root / "_book" / "index.md", _kapitel("Renderausgabe"))
    _schreibe(root / "export" / "kopie.md", _kapitel("Exportkopie"))
    return root


class TestReihenfolge:
    def test_folgt_quarto_yml_und_nicht_dem_alphabet(self, buch: Path) -> None:
        """Der teuerste Fehler des Vorgaengers: ein Buch mit vertauschten Kapiteln."""
        rows = build_chapter_list(buch)
        kapitel = [row.path for row in rows if row.in_quarto]
        assert kapitel == [
            "index.md",
            "content/zulaufen.md",
            "content/anfang.qmd",
            "content/teil/tief.md",
        ]
        assert [row.number for row in rows if row.in_quarto] == [1, 2, 3, 4]

    def test_qmd_faellt_nicht_durch(self, buch: Path) -> None:
        """Quarto laesst beide Endungen als Kapitel zu."""
        rows = build_chapter_list(buch)
        assert "content/anfang.qmd" in [row.path for row in rows]

    def test_unterordner_zaehlen_mit_renderausgaben_nicht(self, buch: Path) -> None:
        pfade = {row.path for row in build_chapter_list(buch)}
        assert "content/teil/tief.md" in pfade
        assert not [p for p in pfade if p.startswith(("_book/", "export/"))]

    def test_pfade_tragen_schraegstriche(self, buch: Path) -> None:
        """Die CSV wird auf fremden Rechnern gelesen -- kein Backslash."""
        assert not [row for row in build_chapter_list(buch) if "\\" in row.path]


class TestNichtGelistet:
    def test_steht_am_ende_und_ist_markiert(self, buch: Path) -> None:
        """Gezeigt, nicht verschwiegen -- aber als das, was es ist."""
        rows = build_chapter_list(buch)
        letzte = rows[-1]
        assert letzte.path == "content/uebrig.md"
        assert letzte.number is None
        assert letzte.in_quarto is False
        assert letzte.as_csv_row()[0] == ""
        assert letzte.as_csv_row()[-1] == "nein"

    def test_kapitel_stehen_davor(self, buch: Path) -> None:
        rows = build_chapter_list(buch)
        letzter_kapitelindex = max(i for i, r in enumerate(rows) if r.in_quarto)
        erster_restindex = min(i for i, r in enumerate(rows) if not r.in_quarto)
        assert letzter_kapitelindex < erster_restindex

    def test_kapitel_erscheinen_nur_einmal(self, buch: Path) -> None:
        """``markdown_files`` findet dieselben Dateien noch einmal."""
        pfade = [row.path for row in build_chapter_list(buch)]
        assert len(pfade) == len(set(pfade))


class TestTitel:
    def test_ohne_frontmatter_titel_kommt_kein_titel(self, tmp_path: Path) -> None:
        root = tmp_path / "B"
        _schreibe(root / "_quarto.yml", "book:\n  chapters:\n  - a.md\n")
        _schreibe(root / "a.md", "Nur Text, kein Frontmatter.\n")
        assert build_chapter_list(root)[0].title == NO_TITLE

    def test_leerer_titel_zaehlt_als_fehlend(self, tmp_path: Path) -> None:
        root = tmp_path / "B"
        _schreibe(root / "_quarto.yml", "book:\n  chapters:\n  - a.md\n")
        _schreibe(root / "a.md", '---\ntitle: "  "\n---\n\nText\n')
        assert build_chapter_list(root)[0].title == NO_TITLE


class TestUmfang:
    def test_frontmatter_zaehlt_nicht_mit(self, tmp_path: Path) -> None:
        root = tmp_path / "B"
        _schreibe(root / "_quarto.yml", "book:\n  chapters:\n  - a.md\n")
        _schreibe(root / "a.md", "---\ntitle: Sehr langer Titel hier\n---\n\nEins zwei\n")
        row = build_chapter_list(root)[0]
        assert row.words == 2
        assert row.characters == len("Eins zwei")

    def test_auszeichnungs_marker_zaehlen_nicht_als_text(self) -> None:
        """``::: {.fachtext}`` ist Auszeichnung; wer sie mitzaehlt, nennt dem
        Lektorat einen Umfang, den es nicht zu lesen bekommt."""
        woerter, _zeichen = count_body("::: {.fachtext}\nDrei echte Woerter\n:::\n")
        assert woerter == 3

    def test_code_inhalt_zaehlt_seine_zaeune_nicht(self) -> None:
        """Der Code steht im Buch, seine Fence-Zeilen nicht."""
        woerter, _zeichen = count_body("```python\nprint(1)\n```\n")
        assert woerter == 1

    def test_doppelpunkte_im_code_bleiben_beispiel(self) -> None:
        """Ein ``:::`` im Code-Block ist Text ueber Auszeichnung, keine."""
        woerter, _zeichen = count_body("```\n::: {.prompt}\n```\n")
        assert woerter == 2


class TestFehlendeKapitelliste:
    """Eine Liste ohne Reihenfolge ist besser als keine Liste."""

    @pytest.fixture()
    def ohne_kapitel(self, tmp_path: Path) -> Path:
        root = tmp_path / "B"
        _schreibe(root / "_quarto.yml", "project:\n  type: book\n")
        _schreibe(root / "a.md", _kapitel("A"))
        _schreibe(root / "content" / "b.qmd", _kapitel("B"))
        return root

    def test_liefert_trotzdem_alle_dateien(self, ohne_kapitel: Path) -> None:
        rows = build_chapter_list(ohne_kapitel)
        assert {row.path for row in rows} == {"a.md", "content/b.qmd"}

    def test_nummern_bleiben_leer(self, ohne_kapitel: Path) -> None:
        """Geraten wird die Reihenfolge nicht -- auch nicht stillschweigend."""
        assert all(row.number is None for row in build_chapter_list(ohne_kapitel))

    def test_der_vorbehalt_wird_benannt(self, ohne_kapitel: Path) -> None:
        liste = build_chapter_list_detailed(ohne_kapitel)
        assert liste.order_problem
        assert "book.chapters" in liste.order_problem

    def test_bei_vorhandener_liste_kein_vorbehalt(self, buch: Path) -> None:
        assert build_chapter_list_detailed(buch).order_problem is None


class TestUnlesbaresBuch:
    def test_kein_verzeichnis(self, tmp_path: Path) -> None:
        with pytest.raises(ChapterListError):
            build_chapter_list(tmp_path / "gibt_es_nicht")

    def test_ordner_ohne_quarto_yml(self, tmp_path: Path) -> None:
        """Ein beliebiger Ordner ist kein Buchprojekt -- das wird gesagt."""
        (tmp_path / "irgendwas").mkdir()
        with pytest.raises(ChapterListError):
            build_chapter_list(tmp_path / "irgendwas")


class TestCsv:
    def test_ziel_liegt_im_buch(self, buch: Path) -> None:
        ziel = write_chapter_list(buch, build_chapter_list(buch))
        assert ziel == buch / "export" / "kapitelliste.csv"
        assert ziel.is_file()

    def test_kopfzeile_und_trennzeichen(self, buch: Path) -> None:
        ziel = write_chapter_list(buch, build_chapter_list(buch))
        erste = ziel.read_text(encoding="utf-8-sig").splitlines()[0]
        assert erste == ";".join(CSV_HEADER)

    def test_bom_damit_excel_die_umlaute_nicht_zerlegt(self, buch: Path) -> None:
        ziel = write_chapter_list(buch, build_chapter_list(buch))
        roh = ziel.read_bytes()
        assert roh.startswith(b"\xef\xbb\xbf")
        assert "Übriggeblieben" in ziel.read_text(encoding="utf-8-sig")

    def test_wird_ueberschrieben(self, buch: Path) -> None:
        """Eine Momentaufnahme, kein Dokument, an dem jemand weiterarbeitet."""
        ziel = write_chapter_list(buch, build_chapter_list(buch))
        ziel.write_text("Altbestand\n", encoding="utf-8-sig")
        write_chapter_list(buch, build_chapter_list(buch))
        assert "Altbestand" not in ziel.read_text(encoding="utf-8-sig")

    def test_eigenes_ziel_wird_benutzt(self, buch: Path, tmp_path: Path) -> None:
        ziel = write_chapter_list(buch, build_chapter_list(buch), tmp_path / "x.csv")
        assert ziel == tmp_path / "x.csv"
        assert ziel.is_file()


class TestCli:
    def test_schreibt_und_meldet_null(self, buch: Path, capsys) -> None:
        from tools.chapter_list.__main__ import main

        assert main(["--book", str(buch)]) == 0
        ausgabe = capsys.readouterr()
        assert "kapitelliste.csv" in ausgabe.out
        assert "nicht in _quarto.yml" in ausgabe.err

    def test_unlesbares_buch_ergibt_zwei(self, tmp_path: Path, capsys) -> None:
        from tools.chapter_list.__main__ import main

        assert main(["--book", str(tmp_path / "nichts")]) == 2
        assert "FEHLER" in capsys.readouterr().err

    def test_fehlende_reihenfolge_wird_angesagt(self, tmp_path: Path, capsys) -> None:
        from tools.chapter_list.__main__ import main

        root = tmp_path / "B"
        _schreibe(root / "_quarto.yml", "project:\n  type: book\n")
        _schreibe(root / "a.md", _kapitel("A"))
        assert main(["--book", str(root)]) == 0
        assert "ACHTUNG" in capsys.readouterr().err


class TestPluginManifest:
    def test_label_nennt_den_export(self) -> None:
        """Aus „Dateien indexieren“ ist ein Export geworden -- ehrlich benannt."""
        import json

        daten = json.loads(
            (
                Path(__file__).resolve().parents[1] / "plugins" / "file_indexer" / "plugin.json"
            ).read_text(encoding="utf-8")
        )
        assert daten["label"] == "📤 Kapitelliste exportieren (CSV)…"
        assert "Kapitel" in daten["description"]
        assert "python -m tools.chapter_list" in daten["help_text"]

    def test_altes_werkzeug_ist_ersetzt_nicht_danebengestellt(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        assert not (repo / "tools" / "Files_Indexer.py").exists()


@pytest.mark.gui
class TestDialog:
    @pytest.fixture(scope="class")
    def qapp(self):
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication

        yield QApplication.instance() or QApplication([])

    def test_tabelle_zeigt_die_csv_spalten(self, qapp, buch: Path) -> None:
        """Die Vorschau darf nichts anderes behaupten als die Datei."""
        from ui_qt.dialogs.chapter_list_dialog import ChapterListDialog

        dialog = ChapterListDialog(buch)
        try:
            kopf = [
                dialog.tabelle.horizontalHeaderItem(i).text()
                for i in range(dialog.tabelle.columnCount())
            ]
            assert kopf == list(CSV_HEADER)
            assert dialog.tabelle.rowCount() == len(build_chapter_list(buch))
        finally:
            dialog.deleteLater()

    def test_hinweis_bei_fehlender_kapitelliste(self, qapp, tmp_path: Path) -> None:
        """Sonst haelt der Empfaenger die alphabetische Liste fuer das Buch."""
        from ui_qt.dialogs.chapter_list_dialog import ChapterListDialog

        root = tmp_path / "B"
        _schreibe(root / "_quarto.yml", "project:\n  type: book\n")
        _schreibe(root / "a.md", _kapitel("A"))
        dialog = ChapterListDialog(root)
        try:
            assert dialog.hinweis_label.isVisibleTo(dialog)
            assert "book.chapters" in dialog.hinweis_label.text()
        finally:
            dialog.deleteLater()

    def test_ohne_fehlende_liste_kein_hinweis(self, qapp, buch: Path) -> None:
        from ui_qt.dialogs.chapter_list_dialog import ChapterListDialog

        dialog = ChapterListDialog(buch)
        try:
            assert not dialog.hinweis_label.isVisibleTo(dialog)
        finally:
            dialog.deleteLater()


@pytest.mark.gui
class TestBuchauswahl:
    """Kein Dateidialog beim Oeffnen -- die Anwendung kennt ihre Buecher."""

    @pytest.fixture(scope="class")
    def qapp(self):
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication

        yield QApplication.instance() or QApplication([])

    @pytest.fixture()
    def dialog(self, qapp):
        from ui_qt.dialogs.chapter_list_dialog import ChapterListDialog

        d = ChapterListDialog(None)
        yield d
        d.deleteLater()

    def test_liste_ist_gefuellt(self, dialog) -> None:
        assert dialog.buch_auswahl.count() > 1

    def test_ausweg_steht_am_ende(self, dialog) -> None:
        from ui_qt.dialogs.chapter_list_dialog import _ANDERES_VERZEICHNIS

        letzter = dialog.buch_auswahl.count() - 1
        assert dialog.buch_auswahl.itemText(letzter) == _ANDERES_VERZEICHNIS
        assert not dialog.buch_auswahl.itemData(letzter)

    def test_export_ordner_stehen_nicht_zur_wahl(self, dialog) -> None:
        """``Publish_*`` sind Ergebnisse, nicht Quellen."""
        eintraege = [dialog.buch_auswahl.itemText(i) for i in range(dialog.buch_auswahl.count())]
        assert not [e for e in eintraege if e.startswith("Publish_")]
