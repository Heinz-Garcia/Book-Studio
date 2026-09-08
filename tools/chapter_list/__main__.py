"""CLI der Kapitelliste: ``python -m tools.chapter_list --book <Buchprojekt>``

``print`` ist hier zulaessig (CLI-Werkzeug unter ``tools/``, siehe AGENTS.md).
"""

from __future__ import annotations

import argparse
import sys

from tools.chapter_list.builder import (
    ChapterListError,
    build_chapter_list_detailed,
    write_chapter_list,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.chapter_list",
        description=(
            "Exportiert die Kapitelliste eines Buchprojekts als CSV -- "
            "in der Reihenfolge, in der das Buch gelesen wird."
        ),
    )
    parser.add_argument("-b", "--book", required=True, help="Buchprojekt")
    parser.add_argument(
        "-o",
        "--out",
        default=None,
        help="Zieldatei (Standard: <Buchprojekt>/export/kapitelliste.csv)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        liste = build_chapter_list_detailed(args.book)
        ziel = write_chapter_list(liste.book_path, list(liste.rows), args.out)
    except ChapterListError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"FEHLER: CSV nicht schreibbar: {exc}", file=sys.stderr)
        return 2

    print(f"{len(liste.rows)} Zeilen ({len(liste.chapters)} Kapitel)")
    print(f"Datei: {ziel}")
    if liste.order_problem:
        # Ohne diesen Hinweis haelt der Empfaenger die alphabetische Liste fuer
        # die Kapitelfolge des Buchs -- der teuerste Irrtum, den diese CSV
        # ausloesen kann.
        print(f"ACHTUNG: {liste.order_problem}", file=sys.stderr)
        print(
            "Die Spalte NR bleibt deshalb leer; die Zeilen stehen alphabetisch.",
            file=sys.stderr,
        )
    if liste.extras:
        print(
            f"Hinweis: {len(liste.extras)} Datei(en) stehen nicht in _quarto.yml "
            "-- sie stehen am Ende der CSV mit IN_QUARTO=nein.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
