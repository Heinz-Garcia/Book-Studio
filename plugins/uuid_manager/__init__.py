"""UUID-Manager Plugin-Adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def _maybe_grammargraph_repo() -> Path | None:
    candidate = _REPO_ROOT.parent / "GrammarGraph"
    if candidate.is_dir():
        return candidate.resolve()
    return None


def run(studio: Optional[Any] = None, **kwargs) -> None:
    from tools.uuid_manager.dialog import run_dialog

    parent = kwargs.get("parent") or getattr(studio, "root", None)
    run_dialog(
        parent=parent,
        studio=studio,
        book_studio_repo=_REPO_ROOT,
        grammargraph_repo=_maybe_grammargraph_repo(),
        window_title="UUID-Manager",
    )


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "tools", "uuid_manager", "dialog.py")


__all__ = ["run", "is_available"]
