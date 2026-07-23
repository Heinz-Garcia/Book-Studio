"""Toolkit-Auswahl — Phase 6: nur noch Qt."""

from __future__ import annotations

import os
from typing import Optional

_QT_ALIASES = frozenset({"qt", "pyside6", "pyside", ""})
_TK_ALIASES = frozenset({"tk", "tkinter", "legacy"})


def resolve_ui_toolkit(cli_ui: Optional[str] = None) -> str:
    """Liefert immer ``\"qt\"``.

    ``--ui tk`` / ``BOOK_STUDIO_UI=tk`` werden vom Einstieg in
    ``book_studio.py`` mit Exit 2 abgelehnt; diese Funktion bleibt für
    Tests und Aufrufer, die nur die gewünschte Toolkit-ID lesen.
    """
    raw = cli_ui if cli_ui is not None else os.environ.get("BOOK_STUDIO_UI")
    if raw is None:
        return "qt"
    normalized = str(raw).strip().lower()
    if normalized in _TK_ALIASES:
        return "tk"  # Signal an den Caller — Einstieg startet Tk nicht mehr
    return "qt"


def wants_qt_ui(cli_ui: Optional[str] = None) -> bool:
    return resolve_ui_toolkit(cli_ui) == "qt"


def is_tk_requested(cli_ui: Optional[str] = None) -> bool:
    """True, wenn CLI/Env explizit Legacy-Tk verlangen (nicht mehr unterstützt)."""
    return resolve_ui_toolkit(cli_ui) == "tk"
