"""Persist last KDP Cover-Designer dialog geometry (SSOT).

Stored under ``tools/kdp_cover/last_session.json`` (user-local, gitignored).
No Qt imports — the dialog maps fields to/from a plain dict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SETTINGS_FILENAME = "last_session.json"
_SCHEMA_VERSION = 1

# Default matches the previous hardcoded QDialog.resize(...) values.
DEFAULT_WINDOW_WIDTH = 1540
DEFAULT_WINDOW_HEIGHT = 920
MIN_WINDOW_WIDTH = 1280
MIN_WINDOW_HEIGHT = 720


def settings_path() -> Path:
    return Path(__file__).resolve().parent / _SETTINGS_FILENAME


def default_settings() -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "window_width": DEFAULT_WINDOW_WIDTH,
        "window_height": DEFAULT_WINDOW_HEIGHT,
    }


def load_settings(path: Path | None = None) -> dict[str, Any]:
    """Load last session; unknown/missing keys fall back to defaults."""
    target = path or settings_path()
    base = default_settings()
    if not target.is_file():
        base["window_geometry_saved"] = False
        return base
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        base["window_geometry_saved"] = False
        return base
    if not isinstance(raw, dict):
        base["window_geometry_saved"] = False
        return base
    merged = dict(base)
    for key, value in raw.items():
        if key in base:
            merged[key] = value
    merged["schema_version"] = _SCHEMA_VERSION
    merged["window_geometry_saved"] = "window_width" in raw and "window_height" in raw
    return merged


def resolve_window_size(data: dict[str, Any]) -> tuple[int, int]:
    """Return dialog (width, height); fallback when geometry was never saved."""
    if not data.get("window_geometry_saved"):
        return DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
    try:
        width = int(data.get("window_width", DEFAULT_WINDOW_WIDTH))
        height = int(data.get("window_height", DEFAULT_WINDOW_HEIGHT))
    except (TypeError, ValueError):
        return DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
    return max(MIN_WINDOW_WIDTH, width), max(MIN_WINDOW_HEIGHT, height)


def save_settings(data: dict[str, Any], path: Path | None = None) -> Path:
    """Write session settings (write then replace)."""
    target = path or settings_path()
    payload = default_settings()
    for key in payload:
        if key in data:
            payload[key] = data[key]
    payload["schema_version"] = _SCHEMA_VERSION
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return target
