"""Toolkit-Auswahl ohne PySide6-Import (Tk-Pfad bleibt unabhängig)."""

from __future__ import annotations

import os
from typing import Optional

_QT_ALIASES = frozenset({"qt", "pyside6", "pyside"})


def resolve_ui_toolkit(cli_ui: Optional[str] = None) -> str:
    """Liefert ``\"qt\"`` oder ``\"tk\"``.

    Reihenfolge: explizites CLI-Argument, sonst ``BOOK_STUDIO_UI``, sonst ``tk``.
    """
    raw = (cli_ui if cli_ui is not None else os.environ.get("BOOK_STUDIO_UI") or "tk")
    normalized = str(raw).strip().lower()
    if normalized in _QT_ALIASES:
        return "qt"
    return "tk"


def wants_qt_ui(cli_ui: Optional[str] = None) -> bool:
    return resolve_ui_toolkit(cli_ui) == "qt"
