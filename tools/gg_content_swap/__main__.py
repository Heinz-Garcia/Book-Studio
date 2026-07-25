"""CLI: python -m tools.gg_content_swap --book … --source … [--bundle] [--yes] [--dry-run]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GrammarGraph-Nutzinhalt tauschen (Body), Frontmatter bleibt."
    )
    parser.add_argument("--book", type=Path, required=True, help="Buchprojekt-Pfad")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Publish_*-Export-Ordner oder einzelne .md (nicht die Sammelmappe)",
    )
    parser.add_argument(
        "--bundle",
        action="store_true",
        help="Komplett: Payload+Titel+Protokoll+Meta+Provenance(+Bilder)",
    )
    parser.add_argument("--yes", action="store_true", help="Schreiben ohne Rückfrage")
    parser.add_argument("--dry-run", action="store_true", help="Nur Plan, nichts schreiben")
    args = parser.parse_args(argv)

    if str(Path(__file__).resolve().parents[2]) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from tools.gg_content_swap.bundle import (
        apply_gg_export_bundle,
        format_bundle_summary,
        resolve_export_root_from_path,
    )
    from tools.gg_content_swap.source_guard import check_source_folder
    from tools.gg_content_swap.swap import run_swap

    source_arg = Path(args.source)
    source_root, payload_rel = resolve_export_root_from_path(source_arg)

    hub = check_source_folder(source_root)
    if hub.is_publish_hub:
        print(f"ERROR: {hub.reason}", file=sys.stderr)
        print(
            "Hinweis: --source muss ein einzelner Publish_*-Ordner oder eine .md darin sein.",
            file=sys.stderr,
        )
        return 2

    dry = args.dry_run or not args.yes
    if not args.yes and not args.dry_run:
        print("Hinweis: ohne --yes wird ein Dry-Run ausgeführt.", file=sys.stderr)

    if args.bundle or source_arg.is_file():
        result = apply_gg_export_bundle(
            args.book,
            source_root,
            payload_rel=payload_rel,
            dry_run=dry,
        )
        print(format_bundle_summary(result))
        return 1 if result.errors else 0

    plan, result = run_swap(args.book, source_root, dry_run=dry)
    for line in plan:
        src = line.source_rel or "-"
        print(f"[{line.status}] {line.book_rel} <- {src} ({line.message})")
    print(
        f"written={len(result.written)} skipped={len(result.skipped)} "
        f"titles={len(result.titles_updated)} errors={len(result.errors)}"
    )
    for err in result.errors:
        print(f"ERROR: {err}", file=sys.stderr)
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
