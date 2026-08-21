"""Cover ↔ Production-UUID registry (SSOT).

User-local file ``tools/kdp_cover/cover_uuid_registry.json`` (gitignored).
Links GrammarGraph/Book-Studio production UUIDs to one or more cover layouts
(primary + alternatives).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from tools.production_uuid import normalize_uuid

_REGISTRY_FILENAME = "cover_uuid_registry.json"
_SCHEMA_VERSION = 1

CoverRole = Literal["primary", "alternative"]


@dataclass
class CoverRegistryEntry:
    production_uuid: str
    cover_path: str
    book_path: str = ""
    cover_label: str = ""
    cover_role: CoverRole = "primary"
    title_hint: str = ""
    source_kinds: list[str] = field(default_factory=list)
    saved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        role = "alternative" if self.cover_role == "alternative" else "primary"
        return {
            "production_uuid": self.production_uuid,
            "cover_path": self.cover_path,
            "book_path": self.book_path or "",
            "cover_label": self.cover_label or "",
            "cover_role": role,
            "title_hint": self.title_hint or "",
            "source_kinds": list(self.source_kinds or []),
            "saved_at": self.saved_at or "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverRegistryEntry:
        role_raw = str(data.get("cover_role") or "primary").strip().lower()
        role: CoverRole = "alternative" if role_raw == "alternative" else "primary"
        kinds = data.get("source_kinds") or []
        if not isinstance(kinds, list):
            kinds = []
        return cls(
            production_uuid=str(data.get("production_uuid") or "").strip(),
            cover_path=str(data.get("cover_path") or "").strip(),
            book_path=str(data.get("book_path") or "").strip(),
            cover_label=str(data.get("cover_label") or "").strip(),
            cover_role=role,
            title_hint=str(data.get("title_hint") or "").strip(),
            source_kinds=[str(k) for k in kinds if str(k).strip()],
            saved_at=str(data.get("saved_at") or "").strip(),
        )


def registry_path() -> Path:
    return Path(__file__).resolve().parent / _REGISTRY_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_path_key(path: str | Path) -> str:
    try:
        return str(Path(path).expanduser().resolve()).casefold()
    except OSError:
        return str(path).strip().casefold()


def load_registry(path: Path | None = None) -> dict[str, Any]:
    target = path or registry_path()
    empty = {
        "schema_version": _SCHEMA_VERSION,
        "updated_at": "",
        "entries": [],
    }
    if not target.is_file():
        return empty
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return empty
    if not isinstance(raw, dict):
        return empty
    entries_raw = raw.get("entries")
    entries: list[dict[str, Any]] = []
    if isinstance(entries_raw, list):
        for item in entries_raw:
            if isinstance(item, dict) and str(item.get("production_uuid") or "").strip():
                entries.append(CoverRegistryEntry.from_dict(item).to_dict())
    return {
        "schema_version": _SCHEMA_VERSION,
        "updated_at": str(raw.get("updated_at") or ""),
        "entries": entries,
    }


def save_registry(data: dict[str, Any], path: Path | None = None) -> Path:
    target = path or registry_path()
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "updated_at": _now_iso(),
        "entries": list(data.get("entries") or []),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return target


def list_covers_for_uuid(
    production_uuid: str,
    *,
    path: Path | None = None,
) -> list[CoverRegistryEntry]:
    uid = normalize_uuid(production_uuid) or str(production_uuid or "").strip()
    if not uid:
        return []
    data = load_registry(path)
    out: list[CoverRegistryEntry] = []
    for raw in data.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        entry = CoverRegistryEntry.from_dict(raw)
        entry_uid = normalize_uuid(entry.production_uuid) or entry.production_uuid
        if entry_uid.casefold() == uid.casefold():
            out.append(entry)
    return out


def resolve_primary_cover(
    production_uuid: str,
    *,
    path: Path | None = None,
) -> Optional[CoverRegistryEntry]:
    covers = list_covers_for_uuid(production_uuid, path=path)
    for entry in covers:
        if entry.cover_role == "primary":
            return entry
    return covers[0] if covers else None


def upsert_cover_link(
    *,
    production_uuid: str,
    cover_path: str | Path,
    book_path: str | Path | None = None,
    cover_label: str = "",
    cover_role: CoverRole = "primary",
    title_hint: str = "",
    source_kinds: list[str] | None = None,
    path: Path | None = None,
) -> CoverRegistryEntry:
    """Insert or update a cover link. Enforces one primary per UUID."""
    uid = normalize_uuid(production_uuid)
    if not uid:
        raise ValueError("production_uuid fehlt oder ist ungültig.")
    cover = str(Path(cover_path).expanduser().resolve())
    book = ""
    if book_path is not None and str(book_path).strip():
        try:
            book = str(Path(book_path).expanduser().resolve())
        except OSError:
            book = str(book_path).strip()
    role: CoverRole = "alternative" if cover_role == "alternative" else "primary"
    kinds = [str(k) for k in (source_kinds or []) if str(k).strip()]
    entry = CoverRegistryEntry(
        production_uuid=uid,
        cover_path=cover,
        book_path=book,
        cover_label=str(cover_label or "").strip(),
        cover_role=role,
        title_hint=str(title_hint or "").strip(),
        source_kinds=kinds,
        saved_at=_now_iso(),
    )

    data = load_registry(path)
    entries: list[dict[str, Any]] = []
    cover_key = _normalize_path_key(cover)
    replaced = False
    for raw in data.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        existing = CoverRegistryEntry.from_dict(raw)
        existing_uid = normalize_uuid(existing.production_uuid) or existing.production_uuid
        same_uuid = existing_uid.casefold() == uid.casefold()
        same_path = _normalize_path_key(existing.cover_path) == cover_key
        if same_path:
            # Replace this path entry (may also reassign UUID).
            entries.append(entry.to_dict())
            replaced = True
            continue
        if same_uuid and role == "primary" and existing.cover_role == "primary":
            existing.cover_role = "alternative"
            entries.append(existing.to_dict())
            continue
        entries.append(existing.to_dict())
    if not replaced:
        entries.append(entry.to_dict())
    data["entries"] = entries
    save_registry(data, path)
    return entry


__all__ = [
    "CoverRegistryEntry",
    "CoverRole",
    "list_covers_for_uuid",
    "load_registry",
    "registry_path",
    "resolve_primary_cover",
    "save_registry",
    "upsert_cover_link",
]
