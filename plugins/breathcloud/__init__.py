"""Breathcloud plugin — redirects to Cover-Schlagwortwolke (Freie Form / Hub).

The packer SSOT remains ``tools.breathcloud.engine``; the UI lives in Stylecloud.
"""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> None:
    from ui_qt.dialogs.stylecloud_dialog import open_stylecloud_qt

    parent = kwargs.get("parent") or getattr(studio, "root", None)
    open_stylecloud_qt(studio, parent, force_hub=True)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "ui_qt", "dialogs", "stylecloud_dialog.py")


__all__ = ["run", "is_available"]
