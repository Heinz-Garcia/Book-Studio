"""Ein ganzes Buch mit einer Layout-Definition setzen -- ``.docx`` und ``.pdf``.

Die Luecke, die dieses Modul schliesst: Der Editor konnte bisher **vorbereiten**
(``apply_layout`` legt ``reference.docx`` und ``classmap.lua`` ins Buch und
traegt sie in ``_quarto.yml`` ein) und einen **Mustertext** vorschauen. Was
dazwischen fehlte, war der Schritt vom Layout zum fertigen Band: der Pandoc-
Aufruf ueber die echten Kapitel, mit Verzeichnis, Umbruch und Buchdaten.

Dieser Schritt existierte -- aber nur als Folge von Kommandozeilen, die jemand
tippen musste. Damit war er weder wiederholbar noch pruefbar. Hier steht er
jetzt an einer Stelle.

**Nicht** die Render-Pipeline des Studios: Die setzt ueber Quarto und Typst und
bleibt unberuehrt (siehe ``.doc/gui_architektur.md`` und ``apply.py``). Dies ist
der Word-Weg -- derselbe, den die Definition ohnehin beschreibt.

GUI-frei; der Dialog ruft :func:`typeset_book` in einem eigenen Faden auf.
"""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from tools.doclayout.apply import LUA_FILTER_NAME, REFERENCE_DOCX_NAME, apply_layout
from tools.doclayout.library import book_output_dir
from tools.doclayout.preview import (
    PreviewError,
    _convert_to_pdf,
    find_soffice,
    toc_title_for,
)
from tools.doclayout.process import run_hidden
from tools.doclayout.schema import LayoutDefinition
from tools.doclayout.targets.docx import find_pandoc

#: Wohin das Ergebnis geht. Unter ``export/``, weil es dorthin gehoert, und in
#: einen eigenen Ordner, damit es keine Renderausgabe der Studio-Pipeline
#: ueberschreibt.
OUTPUT_SUBDIR = ("export", "doclayout")

#: Ein ganzes Buch braucht laenger als ein Mustertext.
BOOK_PANDOC_TIMEOUT_S = 600

#: Die eine Eingabedatei, die Pandoc bekommt: alle Kapitel ohne Frontmatter,
#: getrennt durch Kapitelgrenzen. Liegt nur waehrend des Laufs im Ausgabeordner.
ASSEMBLED_NAME = "_satz.md"

#: Grenze zwischen zwei Kapiteldateien. Der Klassen-Filter macht daraus einen
#: Seitenumbruch vor dem naechsten **sichtbaren** Block -- reine Typst-Seiten
#: (Schmutztitel, Deckblatt) erzeugen so keine Leerseiten.
CHAPTER_BOUNDARY = "::: {.bs-kapitel}\n:::"

#: Platzhalter fuer das Verzeichnis. Die Pflichtseite ``IVZ.md`` traegt ihn;
#: fehlt er im Buch, setzt der Satz ihn als eigene Seite vor das erste Kapitel.
#: Pandocs ``--toc`` wird nicht benutzt: Es setzt das Verzeichnis immer direkt
#: hinter den Titelblock, vor Impressum und Titelseiten.
TOC_PLACEHOLDER = "::: {.bs-ivz}\n:::"

#: Reines Pandoc-Markdown wie im Quarto/Typst-Weg -- keine Erweiterung, die
#: den Text anders liest. Listen ohne Leerzeile repariert die gemeinsame
#: Vorbereitung (``render_text_prep``) fuer beide Formate.
MARKDOWN_FORMAT = "markdown"

_TOC_PLACEHOLDER_RE = re.compile(r"(?m)^:::+\s*\{[^}\n]*\.bs-ivz\b")


class TypesetError(PreviewError):
    """Das Buch liess sich nicht setzen."""


@dataclass
class TypesetResult:
    """Was beim Setzen herausgekommen ist."""

    docx: Path
    pdf: Optional[Path]
    chapters: tuple[str, ...] = ()
    note: str = ""
    #: Meldungen von Pandoc, die kein Abbruch waren (unaufgeloeste Bilder,
    #: nicht geschlossene Divs). Sie gehoeren dem Benutzer gezeigt: Sie sagen
    #: etwas ueber sein Manuskript, nicht ueber dieses Werkzeug.
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def complete(self) -> bool:
        return self.pdf is not None and self.pdf.is_file()

    def summary(self) -> str:
        teile = [f"{len(self.chapters)} Kapiteldatei(en) gesetzt", f"DOCX: {self.docx.name}"]
        teile.append(f"PDF: {self.pdf.name}" if self.pdf else "PDF: keine")
        if self.note:
            teile.append(self.note)
        return " | ".join(teile)


# ---------------------------------------------------------------------------
# Was gehoert ins Buch?
# ---------------------------------------------------------------------------


def book_chapters(book_path: Path | str) -> list[Path]:
    """Die Kapitel **in der Reihenfolge des ``_quarto.yml``**.

    Die Reihenfolge ist nicht verhandelbar: ``_quarto.yml`` ist die Struktur-
    SSOT des Buchs (siehe CLAUDE.md). Sie alphabetisch zu erraten -- wie es der
    Klassen-Abgleich tut, der nur zaehlt und nicht setzt -- ergaebe ein Buch mit
    vertauschten Kapiteln.

    Fehlt der Eintrag oder ist er leer, wird nichts geraten, sondern gemeldet.
    """
    root = Path(book_path)
    quarto = root / "_quarto.yml"
    if not quarto.is_file():
        raise TypesetError(f"{root} sieht nicht wie ein Quarto-Buchprojekt aus.")
    try:
        data = yaml.safe_load(quarto.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise TypesetError(f"_quarto.yml nicht lesbar: {exc}") from exc

    book = data.get("book") if isinstance(data.get("book"), dict) else {}
    eintraege = book.get("chapters") or data.get("chapters") or []
    if not isinstance(eintraege, list) or not eintraege:
        raise TypesetError(
            "In _quarto.yml steht keine Kapitelliste (book.chapters) -- ohne sie "
            "ist die Reihenfolge des Buchs nicht bekannt."
        )

    kapitel: list[Path] = []
    fehlend: list[str] = []
    for eintrag in eintraege:
        # Quarto laesst auch Teile mit eigener Kapitelliste zu.
        if isinstance(eintrag, dict):
            for unter in eintrag.get("chapters") or []:
                _sammle(root, unter, kapitel, fehlend)
            continue
        _sammle(root, eintrag, kapitel, fehlend)

    if fehlend:
        raise TypesetError(
            "In _quarto.yml stehen Kapitel, die es nicht gibt: " + ", ".join(fehlend)
        )
    if not kapitel:
        raise TypesetError("Die Kapitelliste in _quarto.yml enthaelt keine Dateien.")
    return kapitel


def _sammle(root: Path, eintrag: object, ziel: list[Path], fehlend: list[str]) -> None:
    if not isinstance(eintrag, str) or not eintrag.strip():
        return
    pfad = root / eintrag
    if pfad.is_file():
        ziel.append(pfad)
    else:
        fehlend.append(eintrag)


def book_metadata(book_path: Path | str) -> dict[str, str]:
    """Titel, Autor und Sprache aus ``_quarto.yml``.

    Ohne diese Angaben setzt Pandoc keine Titelseite -- und ein Buch ohne Titel
    ist der erste Eindruck, den niemand haben will. Fehlt etwas, wird der
    Schluessel weggelassen statt mit einem Platzhalter gefuellt: Ein sichtbares
    "Unbenannt" waere schlimmer als eine fehlende Zeile.
    """
    root = Path(book_path)
    try:
        data = yaml.safe_load((root / "_quarto.yml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    book = data.get("book") if isinstance(data.get("book"), dict) else {}
    meta: dict[str, str] = {}
    titel = str(book.get("title") or data.get("title") or "").strip()
    if titel:
        meta["title"] = titel
    autor = book.get("author") or data.get("author")
    if isinstance(autor, list):
        autor = ", ".join(str(a) for a in autor if str(a).strip())
    autor = str(autor or "").strip()
    if autor:
        meta["author"] = autor
    sprache = str(data.get("lang") or "").strip()
    if sprache:
        meta["lang"] = sprache
    return meta


def assemble_book(root: Path, kapitel: list[Path], *, toc: bool) -> str:
    """Die Kapitel als **ein** Markdown -- mit denselben Regeln wie der Typst-Weg.

    Das Typst-PDF ist der Massstab: Beide Formate sollen inhaltlich gleich sein.
    Deshalb gelten hier die Regeln des ``PreProcessor``, keine eigenen:

    - Frontmatter faellt weg; der Text durchlaeuft die formatneutrale
      Vorbereitung (``render_text_prep.bereite_markdown_vor``).
    - Die erste ``#`` im Text wird entfernt (sie konkurrierte mit dem
      Kapiteltitel); der Frontmatter-``title`` wird zur Ueberschrift, wenn
      ``chapter_title_render`` ihn drucken laesst. Stille Pflichtseiten
      (Impressum, Titelei) bekommen so auch im DOCX keine Ueberschrift.
    - Es wird **nichts erfunden**: Ein Kapitel ohne Titel bleibt ohne Titel.
      Ueberschriften im Nutzinhalt liefert der Generator.
    - Zwischen den Kapiteln steht :data:`CHAPTER_BOUNDARY`.
    - Traegt kein Kapitel den :data:`TOC_PLACEHOLDER`, steht er (bei *toc*)
      vor dem ersten Kapitel.
    """
    import frontmatter_parser
    from chapter_title_render import resolve_print_title_text, should_print_chapter_title
    from render_text_prep import bereite_markdown_vor, ohne_erste_h1

    teile: list[tuple[str, str]] = []  # (Ueberschrift, Text)
    for pfad in kapitel:
        roh = pfad.read_text(encoding="utf-8")
        parts = frontmatter_parser.parse(roh)
        body = parts.body if parts.has_frontmatter else roh.lstrip("﻿")
        daten = parts.parsed() if parts.has_frontmatter else {}
        body = ohne_erste_h1(bereite_markdown_vor(body))
        rel = pfad.relative_to(root).as_posix()
        ueberschrift = ""
        if daten and should_print_chapter_title(daten, rel_path=rel):
            ueberschrift = resolve_print_title_text(daten, node_title="")
        teile.append((ueberschrift, body))

    bloecke: list[str] = []
    if toc and not any(_TOC_PLACEHOLDER_RE.search(body) for _, body in teile):
        bloecke += [CHAPTER_BOUNDARY, TOC_PLACEHOLDER]
    for ueberschrift, body in teile:
        bloecke.append(CHAPTER_BOUNDARY)
        if ueberschrift:
            bloecke.append(f"# {ueberschrift}")
        bloecke.append(body.strip("\n"))
    return "\n\n".join(bloecke) + "\n"


# ---------------------------------------------------------------------------
# Der Lauf
# ---------------------------------------------------------------------------


def typeset_book(
    definition: LayoutDefinition,
    book_path: Path | str,
    *,
    out_dir: Optional[Path] = None,
    to_pdf: bool = True,
    toc: bool = True,
    toc_depth: int = 2,
    pandoc: Optional[str] = None,
    soffice: Optional[str] = None,
    rebuild_template: bool = True,
) -> TypesetResult:
    """Setzt *book_path* mit *definition* als ``.docx`` und (wenn moeglich) PDF.

    *rebuild_template* erzeugt vorher ``reference.docx`` und ``classmap.lua``
    frisch im Buch. Das ist die Voreinstellung, weil der haeufigste Fehlgriff
    sonst unbemerkt bliebe: eine Definition aendern und ein Buch setzen, das
    noch die Vorlage von vorgestern traegt.
    """
    problems = definition.validate()
    if problems:
        raise TypesetError("Layout ist nicht erzeugbar:\n  - " + "\n  - ".join(problems))

    # Aufgeloest, nicht wie uebergeben: Pandoc laeuft mit ``cwd`` im Buch, damit
    # Bildverweise wie ``images/x.png`` stimmen. Ein relativ uebergebener
    # Buchpfad wuerde dann von dort aus noch einmal gedeutet -- und keine der
    # Eingabedateien waere mehr auffindbar.
    root = Path(book_path).resolve()
    kapitel = book_chapters(root)

    executable = find_pandoc(pandoc)
    if not executable:
        raise TypesetError(
            "Pandoc wurde nicht gefunden -- ohne das laesst sich nichts setzen. "
            "Es liegt auch der Quarto-Installation bei."
        )

    if rebuild_template:
        apply_layout(
            definition, root, write_quarto_yml=True, pandoc=pandoc
        )

    ziel_dir = Path(out_dir) if out_dir else root.joinpath(*OUTPUT_SUBDIR)
    ziel_dir.mkdir(parents=True, exist_ok=True)
    docx = ziel_dir / f"{definition.name}.docx"

    vorlagen = book_output_dir(root)
    reference = vorlagen / REFERENCE_DOCX_NAME
    lua = vorlagen / LUA_FILTER_NAME
    for datei, was in ((reference, "Formatvorlage"), (lua, "Klassen-Filter")):
        if not datei.is_file():
            raise TypesetError(
                f"{was} fehlt: {datei}. Erst »Auf Buch anwenden«, dann setzen."
            )

    meta = book_metadata(root)
    try:
        text = assemble_book(root, kapitel, toc=toc)
    except (OSError, UnicodeDecodeError) as exc:
        raise TypesetError(f"Kapitel nicht lesbar: {exc}") from exc
    satz = ziel_dir / ASSEMBLED_NAME
    satz.write_text(text, encoding="utf-8", newline="\n")

    befehl = [
        executable,
        "--from", MARKDOWN_FORMAT,
        "--to", "docx",
        f"--reference-doc={reference}",
        f"--lua-filter={lua}",
        f"--resource-path={root}",
        "--output", str(docx),
        "--metadata", "bs-typeset=true",
        "--metadata", f"bs-toc-depth={toc_depth}",
    ]
    if toc:
        titel = toc_title_for(definition.typography.language)
        if titel:
            befehl += ["--metadata", f"toc-title={titel}"]
    # Nur die Sprache: Mit ``title`` setzte Pandoc ein eigenes Titelblatt, das
    # es im Typst-PDF nicht gibt. Titel und Autor gehen danach nur in die
    # Dokumenteigenschaften (patch_docx_core_properties).
    if meta.get("lang"):
        befehl += ["--metadata", f"lang={meta['lang']}"]
    befehl.append(str(satz))

    try:
        ergebnis = run_hidden(
            befehl, capture_output=True, timeout=BOOK_PANDOC_TIMEOUT_S, check=False,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired as exc:
        raise TypesetError(
            f"Pandoc antwortet nicht ({BOOK_PANDOC_TIMEOUT_S}s)."
        ) from exc
    except OSError as exc:
        raise TypesetError(f"Pandoc nicht ausfuehrbar: {exc}") from exc
    finally:
        satz.unlink(missing_ok=True)

    meldungen = (ergebnis.stderr or b"").decode("utf-8", "replace").strip()
    if ergebnis.returncode != 0 or not docx.is_file():
        raise TypesetError(f"Pandoc konnte das Buch nicht setzen:\n{meldungen}")

    try:
        from tools.doclayout.targets.docx import patch_docx_style_languages

        patch_docx_style_languages(docx, definition)
    except Exception:  # noqa: BLE001 - Sprache ist Zusatz, Satz darf nicht scheitern
        pass
    try:
        from tools.doclayout.targets.docx import patch_docx_core_properties

        patch_docx_core_properties(
            docx, title=meta.get("title", ""), author=meta.get("author", "")
        )
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        meldungen += f"\nDokumenteigenschaften nicht gesetzt: {exc}"

    warnungen = tuple(
        zeile.strip() for zeile in meldungen.splitlines() if zeile.strip()
    )[:20]
    namen = tuple(str(p.relative_to(root)) for p in kapitel)

    if not to_pdf:
        return TypesetResult(
            docx=docx, pdf=None, chapters=namen,
            note="PDF nicht angefordert.", warnings=warnungen,
        )

    converter = find_soffice(soffice)
    if not converter:
        return TypesetResult(
            docx=docx, pdf=None, chapters=namen, warnings=warnungen,
            note=(
                "LibreOffice wurde nicht gefunden -- die ``.docx`` ist fertig, "
                "die PDF muss ein Textprogramm erzeugen."
            ),
        )

    pdf, grund = _convert_to_pdf(converter, docx, ziel_dir)
    if toc and pdf is not None and pdf.is_file():
        # Die DOCX ist das Endformat: Verzeichnis mit den Seitenzahlen der
        # eben gesetzten PDF fuellen, statt ein leeres Feld auszuliefern.
        from tools.doclayout.toc_fill import fuelle_verzeichnis

        try:
            fuelle_verzeichnis(docx, pdf, definition, tiefe=toc_depth)
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            warnungen += (f"Verzeichnis nicht in die DOCX geschrieben: {exc}",)
    return TypesetResult(
        docx=docx, pdf=pdf, chapters=namen, note=grund, warnings=warnungen
    )


__all__ = [
    "ASSEMBLED_NAME",
    "BOOK_PANDOC_TIMEOUT_S",
    "CHAPTER_BOUNDARY",
    "MARKDOWN_FORMAT",
    "OUTPUT_SUBDIR",
    "TOC_PLACEHOLDER",
    "TypesetError",
    "TypesetResult",
    "assemble_book",
    "book_chapters",
    "book_metadata",
    "typeset_book",
]
