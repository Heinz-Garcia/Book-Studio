"""Persist Breathcloud dialog fields (own SSOT — never overwrite from freeForm).

Source path/mode may come from the Stylecloud ``freeForm`` preset (once).
Word count, fonts, hub, and gradient live here so opening the dialog cannot
silently replace the user's numbers with preset values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SCHEMA = 1
_FILENAME = "last_session.json"


def session_path() -> Path:
    return Path(__file__).resolve().parent / _FILENAME


def default_session() -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA,
        "hub_word": "",
        "hub_font_size": 120,
        "max_font_size": 72,
        "max_words": 200,
        "gradient": ["#1e5f8a", "#2ec4b6", "#c8f542"],
        "output_path": "",
    }


def load_session(path: Path | None = None) -> dict[str, Any]:
    """Return stored overrides only. Empty dict if no session file yet."""
    target = path or session_path()
    if not target.is_file():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    allowed = set(default_session())
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key in allowed and key != "schema_version":
            out[key] = value
    return out


def save_session(data: dict[str, Any], path: Path | None = None) -> Path:
    target = path or session_path()
    payload = default_session()
    for key in payload:
        if key in data:
            payload[key] = data[key]
    payload["schema_version"] = _SCHEMA
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def resolve_ui_defaults(
    *,
    freeform_preset: dict[str, Any] | None,
    style_session: dict[str, Any] | None,
    breath_session: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge defaults for the dialog.

    - Source / canvas size / stopwords: freeForm, then Stylecloud session.
    - max_words / fonts / hub / gradient: Breathcloud session, then Stylecloud
      session — **never** freeForm ``max_words`` (that was overwriting the UI).
    """
    preset = freeform_preset or {}
    style = style_session or {}
    breath = breath_session or {}

    def _first(*values: Any, default: Any = None) -> Any:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
        return default

    size = preset.get("size") or style.get("size") or [1594, 2539]
    hub = _first(breath.get("hub_word"), style.get("must_word"), default="")
    # Intentionally skip preset["max_words"] — freeForm must not clobber this.
    max_words = _first(
        breath.get("max_words") if "max_words" in breath else None,
        style.get("max_words"),
        default=200,
    )
    hub_size = _first(
        breath.get("hub_font_size") if "hub_font_size" in breath else None,
        style.get("must_word_font_size"),
        style.get("user_font_size"),
        default=120,
    )
    max_font = _first(
        breath.get("max_font_size") if "max_font_size" in breath else None,
        style.get("user_font_size"),
        style.get("max_font_size"),
        default=72,
    )
    grad = breath.get("gradient")
    if not isinstance(grad, list) or len(grad) < 2:
        grad = ["#1e5f8a", "#2ec4b6", "#c8f542"]

    return {
        "source_mode": str(
            _first(preset.get("source_mode"), style.get("source_mode"), default="book")
        ),
        "source_path": str(
            _first(preset.get("source_path"), style.get("source_path"), default="") or ""
        ),
        "output_path": str(
            _first(breath.get("output_path"), style.get("output_path"), default="") or ""
        ),
        "hub_word": str(hub or ""),
        "hub_font_size": int(hub_size),
        "max_font_size": int(max_font),
        "max_words": int(max_words),
        "gradient": [str(c) for c in grad[:3]],
        "use_german_stopwords": bool(
            preset.get(
                "use_german_stopwords",
                style.get("use_german_stopwords", True),
            )
        ),
        "size": size,
    }
