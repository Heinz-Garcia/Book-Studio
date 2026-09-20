"""Kapitel/Buchstruktur — Status der strukturierten Seiten (ohne UI).

Unterschied zu Rahmen (``rahmen_pages``):
- **Rahmen**: Pflichtseiten-Dateien existieren im Buch (``required`` / Legacy).
- **Kapitel**: diese Pflichtseiten stehen in der Buchstruktur (rechts /
  ``_quarto.yml``), und nicht-required Kapitel haben Inhalt (Wortzahl > 0).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import frontmatter_parser
from page_required import is_page_required_at, list_required_page_paths

__all__ = [
    "KapitelPageKind",
    "KapitelPageStatus",
    "assess_kapitel_pages",
]


class KapitelPageKind(str, Enum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True)
class KapitelPageStatus:
    rel_path: str
    title: str
    words: int
    is_required: bool
    in_structure: bool
    kind: KapitelPageKind
    detail: str


def _title_from_file(book: Path, rel: str) -> str:
    full = book / rel
    if not full.is_file():
        return ""
    try:
        text = full.read_text(encoding="utf-8")
    except OSError:
        return ""
    parts = frontmatter_parser.parse(text)
    if not parts.has_frontmatter:
        return Path(rel).stem
    data = parts.parsed()
    if isinstance(data, dict) and data.get("title") is not None:
        title = str(data.get("title")).strip()
        if title:
            return title
    return Path(rel).stem


def _words_from_listing(book: Path, rel: str) -> Optional[int]:
    try:
        from tools.chapter_list.builder import build_chapter_list_detailed
    except ImportError:
        return None
    try:
        listing = build_chapter_list_detailed(book)
    except (OSError, TypeError, ValueError, RuntimeError):
        return None
    for row in listing.chapters:
        path = str(row.path or "").replace("\\", "/")
        if path == rel:
            return int(row.words or 0)
    return None


def assess_kapitel_pages(
    book_path: Path,
    *,
    structure_paths: Optional[list[str]] = None,
) -> list[KapitelPageStatus]:
    """Statuszeilen: fehlende Required + Einträge in der Buchstruktur."""
    book = Path(book_path)
    if structure_paths is not None:
        in_structure = [str(p).replace("\\", "/") for p in structure_paths if p]
        structure_set = set(in_structure)
    else:
        try:
            from tools.chapter_list.builder import build_chapter_list_detailed

            listing = build_chapter_list_detailed(book)
            in_structure = [
                str(row.path or "").replace("\\", "/")
                for row in listing.chapters
                if row.path
            ]
            structure_set = set(in_structure)
        except (ImportError, OSError, TypeError, ValueError, RuntimeError):
            in_structure = []
            structure_set = set()

    try:
        required = list_required_page_paths(book)
    except (OSError, TypeError, ValueError):
        required = []

    rows: list[KapitelPageStatus] = []
    for rel in required:
        if rel in structure_set:
            continue
        rows.append(
            KapitelPageStatus(
                rel_path=rel,
                title=_title_from_file(book, rel),
                words=0,
                is_required=True,
                in_structure=False,
                kind=KapitelPageKind.ERROR,
                detail="fehlt in der Buchstruktur (rechts einfügen)",
            )
        )

    for rel in in_structure:
        is_req = False
        try:
            is_req = is_page_required_at(book, rel)
        except (OSError, TypeError, ValueError):
            is_req = rel in required
        words_opt = _words_from_listing(book, rel)
        title = _title_from_file(book, rel)
        if not (book / rel).is_file():
            rows.append(
                KapitelPageStatus(
                    rel_path=rel,
                    title=title,
                    words=0,
                    is_required=is_req,
                    in_structure=True,
                    kind=KapitelPageKind.ERROR,
                    detail="Datei fehlt auf dem Datenträger",
                )
            )
            continue
        if words_opt is None:
            rows.append(
                KapitelPageStatus(
                    rel_path=rel,
                    title=title,
                    words=0,
                    is_required=is_req,
                    in_structure=True,
                    kind=KapitelPageKind.WARN if not is_req else KapitelPageKind.OK,
                    detail=(
                        "Pflichtseite in Struktur"
                        if is_req
                        else "Wortzahl nicht prüfbar"
                    ),
                )
            )
            continue
        words = words_opt
        if not is_req and words <= 0:
            rows.append(
                KapitelPageStatus(
                    rel_path=rel,
                    title=title,
                    words=words,
                    is_required=False,
                    in_structure=True,
                    kind=KapitelPageKind.ERROR,
                    detail="leeres Nutzkapitel — Inhalt fehlt",
                )
            )
            continue
        detail = "Pflichtseite in Struktur" if is_req else f"{words} Wörter"
        rows.append(
            KapitelPageStatus(
                rel_path=rel,
                title=title,
                words=words,
                is_required=is_req,
                in_structure=True,
                kind=KapitelPageKind.OK,
                detail=detail,
            )
        )
    return rows
