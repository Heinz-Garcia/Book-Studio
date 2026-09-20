"""Backup, YAML-Prüfung und Restore für ``_quarto.yml``.

Kein Render — nur Dateisicherung und strukturelle Prüfung vor dem Speichern.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

BACKUP_SUBDIR = Path(".backups") / "quarto_yml"
BACKUP_PREFIX = "quarto_"


def backup_dir_for(yml_path: Path) -> Path:
    """``.backups/quarto_yml`` neben der Buchwurzel (Parent von ``_quarto.yml``)."""
    return Path(yml_path).resolve().parent / BACKUP_SUBDIR


def create_backup(yml_path: Path) -> Optional[Path]:
    """Kopiert die aktuelle Datei nach ``.backups/quarto_yml/quarto_<ts>.yml``.

    Fehlt die Datei oder ist sie leer lesbar, ``None``.
    """
    src = Path(yml_path)
    if not src.is_file():
        return None
    try:
        text = src.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    dest_dir = backup_dir_for(src)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"{BACKUP_PREFIX}{stamp}.yml"
    # Kollision in derselben Sekunde
    n = 1
    while dest.exists():
        dest = dest_dir / f"{BACKUP_PREFIX}{stamp}_{n}.yml"
        n += 1
    dest.write_text(text, encoding="utf-8")
    return dest


def list_backups(yml_path: Path) -> list[Path]:
    """Vorhandene Sicherungen, neueste zuerst."""
    folder = backup_dir_for(yml_path)
    if not folder.is_dir():
        return []
    files = [
        p
        for p in folder.glob(f"{BACKUP_PREFIX}*.yml")
        if p.is_file()
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def latest_backup(yml_path: Path) -> Optional[Path]:
    items = list_backups(yml_path)
    return items[0] if items else None


def restore_backup(yml_path: Path, backup: Path) -> None:
    """Schreibt ``backup`` nach ``yml_path`` (überschreibt)."""
    text = Path(backup).read_text(encoding="utf-8")
    Path(yml_path).write_text(text, encoding="utf-8")


def validate_quarto_yml_text(text: str) -> tuple[bool, str, bool]:
    """Prüft YAML-Text für ``_quarto.yml``.

    Rückgabe: ``(ok_to_save_without_confirm, message, needs_confirm)``.

    - Syntaxfehler / kein Mapping → ``ok=False``, ``needs_confirm=False`` (blockiert).
    - Mapping ok, aber ``project``/``book`` fehlen → ``ok=True``, ``needs_confirm=True``.
    - Alles plausibel → ``ok=True``, ``needs_confirm=False``.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return False, f"YAML-Syntaxfehler:\n{exc}", False

    if data is None:
        return False, "Datei ist leer — kein gültiges Quarto-Projekt.", False
    if not isinstance(data, dict):
        return (
            False,
            f"YAML-Wurzel muss eine Zuordnung sein, nicht {type(data).__name__}.",
            False,
        )

    missing: list[str] = []
    if "project" not in data:
        missing.append("project")
    elif data.get("project") is not None and not isinstance(data.get("project"), dict):
        return False, "Schlüssel „project“ muss eine Zuordnung sein.", False
    if "book" not in data:
        missing.append("book")
    elif data.get("book") is not None and not isinstance(data.get("book"), dict):
        return False, "Schlüssel „book“ muss eine Zuordnung sein.", False

    if missing:
        return (
            True,
            "Warnung: fehlende Schlüssel: "
            + ", ".join(missing)
            + ".\nTrotzdem speichern?",
            True,
        )
    return True, "YAML ok.", False


__all__ = [
    "BACKUP_SUBDIR",
    "backup_dir_for",
    "create_backup",
    "latest_backup",
    "list_backups",
    "restore_backup",
    "validate_quarto_yml_text",
]
