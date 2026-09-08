"""Memo-Block — Plugin-Adapter (Qt).

Duenner Adapter nach dem Muster von ``plugins/doclayout_editor``: Die Ablage
liegt in ``tools/memo_pad/`` (GUI-frei), das Fenster in
``ui_qt/dialogs/memo_pad_dialog.py`` (nur Widgets). Kein Kernmodul wird
angefasst -- die Auto-Discovery in ``services/plugin_loader.py`` haengt den
Eintrag additiv ins Menue.
"""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    from ui_qt.dialogs.memo_pad_dialog import open_memo_pad

    # ``pop`` statt ``get``: ``parent`` geht ausdruecklich hinaus und darf
    # nicht zusaetzlich in ``**kwargs`` stecken bleiben -- sonst
    # ``TypeError: got multiple values for argument 'parent'``.
    parent = kwargs.pop("parent", None) or getattr(studio, "root", None)
    return open_memo_pad(studio=studio, parent=parent, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "memo_pad_dialog.py")


__all__ = ["run", "is_available"]
