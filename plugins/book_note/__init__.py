"""Buchnotizen — Plugin-Adapter (Qt).

Duenner Adapter nach dem Muster von ``plugins/memo_pad``: Die Ablage liegt in
``tools/book_note/`` (GUI-frei), das Fenster in
``ui_qt/dialogs/book_note_dialog.py`` (nur Widgets). Kein Kernmodul wird
angefasst -- die Auto-Discovery in ``services/plugin_loader.py`` haengt den
Eintrag additiv ins Menue.

Nicht zu verwechseln mit ``plugins/memo_pad``: Der Memo-Block ist bewusst
projektlos, diese Notiz gehoert zu genau einem Buch.
"""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    from ui_qt.dialogs.book_note_dialog import open_book_note_qt

    parent = kwargs.get("parent") or getattr(studio, "root", None)
    return open_book_note_qt(studio=studio, parent=parent, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "book_note_dialog.py")


__all__ = ["run", "is_available"]
