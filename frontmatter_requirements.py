"""Frontmatter-Vorlage aus `app_config.json` und Platzhalter-Auflösung.

SSOT für `frontmatter_requirements` / `frontmatter_update_mode`.
Wird von `yaml_engine`, `book_doctor` und der Heal-Aktion genutzt.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import app_config as _app_config_service

DEFAULT_REQUIREMENTS: dict[str, str] = {
    "title": "<h1>",
    "description": "<title>",
    "status": "bookstudio",
}
DEFAULT_UPDATE_MODE = "append_only"
_H1_RE = re.compile(r"^#\s+(.*)$", re.MULTILINE)


def load_frontmatter_settings(
    config_path: Path | None = None,
) -> tuple[dict[str, str], str]:
    """Liest Vorlage und Modus aus der App-Config (mit Defaults)."""
    config_path = config_path or Path(__file__).parent / "app_config.json"
    required_fields = dict(DEFAULT_REQUIREMENTS)
    update_mode = DEFAULT_UPDATE_MODE
    try:
        config_data = _app_config_service.load_validated_config(config_path)
        raw = config_data.get("frontmatter_requirements")
        if isinstance(raw, dict):
            required_fields = {str(k): str(v) for k, v in raw.items()}
        update_mode = str(
            config_data.get("frontmatter_update_mode", update_mode)
        ).strip().lower()
    except (OSError, ValueError, TypeError):
        pass
    return required_fields, update_mode


def ordered_frontmatter_keys(required_fields: dict[str, str]) -> list[str]:
    """title zuerst, danach übrige Keys in Config-Reihenfolge."""
    keys = list(required_fields.keys())
    if "title" in keys:
        keys.remove("title")
        keys.insert(0, "title")
    return keys


def extract_h1_from_body(body: str) -> str | None:
    """Erste Markdown-H1 aus dem Body (ohne Frontmatter)."""
    match = _H1_RE.search(body or "")
    if not match:
        return None
    title = match.group(1).strip()
    return title or None


def resolve_frontmatter_placeholder(
    template: str,
    *,
    filepath: Path,
    body: str,
    parsed_yaml: dict[str, Any] | None,
    value_map: dict[str, str],
    fallback_title: str | None = None,
) -> str:
    """Löst `<filename>`, `<h1>`, `<title>` oder Literal aus der Config auf."""
    parsed_yaml = parsed_yaml or {}
    stem_fallback = fallback_title if fallback_title else filepath.stem

    if template == "<filename>":
        return stem_fallback
    if template == "<h1>":
        return extract_h1_from_body(body) or stem_fallback
    if template == "<title>":
        return (
            str(value_map.get("title"))
            if value_map.get("title")
            else str(parsed_yaml.get("title") or stem_fallback)
        )
    return template
