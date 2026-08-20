"""Breathcloud plugin — opens the autonomous organic word-cloud dialog."""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> None:
    from tools.breathcloud.dialog import open_breathcloud_dialog

    parent = kwargs.get("parent") or getattr(studio, "root", None)
    open_breathcloud_dialog(studio, parent)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "tools", "breathcloud", "dialog.py")


__all__ = ["run", "is_available"]
