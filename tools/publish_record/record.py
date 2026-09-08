"""CRUD für bookconfig/publish_record.json."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import json_io
from tools.publish_record.schema import BOOKCONFIG_DIR, RECORD_FILENAME, SCHEMA_VERSION

_LOG = logging.getLogger(__name__)


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
    """Schreibt das Protokoll -- atomar (siehe ``json_io``).

    ``append_event`` liest die ganze Datei, haengt einen Eintrag an und
    schreibt alles zurueck. Je laenger die Historie, desto groesser das
    Zeitfenster, in dem ein Abbruch eine halbe Datei hinterlaesst -- und dieses
    Protokoll ist zugleich die Quelle, aus der ``publish_map`` sich
    wiederherstellen kann (``sync_map_from_record``).
    """
    dest = publish_record_path(book_path)
    payload = dict(data)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["updated_at"] = _utc_now_iso()
    json_io.write_json_atomic(dest, payload, indent=2)
    return dest


def ensure_record(book_path: Path) -> dict[str, Any]:
    existing = read_record(book_path)
    if existing is not None:
        return existing
    # Eine vorhandene, aber unlesbare Datei wird gesichert statt ersetzt. Das
    # wiegt hier schwerer als bei ``publish_map``: Dort zieht
    # ``refresh_publish_map`` die Renderausgaben notfalls nach -- unter anderem
    # aus **diesem** Protokoll. Verschwindet es wortlos, verschwindet auch die
    # Rettung.
    beschaedigt = json_io.quarantine_corrupt(publish_record_path(book_path))
    if beschaedigt is not None:
        _LOG.warning(
            "publish_record.json war unlesbar und wurde gesichert: %s", beschaedigt
        )
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


#: Wie viele Ereignisse das Protokoll höchstens behält.
#:
#: ``append_event`` liest die ganze Datei, hängt an und schreibt alles zurück.
#: Ohne Obergrenze wächst dieser Vorgang mit jedem Import, jeder Doktor-Prüfung
#: und jedem Render — und mit ihm das Zeitfenster für einen abgebrochenen
#: Schreibvorgang. 2000 Einträge sind für jedes reale Buchprojekt weit mehr als
#: seine Lebensgeschichte und bleiben trotzdem eine Datei, die man öffnen kann.
MAX_EVENTS = 2000


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
    if len(events) > MAX_EVENTS:
        # Die ältesten fallen heraus, und dass sie es taten, steht in der Datei.
        # Stillschweigend zu kürzen hiesse, ein Protokoll zu führen, das über
        # sich selbst schweigt.
        entfernt = len(events) - MAX_EVENTS
        events = events[entfernt:]
        record["truncated_events"] = int(record.get("truncated_events") or 0) + entfernt
        record["truncated_at"] = _utc_now_iso()
    record["events"] = events
    write_record(book_path, record)
    return event
