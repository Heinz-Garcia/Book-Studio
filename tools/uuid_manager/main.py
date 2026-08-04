"""Standalone-Einstieg für den UUID-Manager."""

# pylint: disable=no-name-in-module

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UUID-Manager öffnen")
    parser.add_argument("--book-studio-repo", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--grammargraph-repo", default="")
    parser.add_argument("--title", default="UUID-Manager")
    args = parser.parse_args(argv)

    from tools.uuid_manager.dialog import run_dialog
    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    return run_dialog(
        book_studio_repo=Path(args.book_studio_repo),
        grammargraph_repo=Path(args.grammargraph_repo).resolve()
        if str(args.grammargraph_repo).strip()
        else None,
        window_title=str(args.title or "UUID-Manager"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
