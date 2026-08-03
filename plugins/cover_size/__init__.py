"""Cover-Größe berechnen — Plugin-Adapter (Qt).

Dünner UI-Einstiegspunkt, keine eigene Logik: die Rechenlogik lebt
vollständig in ``tools.cover_size.calculator`` (kein UI-Bezug dort), der
Dialog in ``ui_qt.dialogs.cover_size_dialog``. Braucht -- anders als die
meisten anderen Plugins -- kein aktives Buchprojekt (reiner Rechner).
"""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> None:
    from ui_qt.dialogs.cover_size_dialog import open_cover_size_qt

    parent = kwargs.get("parent") or getattr(studio, "root", None)
    open_cover_size_qt(studio, parent)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "cover_size_dialog.py")


__all__ = ["run", "is_available"]
