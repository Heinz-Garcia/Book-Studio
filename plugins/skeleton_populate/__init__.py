"""Skeleton-Populate — Plugin-Adapter für tools.skeleton."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    """Menü-/Hook-Entrypoint: Qt-Dialog (Profil + optionale Snippets).

    Der stille CLI-Pfad ``tools.skeleton.populate.run`` bleibt für Skripte;
    aus der Oberfläche und dem Import-Hook soll derselbe Dialog kommen wie
    über ``plugin_dispatch`` — sonst landet der Hook auf dem Default-Profil
    ohne Auswahl.
    """
    from ui_qt.dialogs.skeleton_qt import open_skeleton_populate_qt

    # Klammern gesetzt und ``parent`` entnommen -- beides war vorher falsch:
    #
    # 1. ``a or b if studio else None`` bindet als ``(a or b) if studio else None``.
    #    Ohne ``studio`` war ``parent`` deshalb ``None``, **auch wenn** es
    #    ausdruecklich uebergeben wurde; der Dialog oeffnete elternlos.
    # 2. ``parent`` blieb zusaetzlich in ``kwargs`` stehen und ging als
    #    ``open_...(studio, parent, **kwargs)`` ein zweites Mal hinaus --
    #    ``TypeError: got multiple values for argument 'parent'``.
    parent = kwargs.pop("parent", None) or (getattr(studio, "root", None) if studio else None)
    return open_skeleton_populate_qt(studio, parent, **kwargs)


def on_after_book_import(studio: Optional[Any] = None, **kwargs) -> None:
    """Hook: nach Import ohne Pflichtseiten einmalig Populate anbieten."""
    import ui_hooks
    from page_required import book_has_required_pages

    if studio is None or not getattr(studio, "current_book", None):
        return
    book = Path(studio.current_book)
    if book_has_required_pages(book):
        return
    if not ui_hooks.messagebox.askyesno(
        "Skeleton-Rahmen übernehmen?",
        "Für dieses Buch wurden noch keine Pflichtseiten (Titel, Klappentext, "
        "Impressum, Einleitung, …) gefunden.\n\n"
        "Rahmen aus der Skeleton-Bibliothek jetzt ins Buch übernehmen?",
    ):
        return
    run(studio=studio, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "tools", "skeleton", "populate.py")


__all__ = ["run", "on_after_book_import", "is_available"]
