"""BackupService – Time-Machine, Full-Backups, Sanitizer-Backups.

B8: Stub mit dokumentierter Public-API. Logik liegt aktuell in
`book_doctor.BackupManager` und in `book_studio.run_sanitizer_pipeline`.

Phase 2 / Schritt 2.5a: Die *reinen Daten-Pfade* der Sanitizer-Pipeline
sind in diesen Service verlagert. Die Pfad-Berechnung (Basis-Verzeichnis
+ Zeitstempel + End-Pfad) ist deterministisch und damit ohne
Side-Effects testbar.

Phase 2 / Schritt 2.5b: Die *physische Backup-Erstellung*
(`mkdir(parents=True, exist_ok=True)` + `shutil.copytree`) ist in
diesem Service. UI-Concerns (`messagebox`, `self.log`, `self.root.after`)
und Threading bleiben in `BookStudio.run_sanitizer_pipeline`, weil
sie UI-/System-Konzerne sind. Der Service liefert bei Fehlern
statt zu raisen ein `(None, error_message)`-Tuple zurück, damit
das Studio entscheiden kann, ob/wie es `messagebox.showerror` ruft.

Phase 4: Die Subprocess-Logik der Sanitizer-Pipeline ist in
`run_sanitizer_subprocess` extrahiert. Die Methode nimmt einen
`popen_factory` (Default `subprocess.Popen`) und einen
`on_log_line`-Callback; UI-Callbacks (`root.after` + `self.log`)
bleiben im Studio.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Protocol


# Default-Basis-Verzeichnis relativ zum Buch-Verzeichnis, wenn in der
# App-Config kein `sanitizer_backup_path` gesetzt ist.
SANITIZER_BACKUP_DIR_PREFIX = "_Sanitizer_Backups_"

# Zeitstempel-Format fuer Sanitizer-Backup-Ordner (z. B. "030726_1755").
SANITIZER_BACKUP_TIMESTAMP_FMT = "%d%m%y_%H%M"

SANITIZER_BACKUP_DIR_NAME_TEMPLATE = "sanitizer_backup_{timestamp}"

# Default-Python-Executable fuer die Sanitizer-Subprocess-Argv-Liste.
SANITIZER_SUBPROCESS_SCRIPT = "Sanitizer.py"


class BackupLike(Protocol):
    """Schnittstelle, die `BookStudio` fuer `BackupService` anbieten muss."""

    backup_mgr: Any
    current_book: Optional[Path]


class BackupService:
    """Backup-Pfad-Logik + physische Backup-Erstellung.

    Phase 2 / 2.5a: Pfad-Aufloesung (Basis-Pfad, Zeitstempel,
    End-Pfad) ist in *pure* Funktionen extrahiert.
    Phase 2 / 2.5b: Physische Backup-Erstellung (`create_physical_backup`)
    ist hier. UI- und Threading-Concerns bleiben im Studio.
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

    # --- Physische Backup-Erstellung (2.5b) ----------------------------

    @staticmethod
    def create_physical_backup(
        content_dir: Path,
        backup_base_dir: Path,
        backup_dir: Path,
    ) -> tuple[Optional[Path], Optional[str]]:
        """Erstellt das Sanitizer-Backup physisch.

        Reihenfolge:
        1. `backup_base_dir.mkdir(parents=True, exist_ok=True)`
        2. `shutil.copytree(content_dir, backup_dir)`

        Returns: `(backup_dir, None)` bei Erfolg, `(None, error_message)`
        bei `OSError` oder `shutil.Error`. Die Fehlermeldung ist
        stringifiziert (`str(e)`), damit das Studio sie in
        `messagebox.showerror` anzeigen kann.

        Eingaben werden defensiv geprueft:
        - `content_dir` muss existieren und ein Verzeichnis sein.
        - `backup_base_dir` und `backup_dir` werden als Pfade
          akzeptiert (Existenz wird nicht validiert).
        """
        try:
            if not isinstance(content_dir, Path):
                content_dir = Path(content_dir)
            if not content_dir.exists() or not content_dir.is_dir():
                return None, f"content-Verzeichnis fehlt: {content_dir}"
            if not isinstance(backup_base_dir, Path):
                backup_base_dir = Path(backup_base_dir)
            if not isinstance(backup_dir, Path):
                backup_dir = Path(backup_dir)

            backup_base_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(content_dir, backup_dir)
            return backup_dir, None
        except (OSError, shutil.Error) as exc:
            return None, str(exc)

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

    # --- Sanitizer-Subprocess (Phase 4) ---------------------------------

    @staticmethod
    def build_sanitizer_command(
        executable: str, book: Path, script_name: str = SANITIZER_SUBPROCESS_SCRIPT
    ) -> list:
        """Baut die argv-Liste fuer den Sanitizer-Subprocess.

        Aufbau: `[executable, script_name, str(book)]`. Die Funktion
        ist *pur* (kein Subprocess-Aufruf, kein I/O).
        """
        return [str(executable), str(script_name), str(book)]

    @staticmethod
    def run_sanitizer_subprocess(
        book: Path,
        on_log_line: Callable[[str], None],
        cwd: Optional[Path] = None,
        executable: Optional[str] = None,
        script_name: str = SANITIZER_SUBPROCESS_SCRIPT,
        popen_factory: Optional[Callable[..., Any]] = None,
    ) -> int:
        """Startet den Sanitizer-Subprocess und streamt stdout.

        Verhalten (1:1 wie der Inline-Block in
        `BookStudio.run_sanitizer_pipeline`):

        1. Baue argv via `build_sanitizer_command`.
        2. Starte den Subprocess ueber `popen_factory` (Default
           `subprocess.Popen`) mit `cwd=base_path` (falls angegeben).
        3. Iteriere zeilenweise ueber `proc.stdout`. Nicht-leere
           Zeilen gehen an `on_log_line(line)`.
        4. `proc.wait()`. Rueckgabe: `proc.returncode`.

        Die Methode ist **nicht** Tk-frei; `on_log_line` ist
        typischerweise ein UI-Callback. Die Subprocess-Erzeugung
        ist ueber `popen_factory` injiziert (testbar).

        Rueckgabe: `returncode` (int).
        """
        if executable is None:
            executable = sys.executable
        if popen_factory is None:
            popen_factory = subprocess.Popen

        cmd = BackupService.build_sanitizer_command(
            executable=executable, book=book, script_name=script_name
        )
        proc_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
        }
        if cwd is not None:
            proc_kwargs["cwd"] = str(cwd)
        proc = popen_factory(cmd, **proc_kwargs)
        stdout = getattr(proc, "stdout", None)
        if stdout is not None:
            for raw_line in stdout:
                stripped = raw_line.rstrip() if isinstance(raw_line, str) else raw_line
                if stripped:
                    on_log_line(stripped)
        if hasattr(proc, "wait"):
            proc.wait()
        return getattr(proc, "returncode", 0)


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
    "SANITIZER_SUBPROCESS_SCRIPT",
    "default_sanitizer_backup_dir",
]
