"""Anzeigename für Buchprojekte (bookconfig/project_label.json)."""

from __future__ import annotations

import json
from pathlib import Path

_LABEL_REL = Path("bookconfig") / "project_label.json"


def label_file(book_path: Path) -> Path:
    return Path(book_path) / _LABEL_REL


def read_display_name(book_path: Path) -> str:
    """Gespeicherter Anzeigename — leer, wenn noch nie vergeben."""
    path = label_file(book_path)
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("display_name") or "").strip()


def write_display_name(book_path: Path, display_name: str) -> None:
    """Schreibt oder löscht den Anzeigenamen (leerer String → Datei entfernen)."""
    book = Path(book_path)
    path = label_file(book)
    name = str(display_name or "").strip()
    if not name:
        if path.is_file():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"display_name": name}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


__all__ = ["label_file", "read_display_name", "write_display_name"]
