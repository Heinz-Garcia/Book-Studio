"""Qt-Time-Machine: Struktur-Snapshots previewen und wiederherstellen."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def list_structure_backups(book: Path) -> list[Path]:
    backup_dir = Path(book) / ".backups"
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob("struct_*.json"), reverse=True)


def format_backup_label(path: Path) -> str:
    try:
        raw_time = path.stem.replace("struct_", "")
        dt = datetime.strptime(raw_time, "%Y%m%d_%H%M%S")
        nice = dt.strftime("%d.%m.%Y - %H:%M:%S Uhr")
        return f"{nice} ({path.name})"
    except ValueError:
        return path.name


class TimeMachineDialog(QDialog):
    """Live-Preview von Struktur-Backups (Parität zu BackupManager.show_restore_manager)."""

    def __init__(
        self,
        parent: Optional[QWidget],
        backups: list[Path],
        *,
        on_preview: Callable[[Any], None],
        on_apply: Callable[[], bool],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("⏪ Time Machine: Live-Preview")
        self.resize(560, 430)
        self.setModal(True)
        self._backups = backups
        self._on_preview = on_preview
        self._on_apply = on_apply
        self._on_cancel = on_cancel
        self._accepted = False

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Klicke auf ein Backup, um es im Hintergrund live anzusehen:")
        )
        self._list = QListWidget()
        for path in backups:
            self._list.addItem(format_backup_label(path))
        self._list.currentRowChanged.connect(self._preview_row)
        layout.addWidget(self._list, stretch=1)

        buttons = QHBoxLayout()
        apply_btn = QPushButton("✅ DIESE STRUKTUR ÜBERNEHMEN")
        apply_btn.clicked.connect(self._apply)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self._cancel)
        buttons.addWidget(apply_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def _preview_row(self, row: int) -> None:
        if row < 0 or row >= len(self._backups):
            return
        target = self._backups[row]
        try:
            tree_data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Time Machine", f"Backup konnte nicht gelesen werden:\n{exc}")
            return
        self._on_preview(tree_data)

    def _apply(self) -> None:
        success = bool(self._on_apply())
        if success:
            QMessageBox.information(self, "Erfolg", "Struktur wurde dauerhaft wiederhergestellt!")
            self._accepted = True
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Nicht gespeichert",
                "Die Struktur wurde NICHT dauerhaft übernommen.\n\n"
                "Das Speichern ist fehlgeschlagen oder wurde abgebrochen. Bitte prüfe das Log.",
            )

    def _cancel(self) -> None:
        self.reject()

    def reject(self) -> None:
        if not self._accepted:
            self._on_cancel()
            self._accepted = True  # verhindert doppeltes Restore bei closeEvent
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._accepted:
            self._on_cancel()
            self._accepted = True
        event.accept()


def open_time_machine_qt(
    parent: Optional[QWidget],
    book: Path,
    *,
    on_preview: Callable[[Any], None],
    on_apply: Callable[[], bool],
    on_cancel: Callable[[], None],
) -> None:
    backups = list_structure_backups(book)
    if not backups:
        QMessageBox.information(
            parent,
            "Time Machine",
            "Keine Struktur-Backups gefunden.\n\n"
            "Speichere das Buch einmal, um den ersten Snapshot anzulegen!",
        )
        return
    TimeMachineDialog(
        parent,
        backups,
        on_preview=on_preview,
        on_apply=on_apply,
        on_cancel=on_cancel,
    ).exec()
