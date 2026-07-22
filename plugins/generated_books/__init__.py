"""Generierte Bücher — Plugin-Adapter für tools.generated_books."""

from __future__ import annotations

from typing import Any, Optional

from services.plugin_runtime import ensure_repo_on_path, tool_exists

_REPO_ROOT = ensure_repo_on_path(__file__)


def run(studio: Optional[Any] = None, **kwargs) -> int:
    """Menü-Entrypoint: öffnet den PDF-Browser-Dialog."""
    from tools.generated_books.dialog import run_dialog

    return run_dialog(studio)


def is_available() -> bool:
    return tool_exists(_REPO_ROOT, "tools", "generated_books", "dialog.py")


__all__ = ["run", "is_available"]
