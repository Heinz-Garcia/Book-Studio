"""Zuordnung Buch-GG-Dateien ↔ Export-Markdown."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import frontmatter_parser
from content_source import is_gg_nutzinhalt_candidate
from tools.gg_content_swap.types import MatchScanResult, SwapPlanLine, SwapStatus

# Typische Nicht-Inhaltsdateien im Export (kein Sole-/Basename-Match-Ziel).
_EXPORT_SKIP_NAMES = frozenset(
    {
        "readme.md",
        "changelog.md",
        "license.md",
        "contributing.md",
        "index.md",
        "erstellungsprotokoll.md",
    }
)


def _normalize_rel(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _basename(rel: str) -> str:
    return Path(_normalize_rel(rel)).name.casefold()


def _stem(rel: str) -> str:
    return Path(_normalize_rel(rel)).stem.casefold()


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


def index_export_files(
    source_root: Path,
) -> tuple[dict[str, Path], dict[str, list[Path]], dict[str, list[Path]], dict[str, list[Path]]]:
    """Pfad-, Titel-, Basename- und Stem-Index."""
    root = Path(source_root).resolve()
    by_rel: dict[str, Path] = {}
    by_title: dict[str, list[Path]] = {}
    by_basename: dict[str, list[Path]] = {}
    by_stem: dict[str, list[Path]] = {}
    for path in iter_markdown_files(root):
        rel = _normalize_rel(path.relative_to(root))
        by_rel[rel] = path
        by_basename.setdefault(_basename(rel), []).append(path)
        by_stem.setdefault(_stem(rel), []).append(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        title = _title_of(text)
        if not title:
            continue
        key = title.casefold()
        by_title.setdefault(key, []).append(path)
    return by_rel, by_title, by_basename, by_stem


def _content_export_rels(by_rel: dict[str, Path]) -> list[str]:
    """Export-Markdown ohne typische Meta-Dateien."""
    out: list[str] = []
    for rel in sorted(by_rel):
        if Path(rel).name.casefold() in _EXPORT_SKIP_NAMES:
            continue
        out.append(rel)
    return out


def match_source_for_book_file(
    book_rel: str,
    book_title: str,
    *,
    by_rel: dict[str, Path],
    by_title: dict[str, list[Path]],
    by_basename: dict[str, list[Path]],
    by_stem: dict[str, list[Path]],
    source_root: Path,
    sole_export_rel: Optional[str] = None,
) -> tuple[Optional[str], SwapStatus, str]:
    """Liefert ``(source_rel | None, status, message)``."""
    source_root = Path(source_root).resolve()
    if book_rel in by_rel:
        return book_rel, "ok", "Pfad-Match"

    if book_title:
        candidates = by_title.get(book_title.casefold()) or []
        if len(candidates) == 1:
            rel = _normalize_rel(candidates[0].relative_to(source_root))
            return rel, "ok", "Titel-Match"
        if len(candidates) > 1:
            return None, "ambiguous", f"Titel mehrdeutig ({len(candidates)} Treffer)"

    base_hits = by_basename.get(_basename(book_rel)) or []
    if len(base_hits) == 1:
        rel = _normalize_rel(base_hits[0].relative_to(source_root))
        return rel, "ok", "Dateiname-Match"
    if len(base_hits) > 1:
        return None, "ambiguous", f"Dateiname mehrdeutig ({len(base_hits)} Treffer)"

    stem_hits = by_stem.get(_stem(book_rel)) or []
    if len(stem_hits) == 1:
        rel = _normalize_rel(stem_hits[0].relative_to(source_root))
        return rel, "ok", "Stammname-Match"
    if len(stem_hits) > 1:
        return None, "ambiguous", f"Stammname mehrdeutig ({len(stem_hits)} Treffer)"

    if sole_export_rel:
        return sole_export_rel, "ok", "Alleiniger Export-Inhalt"

    return None, "missing", "Keine passende Export-Datei (Pfad/Titel/Dateiname)"


def build_match_plan(
    book_path: Path,
    source_root: Path,
) -> list[SwapPlanLine]:
    """Baut den Zuordnungsplan für automatisch erkannte GG-Nutzinhalt-Dateien."""
    return scan_match(book_path, source_root).plan


def scan_match(book_path: Path, source_root: Path) -> MatchScanResult:
    """Zuordnungsplan inkl. Export-Inventar (für Dialog und Diagnose)."""
    by_rel, by_title, by_basename, by_stem = index_export_files(source_root)
    export_files = sorted(by_rel.keys())
    book_files = list_book_gg_files(book_path)
    content_exports = _content_export_rels(by_rel)
    sole_export: Optional[str] = None
    if len(book_files) == 1 and len(content_exports) == 1:
        sole_export = content_exports[0]

    lines: list[SwapPlanLine] = []
    used_sources: set[str] = set()
    for rel, _path, title in book_files:
        source_rel, status, message = match_source_for_book_file(
            rel,
            title,
            by_rel=by_rel,
            by_title=by_title,
            by_basename=by_basename,
            by_stem=by_stem,
            source_root=source_root,
            sole_export_rel=sole_export,
        )
        if source_rel and status == "ok":
            used_sources.add(source_rel)
        lines.append(
            SwapPlanLine(
                book_rel=rel,
                source_rel=source_rel,
                status=status,
                title=title,
                message=message,
            )
        )

    unmatched = [rel for rel in export_files if rel not in used_sources]
    return MatchScanResult(plan=lines, export_files=export_files, unmatched_export=unmatched)
