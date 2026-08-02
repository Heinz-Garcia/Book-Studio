"""Datei-Aktionen für den Mapping Manager."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from tools.generated_books.discovery import delete_generated_pdf
from render_artifact_store import (
    ARCHIVE_TIMESTAMP_FMT,
    archive_render_source,
    restore_source_archive,
)


def open_path(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def reveal_in_explorer(path: Path) -> None:
    target = path if path.is_dir() else path.parent
    if sys.platform.startswith("win"):
        if path.is_file():
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        else:
            os.startfile(str(target))  # noqa: S606
    else:
        open_path(target)


def delete_pdf(path: Path) -> None:
    delete_generated_pdf(path)


def delete_source_archive(path: Path) -> None:
    """Löscht einen archivierten Quellstand (siehe `archive_render_source`)
    unwiderruflich von der Platte. Danach ist der exakte Quellstand der
    zugehörigen PDF nicht mehr reproduzierbar -- Aufrufer (UI) muss VORHER
    explizit bestätigen lassen, siehe `mapping_manager_dialog._delete_selected`."""
    target = Path(path)
    if not target.is_dir():
        raise FileNotFoundError(f"Archivierter Quellstand nicht gefunden: {target}")
    shutil.rmtree(target)


def rename_pdf(path: Path, new_name: str) -> Path:
    """Benennt eine PDF-Datei im selben Ordner um. Gibt den neuen Pfad
    zurück. Lehnt Pfadtrennzeichen (Verzeichniswechsel), leere Namen,
    Nicht-PDF-Ziele und ein bereits existierendes Ziel ab."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")

    candidate = (new_name or "").strip()
    if not candidate:
        raise ValueError("Neuer Dateiname darf nicht leer sein.")
    if "/" in candidate or "\\" in candidate or candidate in (".", ".."):
        raise ValueError(f"Ungültiger Dateiname (kein Verzeichniswechsel erlaubt): {candidate!r}")
    if not candidate.lower().endswith(".pdf"):
        candidate += ".pdf"

    dest = path.parent / candidate
    if dest == path:
        return path
    if dest.exists():
        raise ValueError(f"Datei existiert bereits: {dest.name}")

    path.rename(dest)
    return dest


def restore_source(source_archive_dir: Path, book_path: Path) -> tuple[Path, list[str]]:
    """Stellt einen archivierten Quellstand (siehe `archive_render_source`)
    im lebenden Buchprojekt wieder her -- überschreibt dort jeden Eintrag,
    der im Archiv vorkommt.

    Sichert VORHER den aktuellen Stand von `book_path` selbst mit derselben
    Archivierungslogik wie beim Render nach
    `book_path/export/pre_restore_backups/source_<timestamp>/`, damit auch
    das Wiederherstellen selbst rückgängig gemacht werden kann -- ein
    Restore darf nie unwiderruflich sein.

    Gibt `(backup_dir, restored_entry_names)` zurück.
    """
    book_path = Path(book_path)
    backup_root = book_path / "export" / "pre_restore_backups"
    stamp = datetime.now().strftime(ARCHIVE_TIMESTAMP_FMT)
    backup_dir = archive_render_source(book_path, backup_root, timestamp=stamp)
    if backup_dir is None:
        raise OSError(f"Sicherheits-Backup vor Restore fehlgeschlagen: {book_path}")
    restored = restore_source_archive(source_archive_dir, book_path)
    return backup_dir, restored
