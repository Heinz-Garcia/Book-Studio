"""Scanner für GrammarGraph-Lieferungen mit UUID."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import app_config as _app_config
from tools.production_paths.paths import target_inbox_dir
from tools.production_uuid import normalize_uuid
from tools.uuid_manager.batch_completeness import batch_is_fully_complete
from tools.uuid_manager.model import DeliveryRecord

# Stable namespace for synthetic UUIDs of older output batches without
# ``_run_identity.json`` (uuid5 over resolved batch path).
_GG_OUTPUT_UUID_NS = uuid.UUID("6b0c5e2a-4d91-4f3a-9c8e-1a2b3c4d5e6f")


def _configured_inbox_root(book_studio_repo: Path) -> Path:
    try:
        cfg = _app_config.read_config(book_studio_repo / "app_config.json")
    except (OSError, TypeError, ValueError):
        cfg = {}
    raw = str(cfg.get("grammargraph_inbox_path") or "").strip()
    if raw:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (book_studio_repo / candidate).resolve()
        return candidate.resolve()
    return target_inbox_dir(repo=book_studio_repo)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_publish_meta(path: Path) -> dict:
    return _read_json(path)


def _mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return ""


def _synthetic_run_uuid(batch_dir: Path) -> str:
    """Deterministic UUID for legacy batches without ``_run_identity.json``."""
    key = str(batch_dir.resolve()).casefold().replace("\\", "/")
    return str(uuid.uuid5(_GG_OUTPUT_UUID_NS, key))


def _record_from_publish_dir(path: Path, *, source_kind: str) -> DeliveryRecord | None:
    meta = _read_publish_meta(path / "publish_meta.json")
    uid = normalize_uuid(meta.get("uuid"))
    if not uid:
        return None
    return DeliveryRecord(
        uuid=uid,
        publish_dir=path.resolve(),
        book_title=str(meta.get("book_title") or meta.get("name") or path.name),
        batch_id=str(meta.get("batch_id") or ""),
        created_at=str(meta.get("created_at") or ""),
        description=str(meta.get("description") or ""),
        source_kind=source_kind,
        market_variant=str(meta.get("market_variant") or "").strip().lower(),
        run_uuid=normalize_uuid(meta.get("run_uuid")) or "",
    )


def _scan_inbox(root: Path) -> list[DeliveryRecord]:
    records: list[DeliveryRecord] = []
    if not root.is_dir():
        return records
    for meta_file in root.rglob("publish_meta.json"):
        rec = _record_from_publish_dir(meta_file.parent, source_kind="inbox")
        if rec is not None:
            records.append(rec)
    return records


def _scan_legacy_publish(roots: Iterable[Path]) -> list[DeliveryRecord]:
    seen: set[Path] = set()
    out: list[DeliveryRecord] = []
    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if not child.name.startswith("Publish_") and not (
                child / "publish_meta.json"
            ).is_file():
                continue
            resolved = child.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            rec = _record_from_publish_dir(resolved, source_kind="legacy_publish")
            if rec is not None:
                out.append(rec)
    return out


def _batch_title(batch_dir: Path, vorgabe: dict[str, Any], metrics: dict[str, Any]) -> str:
    title = str(
        vorgabe.get("project_path") or metrics.get("batch_id") or batch_dir.name
    ).strip()
    if title:
        try:
            title = Path(title).name or title
        except (TypeError, ValueError):
            pass
    return title or batch_dir.name


def _record_from_output_batch(batch_dir: Path) -> DeliveryRecord | None:
    """Fully complete GG output folder → DeliveryRecord.

    Incomplete batches are skipped. UUID preference:
    ``publish_meta.uuid`` → ``_run_identity`` / vorgabe ``run_uuid`` →
    deterministic uuid5 from batch path (legacy folders without identity).
    """
    if (batch_dir / "publish_meta.json").is_file():
        return _record_from_publish_dir(batch_dir, source_kind="gg_output")

    if not batch_is_fully_complete(batch_dir):
        return None

    identity = _read_json(batch_dir / "_run_identity.json")
    vorgabe = _read_json(batch_dir / "_batch_vorgabe.json")
    metrics = _read_json(batch_dir / "metrics.json")
    run_uuid = normalize_uuid(
        identity.get("run_uuid") or vorgabe.get("run_uuid") or metrics.get("run_uuid")
    )
    if not run_uuid:
        run_uuid = _synthetic_run_uuid(batch_dir)

    created = str(metrics.get("generated_at") or "").strip() or _mtime_iso(batch_dir)
    market = str(vorgabe.get("market_variant") or "").strip().lower()
    has_identity_file = (batch_dir / "_run_identity.json").is_file()
    description = (
        "GrammarGraph-Output (vollständig, noch nicht publiziert)."
        if has_identity_file
        else (
            "GrammarGraph-Output (vollständig, ohne _run_identity.json; "
            "UUID synthetisch aus Batch-Pfad)."
        )
    )

    return DeliveryRecord(
        uuid=run_uuid,
        publish_dir=batch_dir.resolve(),
        book_title=_batch_title(batch_dir, vorgabe, metrics),
        batch_id=batch_dir.name,
        created_at=created,
        description=description,
        source_kind="gg_output",
        market_variant=market,
        run_uuid=run_uuid,
    )


def _scan_output_batches(output_root: Path) -> list[DeliveryRecord]:
    """Scan ``GrammarGraph/output/*`` — only fully complete batches."""
    records: list[DeliveryRecord] = []
    if not output_root.is_dir():
        return records
    try:
        children = list(output_root.iterdir())
    except OSError:
        return records
    for child in children:
        if not child.is_dir():
            continue
        rec = _record_from_output_batch(child)
        if rec is not None:
            records.append(rec)
    return records


def scan_deliveries(
    *,
    book_studio_repo: Path,
    grammargraph_repo: Path | None = None,
) -> list[DeliveryRecord]:
    """Liest GG-Lieferungen (Inbox/Publish) und vollständige Output-Batches."""
    records = _scan_inbox(_configured_inbox_root(book_studio_repo))
    if grammargraph_repo is not None:
        gg = Path(grammargraph_repo)
        records.extend(_scan_legacy_publish([gg / "Publish", gg / "output"]))
        records.extend(_scan_output_batches(gg / "output"))

    by_uuid: dict[str, DeliveryRecord] = {}

    def _rank(rec: DeliveryRecord) -> int:
        if rec.source_kind == "inbox":
            return 3
        if rec.source_kind == "legacy_publish":
            return 2
        if rec.source_kind == "gg_output":
            return 1
        return 0

    for rec in sorted(records, key=lambda r: (r.created_at, r.book_title), reverse=True):
        existing = by_uuid.get(rec.uuid)
        if existing is None or _rank(rec) > _rank(existing):
            by_uuid[rec.uuid] = rec

    published_run = {
        r.run_uuid.casefold()
        for r in by_uuid.values()
        if r.run_uuid and r.source_kind in {"inbox", "legacy_publish"}
    }
    filtered: list[DeliveryRecord] = []
    for rec in by_uuid.values():
        if (
            rec.source_kind == "gg_output"
            and rec.run_uuid
            and rec.run_uuid.casefold() in published_run
            and rec.uuid.casefold() == rec.run_uuid.casefold()
        ):
            continue
        filtered.append(rec)
    return filtered


__all__ = ["scan_deliveries"]
