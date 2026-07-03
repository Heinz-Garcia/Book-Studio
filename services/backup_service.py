"""BackupService – Time-Machine, Full-Backups, Sanitizer-Backups.

B8: Stub mit dokumentierter Public-API. Logik liegt aktuell in
`book_doctor.BackupManager` und in `book_studio.run_sanitizer_pipeline`.

Phase 2 / Schritt 2.5a: Die *reinen Daten-Pfade* der Sanitizer-Pipeline
sind in diesen Service verlagert. Die Pfad-Berechnung (Basis-Verzeichnis
+ Zeitstempel + End-Pfad) ist deterministisch und damit ohne
Side-Effects testbar.

Phase 2 / Schritt 2.5b: Schreiben (`shutil.copytree`), UI-Calls
(`messagebox.askyesno/showerror`, `self.log`, `self.root.after`) und
Threading bleiben in `book_studio.run_sanitizer_pipeline` und werden
in einer eigenen Session in `BackupService` verlagert.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Protocol


# Default-Basis-Verzeichnis relativ zum Buch-Verzeichnis, wenn in der
# App-Config kein `sanitizer_backup_path` gesetzt ist.
SANITIZER_BACKUP_DIR_PREFIX = "_Sanitizer_Backups_"

# Zeitstempel-Format fuer Sanitizer-Backup-Ordner (z. B. "030726_1755").
SANITIZER_BACKUP_TIMESTAMP_FMT = "%d%m%y_%H%M"

SANITIZER_BACKUP_DIR_NAME_TEMPLATE = "sanitizer_backup_{timestamp}"


class BackupLike(Protocol):
    """Schnittstelle, die `BookStudio` fuer `BackupService` anbieten muss."""

    backup_mgr: Any
    current_book: Optional[Path]


class BackupService:
    """Backup-Pfad-Logik + Wrapper fuer `BackupManager`-Delegation.

    Phase 2 / 2.5a: Pfad-Aufloesung (Basis-Pfad, Zeitstempel,
    End-Pfad) ist in *pure* Funktionen extrahiert. Der Schreib- und
    Threading-Teil bleibt in 2.5b.
    """

    def __init__(self, studio: BackupLike):
        self._studio = studio

    # --- Wrapper fuer BackupManager (unveraendert) ----------------------

    def create_structure_backup(self, tree_data: list[dict]) -> str:
        if not self._studio.backup_mgr:
            return ""
        return self._studio.backup_mgr.create_structure_backup(tree_data)

    def get_sanitizer_backup_dir(self) -> Optional[Path]:
        """Liefert das Default-Sanitizer-Backup-Basis-Verzeichnis
        (relativ zum Buch-Parent). `None`, wenn kein Buch aktiv ist.
        """
        if not self._studio.current_book:
            return None
        return BackupService.default_sanitizer_backup_dir_for(
            self._studio.current_book
        )

    # --- Pfad-Aufloesung: pure Funktionen -----------------------------

    @staticmethod
    def resolve_backup_base_dir(
        current_book: Optional[Path], custom_path: Optional[str]
    ) -> Optional[Path]:
        """Berechnet das Basis-Verzeichnis fuer den Sanitizer-Backup.

        Logik:
        - `None`, wenn kein `current_book` aktiv ist.
        - Wenn `custom_path` ein nicht-leerer String ist, wird er als
          Basis-Verzeichnis verwendet (egal ob relativ oder absolut).
        - Sonst Default: `<current_book.parent> / "_Sanitizer_Backups_<name>"`.

        Die Funktion ist *pur* und hat keine Studio-Abhaengigkeit.
        Sie validiert nicht, ob das Verzeichnis existiert oder schreibbar
        ist — das ist Aufgabe der Schreib-Pipeline in 2.5b.
        """
        if current_book is None:
            return None
        if isinstance(custom_path, str) and custom_path.strip():
            return Path(custom_path.strip())
        return BackupService.default_sanitizer_backup_dir_for(current_book)

    @staticmethod
    def default_sanitizer_backup_dir_for(current_book: Path) -> Path:
        """Default-Basis-Verzeichnis relativ zum Buch-Parent.

        `current_book.parent / f"_Sanitizer_Backups_{current_book.name}"`
        """
        return current_book.parent / f"{SANITIZER_BACKUP_DIR_PREFIX}{current_book.name}"

    @staticmethod
    def compute_backup_timestamp(now: Optional[datetime] = None) -> str:
        """Liefert den Zeitstempel im Format `DDMMYY_HHMM`.

        `now` ist nur fuer Tests injizierbar; in Produktion ruft die
        Funktion `datetime.now()` auf.
        """
        moment = now if now is not None else datetime.now()
        return moment.strftime(SANITIZER_BACKUP_TIMESTAMP_FMT)

    @staticmethod
    def build_backup_path(base_dir: Path, timestamp: str) -> Path:
        """Baut den End-Pfad des Backups: `base_dir/sanitizer_backup_<timestamp>`.

        `timestamp` wird nicht validiert; Aufrufer sind fuer ein
        sinnvolles Format verantwortlich (siehe `compute_backup_timestamp`).
        """
        return base_dir / SANITIZER_BACKUP_DIR_NAME_TEMPLATE.format(timestamp=timestamp)


# Bequemer Zugriff fuer `BookStudio` ohne expliziten Service-Holder.
def default_sanitizer_backup_dir(current_book: Optional[Path]) -> Optional[Path]:
    """Modul-Level-Helper: liefert das Default-Backup-Basis-Verzeichnis.

    Wird von `BookStudio` ueber `self._services.backup.default_sanitizer_backup_dir`
    oder direkt aufgerufen, wenn nur der Pfad ohne Service-Kontext
    benoetigt wird.
    """
    if current_book is None:
        return None
    return BackupService.default_sanitizer_backup_dir_for(current_book)


__all__ = [
    "BackupLike",
    "BackupService",
    "SANITIZER_BACKUP_DIR_PREFIX",
    "SANITIZER_BACKUP_DIR_NAME_TEMPLATE",
    "SANITIZER_BACKUP_TIMESTAMP_FMT",
    "default_sanitizer_backup_dir",
]
