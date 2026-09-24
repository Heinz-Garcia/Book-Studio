"""Geplante Production-UUIDs: Cover-first, noch ohne Buchprojekt.

SSOT: Book Studio erzeugt UUID + Registry-Metadaten; GrammarGraph wählt dieselbe
UUID beim Projekt-Anlegen. Siehe ``.doc/cover-planned-uuid.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from tools.kdp_cover.assign_link import assign_cover_to_uuid
from tools.kdp_cover.cover_paths import canonical_cover_dir
from tools.kdp_cover.cover_registry import (
    CoverRegistryEntry,
    load_registry,
    registry_path,
)
from tools.production_uuid import normalize_uuid

SOURCE_KIND_PLANNED = "planned_cover"


@dataclass(frozen=True)
class PlannedCoverUuid:
    """Ergebnis von ``create_planned_cover_uuid``."""

    production_uuid: str
    title_hint: str
    series_id: str
    cover_dir: Path
    cover_path: Path
    entry: CoverRegistryEntry


def create_planned_cover_uuid(
    *,
    title_hint: str,
    series_id: str = "",
    cover_label: str = "",
    repo: Path | None = None,
    registry_file: Path | None = None,
) -> PlannedCoverUuid:
    """Neue UUID erzeugen, Cover-Ordner anlegen, Registry-Eintrag mit Titel.

    Die Layout-JSON wird hier noch nicht geschrieben — nur Parent-Ordner + Link.
    """
    title = str(title_hint or "").strip()
    if not title:
        raise ValueError("Arbeitstitel (title_hint) ist Pflicht.")
    uid = str(uuid4())
    series = str(series_id or "").strip()
    label = str(cover_label or "").strip() or "Hauptcover"
    kinds = [SOURCE_KIND_PLANNED]

    entry = assign_cover_to_uuid(
        production_uuid=uid,
        cover_label=label,
        cover_role="primary",
        title_hint=title,
        series_id=series,
        source_kinds=kinds,
        book_path=None,
        repo=repo,
        registry_file=registry_file,
    )
    cover_dir = canonical_cover_dir(uid, cover_role="primary", repo=repo)
    return PlannedCoverUuid(
        production_uuid=uid,
        title_hint=title,
        series_id=series,
        cover_dir=cover_dir,
        cover_path=Path(entry.cover_path),
        entry=entry,
    )


def is_planned_registry_entry(entry: CoverRegistryEntry) -> bool:
    """True wenn Cover-first / noch ohne Buchbindung.

    Sobald ``book_path`` gesetzt ist, ist der Eintrag gebunden — auch wenn
    ``planned_cover`` in ``source_kinds`` bleibt (Historie).
    """
    if str(entry.book_path or "").strip():
        return False
    kinds = {str(k).strip().lower() for k in (entry.source_kinds or [])}
    if SOURCE_KIND_PLANNED in kinds:
        return True
    return bool(str(entry.title_hint or "").strip())


def list_planned_cover_uuids(
    *,
    registry_file: Path | None = None,
) -> list[dict[str, Any]]:
    """Ungebundene / geplante Covers für GrammarGraph (JSON-freundlich).

    Pro UUID höchstens ein Primary-Eintrag. Sortierung: title_hint, dann UUID.
    """
    data = load_registry(registry_file or registry_path())
    by_uid: dict[str, CoverRegistryEntry] = {}
    for raw in data.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        entry = CoverRegistryEntry.from_dict(raw)
        uid = normalize_uuid(entry.production_uuid) or entry.production_uuid
        if not uid or not is_planned_registry_entry(entry):
            continue
        key = uid.casefold()
        existing = by_uid.get(key)
        if existing is None:
            by_uid[key] = entry
            continue
        if entry.cover_role == "primary" and existing.cover_role != "primary":
            by_uid[key] = entry

    rows: list[dict[str, Any]] = []
    for entry in by_uid.values():
        uid = normalize_uuid(entry.production_uuid) or entry.production_uuid
        rows.append(
            {
                "production_uuid": uid,
                "title_hint": str(entry.title_hint or "").strip(),
                "series_id": str(entry.series_id or "").strip(),
                "cover_path": str(entry.cover_path or "").strip(),
                "cover_label": str(entry.cover_label or "").strip(),
                "book_path": "",
                "source_kinds": list(entry.source_kinds or []),
                "saved_at": str(entry.saved_at or "").strip(),
            }
        )
    rows.sort(
        key=lambda r: (
            str(r.get("title_hint") or "").casefold(),
            str(r.get("production_uuid") or "").casefold(),
        )
    )
    return rows


__all__ = [
    "SOURCE_KIND_PLANNED",
    "PlannedCoverUuid",
    "create_planned_cover_uuid",
    "is_planned_registry_entry",
    "list_planned_cover_uuids",
]
