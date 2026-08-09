"""Buchspezifische Vertriebskanal-Flags (bookconfig/distribution.json).

SSOT für Kanal-Opt-in (z. B. KDP-Taschenbuch). Nicht mit Cover-Layout
(``export/kdp_cover/cover_project.json``) vermischen — das ist Artefakt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

BOOKCONFIG_DIR = "bookconfig"
DISTRIBUTION_FILENAME = "distribution.json"
SCHEMA_VERSION = 1
CHANNEL_KDP_PAPERBACK = "kdp_paperback"


def distribution_path(book_path: Path) -> Path:
    return Path(book_path) / BOOKCONFIG_DIR / DISTRIBUTION_FILENAME


def _empty_payload() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "channels": {}, "chapter_overrides": {}}


def _clean_chapter_overrides(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalisiert ``chapter_overrides`` — tolerant gegenüber fehlenden/kaputten Daten."""
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, dict[str, Any]] = {}
    for channel_id, override in raw.items():
        if not isinstance(override, dict):
            continue
        exclude_paths = override.get("exclude_paths")
        if not isinstance(exclude_paths, list):
            continue
        paths = sorted({str(p) for p in exclude_paths if str(p).strip()})
        if paths:
            cleaned[str(channel_id)] = {"exclude_paths": paths}
    return cleaned


def read_distribution(book_path: Path) -> dict[str, Any]:
    """Liest distribution.json; fehlende/ungültige Datei → leeres Schema."""
    path = distribution_path(book_path)
    if not path.is_file():
        return _empty_payload()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_payload()
    if not isinstance(data, dict):
        return _empty_payload()
    channels = data.get("channels")
    if not isinstance(channels, dict):
        channels = {}
    version = data.get("schema_version", SCHEMA_VERSION)
    try:
        schema_version = int(version)
    except (TypeError, ValueError):
        schema_version = SCHEMA_VERSION
    return {
        "schema_version": schema_version,
        "channels": dict(channels),
        "chapter_overrides": _clean_chapter_overrides(data.get("chapter_overrides")),
    }


def write_distribution(book_path: Path, payload: dict[str, Any]) -> Path:
    dest = distribution_path(book_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    channels = payload.get("channels") if isinstance(payload, dict) else {}
    if not isinstance(channels, dict):
        channels = {}
    chapter_overrides = _clean_chapter_overrides(
        payload.get("chapter_overrides") if isinstance(payload, dict) else None
    )
    out = {
        "schema_version": int(payload.get("schema_version") or SCHEMA_VERSION)
        if isinstance(payload, dict)
        else SCHEMA_VERSION,
        "channels": dict(channels),
    }
    if chapter_overrides:
        out["chapter_overrides"] = chapter_overrides
    dest.write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return dest


def is_channel_enabled(book_path: Path, channel_id: str) -> bool:
    data = read_distribution(book_path)
    return bool(data.get("channels", {}).get(channel_id))


def set_channel_enabled(book_path: Path, channel_id: str, enabled: bool) -> Path:
    data = read_distribution(book_path)
    channels = dict(data.get("channels") or {})
    if enabled:
        channels[channel_id] = True
    else:
        channels.pop(channel_id, None)
        # Explicit false is also fine for clarity when other channels remain;
        # keep True-only map when disabling to avoid stale false keys clutter —
        # but if file had explicit false for others, preserve them.
        # Simpler: write boolean.
        channels[channel_id] = False
    data["channels"] = channels
    data["schema_version"] = SCHEMA_VERSION
    return write_distribution(book_path, data)


def is_kdp_paperback(book_path: Path) -> bool:
    return is_channel_enabled(book_path, CHANNEL_KDP_PAPERBACK)


def set_kdp_paperback(book_path: Path, enabled: bool) -> Path:
    return set_channel_enabled(book_path, CHANNEL_KDP_PAPERBACK, enabled)


def list_excluded_chapters(book_path: Path, channel_id: str) -> list[str]:
    """Kapitel-Pfade, die für ``channel_id`` vom Render ausgeschlossen sind."""
    data = read_distribution(book_path)
    override = data.get("chapter_overrides", {}).get(channel_id, {})
    return list(override.get("exclude_paths", []))


def is_chapter_excluded(book_path: Path, channel_id: str, rel_path: str) -> bool:
    normalized = str(rel_path).replace("\\", "/")
    return normalized in {
        p.replace("\\", "/") for p in list_excluded_chapters(book_path, channel_id)
    }


def set_chapter_excluded(
    book_path: Path, channel_id: str, rel_path: str, excluded: bool
) -> Path:
    """Markiert/entmarkiert ein Kapitel als für ``channel_id`` ausgeschlossen."""
    normalized = str(rel_path).replace("\\", "/")
    data = read_distribution(book_path)
    overrides = dict(data.get("chapter_overrides") or {})
    current = set(overrides.get(channel_id, {}).get("exclude_paths", []))
    if excluded:
        current.add(normalized)
    else:
        current.discard(normalized)
    if current:
        overrides[channel_id] = {"exclude_paths": sorted(current)}
    else:
        overrides.pop(channel_id, None)
    data["chapter_overrides"] = overrides
    return write_distribution(book_path, data)


def read_book_distribution_override(book_path: Path) -> Optional[dict[str, Any]]:
    """Legacy-ähnlicher Name: None wenn Datei fehlt (nicht bei leerem Schema)."""
    path = distribution_path(book_path)
    if not path.is_file():
        return None
    data = read_distribution(book_path)
    return data


__all__ = [
    "BOOKCONFIG_DIR",
    "DISTRIBUTION_FILENAME",
    "SCHEMA_VERSION",
    "CHANNEL_KDP_PAPERBACK",
    "distribution_path",
    "read_distribution",
    "write_distribution",
    "is_channel_enabled",
    "set_channel_enabled",
    "is_kdp_paperback",
    "set_kdp_paperback",
    "read_book_distribution_override",
    "list_excluded_chapters",
    "is_chapter_excluded",
    "set_chapter_excluded",
]
