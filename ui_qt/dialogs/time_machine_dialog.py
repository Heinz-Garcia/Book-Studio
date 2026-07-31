"""Time Machine — delegiert an den vereinheitlichten Struktur-Snapshot-Dialog (P3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtWidgets import QMessageBox, QWidget

from ui_qt.dialogs.structure_load_dialog import (
    apply_structure_load_result,
    open_structure_load_dialog,
)
from ui_qt.structure_snapshot import format_backup_label, list_structure_backups

__all__ = [
    "format_backup_label",
    "list_structure_backups",
    "open_time_machine_qt",
]


def open_time_machine_qt(
    parent: Optional[QWidget],
    book: Path,
    *,
    on_preview: Callable[[Any], None],
    on_apply: Callable[[], bool],
    on_cancel: Callable[[], None],
    structure_panel=None,
    session=None,
) -> None:
    """Legacy-Einstieg — nutzt denselben Dialog wie „Struktur laden“."""
    del on_apply  # Ersetzt durch persist_immediately + apply_structure_load_result
    if not list_structure_backups(book):
        QMessageBox.information(
            parent,
            "Struktur-Snapshots",
            "Keine Struktur-Backups gefunden.\n\n"
            "Speichere das Buch („Buchstruktur speichern“) oder nutze "
            "„Struktur-Snapshot speichern…“ mit einem sprechenden Namen.",
        )
        return
    result = open_structure_load_dialog(
        parent,
        book,
        on_preview=on_preview,
        on_restore=on_cancel,
        live_preview_default=True,
        show_save_and_apply=True,
    )
    if result is None or session is None or structure_panel is None:
        return
    apply_structure_load_result(session, structure_panel, result)
