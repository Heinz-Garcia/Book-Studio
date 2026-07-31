"""SSOT: Frontmatter-Bool-Felder als Editor-Toggles.

Bekannte Keys (immer im YAML-Bereich des Markdown-Editors) plus dynamisch
jedes weitere true/false-Feld aus dem aktuellen Frontmatter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import frontmatter_parser
import yaml

from chapter_title_render import (
    apply_print_title_to_content,
    content_prints_chapter_title,
)
from page_required import apply_required_to_content, content_explicitly_required


@dataclass(frozen=True)
class BoolToggleSpec:
    key: str
    button_label: str
    tooltip: str
    known: bool = True


# Reihenfolge = Anzeige im Editor. Labels kurz (Toolbar-Platz).
KNOWN_BOOL_TOGGLES: tuple[BoolToggleSpec, ...] = (
    BoolToggleSpec(
        key="required",
        button_label="📌",
        tooltip=(
            "required — Pflicht-/Rahmenseite.\n"
            "An = required: true · Aus = Feld entfernt."
        ),
    ),
    BoolToggleSpec(
        key="print_title",
        button_label="H1",
        tooltip=(
            "print_title — Kapitelüberschrift im PDF.\n"
            "An = YAML-title erscheint beim Rendern · "
            "Aus = nur Studio/Baum (Vakat, Cover, …)."
        ),
    ),
    BoolToggleSpec(
        key="unnumbered",
        button_label="#–",
        tooltip=(
            "unnumbered — ohne Kapitelnummer.\n"
            "An = unnumbered: true · Aus = unnumbered: false."
        ),
    ),
    BoolToggleSpec(
        key="unlisted",
        button_label="☰–",
        tooltip=(
            "unlisted — nicht im Inhaltsverzeichnis und nicht im\n"
            "PDF-Lesezeichen-Panel (Titel bleibt auf der Seite sichtbar).\n"
            "An = unlisted: true · Aus = unlisted: false."
        ),
    ),
)

_KNOWN_KEYS = frozenset(spec.key for spec in KNOWN_BOOL_TOGGLES)


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "yes", "1", "on", "ja"):
            return True
        if text in ("false", "no", "0", "off", "nein"):
            return False
    return None


def parse_frontmatter_mapping(content: str) -> dict[str, Any]:
    parts = frontmatter_parser.parse(content or "")
    if not parts.has_frontmatter:
        return {}
    data = parts.parsed()
    return data if isinstance(data, dict) else {}


def discover_extra_bool_keys(content: str) -> list[str]:
    """Weitere Bool-Keys im Frontmatter (nicht in KNOWN), sortiert."""
    data = parse_frontmatter_mapping(content)
    extras = [
        str(key)
        for key, value in data.items()
        if str(key) not in _KNOWN_KEYS and _as_bool(value) is not None
    ]
    return sorted(extras)


def list_bool_toggle_specs(content: str) -> list[BoolToggleSpec]:
    """Bekannte Toggles (feste Reihenfolge) + entdeckte Extra-Bools."""
    specs = list(KNOWN_BOOL_TOGGLES)
    for key in discover_extra_bool_keys(content):
        specs.append(
            BoolToggleSpec(
                key=key,
                button_label=key[:6],
                tooltip=f"{key} — Frontmatter true/false umschalten.",
                known=False,
            )
        )
    return specs


def effective_bool(content: str, key: str) -> bool:
    """Aktueller Schalterzustand für die UI."""
    if key == "required":
        return content_explicitly_required(content)
    if key == "print_title":
        return content_prints_chapter_title(content)
    data = parse_frontmatter_mapping(content)
    flag = _as_bool(data.get(key))
    return bool(flag) if flag is not None else False


def apply_bool_to_content(content: str, key: str, value: bool) -> str:
    """Setzt ein Bool-Feld; ``required`` / ``print_title`` über bestehende SSOT."""
    if key == "required":
        return apply_required_to_content(content, bool(value))
    if key == "print_title":
        return apply_print_title_to_content(content, bool(value))

    parts = frontmatter_parser.parse(content or "")
    newline = "\r\n" if "\r\n" in (content or "") else "\n"
    wanted = bool(value)

    if not parts.has_frontmatter:
        header = yaml.safe_dump(
            {key: wanted},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).rstrip("\r\n")
        body = parts.body if parts.body is not None else (content or "")
        return (
            parts.bom + "---" + newline + header + newline + "---" + newline + body
        )

    data = parts.parsed()
    if not isinstance(data, dict):
        data = {}
    if data.get(key) is wanted:
        return content
    data[key] = wanted
    header_text = yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).rstrip("\r\n")
    return (
        parts.bom
        + "---"
        + newline
        + header_text
        + newline
        + "---"
        + newline
        + parts.body
    )


def toggle_bool_in_content(content: str, key: str) -> tuple[str, bool]:
    new_state = not effective_bool(content, key)
    return apply_bool_to_content(content, key, new_state), new_state


def toggle_keys_signature(content: str) -> tuple[str, ...]:
    """Signatur der sichtbaren Toggle-Keys (für UI-Rebuild nur bei Änderung)."""
    return tuple(spec.key for spec in list_bool_toggle_specs(content))


__all__ = [
    "BoolToggleSpec",
    "KNOWN_BOOL_TOGGLES",
    "apply_bool_to_content",
    "discover_extra_bool_keys",
    "effective_bool",
    "list_bool_toggle_specs",
    "parse_frontmatter_mapping",
    "toggle_bool_in_content",
    "toggle_keys_signature",
]
