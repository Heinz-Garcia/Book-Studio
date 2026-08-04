"""Separates Speichern/Laden nur der Vorderseiten-Elemente (Elementset)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.kdp_cover.compose_front.model import FrontComposeSpec
from tools.kdp_cover.model import cover_export_dir, sanitize_book_filename_stem

ELEMENT_SET_KIND = "kdp_front_elementset"
ELEMENT_SET_VERSION = 1


def default_element_set_filename(title: str, *, book_folder_name: str = "") -> str:
    """Vorschlagsname aus Buchtitel (Fallback: Buchordnername)."""
    stem_src = (title or "").strip() or (book_folder_name or "").strip() or "elementset"
    stem = sanitize_book_filename_stem(stem_src)
    return f"{stem}_elementset.json"


def default_element_set_path(
    book_root: Path,
    *,
    title: str = "",
) -> Path:
    """Kanonischer Pfad unter ``export/kdp_cover/{Titel}_elementset.json``."""
    root = Path(book_root)
    name = default_element_set_filename(title, book_folder_name=root.name)
    return cover_export_dir(root) / name


def element_set_to_dict(front_compose: dict[str, Any] | FrontComposeSpec | None) -> dict[str, Any]:
    if isinstance(front_compose, FrontComposeSpec):
        compose = front_compose.to_dict()
    elif isinstance(front_compose, dict):
        compose = FrontComposeSpec.from_dict(front_compose).to_dict()
    else:
        compose = FrontComposeSpec(enabled=False).to_dict()
    return {
        "kind": ELEMENT_SET_KIND,
        "version": ELEMENT_SET_VERSION,
        "front_compose": compose,
    }


def element_set_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Extrahiert ``front_compose`` aus Elementset-JSON (oder nacktem Compose-Dict)."""
    if not isinstance(data, dict):
        raise ValueError("Elementset-JSON muss ein Objekt sein.")
    if "ok_for_safe_export" in data and "issues" in data:
        raise ValueError(
            "Das ist ein Validierungsbericht, kein Elementset."
        )
    if "page_count" in data and "trim_width_mm" in data:
        raise ValueError(
            "Das ist ein Cover-Layout, kein Elementset. "
            "Bitte „Cover-Layout laden…“ verwenden."
        )
    if "front_compose" in data:
        raw = data.get("front_compose")
        if not isinstance(raw, dict):
            raise ValueError("Elementset: front_compose muss ein Objekt sein.")
        kind = data.get("kind")
        if kind is not None and kind != ELEMENT_SET_KIND:
            raise ValueError(f"Unbekanntes Elementset-Format: kind={kind!r}")
        return FrontComposeSpec.from_dict(raw).to_dict()
    # Nacktes Compose-Objekt (ohne Wrapper) — z. B. manuell kopiert.
    if "enabled" in data or "fade" in data or "band" in data or "titles" in data:
        return FrontComposeSpec.from_dict(data).to_dict()
    raise ValueError(
        "Keine Elementset-Daten gefunden. Erwartet: *_elementset.json "
        f"mit kind={ELEMENT_SET_KIND!r}."
    )


def save_element_set(
    front_compose: dict[str, Any] | FrontComposeSpec | None,
    path: Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = element_set_to_dict(front_compose)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_element_set(path: Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Elementset-JSON muss ein Objekt sein.")
    return element_set_from_dict(raw)


__all__ = [
    "ELEMENT_SET_KIND",
    "ELEMENT_SET_VERSION",
    "default_element_set_filename",
    "default_element_set_path",
    "element_set_to_dict",
    "element_set_from_dict",
    "save_element_set",
    "load_element_set",
]
