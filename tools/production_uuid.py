"""Production-UUID eines GrammarGraph-Exports am Buch lesen.

SSOT-Reihenfolge:
1. ``publish_meta.json`` (Top-Level ``uuid``)
2. ``bookconfig/grammargraph_export.json`` (Top-Level oder ``content.uuid``)
3. ``_book_studio.toml`` (``book.uuid`` oder ``metadata.uuid``)
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Optional
from uuid import UUID

from tools.provenance.io import read_provenance

# Sentinel im PDF-Custom-Feld, wenn keine Production-UUID am Buch vorliegt.
UUID_MISSING = "n/a"

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def normalize_uuid(value: object) -> Optional[str]:
    """Gibt eine kanonische UUID-Zeichenkette zurück oder ``None``."""
    text = str(value or "").strip()
    if not text or not _UUID_RE.match(text):
        return None
    try:
        return str(UUID(text))
    except ValueError:
        return None


def _from_publish_meta(book_root: Path) -> Optional[str]:
    path = book_root / "publish_meta.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    return normalize_uuid(data.get("uuid"))


def _from_provenance(book_root: Path) -> Optional[str]:
    data = read_provenance(book_root)
    if not data:
        return None
    top = normalize_uuid(data.get("uuid"))
    if top:
        return top
    content = data.get("content")
    if isinstance(content, dict):
        return normalize_uuid(content.get("uuid"))
    return None


def _from_book_studio_toml(book_root: Path) -> Optional[str]:
    path = book_root / "_book_studio.toml"
    if not path.is_file():
        return None
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    book = raw.get("book")
    if isinstance(book, dict):
        found = normalize_uuid(book.get("uuid"))
        if found:
            return found
    meta = raw.get("metadata")
    if isinstance(meta, dict):
        return normalize_uuid(meta.get("uuid"))
    return None


def read_book_uuid(book_root: Path | str) -> Optional[str]:
    """Liest die Production-UUID des Buchs oder ``None`` wenn unbekannt."""
    root = Path(book_root)
    if not root.is_dir():
        return None
    for reader in (_from_publish_meta, _from_provenance, _from_book_studio_toml):
        found = reader(root)
        if found:
            return found
    return None


def pdf_uuid_value(book_root: Path | str) -> str:
    """Wert für PDF-Feld ``UUID``: echte UUID oder ``UUID_MISSING`` (``n/a``)."""
    return read_book_uuid(book_root) or UUID_MISSING


__all__ = ["UUID_MISSING", "normalize_uuid", "read_book_uuid", "pdf_uuid_value"]
