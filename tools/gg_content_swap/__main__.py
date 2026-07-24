"""CLI: python -m tools.gg_content_swap --book … --source … [--yes] [--dry-run]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GrammarGraph-Nutzinhalt tauschen (Body), Frontmatter bleibt."
    )
    parser.add_argument("--book", type=Path, required=True, help="Buchprojekt-Pfad")
    parser.add_argument("--source", type=Path, required=True, help="GG-Export-Ordner")
    parser.add_argument("--yes", action="store_true", help="Schreiben ohne Rückfrage")
    parser.add_argument("--dry-run", action="store_true", help="Nur Plan, nichts schreiben")
    args = parser.parse_args(argv)

    if str(Path(__file__).resolve().parents[2]) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from tools.gg_content_swap.swap import run_swap

    if not args.yes and not args.dry_run:
        print("Hinweis: ohne --yes wird ein Dry-Run ausgeführt.", file=sys.stderr)
        args.dry_run = True

    plan, result = run_swap(args.book, args.source, dry_run=args.dry_run or not args.yes)
    for line in plan:
        src = line.source_rel or "—"
        print(f"[{line.status}] {line.book_rel} ← {src} ({line.message})")
    print(
        f"written={len(result.written)} skipped={len(result.skipped)} errors={len(result.errors)}"
    )
    for err in result.errors:
        print(f"ERROR: {err}", file=sys.stderr)
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
