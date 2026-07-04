"""Skeleton-Editor — dünner Plugin-Adapter für tools.skeleton.editor."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional


def _ensure_repo_on_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run(studio: Optional[Any] = None, **kwargs) -> int:
    _ensure_repo_on_path()
    from tools.skeleton.editor import run as editor_run

    return editor_run(studio=studio, **kwargs)


def is_available() -> bool:
    root = Path(__file__).resolve().parents[1]
    return (root / "tools" / "skeleton" / "editor.py").is_file()


__all__ = ["run", "is_available"]
