"""Persist last Cover-Schlagwortwolke dialog settings (SSOT).

Stored under ``tools/stylecloud/last_session.json`` (user-local, gitignored).
No Qt imports — the dialog maps fields to/from a plain dict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.stylecloud.generator import DEFAULT_PRINT_SIZE, suggested_max_font_size

_SETTINGS_FILENAME = "last_session.json"
_SCHEMA_VERSION = 1

# Dialog geometry SSOT — fits all controls without a vertical scrollbar (see UI screenshot).
DEFAULT_WINDOW_WIDTH = 1024
DEFAULT_WINDOW_HEIGHT = 583


def settings_path() -> Path:
    return Path(__file__).resolve().parent / _SETTINGS_FILENAME


def default_settings() -> dict[str, Any]:
    print_size = DEFAULT_PRINT_SIZE
    return {
        "schema_version": _SCHEMA_VERSION,
        "source_mode": "book",
        "source_path": "",
        "output_path": "",
        "size": list(print_size),  # JSON-friendly; load restores tuple
        "icon_name": "__none__",
        "mask_path": "",
        "free_form_margin_pct": 14.0,
        "free_form_density": "airy",
        "free_form_packing": "normal",
        "free_form_orient_auto": True,
        "free_form_orient_pct": 50,
        "palette": "cartocolors.qualitative.Bold_5",
        "gradient": None,
        "background_color": "white",
        "max_colors": 5,
        "max_words": 500,
        "max_font_size": suggested_max_font_size(print_size),
        "user_font_size": None,
        "use_german_stopwords": True,
        "nouns_only": False,
        "collocations": False,
        "invert_mask": False,
        "extra_stopwords": "",
        "must_word": "",
        "must_word_line2": "",
        "must_word_font_size": max(24, suggested_max_font_size(print_size) // 2),
        "must_word_color": "#c0392b",
        "must_word_angle": 0,
        "must_word_gap": 40,
        "must_word_match_line1_width": True,
        "png_compress_level": 6,
        "png_optimize": True,
        "png_dpi": 300,
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
    merged["window_geometry_saved"] = (
        "window_width" in raw and "window_height" in raw
    )
    # Normalize size tuple encoded as JSON list.
    size = merged.get("size")
    if isinstance(size, list) and len(size) == 2:
        try:
            merged["size"] = (int(size[0]), int(size[1]))
        except (TypeError, ValueError):
            merged["size"] = 1024
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
    return max(860, width), max(480, height)


def save_settings(data: dict[str, Any], path: Path | None = None) -> Path:
    """Write session settings atomically-ish (write then replace)."""
    target = path or settings_path()
    payload = default_settings()
    for key in payload:
        if key in data:
            payload[key] = data[key]
    payload["schema_version"] = _SCHEMA_VERSION
    size = payload.get("size")
    if isinstance(size, tuple):
        payload["size"] = list(size)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return target
