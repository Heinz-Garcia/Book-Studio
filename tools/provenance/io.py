"""Lesen/Schreiben von bookconfig/grammargraph_export.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from tools.provenance.schema import BOOKCONFIG_DIR, PROVENANCE_FILENAME, SCHEMA_VERSION


def provenance_path(book_path: Path) -> Path:
    return Path(book_path) / BOOKCONFIG_DIR / PROVENANCE_FILENAME


def read_provenance(book_path: Path) -> Optional[dict[str, Any]]:
    path = provenance_path(book_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_provenance(book_path: Path, data: dict[str, Any]) -> Path:
    dest = provenance_path(book_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest
