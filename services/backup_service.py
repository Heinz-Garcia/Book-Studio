"""BackupService – Time-Machine, Full-Backups, Sanitizer-Backups.

B8: Stub mit dokumentierter Public-API. Logik liegt aktuell in
`book_doctor.BackupManager` und in `book_studio.run_sanitizer_pipeline`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol


class BackupLike(Protocol):
    backup_mgr: Any
    current_book: Optional[Path]


class BackupService:
    def __init__(self, studio: BackupLike):
        self._studio = studio

    def create_structure_backup(self, tree_data: list[dict]) -> str:
        if not self._studio.backup_mgr:
            return ""
        return self._studio.backup_mgr.create_structure_backup(tree_data)

    def get_sanitizer_backup_dir(self) -> Optional[Path]:
        if not self._studio.current_book:
            return None
        return self._studio.current_book.parent / f"_Sanitizer_Backups_{self._studio.current_book.name}"
