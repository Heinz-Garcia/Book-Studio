"""PySide6-UI-Paket für Book Studio (Migrationspfad).

Aktivierung: Umgebungsvariable ``BOOK_STUDIO_UI=qt`` oder CLI ``--ui qt``.
Tk bleibt der Default, bis die Migration abgeschlossen ist.
"""

from __future__ import annotations

from ui_qt.toolkit import resolve_ui_toolkit, wants_qt_ui

__all__ = ["resolve_ui_toolkit", "run_qt_app", "wants_qt_ui"]


def run_qt_app(*, import_path=None) -> int:
    """Lazy-Import: PySide6 wird erst beim Qt-Start geladen."""
    from ui_qt.app import run_qt_app as _run

    return _run(import_path=import_path)
