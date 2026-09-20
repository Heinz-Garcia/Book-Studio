"""Rahmen/Pflichtseiten — Status und Frontmatter-Prüfung (ohne UI).

Analog zu ``quarto_yml_guard``: Kontrolle und sicheres Speichern der
required-Markdown-Seiten im Buch, kein Render.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import frontmatter_parser
from page_required import is_page_required, list_required_page_paths

BACKUP_SUBDIR = Path(".backups") / "rahmen"
BACKUP_PREFIX = "rahmen_"


class RahmenPageKind(str, Enum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True)
class RahmenPageStatus:
    rel_path: str
    title: str
    kind: RahmenPageKind
    detail: str
    exists: bool


def backup_dir_for(book_path: Path) -> Path:
    return Path(book_path).resolve() / BACKUP_SUBDIR


def create_backup(md_path: Path, *, book_path: Path) -> Optional[Path]:
    """Sichert ``md_path`` unter ``.backups/rahmen/<stem>_<ts>.md``."""
    src = Path(md_path)
    if not src.is_file():
        return None
    try:
        text = src.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    dest_dir = backup_dir_for(book_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = src.stem.replace(" ", "_")[:40] or "page"
    dest = dest_dir / f"{BACKUP_PREFIX}{stem}_{stamp}.md"
    n = 1
    while dest.exists():
        dest = dest_dir / f"{BACKUP_PREFIX}{stem}_{stamp}_{n}.md"
        n += 1
    dest.write_text(text, encoding="utf-8")
    return dest


def list_backups(book_path: Path, *, stem_hint: Optional[str] = None) -> list[Path]:
    folder = backup_dir_for(book_path)
    if not folder.is_dir():
        return []
    files = [p for p in folder.glob(f"{BACKUP_PREFIX}*.md") if p.is_file()]
    if stem_hint:
        hint = stem_hint.replace(" ", "_")[:40]
        filtered = [p for p in files if hint in p.name]
        if filtered:
            files = filtered
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def latest_backup(book_path: Path, *, stem_hint: Optional[str] = None) -> Optional[Path]:
    items = list_backups(book_path, stem_hint=stem_hint)
    return items[0] if items else None


def restore_backup(md_path: Path, backup: Path) -> None:
    text = Path(backup).read_text(encoding="utf-8")
    Path(md_path).write_text(text, encoding="utf-8")


def validate_rahmen_page_text(
    text: str,
    *,
    rel_path: str,
) -> tuple[bool, str, bool]:
    """Prüft Markdown-Text einer Rahmenseite.

    Rückgabe: ``(ok_to_save_without_confirm, message, needs_confirm)``.

    - Frontmatter-Syntaxfehler / kein Frontmatter → blockiert.
    - Parsing ok, aber ``title`` fehlt oder ``required`` nicht gesetzt
      (und kein Legacy-Pfad) → Speichern mit Bestätigung.
    - Sonst ok.
    """
    parts = frontmatter_parser.parse(text)
    if not parts.has_frontmatter:
        return (
            False,
            "Kein YAML-Frontmatter (--- … ---). Rahmenseiten brauchen Metadaten.",
            False,
        )
    data = parts.parsed()
    err = parts.parse_error
    if err:
        return False, f"Frontmatter-Fehler:\n{err}", False
    if not isinstance(data, dict):
        return (
            False,
            f"Frontmatter muss eine Zuordnung sein, nicht {type(data).__name__}.",
            False,
        )

    warnings: list[str] = []
    title = data.get("title")
    if title is None or str(title).strip() == "":
        warnings.append("title fehlt")

    if not is_page_required(rel_path=rel_path, frontmatter=data):
        warnings.append(
            "required ist nicht true (und kein Legacy-Pfad content/required/)"
        )

    if warnings:
        return (
            True,
            "Warnung: "
            + "; ".join(warnings)
            + ".\nTrotzdem speichern?",
            True,
        )
    return True, "Frontmatter ok.", False


def assess_rahmen_page(book_path: Path, rel_path: str) -> RahmenPageStatus:
    """Status einer einzelnen Pflichtseite (Datei muss existieren oder fehlt)."""
    book = Path(book_path)
    rel = str(rel_path).replace("\\", "/")
    full = book / rel
    if not full.is_file():
        return RahmenPageStatus(
            rel_path=rel,
            title="",
            kind=RahmenPageKind.ERROR,
            detail="Datei fehlt",
            exists=False,
        )
    try:
        text = full.read_text(encoding="utf-8")
    except OSError as exc:
        return RahmenPageStatus(
            rel_path=rel,
            title="",
            kind=RahmenPageKind.ERROR,
            detail=f"Nicht lesbar: {exc}",
            exists=True,
        )

    ok, message, needs_confirm = validate_rahmen_page_text(text, rel_path=rel)
    title = ""
    parts = frontmatter_parser.parse(text)
    if parts.has_frontmatter:
        try:
            data = parts.parsed()
            if isinstance(data, dict) and data.get("title") is not None:
                title = str(data.get("title")).strip()
        except Exception:  # noqa: BLE001
            title = ""

    if not ok:
        return RahmenPageStatus(
            rel_path=rel,
            title=title,
            kind=RahmenPageKind.ERROR,
            detail=message.split("\n")[0],
            exists=True,
        )
    if needs_confirm:
        return RahmenPageStatus(
            rel_path=rel,
            title=title,
            kind=RahmenPageKind.WARN,
            detail=message.split("\n")[0].removeprefix("Warnung: ").rstrip("."),
            exists=True,
        )
    return RahmenPageStatus(
        rel_path=rel,
        title=title or Path(rel).stem,
        kind=RahmenPageKind.OK,
        detail="ok",
        exists=True,
    )


def assess_rahmen_pages(book_path: Path) -> list[RahmenPageStatus]:
    """Alle bekannten Pflichtseiten des Buchs inkl. Status."""
    book = Path(book_path)
    return [assess_rahmen_page(book, rel) for rel in list_required_page_paths(book)]


__all__ = [
    "BACKUP_SUBDIR",
    "RahmenPageKind",
    "RahmenPageStatus",
    "assess_rahmen_page",
    "assess_rahmen_pages",
    "backup_dir_for",
    "create_backup",
    "latest_backup",
    "list_backups",
    "restore_backup",
    "validate_rahmen_page_text",
]
