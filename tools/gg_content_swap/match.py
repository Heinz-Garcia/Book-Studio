"""Zuordnung Buch-GG-Dateien ↔ Export-Markdown."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import frontmatter_parser
from content_source import is_gg_nutzinhalt_candidate
from tools.gg_content_swap.types import SwapPlanLine, SwapStatus


def _normalize_rel(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _title_of(content: str) -> str:
    parts = frontmatter_parser.parse(content)
    if parts.has_frontmatter:
        data = parts.parsed()
        if isinstance(data, dict) and data.get("title") not in (None, ""):
            return str(data.get("title")).strip()
    return ""


def iter_markdown_files(root: Path) -> list[Path]:
    root = Path(root)
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if any(part.startswith(".") for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def list_book_gg_files(book_path: Path) -> list[tuple[str, Path, str]]:
    """Liefert ``(rel_path, abs_path, title)`` für GG-Nutzinhalt-Kandidaten.

    Automatisch: nicht Required-/Skeleton-Rahmen, nicht Root-``index.md``,
    nicht ``content_role: outline``.
    """
    book = Path(book_path).resolve()
    out: list[tuple[str, Path, str]] = []
    for path in iter_markdown_files(book):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = _normalize_rel(path.relative_to(book))
        if not is_gg_nutzinhalt_candidate(rel_path=rel, content=text):
            continue
        out.append((rel, path, _title_of(text)))
    return out


def index_export_files(source_root: Path) -> tuple[dict[str, Path], dict[str, list[Path]]]:
    """Pfad-Index und Titel-Index (Titel → Liste von Pfaden)."""
    root = Path(source_root).resolve()
    by_rel: dict[str, Path] = {}
    by_title: dict[str, list[Path]] = {}
    for path in iter_markdown_files(root):
        rel = _normalize_rel(path.relative_to(root))
        by_rel[rel] = path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        title = _title_of(text)
        if not title:
            continue
        key = title.casefold()
        by_title.setdefault(key, []).append(path)
    return by_rel, by_title


def match_source_for_book_file(
    book_rel: str,
    book_title: str,
    *,
    by_rel: dict[str, Path],
    by_title: dict[str, list[Path]],
    source_root: Path,
) -> tuple[Optional[str], SwapStatus, str]:
    """Liefert ``(source_rel | None, status, message)``."""
    source_root = Path(source_root)
    if book_rel in by_rel:
        return book_rel, "ok", "Pfad-Match"
    if book_title:
        candidates = by_title.get(book_title.casefold()) or []
        if len(candidates) == 1:
            rel = _normalize_rel(candidates[0].relative_to(source_root.resolve()))
            return rel, "ok", "Titel-Match"
        if len(candidates) > 1:
            return None, "ambiguous", f"Titel mehrdeutig ({len(candidates)} Treffer)"
    return None, "missing", "Keine passende Export-Datei"


def build_match_plan(
    book_path: Path,
    source_root: Path,
) -> list[SwapPlanLine]:
    """Baut den Zuordnungsplan für automatisch erkannte GG-Nutzinhalt-Dateien."""
    by_rel, by_title = index_export_files(source_root)
    lines: list[SwapPlanLine] = []
    for rel, _path, title in list_book_gg_files(book_path):
        source_rel, status, message = match_source_for_book_file(
            rel,
            title,
            by_rel=by_rel,
            by_title=by_title,
            source_root=source_root,
        )
        lines.append(
            SwapPlanLine(
                book_rel=rel,
                source_rel=source_rel,
                status=status,
                title=title,
                message=message,
            )
        )
    return lines
