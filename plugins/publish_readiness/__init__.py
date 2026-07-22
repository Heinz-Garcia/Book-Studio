"""Publish Readiness — Plugin-Adapter für tools.publish_readiness."""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> None:
    from tools.publish_readiness.dialog import open_publish_readiness_dialog

    open_publish_readiness_dialog(studio, **kwargs)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "tools", "publish_readiness", "dialog.py")


__all__ = ["run", "is_available"]
