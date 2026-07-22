"""CRUD für bookconfig/publish_map.json — Produktionslinien (Snapshots → Renders)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tools.publish_map.metadata import provenance_summary, read_book_metadata
from tools.publish_map.schema import (
    BOOKCONFIG_DIR,
    MAP_FILENAME,
    ORIGIN_GRAMMARGRAPH,
    ORIGIN_LOCAL,
    SCHEMA_VERSION,
)
from tools.publish_record.record import read_record


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def publish_map_path(book_path: Path) -> Path:
    return Path(book_path) / BOOKCONFIG_DIR / MAP_FILENAME


def read_map(book_path: Path) -> Optional[dict[str, Any]]:
    path = publish_map_path(book_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_map(book_path: Path, data: dict[str, Any]) -> Path:
    dest = publish_map_path(book_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["updated_at"] = _utc_now_iso()
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def ensure_map(book_path: Path) -> dict[str, Any]:
    existing = read_map(book_path)
    if existing is not None:
        return existing
    now = _utc_now_iso()
    data = {
        "schema_version": SCHEMA_VERSION,
        "book_path": str(Path(book_path).resolve()),
        "created_at": now,
        "updated_at": now,
        "active_snapshot_id": "",
        "snapshots": [],
    }
    write_map(book_path, data)
    return data


def _find_snapshot(data: dict[str, Any], snapshot_id: str) -> Optional[dict[str, Any]]:
    for snap in data.get("snapshots") or []:
        if isinstance(snap, dict) and snap.get("id") == snapshot_id:
            return snap
    return None


def get_active_snapshot(data: dict[str, Any]) -> Optional[dict[str, Any]]:
    snap_id = str(data.get("active_snapshot_id") or "")
    if not snap_id:
        snapshots = data.get("snapshots") or []
        if snapshots and isinstance(snapshots[-1], dict):
            return snapshots[-1]
        return None
    return _find_snapshot(data, snap_id)


def ensure_active_snapshot(book_path: Path, *, origin: str = ORIGIN_LOCAL) -> dict[str, Any]:
    """Stellt sicher, dass mindestens ein Snapshot existiert und aktiv ist."""
    data = ensure_map(book_path)
    snap = get_active_snapshot(data)
    if snap is not None:
        return snap
    meta = read_book_metadata(book_path)
    snap = {
        "id": str(uuid.uuid4()),
        "created_at": _utc_now_iso(),
        "origin": origin,
        "import_path": "",
        "import_run_id": "",
        "book_title": meta.get("title", ""),
        "book_author": meta.get("author", ""),
        "provenance": provenance_summary(book_path),
        "renders": [],
    }
    snapshots = list(data.get("snapshots") or [])
    snapshots.append(snap)
    data["snapshots"] = snapshots
    data["active_snapshot_id"] = snap["id"]
    write_map(book_path, data)
    return snap


def create_import_snapshot(
    book_path: Path,
    *,
    import_path: str = "",
    import_run_id: str = "",
) -> dict[str, Any]:
    """Neuer Snapshot nach GrammarGraph-/CLI-Import."""
    data = ensure_map(book_path)
    meta = read_book_metadata(book_path)
    snap = {
        "id": str(uuid.uuid4()),
        "created_at": _utc_now_iso(),
        "origin": ORIGIN_GRAMMARGRAPH if import_path else ORIGIN_LOCAL,
        "import_path": import_path,
        "import_run_id": import_run_id,
        "book_title": meta.get("title", ""),
        "book_author": meta.get("author", ""),
        "provenance": provenance_summary(book_path),
        "renders": [],
    }
    snapshots = list(data.get("snapshots") or [])
    snapshots.append(snap)
    data["snapshots"] = snapshots
    data["active_snapshot_id"] = snap["id"]
    write_map(book_path, data)
    return snap


def append_render(
    book_path: Path,
    payload: dict[str, Any],
    *,
    snapshot_id: Optional[str] = None,
) -> dict[str, Any]:
    """Hängt einen Render-Lauf am aktiven (oder gewählten) Snapshot an."""
    data = ensure_map(book_path)
    target_id = snapshot_id or str(data.get("active_snapshot_id") or "")
    snap = _find_snapshot(data, target_id) if target_id else None
    if snap is None:
        ensure_active_snapshot(book_path)
        data = read_map(book_path) or ensure_map(book_path)
        target_id = snapshot_id or str(data.get("active_snapshot_id") or "")
        snap = _find_snapshot(data, target_id) if target_id else None
    if snap is None:
        snap = ensure_active_snapshot(book_path)
        data = read_map(book_path) or ensure_map(book_path)
        snap = get_active_snapshot(data)
    if snap is None:
        raise RuntimeError("publish_map: aktiver Snapshot konnte nicht angelegt werden")

    render = {
        "id": str(uuid.uuid4()),
        "at": _utc_now_iso(),
        "format": str(payload.get("format") or ""),
        "target_format": str(payload.get("target_format") or ""),
        "template": str(payload.get("template") or ""),
        "layout_profile": str(payload.get("layout_profile") or ""),
        "profile_name": str(payload.get("profile_name") or ""),
        "artifact_path": str(payload.get("artifact_path") or ""),
        "record_event_id": str(payload.get("record_event_id") or ""),
        "metadata": dict(payload.get("metadata") or {}),
    }
    renders = list(snap.get("renders") or [])
    renders.append(render)
    snap["renders"] = renders
    write_map(book_path, data)
    return render


def _normalize_artifact_key(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    try:
        return str(Path(raw).resolve()).casefold()
    except OSError:
        return raw.casefold()


def _known_render_keys(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    paths: set[str] = set()
    event_ids: set[str] = set()
    for snap in data.get("snapshots") or []:
        if not isinstance(snap, dict):
            continue
        for render in snap.get("renders") or []:
            if not isinstance(render, dict):
                continue
            artifact_key = _normalize_artifact_key(str(render.get("artifact_path") or ""))
            if artifact_key:
                paths.add(artifact_key)
            event_id = str(render.get("record_event_id") or "").strip()
            if event_id:
                event_ids.add(event_id)
    return paths, event_ids


def _append_render_to_snapshot(
    snap: dict[str, Any],
    *,
    at: str,
    payload: dict[str, Any],
    record_event_id: str = "",
) -> None:
    render = {
        "id": str(uuid.uuid4()),
        "at": at or _utc_now_iso(),
        "format": str(payload.get("format") or ""),
        "target_format": str(payload.get("target_format") or ""),
        "template": str(payload.get("template") or ""),
        "layout_profile": str(payload.get("layout_profile") or ""),
        "profile_name": str(payload.get("profile_name") or ""),
        "artifact_path": str(payload.get("artifact_path") or ""),
        "record_event_id": record_event_id,
        "metadata": dict(payload.get("metadata") or {}),
    }
    renders = list(snap.get("renders") or [])
    renders.append(render)
    snap["renders"] = renders


def _merge_record_renders(book_path: Path, data: dict[str, Any]) -> int:
    """Hängt fehlende render_success-Einträge aus publish_record an."""
    record = read_record(book_path)
    if not record:
        return 0
    paths, event_ids = _known_render_keys(data)
    snap = get_active_snapshot(data)
    if snap is None:
        ensure_active_snapshot(book_path)
        fresh = read_map(book_path)
        if not fresh:
            return 0
        data.clear()
        data.update(fresh)
        snap = get_active_snapshot(data)
    if snap is None:
        return 0

    added = 0
    for event in record.get("events") or []:
        if not isinstance(event, dict) or event.get("type") != "render_success":
            continue
        event_id = str(event.get("id") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        artifact_key = _normalize_artifact_key(str(payload.get("artifact_path") or ""))
        if event_id and event_id in event_ids:
            continue
        if artifact_key and artifact_key in paths:
            continue
        _append_render_to_snapshot(
            snap,
            at=str(event.get("at") or _utc_now_iso()),
            payload=payload,
            record_event_id=event_id,
        )
        if event_id:
            event_ids.add(event_id)
        if artifact_key:
            paths.add(artifact_key)
        added += 1
    return added


def backfill_renders_from_disk(book_path: Path) -> int:
    """Ergänzt PDFs aus export/_book*, die noch nicht in publish_map stehen."""
    from tools.generated_books.discovery import find_generated_pdfs

    data = read_map(book_path)
    if data is None:
        data = ensure_map(book_path)
    snap = get_active_snapshot(data)
    if snap is None:
        ensure_active_snapshot(book_path)
        data = read_map(book_path)
        if not data:
            return 0
        snap = get_active_snapshot(data)
    if snap is None:
        return 0

    paths, _event_ids = _known_render_keys(data)
    pdfs = find_generated_pdfs([book_path], max_entries=100)
    added = 0
    for entry in pdfs:
        artifact_key = _normalize_artifact_key(str(entry.path))
        if not artifact_key or artifact_key in paths:
            continue
        at = datetime.fromtimestamp(entry.mtime, timezone.utc).replace(microsecond=0).isoformat()
        _append_render_to_snapshot(
            snap,
            at=at,
            payload={"artifact_path": str(entry.path.resolve())},
        )
        paths.add(artifact_key)
        added += 1
    if added:
        write_map(book_path, data)
    return added


def refresh_publish_map(book_path: Path) -> bool:
    """Synchronisiert publish_map aus Record und Platte (fehlende Renders nachziehen)."""
    changed = sync_map_from_record(book_path)
    data = read_map(book_path)
    if data is None:
        data = ensure_map(book_path)
    merged = _merge_record_renders(book_path, data)
    if merged:
        write_map(book_path, data)
        changed = True
    backfilled = backfill_renders_from_disk(book_path)
    return changed or merged > 0 or backfilled > 0


def remove_render(book_path: Path, snapshot_id: str, render_id: str) -> bool:
    data = read_map(book_path)
    if not data:
        return False
    snap = _find_snapshot(data, snapshot_id)
    if snap is None:
        return False
    before = list(snap.get("renders") or [])
    after = [r for r in before if not (isinstance(r, dict) and r.get("id") == render_id)]
    if len(after) == len(before):
        return False
    snap["renders"] = after
    write_map(book_path, data)
    return True


def sync_map_from_record(book_path: Path) -> bool:
    """Baut publish_map aus publish_record nach, wenn noch keine Snapshots existieren."""
    data = read_map(book_path)
    if data and data.get("snapshots"):
        return False
    record = read_record(book_path)
    if not record:
        return False
    events = record.get("events") or []
    if not events:
        return False

    data = ensure_map(book_path)
    snapshots: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None

    def _new_snap(origin: str, payload: dict) -> dict[str, Any]:
        meta = read_book_metadata(book_path)
        return {
            "id": str(uuid.uuid4()),
            "created_at": payload.get("at") or _utc_now_iso(),
            "origin": origin,
            "import_path": str(payload.get("import_path") or ""),
            "import_run_id": str(payload.get("event_id") or ""),
            "book_title": meta.get("title", ""),
            "book_author": meta.get("author", ""),
            "provenance": provenance_summary(book_path),
            "renders": [],
        }

    for event in events:
        if not isinstance(event, dict):
            continue
        etype = event.get("type")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if etype == "book_import":
            current = _new_snap(
                ORIGIN_GRAMMARGRAPH if payload.get("import_path") else ORIGIN_LOCAL,
                {
                    "import_path": payload.get("import_path", ""),
                    "event_id": event.get("id", ""),
                    "at": event.get("at", ""),
                },
            )
            snapshots.append(current)
        elif etype == "render_success":
            if current is None:
                current = _new_snap(ORIGIN_LOCAL, {"at": event.get("at", "")})
                snapshots.append(current)
            renders = list(current.get("renders") or [])
            renders.append({
                "id": str(uuid.uuid4()),
                "at": event.get("at", _utc_now_iso()),
                "format": payload.get("format", ""),
                "target_format": payload.get("target_format", ""),
                "template": payload.get("template", ""),
                "layout_profile": payload.get("layout_profile", ""),
                "profile_name": payload.get("profile_name", ""),
                "artifact_path": payload.get("artifact_path", ""),
                "record_event_id": event.get("id", ""),
                "metadata": payload.get("metadata") or {},
            })
            current["renders"] = renders

    if not snapshots:
        ensure_active_snapshot(book_path)
        return True
    data["snapshots"] = snapshots
    data["active_snapshot_id"] = snapshots[-1]["id"]
    write_map(book_path, data)
    return True
