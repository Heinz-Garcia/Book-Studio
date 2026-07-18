"""Skeleton-Populate — dünner Plugin-Adapter für tools.skeleton."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Optional

_logger = logging.getLogger(__name__)


def _ensure_repo_on_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run(studio: Optional[Any] = None, **kwargs) -> int:
    """Menü-Entrypoint: delegiert an tools.skeleton.populate.run."""
    _ensure_repo_on_path()
    from tools.skeleton.populate import run as populate_run

    return populate_run(studio=studio, **kwargs)


def is_available() -> bool:
    root = Path(__file__).resolve().parents[2]
    return (root / "tools" / "skeleton" / "populate.py").is_file()


__all__ = ["run", "is_available"]
