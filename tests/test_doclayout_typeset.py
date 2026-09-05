"""Vom Layout zum fertigen Band -- der Schritt, der bisher fehlte.

Der Editor konnte **vorbereiten** (``apply_layout``) und einen **Mustertext**
vorschauen. Dazwischen klaffte eine Luecke: der Pandoc-Aufruf ueber die echten
Kapitel, mit Verzeichnis, Umbruch und Buchdaten. Den gab es nur als Folge von
Kommandozeilen, die jemand tippen musste -- also weder wiederholbar noch
pruefbar.

Pandoc wird hier nicht gebraucht: Geprueft wird, **was aufgerufen wird** und
was mit dem Ergebnis geschieht -- nicht, ob Pandoc setzen kann.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.doclayout import typeset as T
from tools.doclayout.library import load_layout
from tools.doclayout.schema import LayoutDefinition


@pytest.fixture()
def layout() -> LayoutDefinition:
    return load_layout("IFJN_layout")


def _buch(root: Path, *, kapitel: tuple[str, ...] = ("index.md", "kap1.md")) -> Path:
    """Ein Buchprojekt mit Kapitelliste und bereits erzeugten Vorlagen."""
    liste = "\n".join(f"    - {name}" for name in kapitel)
    (root / "_quarto.yml").write_text(
        "project:\n  type: book\n"
        "book:\n"
        '  title: "Mein Band"\n'
        '  author: "Eine Autorin"\n'
        "  chapters:\n" + liste + "\n"
        "lang: de\n",
        encoding="utf-8",
    )
    for name in kapitel:
        pfad = root / name
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(f"# {name}\n\nText.\n", encoding="utf-8")
    vorlagen = root / "bookconfig" / "doclayout"
    vorlagen.mkdir(parents=True)
    (vorlagen / "reference.docx").write_bytes(b"PK\x03\x04")
    (vorlagen / "classmap.lua").write_text("-- filter", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Die Reihenfolge des Buchs
# ---------------------------------------------------------------------------


def test_the_chapters_follow_the_quarto_yml(tmp_path: Path):
    """Nicht alphabetisch: ``_quarto.yml`` ist die Struktur-SSOT.

    Der Klassen-Abgleich darf die Dateien sortieren -- er zaehlt nur. Wer
    **setzt**, bekaeme so ein Buch mit vertauschten Kapiteln.
    """
    buch = _buch(tmp_path, kapitel=("zuerst.md", "danach.md", "zuletzt.md"))
    assert [p.name for p in T.book_chapters(buch)] == [
        "zuerst.md", "danach.md", "zuletzt.md"
    ]


def test_chapters_inside_parts_are_taken_along(tmp_path: Path):
    """Quarto laesst Teile mit eigener Kapitelliste zu."""
    (tmp_path / "_quarto.yml").write_text(
        "book:\n"
        "  chapters:\n"
        "    - vorne.md\n"
        "    - part: Teil I\n"
        "      chapters:\n"
        "        - drin.md\n",
        encoding="utf-8",
    )
    for name in ("vorne.md", "drin.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert [p.name for p in T.book_chapters(tmp_path)] == ["vorne.md", "drin.md"]


def test_a_missing_chapter_is_named_not_skipped(tmp_path: Path):
    """Stillschweigend weglassen hiesse, ein unvollstaendiges Buch zu setzen."""
    (tmp_path / "_quarto.yml").write_text(
        "book:\n  chapters:\n    - da.md\n    - weg.md\n", encoding="utf-8"
    )
    (tmp_path / "da.md").write_text("x", encoding="utf-8")
    with pytest.raises(T.TypesetError, match="weg.md"):
        T.book_chapters(tmp_path)


def test_without_a_chapter_list_nothing_is_guessed(tmp_path: Path):
    (tmp_path / "_quarto.yml").write_text("project:\n  type: book\n", encoding="utf-8")
    with pytest.raises(T.TypesetError, match="Kapitelliste"):
        T.book_chapters(tmp_path)


def test_a_directory_without_quarto_yml_is_no_book(tmp_path: Path):
    with pytest.raises(T.TypesetError, match="Quarto-Buchprojekt"):
        T.book_chapters(tmp_path)


# ---------------------------------------------------------------------------
# Buchdaten
# ---------------------------------------------------------------------------


def test_title_author_and_language_come_from_the_book(tmp_path: Path):
    buch = _buch(tmp_path)
    assert T.book_metadata(buch) == {
        "title": "Mein Band", "author": "Eine Autorin", "lang": "de"
    }


def test_several_authors_become_one_line(tmp_path: Path):
    (tmp_path / "_quarto.yml").write_text(
        "book:\n  title: T\n  author:\n    - Eine\n    - Andere\n", encoding="utf-8"
    )
    assert T.book_metadata(tmp_path)["author"] == "Eine, Andere"


def test_missing_data_is_left_out_not_invented(tmp_path: Path):
    """Ein sichtbares "Unbenannt" waere schlimmer als eine fehlende Zeile."""
    (tmp_path / "_quarto.yml").write_text("book:\n  title: Nur Titel\n", encoding="utf-8")
    meta = T.book_metadata(tmp_path)
    assert meta == {"title": "Nur Titel"}


# ---------------------------------------------------------------------------
# Der Aufruf
# ---------------------------------------------------------------------------


@pytest.fixture()
def pandoc_attrappe(monkeypatch):
    """Ersetzt Pandoc und LibreOffice; merkt sich den Aufruf."""
    aufrufe: list[list[str]] = []

    def unecht(command, **kwargs):
        aufrufe.append(list(command))
        ziel = Path(command[command.index("--output") + 1])
        ziel.write_bytes(b"PK\x03\x04 docx")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(T, "run_hidden", unecht)
    monkeypatch.setattr(T, "find_pandoc", lambda explicit=None: "pandoc")
    monkeypatch.setattr(T, "apply_layout", lambda *a, **k: None)
    return aufrufe


def test_the_book_is_typeset_into_its_export_folder(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    ergebnis = T.typeset_book(layout, buch)
    assert ergebnis.docx == buch.joinpath(*T.OUTPUT_SUBDIR) / f"{layout.name}.docx"
    assert ergebnis.docx.is_file()
    assert ergebnis.chapters == ("index.md", "kap1.md")


def test_the_chapters_reach_pandoc_in_order(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    buch = _buch(tmp_path, kapitel=("a.md", "b.md", "c.md"))
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    T.typeset_book(layout, buch)
    befehl = pandoc_attrappe[0]
    eingaben = [Path(t).name for t in befehl if t.endswith(".md")]
    assert eingaben == ["_seitenumbruch.md", "a.md", "b.md", "c.md"]


def test_the_page_break_is_the_first_input_not_an_include(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    """``--include-before-body`` landet **vor** dem Verzeichnis und wirkt nicht.

    Ohne den Umbruch beginnt der Text auf derselben Seite, auf der die letzten
    Verzeichniszeilen stehen -- im Andalusien-Band war das Seite 8.
    """
    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    T.typeset_book(layout, buch)
    befehl = pandoc_attrappe[0]
    assert not any(t.startswith("--include-before-body") for t in befehl)
    md = [t for t in befehl if t.endswith(".md")]
    assert Path(md[0]).name == "_seitenumbruch.md"


def test_the_helper_file_does_not_stay_behind(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    T.typeset_book(layout, buch)
    assert not (buch.joinpath(*T.OUTPUT_SUBDIR) / "_seitenumbruch.md").exists()


def test_the_table_of_contents_is_german_for_a_german_layout(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    T.typeset_book(layout, buch)
    befehl = pandoc_attrappe[0]
    assert "--toc" in befehl
    assert "toc-title=Inhaltsverzeichnis" in befehl


def test_without_a_toc_there_is_no_page_break_either(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    """Der Umbruch trennt Verzeichnis und Text -- ohne Verzeichnis trennt er nichts."""
    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    T.typeset_book(layout, buch, toc=False)
    befehl = pandoc_attrappe[0]
    assert "--toc" not in befehl
    assert not any(Path(t).name == "_seitenumbruch.md" for t in befehl)


def test_the_book_data_reaches_pandoc(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    T.typeset_book(layout, buch)
    befehl = pandoc_attrappe[0]
    assert "title=Mein Band" in befehl
    assert "author=Eine Autorin" in befehl


def test_pandoc_runs_inside_the_book_so_images_resolve(
    tmp_path: Path, layout: LayoutDefinition, monkeypatch
):
    """Ein ``images/x.png`` im Manuskript muss vom Buch aus gedeutet werden."""
    buch = _buch(tmp_path)
    gesehen: dict[str, object] = {}

    def unecht(command, **kwargs):
        gesehen["cwd"] = kwargs.get("cwd")
        Path(command[command.index("--output") + 1]).write_bytes(b"PK")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(T, "run_hidden", unecht)
    monkeypatch.setattr(T, "find_pandoc", lambda explicit=None: "pandoc")
    monkeypatch.setattr(T, "apply_layout", lambda *a, **k: None)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    T.typeset_book(layout, buch)
    assert Path(str(gesehen["cwd"])) == buch.resolve()


def test_a_relative_book_path_still_works(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    """Gefunden beim ersten Lauf: relativer Pfad + ``cwd`` = nichts auffindbar."""
    import os

    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    alt = Path.cwd()
    os.chdir(tmp_path.parent)
    try:
        ergebnis = T.typeset_book(layout, Path(tmp_path.name))
    finally:
        os.chdir(alt)
    assert ergebnis.docx.is_absolute() and ergebnis.docx.is_file()
    assert all(Path(t).is_absolute() for t in pandoc_attrappe[0] if t.endswith(".md"))
    assert buch.exists()


# ---------------------------------------------------------------------------
# Was schiefgehen kann
# ---------------------------------------------------------------------------


def test_missing_templates_point_at_the_apply_button(
    tmp_path: Path, layout: LayoutDefinition, monkeypatch
):
    buch = _buch(tmp_path)
    (buch / "bookconfig" / "doclayout" / "reference.docx").unlink()
    monkeypatch.setattr(T, "find_pandoc", lambda explicit=None: "pandoc")
    monkeypatch.setattr(T, "apply_layout", lambda *a, **k: None)
    with pytest.raises(T.TypesetError, match="Auf Buch anwenden"):
        T.typeset_book(layout, buch)


def test_without_pandoc_the_reason_names_quarto(
    tmp_path: Path, layout: LayoutDefinition, monkeypatch
):
    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_pandoc", lambda explicit=None: None)
    with pytest.raises(T.TypesetError, match="Quarto"):
        T.typeset_book(layout, buch)


def test_pandoc_warnings_are_passed_on_not_swallowed(
    tmp_path: Path, layout: LayoutDefinition, monkeypatch
):
    """Sie sagen etwas ueber das Manuskript, nicht ueber dieses Werkzeug."""
    buch = _buch(tmp_path)

    def unecht(command, **kwargs):
        Path(command[command.index("--output") + 1]).write_bytes(b"PK")
        return subprocess.CompletedProcess(
            command, 0, b"", b"[WARNING] Div unclosed at kap1.md line 7\n"
        )

    monkeypatch.setattr(T, "run_hidden", unecht)
    monkeypatch.setattr(T, "find_pandoc", lambda explicit=None: "pandoc")
    monkeypatch.setattr(T, "apply_layout", lambda *a, **k: None)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    ergebnis = T.typeset_book(layout, buch)
    assert any("Div unclosed" in z for z in ergebnis.warnings)


def test_without_libreoffice_the_docx_still_counts(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    """Kein Notfall: Die Datei laesst sich oeffnen, nur nicht anzeigen."""
    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    ergebnis = T.typeset_book(layout, buch)
    assert ergebnis.docx.is_file()
    assert ergebnis.pdf is None
    assert "LibreOffice" in ergebnis.note
    assert ergebnis.complete is False


def test_the_pdf_comes_from_the_shared_conversion(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    """Derselbe Weg wie die Vorschau -- also mit gefuelltem Verzeichnis."""
    buch = _buch(tmp_path)
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: "soffice")

    def unecht(converter, docx, out_dir):
        pdf = Path(out_dir) / "fertig.pdf"
        pdf.write_bytes(b"%PDF")
        return pdf, ""

    monkeypatch.setattr(T, "_convert_to_pdf", unecht)
    ergebnis = T.typeset_book(layout, buch)
    assert ergebnis.complete is True
    assert ergebnis.pdf is not None and ergebnis.pdf.name == "fertig.pdf"


def test_an_unbuildable_layout_is_refused_before_anything_runs(
    tmp_path: Path, monkeypatch
):
    from tools.doclayout.schema import LayoutDefinition as LD

    kaputt = LD.from_dict({"name": "x", "classmap": {"a": "Gibt-Es-Nicht"}})

    def darf_nicht(*a, **k):
        raise AssertionError("es haette nichts starten duerfen")

    monkeypatch.setattr(T, "run_hidden", darf_nicht)
    with pytest.raises(T.TypesetError, match="nicht erzeugbar"):
        T.typeset_book(kaputt, tmp_path)


def test_the_templates_are_rebuilt_by_default(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    """Sonst setzte man ein Buch mit der Vorlage von vorgestern."""
    gerufen: list[bool] = []
    monkeypatch.setattr(T, "apply_layout", lambda *a, **k: gerufen.append(True))
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    T.typeset_book(layout, _buch(tmp_path))
    assert gerufen == [True]


def test_the_rebuild_can_be_skipped(
    tmp_path: Path, layout: LayoutDefinition, pandoc_attrappe, monkeypatch
):
    monkeypatch.setattr(
        T, "apply_layout", lambda *a, **k: pytest.fail("haette nicht laufen duerfen")
    )
    monkeypatch.setattr(T, "find_soffice", lambda explicit=None: None)
    T.typeset_book(layout, _buch(tmp_path), rebuild_template=False)
