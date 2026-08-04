"""Scanner für GrammarGraph-Lieferungen mit UUID."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import app_config as _app_config
from tools.production_paths.paths import target_inbox_dir
from tools.production_uuid import normalize_uuid
from tools.uuid_manager.model import DeliveryRecord


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


def _read_publish_meta(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


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
            if not child.name.startswith("Publish_") and not (child / "publish_meta.json").is_file():
                continue
            resolved = child.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            rec = _record_from_publish_dir(resolved, source_kind="legacy_publish")
            if rec is not None:
                out.append(rec)
    return out


def scan_deliveries(
    *,
    book_studio_repo: Path,
    grammargraph_repo: Path | None = None,
) -> list[DeliveryRecord]:
    """Liest GG-Lieferungen aus Book-Studio-Inbox und optional Legacy-Publish."""
    records = _scan_inbox(_configured_inbox_root(book_studio_repo))
    if grammargraph_repo is not None:
        roots = [grammargraph_repo / "Publish", grammargraph_repo / "output"]
        records.extend(_scan_legacy_publish(roots))
    dedup: dict[str, DeliveryRecord] = {}
    for rec in sorted(records, key=lambda r: r.created_at, reverse=True):
        dedup.setdefault(rec.uuid, rec)
    return list(dedup.values())


__all__ = ["scan_deliveries"]
