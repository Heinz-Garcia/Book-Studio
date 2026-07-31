"""CLI: python -m tools.production_paths inventory|migrate|rollback."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Buchproduktions-Pfade: Inventar und Migration (Phase 0-2)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inv = sub.add_parser(
        "inventory",
        help="Bücher, Legacy-Publish-Läufe und publish_map-Referenzen auflisten",
    )
    inv.add_argument("--json", action="store_true", help="Maschinenlesbare Ausgabe")
    inv.add_argument("--production-root", type=Path, default=None)
    inv.add_argument("--repo", type=Path, default=None)

    mig = sub.add_parser(
        "migrate",
        help="Legacy Publish_* nach books/ und inbox/ migrieren (Default: dry-run)",
    )
    mig.add_argument("--apply", action="store_true", help="Migration wirklich ausführen")
    mig.add_argument("--books-only", action="store_true", help="Nur Arbeitsbücher verschieben")
    mig.add_argument("--deliveries-only", action="store_true", help="Nur Lieferläufe verschieben")
    mig.add_argument("--source", type=Path, default=None, help="Nur diesen Ordner migrieren")
    mig.add_argument(
        "--prune-legacy-roots",
        action="store_true",
        help="Nach erfolgreicher Migration GrammarGraph/Publish aus content_root_path entfernen",
    )
    mig.add_argument("--manifest", type=Path, default=None, help="Pfad für Migrations-Manifest")
    mig.add_argument("--repo", type=Path, default=None)

    rb = sub.add_parser("rollback", help="Migration anhand Manifest rückgängig machen")
    rb.add_argument("manifest", type=Path, help="Migrations-Manifest (JSON)")
    rb.add_argument("--apply", action="store_true", help="Rollback wirklich ausführen")

    args = parser.parse_args(argv)

    if str(Path(__file__).resolve().parents[2]) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.command == "inventory":
        from tools.production_paths.inventory import format_inventory_report, scan_inventory

        report = scan_inventory(args.repo, production_root=args.production_root)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(format_inventory_report(report))
        return 0

    if args.command == "migrate":
        from tools.production_paths.migrate import (
            build_migration_plan,
            execute_migration_plan,
            format_migration_report,
        )

        migrate_books = not args.deliveries_only
        migrate_deliveries = not args.books_only
        plan = build_migration_plan(
            args.repo,
            migrate_books=migrate_books,
            migrate_deliveries=migrate_deliveries,
            only_source=args.source,
        )
        print(format_migration_report(plan, apply=args.apply))
        result = execute_migration_plan(
            plan,
            apply=args.apply,
            manifest_path=args.manifest,
            prune_legacy_roots=args.prune_legacy_roots,
            log=print,
        )
        if result.errors:
            print("")
            print("Fehler:")
            for err in result.errors:
                print(f"  ! {err}")
            return 1
        if args.apply:
            print("")
            print(f"Manifest: {result.manifest_path}")
        return 0

    if args.command == "rollback":
        from tools.production_paths.migrate import rollback_migration

        result = rollback_migration(args.manifest, apply=args.apply, log=print)
        if result.errors:
            for err in result.errors:
                print(f"! {err}")
            return 1
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
