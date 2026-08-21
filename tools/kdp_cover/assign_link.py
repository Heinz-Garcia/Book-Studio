"""Assign a cover path to a production UUID (registry + canonical path)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from tools.kdp_cover.cover_paths import canonical_layout_path
from tools.kdp_cover.cover_registry import CoverRegistryEntry, CoverRole, upsert_cover_link
from tools.kdp_cover.model import sanitize_book_filename_stem
from tools.production_uuid import normalize_uuid


def assign_cover_to_uuid(
    *,
    production_uuid: str,
    cover_label: str = "",
    cover_role: CoverRole = "primary",
    title_hint: str = "",
    source_kinds: Sequence[str] | None = None,
    book_path: Path | str | None = None,
    cover_path: Path | str | None = None,
    repo: Path | None = None,
) -> CoverRegistryEntry:
    """Persist Cover↔UUID in the registry immediately (visible on next picker open).

    If ``cover_path`` is omitted, uses the canonical layout path under
    ``production/covers/<uuid>/…``. Parent directories are created; the JSON
    file itself is not written here (that happens on Speichern/Export).
    """
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise ValueError("production_uuid fehlt oder ist ungültig.")
    role: CoverRole = (
        "alternative" if str(cover_role).strip().lower() == "alternative" else "primary"
    )
    book = Path(book_path) if book_path else None
    stem_src = (title_hint or "").strip() or (book.name if book else "cover")
    stem = sanitize_book_filename_stem(stem_src)
    if cover_path is not None and str(cover_path).strip():
        target = Path(cover_path).expanduser()
        try:
            target = target.resolve()
        except OSError:
            pass
    else:
        target = canonical_layout_path(
            uid,
            stem=stem,
            cover_role=role,
            cover_label=cover_label,
            repo=repo,
        )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return upsert_cover_link(
        production_uuid=uid,
        cover_path=target,
        book_path=book,
        cover_label=str(cover_label or "").strip(),
        cover_role=role,
        title_hint=str(title_hint or "").strip(),
        source_kinds=list(source_kinds or []),
    )


__all__ = ["assign_cover_to_uuid"]
