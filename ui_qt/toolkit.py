"""Toolkit-Auswahl ohne PySide6-Import."""

from __future__ import annotations

import os
from typing import Optional

_QT_ALIASES = frozenset({"qt", "pyside6", "pyside"})
_TK_ALIASES = frozenset({"tk", "tkinter", "legacy"})


def resolve_ui_toolkit(cli_ui: Optional[str] = None) -> str:
    """Liefert ``\"qt\"`` oder ``\"tk\"``.

    Reihenfolge: explizites CLI-Argument, sonst ``BOOK_STUDIO_UI``,
    sonst **qt** (Default ab Phase 6). Legacy-Tk: ``--ui tk`` oder
    ``BOOK_STUDIO_UI=tk``.
    """
    raw = cli_ui if cli_ui is not None else os.environ.get("BOOK_STUDIO_UI")
    if raw is None or str(raw).strip() == "":
        return "qt"
    normalized = str(raw).strip().lower()
    if normalized in _TK_ALIASES:
        return "tk"
    if normalized in _QT_ALIASES:
        return "qt"
    # Unbekannte Werte: sicherheitshalber Qt
    return "qt"


def wants_qt_ui(cli_ui: Optional[str] = None) -> bool:
    return resolve_ui_toolkit(cli_ui) == "qt"
