"""Kapitelliste eines Buchprojekts -- als CSV nach draussen.

Warum es diesen Kern gibt: Jedes andere Werkzeug zeigt sein Ergebnis *in*
Book Studio. Eine CSV ist das Einzige, was man jemandem geben kann, der die
Anwendung nicht hat -- Lektorat, Uebersetzung, Satz. Von dort kommt immer
dieselbe Frage: Woraus besteht dieses Buch, in welcher Reihenfolge, wie
umfangreich.

Bewertet wird hier nichts. Verwaiste Dateien und Frontmatter-Konsistenz sind
Sache des Buch-Doktors, Textauszeichnungen die des Inventars -- dieses Modul
ist ein Export, keine Pruefung.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import frontmatter_parser
from quarto_block_parser import iter_body_lines_outside_code_fences
from tools.doclayout.typeset import TypesetError, book_chapters
from tools.doclayout.usage import markdown_files

#: Spalten der CSV, in dieser Reihenfolge.
CSV_HEADER = ("NR", "DATEI", "TITEL", "WOERTER", "ZEICHEN", "IN_QUARTO")

#: Trennzeichen der CSV -- Excel in deutscher Lokalisierung erwartet es so.
CSV_DELIMITER = ";"

#: Kodierung der CSV. ``utf-8-sig`` (also mit BOM) ist Absicht: ohne BOM liest
#: Excel die Datei als Latin-1 und macht aus "Fuehrung" ein "FÃ¼hrung".
CSV_ENCODING = "utf-8-sig"

#: Dateiname der Ausgabe unterhalb von ``<Buchprojekt>/export/``.
DEFAULT_FILENAME = "kapitelliste.csv"

#: Ersatz fuer einen fehlenden Frontmatter-Titel -- Verhalten des Vorgaengers.
NO_TITLE = "Kein Titel"

#: Wenn die Datei nicht lesbar ist, wird das gesagt statt verschwiegen.
UNREADABLE_TITLE = "Lese-Fehler"

_JA_NEIN = {True: "ja", False: "nein"}

# Bis zu drei fuehrende Leerzeichen sind nach CommonMark noch derselbe Block.
_DIV_MARKER = re.compile(r"^ {0,3}:{3,}")
_FENCE_MARKER = re.compile(r"^ {0,3}(?:`{3,}|~{3,})")


class ChapterListError(RuntimeError):
    """Das angegebene Verzeichnis ist kein lesbares Buchprojekt."""


@dataclass(frozen=True)
class ChapterRow:
    """Eine Zeile der Kapitelliste -- eine Manuskriptdatei des Buchs."""

    number: Optional[int]
    path: str
    title: str
    words: int
    characters: int
    in_quarto: bool

    def as_csv_row(self) -> list[str]:
        """Die Zeile so, wie sie in der CSV steht."""
        return [
            "" if self.number is None else str(self.number),
            self.path,
            self.title,
            str(self.words),
            str(self.characters),
            _JA_NEIN[self.in_quarto],
        ]


@dataclass(frozen=True)
class ChapterList:
    """Die vollstaendige Liste eines Buchs samt Vorbehalt zur Reihenfolge."""

    book_path: Path
    rows: tuple[ChapterRow, ...]
    order_problem: Optional[str] = None

    @property
    def chapters(self) -> tuple[ChapterRow, ...]:
        """Die in ``_quarto.yml`` gelisteten Dateien, in Lesereihenfolge."""
        return tuple(row for row in self.rows if row.in_quarto)

    @property
    def extras(self) -> tuple[ChapterRow, ...]:
        """Manuskriptdateien, die in ``_quarto.yml`` nicht vorkommen."""
        return tuple(row for row in self.rows if not row.in_quarto)

    @property
    def words(self) -> int:
        return sum(row.words for row in self.rows)

    def summary(self) -> str:
        """Einzeiler fuers Log."""
        teile = [f"{len(self.chapters)} Kapitel", f"{self.words} Woerter"]
        if self.extras:
            teile.append(f"{len(self.extras)} nicht gelistet")
        if self.order_problem:
            teile.append("ohne Reihenfolge")
        return ", ".join(teile)


def build_chapter_list(book_path: Path | str) -> list[ChapterRow]:
    """Die Kapitelliste eines Buchs, in Lesereihenfolge."""
    return list(build_chapter_list_detailed(book_path).rows)


def build_chapter_list_detailed(book_path: Path | str) -> ChapterList:
    """Wie :func:`build_chapter_list`, nennt zusaetzlich den Vorbehalt.

    Fehlt ``book.chapters`` in ``_quarto.yml``, ist die Lesereihenfolge nicht
    bekannt -- geraten wird sie nicht (siehe :func:`book_chapters`). Statt gar
    nichts zu liefern, kommen dann alle Manuskriptdateien alphabetisch und
    ohne Nummer: Eine Liste ohne Reihenfolge ist fuer eine Uebergabe immer
    noch besser als keine Liste. Damit der Empfaenger die fehlende Reihenfolge
    nicht fuer die richtige haelt, steht der Grund in ``order_problem``, und
    Dialog wie CLI sagen ihn an.
    """
    root = Path(book_path)
    if not root.is_dir():
        raise ChapterListError(f"Kein Verzeichnis: {root}")
    if not (root / "_quarto.yml").is_file():
        raise ChapterListError(
            f"{root.name} sieht nicht wie ein Quarto-Buchprojekt aus " "(_quarto.yml fehlt)."
        )

    problem: Optional[str] = None
    try:
        kapitel = book_chapters(root)
    except TypesetError as exc:
        problem = str(exc)
        kapitel = []

    rows: list[ChapterRow] = []
    gelistet: set[Path] = set()
    for nummer, pfad in enumerate(kapitel, start=1):
        rows.append(_row(root, pfad, nummer, in_quarto=True))
        gelistet.add(_key(pfad))

    # Nicht gelistete Dateien werden gezeigt, nicht verschwiegen -- aber am
    # Ende und als solche markiert. Wer eine Uebergabeliste bekommt, soll
    # sehen, dass da noch etwas liegt; ob es ins Buch gehoert, entscheidet er.
    for pfad in markdown_files(root):
        if _key(pfad) in gelistet:
            continue
        rows.append(_row(root, pfad, None, in_quarto=False))

    return ChapterList(book_path=root, rows=tuple(rows), order_problem=problem)


def write_chapter_list(
    book_path: Path | str,
    rows: list[ChapterRow],
    target: Path | str | None = None,
) -> Path:
    """Schreibt die Liste als CSV und gibt den Zielpfad zurueck.

    Ziel ist ``<Buchprojekt>/export/kapitelliste.csv``: Die Datei gehoert zum
    Buch, nicht in den Ordner, den man zufaellig indexiert hat. Sie wird ohne
    Rueckfrage ueberschrieben -- sie ist eine Momentaufnahme des Manuskripts,
    kein Dokument, an dem jemand weiterarbeitet.
    """
    ziel = Path(target) if target else Path(book_path) / "export" / DEFAULT_FILENAME
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("w", encoding=CSV_ENCODING, newline="") as handle:
        writer = csv.writer(handle, delimiter=CSV_DELIMITER)
        writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(row.as_csv_row())
    return ziel


def _key(path: Path) -> Path:
    """Vergleichsschluessel fuer Pfade aus zwei Quellen.

    ``book_chapters`` baut den Pfad aus dem YAML-Eintrag zusammen,
    ``markdown_files`` aus ``rglob`` -- ohne Aufloesung waeren
    ``buch/content/x.md`` und ``buch/./content/x.md`` zwei Dateien.
    """
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _row(root: Path, path: Path, number: Optional[int], *, in_quarto: bool) -> ChapterRow:
    try:
        inhalt = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ChapterRow(
            number=number,
            path=_relative(root, path),
            title=UNREADABLE_TITLE,
            words=0,
            characters=0,
            in_quarto=in_quarto,
        )
    teile = frontmatter_parser.parse(inhalt)
    titel = str(teile.parsed().get("title") or "").strip() or NO_TITLE
    woerter, zeichen = count_body(teile.body)
    return ChapterRow(
        number=number,
        path=_relative(root, path),
        title=titel,
        words=woerter,
        characters=zeichen,
        in_quarto=in_quarto,
    )


def _relative(root: Path, path: Path) -> str:
    """Pfad relativ zum Buchprojekt, immer mit ``/`` als Trenner.

    Die CSV wird auf fremden Rechnern gelesen; ein Windows-Backslash waere
    dort bestenfalls Zierrat und schlimmstenfalls ein Escape-Zeichen.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        try:
            rel = _key(path).relative_to(_key(root))
        except ValueError:
            return path.as_posix()
    return rel.as_posix()


def count_body(body: str) -> tuple[int, int]:
    """Woerter und Zeichen eines Textes -- ohne Auszeichnungs-Marker.

    ``::: {.fachtext}`` ist Auszeichnung, kein Text: Wer sie mitzaehlt, nennt
    dem Lektorat einen Umfang, den es nicht zu lesen bekommt. Der *Inhalt*
    eines Code-Blocks zaehlt dagegen mit -- er steht im Buch --, nur seine
    Fence-Zeilen nicht. Ein ``:::`` innerhalb eines Code-Blocks ist Beispiel
    und keine Auszeichnung; deshalb kommt die Unterscheidung aus dem
    projektweiten Tokenizer und nicht aus einem eigenen Regex.

    Zeichen werden mit Leerzeichen gezaehlt, Leerzeilen fallen heraus.
    """
    zeilen: list[str] = []
    for _nummer, zeile, im_code in iter_body_lines_outside_code_fences(body):
        if im_code:
            if _FENCE_MARKER.match(zeile):
                continue
        elif _DIV_MARKER.match(zeile):
            continue
        if not zeile.strip():
            continue
        zeilen.append(zeile.strip())
    text = "\n".join(zeilen)
    return len(text.split()), len(text)


__all__ = [
    "CSV_DELIMITER",
    "CSV_ENCODING",
    "CSV_HEADER",
    "DEFAULT_FILENAME",
    "NO_TITLE",
    "UNREADABLE_TITLE",
    "ChapterList",
    "ChapterListError",
    "ChapterRow",
    "build_chapter_list",
    "build_chapter_list_detailed",
    "count_body",
    "write_chapter_list",
]
