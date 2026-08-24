"""Quarto Book Studio — Einstieg (nur Qt-UI).

Die ehemalige Tk-``BookStudio``-Klasse wurde entfernt. Geschäftslogik liegt
in ``services/``, ``export_manager``, ``book_doctor`` und ``ui_qt/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quarto Book Studio")
    parser.add_argument("command", nargs="?", choices=["import"], help="Befehl (import)")
    parser.add_argument("path", nargs="?", help="Pfad zum Publish-/Inbox-Verzeichnis")
    parser.add_argument("--index-title", type=str, default="", help="Titel fuer index.md")
    parser.add_argument("--index-author", type=str, default="", help="Autor fuer index.md")
    parser.add_argument(
        "--index-description",
        type=str,
        default="",
        help="Description fuer index.md",
    )
    parser.add_argument(
        "--ui",
        choices=["tk", "qt"],
        default=None,
        help="UI-Toolkit (nur noch qt; tk wurde entfernt)",
    )
    args = parser.parse_args(argv)

    from ui_qt import is_tk_requested, run_qt_app

    if is_tk_requested(args.ui):
        print(
            "Legacy-Tk-UI wurde entfernt.\n"
            "Bitte ohne --ui / BOOK_STUDIO_UI starten — Qt ist die einzige UI.",
            file=sys.stderr,
        )
        return 2

    import_path: Path | None = None
    activate_book: Path | None = None
    if args.command == "import" and args.path:
        candidate = Path(args.path).resolve()
        if candidate.is_dir():
            from tools.book_projects.import_delivery import (
                materialize_delivery_as_working_book,
            )

            try:
                # Inbox-/Publish-Lieferung → production/books/<Projekt>/
                # (nicht den Lauf-Zeitstempel als Buch öffnen)
                activate_book = materialize_delivery_as_working_book(
                    candidate,
                    index_title=args.index_title,
                    index_author=args.index_author,
                    index_description=args.index_description,
                )
                import_path = candidate
                print(f"[Import] Arbeitsbuch: {activate_book}", flush=True)
            except (OSError, ValueError, TypeError) as exc:
                print(f"[Import] Fehler: {exc}", file=sys.stderr)
                return 1

    return int(run_qt_app(import_path=import_path, activate_book=activate_book))


if __name__ == "__main__":
    raise SystemExit(main())
