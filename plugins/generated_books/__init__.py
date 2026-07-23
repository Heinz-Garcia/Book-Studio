"""Generated Books — Plugin-Adapter (Qt)."""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> None:
    from ui_qt.dialogs.generated_books_dialog import open_generated_books_qt

    parent = kwargs.get("parent") or getattr(studio, "root", None)
    open_generated_books_qt(studio, parent)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "generated_books_dialog.py")


__all__ = ["run", "is_available"]
