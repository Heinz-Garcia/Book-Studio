"""Skeleton-Populate — Plugin-Adapter für tools.skeleton."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    """Menü-Entrypoint: delegiert an tools.skeleton.populate.run."""
    from tools.skeleton.populate import run as populate_run

    return populate_run(studio=studio, **kwargs)


def on_after_book_import(studio: Optional[Any] = None, **kwargs) -> None:
    """Hook: nach Import ohne Pflichtseiten einmalig Populate anbieten."""
    from tkinter import messagebox

    if studio is None or not getattr(studio, "current_book", None):
        return
    book = Path(studio.current_book)
    required_dir = book / "content" / "required"
    if required_dir.is_dir() and any(required_dir.glob("*.md")):
        return
    parent = getattr(studio, "root", None)
    if not messagebox.askyesno(
        "Skeleton-Rahmen übernehmen?",
        "Für dieses Buch wurden noch keine Pflichtseiten (Titel, Klappentext, "
        "Impressum, Einleitung, …) gefunden.\n\n"
        "Rahmen aus der Skeleton-Bibliothek jetzt ins Buch übernehmen?",
        parent=parent,
    ):
        return
    run(studio=studio, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "tools", "skeleton", "populate.py")


__all__ = ["run", "on_after_book_import", "is_available"]
