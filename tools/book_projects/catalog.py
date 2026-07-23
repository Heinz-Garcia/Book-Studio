"""Content-Roots und Buchliste (app_config + WorkspaceService)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import app_config as _app_config
from services.workspace_service import WorkspaceService, normalize_content_root_paths

from tools.book_projects.scaffold import create_empty_book as _create_empty_book
from tools.book_projects.scaffold import is_quarto_book, sanitize_book_folder_name


@dataclass(frozen=True)
class BookInfo:
    path: Path
    name: str
    root: Path


def _repo_root(base: Path | None = None) -> Path:
    return Path(base) if base is not None else Path(__file__).resolve().parents[2]


def _config_path(repo: Path) -> Path:
    return Path(repo) / "app_config.json"


def read_content_root_config(repo: Path | None = None) -> list[str]:
    """Rohe content_root_path-Einträge aus app_config.json."""
    root = _repo_root(repo)
    try:
        cfg = _app_config.read_config(_config_path(root))
    except (OSError, TypeError, ValueError):
        return ["."]
    return normalize_content_root_paths(cfg.get("content_root_path", ".")) or ["."]


def write_content_root_config(entries: list[str], *, repo: Path | None = None) -> None:
    """Schreibt content_root_path (Liste) in app_config.json."""
    root = _repo_root(repo)
    path = _config_path(root)
    cfg = _app_config.read_config(path)
    cleaned = [e.strip() for e in entries if isinstance(e, str) and e.strip()]
    if not cleaned:
        cleaned = ["."]
    cfg["content_root_path"] = cleaned if len(cleaned) > 1 else cleaned[0]
    _app_config.write_config(path, cfg)


def list_content_roots(repo: Path | None = None) -> list[Path]:
    """Aufgelöste, existierende Content-Roots (wie WorkspaceService)."""
    root = _repo_root(repo)

    def _read() -> dict[str, Any]:
        try:
            return _app_config.read_config(_config_path(root))
        except (OSError, TypeError, ValueError):
            return {}

    host = SimpleNamespace(
        base_path=root,
        projects_root_path=root,
        projects_root_paths=[root],
        books=[],
    )
    ws = WorkspaceService(host, read_config=_read)
    return ws.get_projects_root_paths()


def list_books(repo: Path | None = None) -> list[BookInfo]:
    """Alle entdeckten Quarto-Bücher mit zugehöriger Content-Root."""
    root = _repo_root(repo)
    roots = list_content_roots(root)
    host = SimpleNamespace(
        base_path=root,
        projects_root_path=roots[0] if roots else root,
        projects_root_paths=roots or [root],
        books=[],
    )
    ws = WorkspaceService(host, read_config=lambda: {})
    books: list[BookInfo] = []
    for book in ws.discover_projects():
        owning = _owning_root(book, roots or [root])
        books.append(BookInfo(path=book, name=book.name, root=owning))
    return books


def _owning_root(book: Path, roots: list[Path]) -> Path:
    try:
        resolved = book.resolve()
    except OSError:
        return roots[0] if roots else book.parent
    best: Path | None = None
    best_len = -1
    for r in roots:
        try:
            rr = r.resolve()
            resolved.relative_to(rr)
        except (OSError, ValueError):
            continue
        n = len(rr.parts)
        if n > best_len:
            best = rr
            best_len = n
    return best if best is not None else (roots[0] if roots else book.parent)


def add_content_root(new_root: Path, *, repo: Path | None = None) -> list[str]:
    """Fügt eine Content-Root hinzu (absolut, dedupliziert)."""
    root = _repo_root(repo)
    candidate = Path(new_root).expanduser().resolve()
    if not candidate.is_dir():
        raise ValueError(f"Kein Ordner: {candidate}")
    entries = read_content_root_config(root)
    abs_entries: list[str] = []
    seen: set[str] = set()
    for e in entries:
        p = Path(e).expanduser()
        resolved = p if p.is_absolute() else (root / p).resolve()
        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            abs_entries.append(str(resolved))
    key_new = str(candidate).lower()
    if key_new not in seen:
        abs_entries.append(str(candidate))
    write_content_root_config(abs_entries, repo=root)
    return abs_entries


def remove_content_root(target: Path, *, repo: Path | None = None) -> list[str]:
    """Entfernt eine Content-Root aus der Config (löscht keine Bücher)."""
    root = _repo_root(repo)
    target_key = str(Path(target).expanduser().resolve()).lower()
    kept: list[str] = []
    for e in read_content_root_config(root):
        p = Path(e).expanduser()
        resolved = p if p.is_absolute() else (root / p).resolve()
        if str(resolved).lower() == target_key:
            continue
        kept.append(str(resolved))
    if not kept:
        kept = [str(root)]
    write_content_root_config(kept, repo=root)
    return kept


def ensure_book_discoverable(book: Path, *, repo: Path | None = None) -> Path:
    """Stellt sicher, dass `book` unter einer Content-Root liegt.

    Fehlt die Root, wird der Elternordner des Buches als Root ergänzt.
    Gibt den Buchpfad zurück.
    """
    book = Path(book).resolve()
    if not is_quarto_book(book):
        raise ValueError(f"Kein Quarto-Buch (_quarto.yml fehlt): {book}")
    root = _repo_root(repo)
    for r in list_content_roots(root):
        try:
            book.relative_to(r.resolve())
            return book
        except (OSError, ValueError):
            continue
    add_content_root(book.parent, repo=root)
    return book


def create_empty_book(
    parent: Path,
    folder_name: str,
    *,
    title: str | None = None,
    repo: Path | None = None,
) -> Path:
    """Legt ein leeres Buch an und macht den Parent ggf. als Content-Root bekannt."""
    parent = Path(parent).resolve()
    book = _create_empty_book(parent, folder_name, title=title)
    ensure_book_discoverable(book, repo=repo)
    return book


__all__ = [
    "BookInfo",
    "add_content_root",
    "create_empty_book",
    "ensure_book_discoverable",
    "is_quarto_book",
    "list_books",
    "list_content_roots",
    "read_content_root_config",
    "remove_content_root",
    "sanitize_book_folder_name",
    "write_content_root_config",
]
