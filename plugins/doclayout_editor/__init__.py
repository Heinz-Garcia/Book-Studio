"""Layout-Editor — Plugin-Adapter (Qt).

Duenner Adapter nach dem Muster von ``plugins/skeleton_editor``: die Logik
liegt vollstaendig in ``tools/doclayout/`` (GUI-frei) und
``ui_qt/dialogs/doclayout_editor_dialog.py`` (nur Widgets). Kein Kernmodul
wird angefasst -- die Auto-Discovery in ``services/plugin_loader.py`` haengt
den Eintrag additiv ins Tools-Menue.
"""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    from ui_qt.dialogs.doclayout_editor_dialog import open_doclayout_editor_qt

    parent = kwargs.get("parent") or getattr(studio, "root", None)
    return open_doclayout_editor_qt(studio=studio, parent=parent, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "doclayout_editor_dialog.py")


__all__ = ["run", "is_available"]
