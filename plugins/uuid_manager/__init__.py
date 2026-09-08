"""UUID-Manager Plugin-Adapter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def _maybe_grammargraph_repo() -> Path | None:
    """GrammarGraph-Repo finden (Sibling, Env, Inbox-Pfad aus app_config)."""
    env = (os.environ.get("GRAMMARGRAPH_ROOT") or "").strip()
    if env:
        candidate = Path(env)
        if candidate.is_dir():
            return candidate.resolve()

    sibling = _REPO_ROOT.parent / "GrammarGraph"
    if sibling.is_dir():
        return sibling.resolve()

    try:
        from app_config import load_validated_config

        cfg = load_validated_config(_REPO_ROOT / "app_config.json")
        inbox = str(cfg.get("grammargraph_inbox_path") or "").strip()
        if inbox:
            inbox_path = Path(inbox)
            # Inbox oft …/GrammarGraph/Publish → zwei Ebenen hoch zum Repo
            for parent in (inbox_path, *inbox_path.parents):
                if (parent / "run.py").is_file() or (parent / "src").is_dir():
                    return parent.resolve()
    except (OSError, TypeError, ValueError, ImportError):
        pass
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
