"""Skeleton-Editor — Plugin-Adapter für tools.skeleton.editor."""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    from tools.skeleton.editor import run as editor_run

    return editor_run(studio=studio, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "tools", "skeleton", "editor.py")


__all__ = ["run", "is_available"]
