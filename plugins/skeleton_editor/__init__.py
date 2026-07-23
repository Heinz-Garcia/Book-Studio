"""Skeleton-Editor — Plugin-Adapter (Qt)."""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    from ui_qt.dialogs.skeleton_editor_dialog import open_skeleton_editor_qt

    parent = kwargs.get("parent") or getattr(studio, "root", None)
    return open_skeleton_editor_qt(studio=studio, parent=parent, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "skeleton_editor_dialog.py")


__all__ = ["run", "is_available"]
