"""CLI der Formatvorlagen-Schicht: ``python -m tools.doclayout ...``

    list                      vorhandene Layouts auflisten
    show   IFJN_layout        Zusammenfassung + Validierung
    build  IFJN_layout -o DIR reference.docx und classmap.lua erzeugen
    apply  IFJN_layout -b BUCH  dasselbe ins Buchprojekt + _quarto.yml
    snippet IFJN_layout       die _quarto.yml-Eintraege ausgeben
    import  ALT.docx -n NAME  bestehende .docx-Vorlage als Layout uebernehmen
    preview IFJN_layout       die Definition wirklich setzen (Pandoc + LibreOffice)
    usage  IFJN_layout -b BUCH  Klassen des Buches gegen die Abbildung halten
    typeset IFJN_layout -b BUCH das ganze Buch setzen (.docx + .pdf)
    classes                   Klassenverzeichnis fuer den Generator schreiben

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
from tools.doclayout.importer import import_docx
from tools.doclayout.library import (
    LIBRARY_DIR,
    available_layouts,
    layout_path,
    load_layout,
)
from tools.doclayout.preview import render_preview
from tools.doclayout.typeset import typeset_book
from tools.doclayout.requirements import check_requirements, is_blocked, missing
from tools.doclayout.registry import build_registry, registry_path, write_registry
from tools.doclayout.schema import LayoutDefinition, LayoutError
from tools.doclayout.usage import (
    compare,
    read_generator_classes,
    scan_book_detailed,
)
from tools.doclayout.targets.docx import build_reference_docx


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
    # Dieselbe Quelle wie im Editor -- sonst laufen die Auskuenfte auseinander.
    requirements = check_requirements(
        pandoc=args.pandoc, soffice=getattr(args, "soffice", None)
    )
    for requirement in requirements:
        state = requirement.path or (
            "NICHT GEFUNDEN" if requirement.essential else "nicht gefunden"
        )
        print(f"{requirement.name:15s}: {state}")
    for requirement in missing(requirements):
        print(f"  -> {requirement.consequence} {requirement.hint}")
    print(f"{'Bibliothek':15s}: {args.library or LIBRARY_DIR}")
    verzeichnis = registry_path(args.library)
    print(
        f"{'Klassenliste':15s}: "
        + (str(verzeichnis) if verzeichnis.is_file() else "noch nicht geschrieben")
    )
    layouts = available_layouts(args.library)
    print(f"{'Layouts':15s}: {len(layouts)}")
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
    return 0 if not is_blocked(requirements) and not broken else 1


def cmd_preview(args: argparse.Namespace) -> int:
    """Setzt die Definition wirklich -- derselbe Weg wie im Editor."""
    definition = _load(args)
    out = Path(args.out) if args.out else Path.cwd() / "doclayout_preview"
    result = render_preview(
        definition,
        out,
        pandoc=args.pandoc,
        soffice=args.soffice,
        to_pdf=not args.no_pdf,
    )
    print(f"Markdown       : {result.markdown}")
    print(f"DOCX           : {result.docx}")
    print(f"PDF            : {result.pdf or '-'}")
    if result.note:
        print(f"Hinweis        : {result.note}")
    return 0 if (result.complete or args.no_pdf) else 1


def cmd_typeset(args: argparse.Namespace) -> int:
    """Setzt das ganze Buch -- der Schritt, der bisher von Hand getippt wurde."""
    definition = _load(args)
    result = typeset_book(
        definition,
        args.book,
        out_dir=Path(args.out) if args.out else None,
        to_pdf=not args.no_pdf,
        toc=not args.no_toc,
        toc_depth=args.toc_depth,
        pandoc=args.pandoc,
        soffice=args.soffice,
        rebuild_template=not args.keep_template,
    )
    print(f"Kapitel : {len(result.chapters)}")
    for name in result.chapters:
        print(f"   {name}")
    print(f"DOCX    : {result.docx}")
    print(f"PDF     : {result.pdf or '-'}")
    if result.note:
        print(f"Hinweis : {result.note}")
    if result.warnings:
        # Pandocs Meldungen betreffen das Manuskript, nicht dieses Werkzeug --
        # sie zu verschlucken hiesse, dem Autor eine Auskunft vorzuenthalten.
        print("Meldungen von Pandoc:")
        for zeile in result.warnings:
            print(f"   {zeile}")
    return 0 if (result.complete or args.no_pdf) else 1


def cmd_usage(args: argparse.Namespace) -> int:
    """Haelt die Klassen des Buches gegen die Klassen-Abbildung."""
    definition = _load(args)
    book = Path(args.book)
    if not (book / "_quarto.yml").is_file():
        print(f"FEHLER: {book} sieht nicht wie ein Quarto-Buchprojekt aus.", file=sys.stderr)
        return 2
    gueltig, altform = scan_book_detailed(book)
    result = compare(
        gueltig, definition, ignore_builtins=not args.all, legacy_form=altform
    )
    print(result.summary())
    if result.unmapped:
        print()
        print("Ohne Vorlage (bleiben im .docx unformatiert):")
        for entry in result.unmapped:
            print(f"  .{entry.name:<22s} {entry.count:5d}x in {len(entry.files)} Datei(en)")
    if result.mapped:
        print()
        print("Zugeordnet:")
        for entry in result.mapped:
            print(f"  .{entry.name:<22s} {entry.count:5d}x -> {definition.classmap[entry.name]}")
    if result.builtin:
        print()
        print("Von Quarto selbst bedient:")
        for entry in result.builtin:
            print(f"  .{entry.name:<22s} {entry.count:5d}x")
    if result.unused:
        print()
        print("Zugeordnet, aber im Buch nicht benutzt:")
        for name in result.unused:
            print(f"  .{name:<22s}      -> {definition.classmap[name]}")
    if result.legacy_form:
        print()
        print("Altform ohne Punkt ('::: {name}' statt '::: {.name}'):")
        print("  Funktioniert -- classmap.lua faengt diese Form ab, die Bloecke")
        print("  bekommen ihr Absatzformat. Wer den Export geradezieht, wird")
        print("  sie los; noetig ist es nicht.")
        for entry in result.legacy_form:
            print(f"  {entry.name:<23s} {entry.count:5d}x in {len(entry.files)} Datei(en)")
    generator = read_generator_classes(book)
    if generator and not generator.is_empty:
        print()
        quelle = f" (aus {generator.source})" if generator.source else ""
        print(f"Laut Generator-Export{quelle}:")
        print("  " + (", ".join(f".{n}" for n in generator.names) or "keine"))
        if generator.malformed:
            print(
                "  In der Altform im Export: "
                + ", ".join(f"{{{n}}}" for n in sorted(generator.malformed))
            )
    # Die Altform ist kein Fehlschlag: Sie wird gesetzt wie jede andere Form.
    # Sie in den Rueckgabewert zu nehmen hiesse, ein Buch mit 240 solchen
    # Bloecken dauerhaft als kaputt zu melden, obwohl nichts kaputt ist.
    return 0 if result.is_complete else 1


def cmd_classes(args: argparse.Namespace) -> int:
    """Schreibt das Klassenverzeichnis, das der Generator auslesen kann."""
    if args.show:
        data = build_registry(args.library)
        print(f"Bibliothek : {data['library']}")
        print(f"Layouts    : {', '.join(data['layouts']) or 'keine'}")
        for name in data["names"]:
            entry = data["classes"][name]
            layouts = ", ".join(entry["layouts"])
            styles = ", ".join(entry["styles"])
            print(f"  .{name:<22s} {styles:<20s} ({layouts})")
        if not data["names"]:
            print("  (keine Klassen zugeordnet)")
        return 0
    target = write_registry(args.library)
    known = build_registry(args.library)["names"]
    print(f"Geschrieben: {target}")
    print(f"Klassen    : {', '.join(known) or 'keine'}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    definition = import_docx(
        args.docx, name=args.name, keep_all_styles=args.keep_all
    )
    target = Path(args.out) if args.out else layout_path(definition.name, args.library)
    if target.exists() and not args.force:
        print(
            f"FEHLER: {target} existiert bereits -- --force zum Ueberschreiben.",
            file=sys.stderr,
        )
        return 2
    definition.save(target)
    print(f"Layout : {target}")
    print(f"Formate: {len(definition.styles)}")
    print(f"Farben : {', '.join(sorted(definition.colors)) or 'keine'}")
    print(
        f"Seite  : {definition.page.width_mm:g} x {definition.page.height_mm:g} mm"
    )
    problems = definition.validate()
    if problems:
        print("\nHinweise:")
        for problem in problems:
            print(f"  - {problem}")
    print(
        "\nDie classmap ist noch leer -- welche Markdown-Klasse auf welches "
        "Format zeigt, weiss nur die Quelle. Im Editor ergaenzen."
    )
    return 0


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

    sp_import = sub.add_parser(
        "import", help="bestehende .docx als Layout-Definition uebernehmen"
    )
    sp_import.add_argument("docx", help="Quelldatei (.docx)")
    sp_import.add_argument("-n", "--name", help="Name des Layouts (Standard: Dateiname)")
    sp_import.add_argument("-o", "--out", help="Zieldatei (Standard: Bibliothek)")
    sp_import.add_argument("--keep-all", action="store_true",
                           help="auch Formate ohne eigene Gestaltung uebernehmen")
    sp_import.add_argument("--force", action="store_true", help="vorhandenes Layout ersetzen")
    sp_import.set_defaults(func=cmd_import)

    sp_preview = sub.add_parser(
        "preview", help="die Definition wirklich setzen (Pandoc + LibreOffice)"
    )
    sp_preview.add_argument("layout", nargs="?", help="Name aus der Bibliothek")
    sp_preview.add_argument("-f", "--file", help="Layout-Datei statt Bibliotheksname")
    sp_preview.add_argument("-o", "--out", help="Ausgabeverzeichnis")
    sp_preview.add_argument("--soffice", help="Pfad zu soffice(.exe)")
    sp_preview.add_argument(
        "--no-pdf", action="store_true", help="nur die .docx erzeugen"
    )
    sp_preview.set_defaults(func=cmd_preview)

    sp_typeset = sub.add_parser(
        "typeset", help="das ganze Buch mit diesem Layout setzen (.docx + .pdf)"
    )
    sp_typeset.add_argument("layout", nargs="?", help="Name aus der Bibliothek")
    sp_typeset.add_argument("-f", "--file", help="Layout-Datei statt Bibliotheksname")
    sp_typeset.add_argument("-b", "--book", required=True, help="Buchprojekt")
    sp_typeset.add_argument("-o", "--out", help="Ausgabeverzeichnis (Vorgabe: export/doclayout)")
    sp_typeset.add_argument("--soffice", help="Pfad zu soffice(.exe)")
    sp_typeset.add_argument("--no-pdf", action="store_true", help="nur die .docx erzeugen")
    sp_typeset.add_argument(
        "--no-toc", action="store_true", help="ohne Inhaltsverzeichnis setzen"
    )
    sp_typeset.add_argument(
        "--toc-depth", type=int, default=1, help="Gliederungstiefe des Verzeichnisses"
    )
    sp_typeset.add_argument(
        "--keep-template", action="store_true",
        help="vorhandene reference.docx/classmap.lua benutzen, nicht neu erzeugen",
    )
    sp_typeset.set_defaults(func=cmd_typeset)

    sp_usage = sub.add_parser(
        "usage", help="Klassen des Buches gegen die Klassen-Abbildung halten"
    )
    sp_usage.add_argument("layout", nargs="?", help="Name aus der Bibliothek")
    sp_usage.add_argument("-f", "--file", help="Layout-Datei statt Bibliotheksname")
    sp_usage.add_argument("-b", "--book", required=True, help="Buchprojekt")
    sp_usage.add_argument(
        "--all", action="store_true",
        help="auch Quarto-eigene Klassen als Luecke werten",
    )
    sp_usage.set_defaults(func=cmd_usage)

    sp_classes = sub.add_parser(
        "classes", help="Klassenverzeichnis fuer den Generator schreiben"
    )
    sp_classes.add_argument(
        "--show", action="store_true", help="nur anzeigen, nichts schreiben"
    )
    sp_classes.set_defaults(func=cmd_classes)

    sp_doctor = sub.add_parser("doctor", help="Voraussetzungen pruefen")
    sp_doctor.add_argument("--soffice", help="Pfad zu soffice(.exe)")
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
