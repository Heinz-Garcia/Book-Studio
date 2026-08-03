"""KDP Cover-Designer — Plugin-Adapter (Qt).

Dünner UI-Einstieg: Domänenlogik in ``tools.kdp_cover``, Dialog in
``ui_qt.dialogs.kdp_cover_dialog``. Keine eigene Geschäftslogik.
"""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> None:
    from ui_qt.dialogs.kdp_cover_dialog import open_kdp_cover_qt

    parent = kwargs.get("parent") or getattr(studio, "root", None)
    open_kdp_cover_qt(studio, parent)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "kdp_cover_dialog.py")


__all__ = ["run", "is_available"]
