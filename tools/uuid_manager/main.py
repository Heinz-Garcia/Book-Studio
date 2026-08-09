"""Standalone-Einstieg für den UUID-Manager."""

# pylint: disable=no-name-in-module

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

# Running ``python tools/uuid_manager/main.py`` puts this file's directory on
# ``sys.path[0]``, not the repo root — so ``import tools...`` fails unless we
# insert the repo root explicitly (same need as ``plugins.uuid_manager``).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT_STR = str(_REPO_ROOT)
if _REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, _REPO_ROOT_STR)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UUID-Manager öffnen")
    parser.add_argument("--book-studio-repo", default=str(_REPO_ROOT))
    parser.add_argument("--grammargraph-repo", default="")
    parser.add_argument("--title", default="UUID-Manager")
    args = parser.parse_args(argv)

    # Prefer the explicit --book-studio-repo for imports when it differs.
    repo = Path(args.book_studio_repo).expanduser().resolve()
    repo_str = str(repo)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)

    from tools.uuid_manager.dialog import run_dialog
    from ui_qt.theme import apply_theme

    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    return run_dialog(
        book_studio_repo=repo,
        grammargraph_repo=Path(args.grammargraph_repo).resolve()
        if str(args.grammargraph_repo).strip()
        else None,
        window_title=str(args.title or "UUID-Manager"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
