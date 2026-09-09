"""Provenance — Plugin-Adapter für tools.provenance."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> None:
    """Menü-Entrypoint: öffnet den Read-only-Provenance-Viewer."""
    from ui_qt.dialogs.provenance_viewer_dialog import open_provenance_viewer_qt

    parent = kwargs.get("parent")
    open_provenance_viewer_qt(studio, parent)


def on_after_book_import(studio: Optional[Any] = None, **kwargs) -> None:
    """Hook: Provenance aus Import-Verzeichnis nach bookconfig/ übernehmen."""
    if studio is None or not getattr(studio, "current_book", None):
        return
    import_path = kwargs.get("import_path")
    if import_path is None:
        return
    from tools.provenance.ingest import ingest_from_import_dir

    book = Path(studio.current_book)
    result = ingest_from_import_dir(book, Path(import_path))
    if result.get("skipped"):
        return
    if result.get("written"):
        studio.log(
            f"📋 Provenance übernommen ({result.get('source', '')}): {result.get('path', '')}",
            "success",
        )


def is_available() -> bool:
    """Der Menueeintrag haengt am Viewer, nicht an den Hooks.

    21 von 23 Plugins beantworten diese Frage; diese beiden fielen aus dem
    Muster. Der Lader kam damit zurecht, aber wer die Menueliste prueft,
    musste fuer zwei Eintraege eine Ausnahme kennen.
    """
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "provenance_viewer_dialog.py")


__all__ = ["run", "is_available", "on_after_book_import"]
