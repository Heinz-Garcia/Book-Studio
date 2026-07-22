"""CRUD für bookconfig/publish_record.json."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tools.publish_record.schema import BOOKCONFIG_DIR, RECORD_FILENAME, SCHEMA_VERSION


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def publish_record_path(book_path: Path) -> Path:
    return Path(book_path) / BOOKCONFIG_DIR / RECORD_FILENAME


def read_record(book_path: Path) -> Optional[dict[str, Any]]:
    path = publish_record_path(book_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_record(book_path: Path, data: dict[str, Any]) -> Path:
    dest = publish_record_path(book_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["updated_at"] = _utc_now_iso()
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def ensure_record(book_path: Path) -> dict[str, Any]:
    existing = read_record(book_path)
    if existing is not None:
        return existing
    now = _utc_now_iso()
    record = {
        "schema_version": SCHEMA_VERSION,
        "book_path": str(Path(book_path).resolve()),
        "created_at": now,
        "updated_at": now,
        "events": [],
    }
    write_record(book_path, record)
    return record


def append_event(
    book_path: Path,
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Hängt ein Ereignis an und speichert publish_record.json."""
    record = ensure_record(book_path)
    event = {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "at": _utc_now_iso(),
        "payload": dict(payload or {}),
    }
    events = list(record.get("events") or [])
    events.append(event)
    record["events"] = events
    write_record(book_path, record)
    return event
