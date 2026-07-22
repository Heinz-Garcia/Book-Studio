"""Discovery fertiger Render-PDFs unter export/_book*."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from tools.publish_map.schema import RENDER_ARCHIVE_DIR as RENDER_ARCHIVE_DIR_NAME


@dataclass(frozen=True)
class GeneratedPdf:
    path: Path
    book_name: str
    book_path: Path
    mtime: float

    @property
    def display_name(self) -> str:
        return f"{self.path.name} · {self.book_name}"

    @property
    def date_str(self) -> str:
        return datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M")

    @property
    def label(self) -> str:
        return f"{self.display_name}  ·  {self.date_str}"


def sort_generated_pdfs(
    entries: list[GeneratedPdf],
    column: str,
    *,
    reverse: bool = False,
) -> list[GeneratedPdf]:
    """Sortiert PDF-Einträge nach Spalte ``name`` oder ``date``."""
    if column == "name":
        key = lambda item: item.display_name.casefold()
    else:
        key = lambda item: item.mtime
    return sorted(entries, key=key, reverse=reverse)


def delete_generated_pdf(path: Path) -> None:
    """Löscht eine generierte PDF-Datei von der Platte."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {target}")
    if target.suffix.lower() != ".pdf":
        raise ValueError(f"Nur PDF-Dateien dürfen gelöscht werden: {target}")
    target.unlink()


def load_settings(config_path: Optional[Path] = None) -> dict:
    """Liest tools/generated_books/config.toml (Defaults bei Fehlern)."""
    defaults = {"max_entries": 15, "recent_only": True}
    path = config_path or (Path(__file__).resolve().parent / "config.toml")
    if not path.is_file():
        return defaults
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return defaults
    display = data.get("display") if isinstance(data.get("display"), dict) else {}
    scan = data.get("scan") if isinstance(data.get("scan"), dict) else {}
    max_entries = display.get("max_entries", defaults["max_entries"])
    try:
        max_entries = int(max_entries)
    except (TypeError, ValueError):
        max_entries = defaults["max_entries"]
    recent_only = scan.get("recent_only", defaults["recent_only"])
    if not isinstance(recent_only, bool):
        recent_only = bool(recent_only)
    return {"max_entries": max(1, max_entries), "recent_only": recent_only}


def _iter_export_pdfs(book_path: Path) -> Iterable[Path]:
    export_root = book_path / "export"
    if not export_root.is_dir():
        return
    for child in export_root.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if name == "_book" or name.startswith("_book_"):
            yield from child.rglob("*.pdf")
        elif name == RENDER_ARCHIVE_DIR_NAME:
            # Dauerhafte, pro-Publish-Input archivierte Renders (siehe
            # tools.publish_map.store.snapshot_render_dir) — Fallback-
            # Discovery, falls publish_map.json verloren geht/verändert wird.
            yield from child.rglob("*.pdf")


def find_generated_pdfs(
    book_paths: Iterable[Path],
    *,
    max_entries: int = 15,
) -> list[GeneratedPdf]:
    """Sammelt PDFs aus export/_book* der gegebenen Bücher, neueste zuerst."""
    found: list[GeneratedPdf] = []
    seen: set[Path] = set()
    for book in book_paths:
        try:
            book_path = Path(book).resolve()
        except OSError:
            book_path = Path(book)
        for pdf in _iter_export_pdfs(book_path):
            try:
                resolved = pdf.resolve()
            except OSError:
                resolved = pdf
            if resolved in seen:
                continue
            if not pdf.is_file():
                continue
            seen.add(resolved)
            try:
                mtime = pdf.stat().st_mtime
            except OSError:
                continue
            found.append(
                GeneratedPdf(
                    path=pdf,
                    book_name=book_path.name,
                    book_path=book_path,
                    mtime=mtime,
                )
            )
    found.sort(key=lambda item: item.mtime, reverse=True)
    return found[: max(1, int(max_entries))]


def collect_book_paths_from_studio(studio, *, recent_only: bool = True) -> list[Path]:
    """Aktives Buch + recent_books (falls vorhanden), dedupliziert.

    Bei ``recent_only=False`` werden zusätzlich alle geladenen ``studio.books``
    einbezogen (gedeckelt).
    """
    paths: list[Path] = []
    seen: set[Path] = set()

    def _add(candidate) -> None:
        if candidate is None:
            return
        try:
            path = Path(candidate).resolve()
        except OSError:
            path = Path(candidate)
        if path in seen:
            return
        if not (path / "_quarto.yml").is_file():
            return
        seen.add(path)
        paths.append(path)

    current = getattr(studio, "current_book", None)
    _add(current)

    session = getattr(studio, "session_manager", None)
    if session is not None and hasattr(session, "get_recent_books"):
        for entry in session.get_recent_books() or []:
            path = entry.get("path") if isinstance(entry, dict) else None
            _add(path)
    elif hasattr(studio, "get_recent_books"):
        for entry in studio.get_recent_books() or []:
            path = entry.get("path") if isinstance(entry, dict) else None
            _add(path)

    if not recent_only:
        for book in getattr(studio, "books", None) or []:
            _add(book)
            if len(paths) >= 50:
                break
    elif len(paths) <= 1:
        # Fallback: wenn noch keine Recent-Liste existiert, trotzdem
        # geladene Bücher anbieten.
        for book in getattr(studio, "books", None) or []:
            _add(book)
            if len(paths) >= 30:
                break
    return paths


__all__ = [
    "GeneratedPdf",
    "collect_book_paths_from_studio",
    "delete_generated_pdf",
    "find_generated_pdfs",
    "load_settings",
    "sort_generated_pdfs",
]
