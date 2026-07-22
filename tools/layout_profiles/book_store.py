"""Buchspezifische Layout-Profil-Overrides (bookconfig/layout_profile.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from tools.layout_profiles.catalog import DEFAULT_LAYOUT_PROFILE_ID, normalize_linestretch

BOOKCONFIG_DIR = "bookconfig"
OVERRIDE_FILENAME = "layout_profile.json"


def override_path(book_path: Path) -> Path:
    return Path(book_path) / BOOKCONFIG_DIR / OVERRIDE_FILENAME


def read_book_layout_override(book_path: Path) -> Optional[dict[str, Any]]:
    path = override_path(book_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_book_layout_override(
    book_path: Path,
    *,
    layout_profile: str,
    linestretch: float,
) -> Path:
    dest = override_path(book_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "layout_profile": layout_profile,
        "linestretch": normalize_linestretch(linestretch),
    }
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def resolve_export_layout_defaults(
    book_path: Optional[Path],
    session_options: dict[str, Any],
    app_defaults: dict[str, Any],
) -> dict[str, Any]:
    """Kaskade: App-Default → Buch-Override → Session (zuletzt gewählt)."""
    profile_id = str(app_defaults.get("layout_profile") or DEFAULT_LAYOUT_PROFILE_ID)
    linestretch = app_defaults.get("linestretch")

    if book_path is not None:
        book_override = read_book_layout_override(book_path)
        if book_override:
            profile_id = str(book_override.get("layout_profile") or profile_id)
            if book_override.get("linestretch") is not None:
                linestretch = book_override.get("linestretch")

    if session_options.get("layout_profile"):
        profile_id = str(session_options["layout_profile"])
    if session_options.get("linestretch") is not None:
        linestretch = session_options.get("linestretch")

    if linestretch is None:
        linestretch = get_profile_default_stretch(profile_id)

    return {
        "layout_profile": profile_id,
        "linestretch": normalize_linestretch(linestretch),
    }


def get_profile_default_stretch(profile_id: str) -> float:
    from tools.layout_profiles.catalog import get_profile

    return get_profile(profile_id).linestretch
