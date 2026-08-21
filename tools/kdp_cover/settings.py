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

DEFAULT_CONFIRM_WINDOW_WIDTH = 720
DEFAULT_CONFIRM_WINDOW_HEIGHT = 480
MIN_CONFIRM_WINDOW_WIDTH = 560
MIN_CONFIRM_WINDOW_HEIGHT = 360

DEFAULT_UUID_PICKER_WINDOW_WIDTH = 900
DEFAULT_UUID_PICKER_WINDOW_HEIGHT = 560
MIN_UUID_PICKER_WINDOW_WIDTH = 640
MIN_UUID_PICKER_WINDOW_HEIGHT = 420


def settings_path() -> Path:
    return Path(__file__).resolve().parent / _SETTINGS_FILENAME


def default_settings() -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "window_width": DEFAULT_WINDOW_WIDTH,
        "window_height": DEFAULT_WINDOW_HEIGHT,
        "window_maximized": False,
        "active_tab": 0,
        "confirm_window_width": DEFAULT_CONFIRM_WINDOW_WIDTH,
        "confirm_window_height": DEFAULT_CONFIRM_WINDOW_HEIGHT,
        "confirm_window_maximized": False,
        "uuid_picker_window_width": DEFAULT_UUID_PICKER_WINDOW_WIDTH,
        "uuid_picker_window_height": DEFAULT_UUID_PICKER_WINDOW_HEIGHT,
        "uuid_picker_window_maximized": False,
        # Per-column widths for CoverUuidPickDialog (empty = use Qt defaults).
        "uuid_picker_column_widths": [],
    }


def load_settings(path: Path | None = None) -> dict[str, Any]:
    """Load last session; unknown/missing keys fall back to defaults."""
    target = path or settings_path()
    base = default_settings()
    if not target.is_file():
        base["window_geometry_saved"] = False
        base["confirm_geometry_saved"] = False
        base["uuid_picker_geometry_saved"] = False
        return base
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        base["window_geometry_saved"] = False
        base["confirm_geometry_saved"] = False
        base["uuid_picker_geometry_saved"] = False
        return base
    if not isinstance(raw, dict):
        base["window_geometry_saved"] = False
        base["confirm_geometry_saved"] = False
        base["uuid_picker_geometry_saved"] = False
        return base
    merged = dict(base)
    for key, value in raw.items():
        if key in base:
            merged[key] = value
    merged["schema_version"] = _SCHEMA_VERSION
    merged["window_geometry_saved"] = "window_width" in raw and "window_height" in raw
    merged["confirm_geometry_saved"] = (
        "confirm_window_width" in raw and "confirm_window_height" in raw
    )
    merged["uuid_picker_geometry_saved"] = (
        "uuid_picker_window_width" in raw and "uuid_picker_window_height" in raw
    )
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


def resolve_confirm_window_size(data: dict[str, Any]) -> tuple[int, int]:
    """Return export-issues dialog size; fallback when never saved."""
    if not data.get("confirm_geometry_saved"):
        return DEFAULT_CONFIRM_WINDOW_WIDTH, DEFAULT_CONFIRM_WINDOW_HEIGHT
    try:
        width = int(data.get("confirm_window_width", DEFAULT_CONFIRM_WINDOW_WIDTH))
        height = int(data.get("confirm_window_height", DEFAULT_CONFIRM_WINDOW_HEIGHT))
    except (TypeError, ValueError):
        return DEFAULT_CONFIRM_WINDOW_WIDTH, DEFAULT_CONFIRM_WINDOW_HEIGHT
    return (
        max(MIN_CONFIRM_WINDOW_WIDTH, width),
        max(MIN_CONFIRM_WINDOW_HEIGHT, height),
    )


def resolve_uuid_picker_window_size(data: dict[str, Any]) -> tuple[int, int]:
    """Return UUID-picker dialog size; fallback when never saved."""
    if not data.get("uuid_picker_geometry_saved"):
        return DEFAULT_UUID_PICKER_WINDOW_WIDTH, DEFAULT_UUID_PICKER_WINDOW_HEIGHT
    try:
        width = int(
            data.get("uuid_picker_window_width", DEFAULT_UUID_PICKER_WINDOW_WIDTH)
        )
        height = int(
            data.get("uuid_picker_window_height", DEFAULT_UUID_PICKER_WINDOW_HEIGHT)
        )
    except (TypeError, ValueError):
        return DEFAULT_UUID_PICKER_WINDOW_WIDTH, DEFAULT_UUID_PICKER_WINDOW_HEIGHT
    return (
        max(MIN_UUID_PICKER_WINDOW_WIDTH, width),
        max(MIN_UUID_PICKER_WINDOW_HEIGHT, height),
    )


def resolve_uuid_picker_column_widths(
    data: dict[str, Any],
    *,
    column_count: int,
) -> list[int] | None:
    """Return saved column widths, or ``None`` when missing/invalid."""
    if column_count <= 0:
        return None
    raw = data.get("uuid_picker_column_widths")
    if not isinstance(raw, list) or len(raw) != column_count:
        return None
    widths: list[int] = []
    try:
        for value in raw:
            width = int(value)
            if width < 24:
                return None
            widths.append(width)
    except (TypeError, ValueError):
        return None
    return widths


def resolve_active_tab(data: dict[str, Any], *, tab_count: int) -> int:
    """Clamp persisted tab index into ``[0, tab_count)``."""
    if tab_count <= 0:
        return 0
    try:
        idx = int(data.get("active_tab", 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(tab_count - 1, idx))


def save_settings(data: dict[str, Any], path: Path | None = None) -> Path:
    """Write session settings (write then replace)."""
    target = path or settings_path()
    # Preserve previously saved keys when callers pass a partial update.
    try:
        existing = load_settings(target)
    except OSError:
        existing = default_settings()
    payload = default_settings()
    for key in payload:
        if key in existing and key != "schema_version":
            payload[key] = existing[key]
    for key in payload:
        if key in data:
            payload[key] = data[key]
    payload["schema_version"] = _SCHEMA_VERSION
    # Normalize types for JSON stability.
    try:
        payload["window_width"] = int(payload["window_width"])
        payload["window_height"] = int(payload["window_height"])
        payload["active_tab"] = int(payload["active_tab"])
        payload["confirm_window_width"] = int(payload["confirm_window_width"])
        payload["confirm_window_height"] = int(payload["confirm_window_height"])
        payload["uuid_picker_window_width"] = int(payload["uuid_picker_window_width"])
        payload["uuid_picker_window_height"] = int(
            payload["uuid_picker_window_height"]
        )
    except (TypeError, ValueError):
        payload["window_width"] = DEFAULT_WINDOW_WIDTH
        payload["window_height"] = DEFAULT_WINDOW_HEIGHT
        payload["active_tab"] = 0
        payload["confirm_window_width"] = DEFAULT_CONFIRM_WINDOW_WIDTH
        payload["confirm_window_height"] = DEFAULT_CONFIRM_WINDOW_HEIGHT
        payload["uuid_picker_window_width"] = DEFAULT_UUID_PICKER_WINDOW_WIDTH
        payload["uuid_picker_window_height"] = DEFAULT_UUID_PICKER_WINDOW_HEIGHT
    payload["window_maximized"] = bool(payload.get("window_maximized"))
    payload["confirm_window_maximized"] = bool(payload.get("confirm_window_maximized"))
    payload["uuid_picker_window_maximized"] = bool(
        payload.get("uuid_picker_window_maximized")
    )
    col_widths = payload.get("uuid_picker_column_widths")
    if isinstance(col_widths, list):
        cleaned: list[int] = []
        try:
            for value in col_widths:
                cleaned.append(max(24, int(value)))
            payload["uuid_picker_column_widths"] = cleaned
        except (TypeError, ValueError):
            payload["uuid_picker_column_widths"] = []
    else:
        payload["uuid_picker_column_widths"] = []
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return target
