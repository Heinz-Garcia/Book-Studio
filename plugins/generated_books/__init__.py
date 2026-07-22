"""Generierte Bücher — dünner Plugin-Adapter für tools.generated_books."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional


def _ensure_repo_on_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run(studio: Optional[Any] = None, **kwargs) -> int:
    """Menü-Entrypoint: öffnet den PDF-Browser-Dialog."""
    _ensure_repo_on_path()
    from tools.generated_books.dialog import run_dialog

    return run_dialog(studio)


def is_available() -> bool:
    root = Path(__file__).resolve().parents[2]
    return (root / "tools" / "generated_books" / "dialog.py").is_file()


__all__ = ["run", "is_available"]
