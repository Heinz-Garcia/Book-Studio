"""PySide6-UI-Paket für Book Studio.

Einstieg: ``python book_studio.py`` (nur Qt). Legacy-Tk-UI wurde in Phase 6 entfernt.
"""

from __future__ import annotations

from ui_qt.toolkit import is_tk_requested, resolve_ui_toolkit, wants_qt_ui

__all__ = ["is_tk_requested", "resolve_ui_toolkit", "run_qt_app", "wants_qt_ui"]


def run_qt_app(*, import_path=None) -> int:
    """Lazy-Import: PySide6 wird erst beim Qt-Start geladen."""
    from ui_qt.app import run_qt_app as _run

    return _run(import_path=import_path)
