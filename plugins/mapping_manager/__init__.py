"""Mapping Manager — Plugin-Adapter."""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> None:
    from tools.mapping_manager.dialog import open_mapping_manager_dialog

    open_mapping_manager_dialog(studio, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "tools", "mapping_manager", "dialog.py")


__all__ = ["run", "is_available"]
