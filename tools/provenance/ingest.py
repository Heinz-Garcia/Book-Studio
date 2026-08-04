"""Provenance-Ingest beim Buch-Import."""

from __future__ import annotations

import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tools.provenance.io import provenance_path, read_provenance, write_provenance
from tools.provenance.schema import MANIFEST_CANDIDATES, SCHEMA_VERSION


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def find_manifest_in_dir(source_dir: Path) -> Optional[Path]:
    """Sucht grammargraph_export.json o. ä. im Import-Verzeichnis."""
    root = Path(source_dir)
    if not root.is_dir():
        return None
    for rel in MANIFEST_CANDIDATES:
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def _load_json_file(path: Path) -> Optional[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def synthesize_from_book_studio_toml(source_dir: Path) -> dict[str, Any]:
    """Fallback-Manifest aus _book_studio.toml (wie import_helpers)."""
    cfg_file = Path(source_dir) / "_book_studio.toml"
    title = Path(source_dir).name
    author = ""
    production_uuid = ""
    market_variant = ""
    variant_anchor_ids: list[str] = []
    variant_system_prompt_path = ""
    if cfg_file.is_file():
        try:
            raw = tomllib.loads(cfg_file.read_text(encoding="utf-8"))
            book = raw.get("book", {}) if isinstance(raw, dict) else {}
            if isinstance(book, dict):
                title = str(book.get("title", title) or title)
                author = str(book.get("author", author) or "")
                production_uuid = str(book.get("uuid") or "").strip()
            if not production_uuid and isinstance(raw, dict):
                meta = raw.get("metadata")
                if isinstance(meta, dict):
                    production_uuid = str(meta.get("uuid") or "").strip()
                    market_variant = str(meta.get("market_variant") or "").strip()
                    variant_system_prompt_path = str(
                        meta.get("variant_system_prompt_path") or ""
                    ).strip()
                    variant_anchor_ids = [
                        str(item).strip()
                        for item in (meta.get("variant_anchor_ids") or [])
                        if str(item).strip()
                    ]
        except (OSError, tomllib.TOMLDecodeError):
            pass
    # publish_meta.json hat Vorrang für die Production-UUID
    meta_file = Path(source_dir) / "publish_meta.json"
    if meta_file.is_file():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if isinstance(meta, dict):
                from_meta = str(meta.get("uuid") or "").strip()
                if from_meta:
                    production_uuid = from_meta
                market_variant = str(meta.get("market_variant") or market_variant).strip()
                variant_system_prompt_path = str(
                    meta.get("variant_system_prompt_path") or variant_system_prompt_path
                ).strip()
                variant_anchor_ids = [
                    str(item).strip()
                    for item in (meta.get("variant_anchor_ids") or variant_anchor_ids)
                    if str(item).strip()
                ]
        except (OSError, json.JSONDecodeError, UnicodeError):
            pass
    content: dict[str, Any] = {
        "source": "book_studio_toml_fallback",
        "export_dir": str(Path(source_dir).resolve()),
        "book_title": title,
        "book_author": author,
    }
    if production_uuid:
        content["uuid"] = production_uuid
    if market_variant:
        content["market_variant"] = market_variant
    if variant_anchor_ids:
        content["variant_anchor_ids"] = variant_anchor_ids
    if variant_system_prompt_path:
        content["variant_system_prompt_path"] = variant_system_prompt_path
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": _utc_now_iso(),
        "grammargraph_version": "",
        "llm": {
            "provider": "",
            "model": "",
        },
        "content": content,
        "checksums": {},
    }
    if production_uuid:
        out["uuid"] = production_uuid
    if market_variant:
        out["market_variant"] = market_variant
    return out


def _normalize_manifest(data: dict[str, Any], *, source_path: Optional[Path]) -> dict[str, Any]:
    out = dict(data)
    out.setdefault("schema_version", SCHEMA_VERSION)
    out.setdefault("exported_at", _utc_now_iso())
    out.setdefault("grammargraph_version", "")
    out.setdefault("llm", {})
    out.setdefault("content", {})
    out.setdefault("checksums", {})
    content = dict(out.get("content") or {}) if isinstance(out.get("content"), dict) else {}
    if source_path is not None:
        content.setdefault("manifest_path", str(source_path.resolve()))
        if "source" not in content:
            content["source"] = "grammargraph_export"
    # UUID aus publish_meta am Import-Root nachziehen, falls Manifest sie nicht hat
    top_uuid = str(out.get("uuid") or "").strip()
    content_uuid = str(content.get("uuid") or "").strip()
    if not top_uuid and not content_uuid and source_path is not None:
        meta_file = source_path.parent / "publish_meta.json"
        if not meta_file.is_file():
            # Manifest kann in bookconfig/ liegen
            meta_file = source_path.parent.parent / "publish_meta.json"
        if meta_file.is_file():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if isinstance(meta, dict):
                    top_uuid = str(meta.get("uuid") or "").strip()
            except (OSError, json.JSONDecodeError, UnicodeError):
                pass
    if top_uuid:
        out["uuid"] = top_uuid
        content.setdefault("uuid", top_uuid)
    elif content_uuid:
        out["uuid"] = content_uuid
    top_variant = str(out.get("market_variant") or "").strip()
    content_variant = str(content.get("market_variant") or "").strip()
    if top_variant:
        content.setdefault("market_variant", top_variant)
    elif content_variant:
        out["market_variant"] = content_variant
    out["content"] = content
    out["ingested_at"] = _utc_now_iso()
    return out


def ingest_from_import_dir(book_path: Path, import_dir: Path) -> dict[str, Any]:
    """Kopiert/synthetisiert Provenance nach bookconfig/grammargraph_export.json.

    Returns:
        dict mit keys: written (bool), path (str|None), source (str), skipped (bool)
    """
    book = Path(book_path)
    source = Path(import_dir)
    if not book.is_dir() or not source.is_dir():
        return {"written": False, "path": None, "source": "", "skipped": True}

    manifest_path = find_manifest_in_dir(source)
    if manifest_path is not None:
        raw = _load_json_file(manifest_path)
        if raw is None:
            payload = synthesize_from_book_studio_toml(source)
            payload["content"]["note"] = f"Manifest {manifest_path.name} nicht lesbar — Fallback."
            source_kind = "fallback_after_bad_manifest"
        else:
            payload = _normalize_manifest(raw, source_path=manifest_path)
            source_kind = "grammargraph_manifest"
    else:
        payload = _normalize_manifest(
            synthesize_from_book_studio_toml(source),
            source_path=None,
        )
        source_kind = "book_studio_toml_fallback"

    # Bereits identisches Manifest nicht erneut schreiben
    existing = read_provenance(book)
    if existing and existing.get("exported_at") == payload.get("exported_at"):
        if existing.get("content", {}).get("export_dir") == payload.get("content", {}).get("export_dir"):
            return {
                "written": False,
                "path": str(provenance_path(book)),
                "source": source_kind,
                "skipped": True,
            }

    dest = write_provenance(book, payload)
    return {
        "written": True,
        "path": str(dest),
        "source": source_kind,
        "skipped": False,
    }
