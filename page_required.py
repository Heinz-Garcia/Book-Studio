"""SSOT: Seiten-„Requiredness“ (Rahmen/Pflichtseite).

Regel (Frontmatter und Manifest):
- ``required: true``  → Pflicht (Populate mitkopieren; Order/📌-fähig)
- ``required: false`` oder Feld fehlt → nicht Pflicht

Legacy-Fallback für bestehende Bücher: liegt die Datei unter
``content/required/`` und hat *kein* explizites ``required``-Feld,
gilt sie weiterhin als required (Pfad-Konvention).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

import frontmatter_parser


def coerce_required_flag(value: Any) -> bool:
    """YAML-/Manifest-Wert → bool."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    if text in ("true", "yes", "1", "on"):
        return True
    if text in ("false", "no", "0", "off", ""):
        return False
    return bool(value)


def required_from_mapping(data: Optional[Mapping[str, Any]]) -> Optional[bool]:
    """Liest ``required`` aus einem Mapping. ``None``, wenn Schlüssel fehlt."""
    if not isinstance(data, dict) or "required" not in data:
        return None
    return coerce_required_flag(data.get("required"))


def path_in_required_folder(rel_path: str) -> bool:
    parts = [p.lower() for p in str(rel_path).replace("\\", "/").split("/") if p]
    return "required" in parts


def is_page_required(
    *,
    rel_path: str,
    frontmatter: Optional[Mapping[str, Any]] = None,
    content: Optional[str] = None,
) -> bool:
    """Entscheidet Requiredness für eine Buch-/Vorlagen-Datei.

    1. Explizites Frontmatter-``required`` gewinnt.
    2. Sonst Legacy: Pfad enthält Ordner ``required``.
    3. Sonst ``False``.
    """
    fm = frontmatter
    if fm is None and content is not None:
        parts = frontmatter_parser.parse(content)
        if parts.has_frontmatter:
            parsed = parts.parsed()
            if isinstance(parsed, dict):
                fm = parsed
    explicit = required_from_mapping(fm if isinstance(fm, dict) else None)
    if explicit is not None:
        return explicit
    return path_in_required_folder(rel_path)


def is_page_required_at(book_or_profile_root: Path, rel_path: str) -> bool:
    """Liest Datei unter ``root/rel_path`` und wertet Requiredness aus."""
    root = Path(book_or_profile_root)
    rel = str(rel_path).replace("\\", "/")
    full = root / rel
    content: Optional[str] = None
    if full.is_file():
        try:
            content = full.read_text(encoding="utf-8")
        except OSError:
            content = None
    return is_page_required(rel_path=rel, content=content)


def book_has_required_pages(book_path: Path) -> bool:
    """True, wenn das Buch mindestens eine required-Seite hat.

    Primär Frontmatter ``required: true``; Legacy: Dateien unter
    ``content/required/*.md``.
    """
    book = Path(book_path)
    legacy_dir = book / "content" / "required"
    if legacy_dir.is_dir() and any(legacy_dir.glob("*.md")):
        # Schneller Legacy-Pfad: Ordner vorhanden → Soft-UX nicht erneut anbieten.
        # Explizites required:false in einzelnen Dateien ändert den Soft-Hint nicht
        # (Import-Hinweis nur „noch keine Rahmen-Seiten“).
        return True
    content_root = book / "content"
    if not content_root.is_dir():
        return False
    for path in content_root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        parts = frontmatter_parser.parse(text)
        if not parts.has_frontmatter:
            continue
        data = parts.parsed()
        if required_from_mapping(data if isinstance(data, dict) else None) is True:
            return True
    return False


def entry_required_from_manifest_item(item: Mapping[str, Any]) -> bool:
    """Manifest-Zeile → required-Flag.

    - ``required:`` gesetzt → dieser Wert
    - sonst Legacy ``optional:`` → ``not optional``
    - sonst ``True`` (alte Profile behandelten Einträge ohne Flag als Pflicht)
    """
    if "required" in item:
        return coerce_required_flag(item.get("required"))
    if "optional" in item:
        return not coerce_required_flag(item.get("optional"))
    return True


def content_explicitly_required(content: str) -> bool:
    """True nur bei explizitem Frontmatter ``required: true`` (kein Pfad-Legacy)."""
    parts = frontmatter_parser.parse(content)
    if not parts.has_frontmatter:
        return False
    data = parts.parsed()
    return required_from_mapping(data if isinstance(data, dict) else None) is True


def apply_required_to_content(content: str, required: bool) -> str:
    """Setzt oder entfernt Frontmatter ``required`` im Markdown-Text.

    ``required=True`` → ``required: true``.
    ``required=False`` → Schlüssel entfernen (fehlendes Feld = nicht required).
    Fehlt Frontmatter und ``required=True``, wird ein minimaler Block angelegt.
    """
    import yaml

    parts = frontmatter_parser.parse(content)
    newline = "\r\n" if "\r\n" in content else "\n"

    if not parts.has_frontmatter:
        if not required:
            return content
        header = yaml.safe_dump(
            {"required": True},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).rstrip("\r\n")
        body = parts.body if parts.body is not None else content
        if body and not body.startswith(("\n", "\r")):
            # Body ohne führendes Newline nach --- beibehalten
            pass
        return (
            parts.bom
            + "---"
            + newline
            + header
            + newline
            + "---"
            + newline
            + body
        )

    data = parts.parsed()
    if not isinstance(data, dict):
        data = {}

    if required:
        if data.get("required") is True:
            return content
        data["required"] = True
    else:
        if "required" not in data:
            return content
        data.pop("required", None)

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


def toggle_required_in_content(content: str) -> tuple[str, bool]:
    """Invertiert explizites ``required``. Liefert ``(neuer_text, neuer_zustand)``."""
    new_state = not content_explicitly_required(content)
    return apply_required_to_content(content, new_state), new_state


__all__ = [
    "apply_required_to_content",
    "book_has_required_pages",
    "coerce_required_flag",
    "content_explicitly_required",
    "entry_required_from_manifest_item",
    "is_page_required",
    "is_page_required_at",
    "path_in_required_folder",
    "required_from_mapping",
    "toggle_required_in_content",
]
