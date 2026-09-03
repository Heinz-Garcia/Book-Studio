"""CLI der Formatvorlagen-Schicht: ``python -m tools.doclayout ...``

    list                      vorhandene Layouts auflisten
    show   IFJN_layout        Zusammenfassung + Validierung
    build  IFJN_layout -o DIR reference.docx und classmap.lua erzeugen
    apply  IFJN_layout -b BUCH  dasselbe ins Buchprojekt + _quarto.yml
    snippet IFJN_layout       die _quarto.yml-Eintraege ausgeben

``print`` ist hier zulaessig (CLI-Werkzeug unter ``tools/``, siehe AGENTS.md).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.doclayout.apply import (
    LUA_FILTER_NAME,
    REFERENCE_DOCX_NAME,
    apply_layout,
    quarto_snippet,
)
from tools.doclayout.classmap import write_lua_filter
from tools.doclayout.library import LIBRARY_DIR, available_layouts, load_layout
from tools.doclayout.schema import LayoutDefinition, LayoutError
from tools.doclayout.targets.docx import build_reference_docx, find_pandoc


def _load(args: argparse.Namespace) -> LayoutDefinition:
    if getattr(args, "file", None):
        return LayoutDefinition.load(args.file)
    return load_layout(args.layout, args.library)


def cmd_list(args: argparse.Namespace) -> int:
    layouts = available_layouts(args.library)
    if not layouts:
        print(f"Keine Layouts in {args.library or LIBRARY_DIR}")
        return 1
    for path in layouts:
        try:
            definition = LayoutDefinition.load(path)
        except LayoutError as exc:
            print(f"  {path.stem:<20} FEHLER: {exc}")
            continue
        problems = definition.validate()
        mark = "!" if problems else " "
        print(f"{mark} {definition.name:<20} {definition.label or '':<26} "
              f"{len(definition.styles)} Formate")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    definition = _load(args)
    page = definition.page
    print(f"Layout    : {definition.name}")
    if definition.label:
        print(f"Bezeichnung: {definition.label}")
    if definition.description:
        print(f"Zweck     : {definition.description.strip()}")
    print(f"Seite     : {page.width_mm:g} x {page.height_mm:g} mm, "
          f"Textbreite {page.text_width_mm:g} mm"
          f"{', gespiegelt' if page.mirrored else ''}")
    print(f"Raender   : oben {page.margin.top_mm:g}, unten {page.margin.bottom_mm:g}, "
          f"innen {page.margin.inner_mm:g}, aussen {page.margin.outer_mm:g} mm")
    print(f"Grundtext : {definition.typography.body_font} "
          f"{definition.typography.base_size_pt:g} pt, "
          f"Zeilenhoehe {definition.typography.line_height:g}, "
          f"Sprache {definition.typography.language}")
    print(f"Farben    : {len(definition.colors)}  "
          f"({', '.join(sorted(definition.colors)) or 'keine'})")
    print(f"Formate   : {len(definition.styles)}")
    print("Klassen-Abbildung:")
    for cls, style in sorted(definition.classmap.items()):
        print(f"    .{cls:<20} -> {style}")
    problems = definition.validate()
    if problems:
        print("\nProbleme:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nValidierung: ok")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    definition = _load(args)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    reference = build_reference_docx(
        definition, out_dir / REFERENCE_DOCX_NAME,
        base_docx=args.base, pandoc=args.pandoc,
    )
    lua = write_lua_filter(definition, out_dir / LUA_FILTER_NAME)
    print(f"Vorlage: {reference} ({reference.stat().st_size} Bytes)")
    print(f"Filter : {lua}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    definition = _load(args)
    result = apply_layout(
        definition, args.book,
        write_quarto_yml=not args.no_quarto_yml,
        base_docx=args.base,
        pandoc=args.pandoc,
    )
    print(result.summary())
    return 0


def cmd_snippet(args: argparse.Namespace) -> int:
    print(quarto_snippet(_load(args)))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Prueft die Voraussetzungen -- haeufigste Supportfrage zuerst."""
    pandoc = find_pandoc(args.pandoc)
    print(f"Pandoc         : {pandoc or 'NICHT GEFUNDEN'}")
    print(f"Bibliothek     : {args.library or LIBRARY_DIR}")
    layouts = available_layouts(args.library)
    print(f"Layouts        : {len(layouts)}")
    broken = 0
    for path in layouts:
        try:
            problems = LayoutDefinition.load(path).validate()
        except LayoutError as exc:
            print(f"  ! {path.stem}: {exc}")
            broken += 1
            continue
        if problems:
            broken += 1
            print(f"  ! {path.stem}: {len(problems)} Problem(e)")
    return 0 if pandoc and not broken else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.doclayout",
        description="Formatvorlagen-Schicht: eine Definition, mehrere Zielformate.",
    )
    parser.add_argument("--library", help="alternatives Bibliotheksverzeichnis")
    parser.add_argument("--pandoc", help="Pfad zu pandoc(.exe)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_layout_arg(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("layout", nargs="?", default="IFJN_layout",
                        help="Name des Layouts (Standard: IFJN_layout)")
        sp.add_argument("--file", help="Layout-Datei direkt statt ueber den Namen")

    sp_list = sub.add_parser("list", help="vorhandene Layouts auflisten")
    sp_list.set_defaults(func=cmd_list)

    sp_show = sub.add_parser("show", help="Zusammenfassung und Validierung")
    add_layout_arg(sp_show)
    sp_show.set_defaults(func=cmd_show)

    sp_build = sub.add_parser("build", help="Vorlagen in ein Verzeichnis erzeugen")
    add_layout_arg(sp_build)
    sp_build.add_argument("-o", "--out", required=True, help="Zielverzeichnis")
    sp_build.add_argument("--base", help="eigene reference.docx als Ausgangspunkt")
    sp_build.set_defaults(func=cmd_build)

    sp_apply = sub.add_parser("apply", help="Layout auf ein Buchprojekt anwenden")
    add_layout_arg(sp_apply)
    sp_apply.add_argument("-b", "--book", required=True, help="Pfad zum Buchprojekt")
    sp_apply.add_argument("--base", help="eigene reference.docx als Ausgangspunkt")
    sp_apply.add_argument("--no-quarto-yml", action="store_true",
                          help="_quarto.yml nicht anfassen")
    sp_apply.set_defaults(func=cmd_apply)

    sp_snippet = sub.add_parser("snippet", help="_quarto.yml-Eintraege ausgeben")
    add_layout_arg(sp_snippet)
    sp_snippet.set_defaults(func=cmd_snippet)

    sp_doctor = sub.add_parser("doctor", help="Voraussetzungen pruefen")
    sp_doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except LayoutError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
