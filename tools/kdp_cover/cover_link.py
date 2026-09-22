"""Wrap-PDF ↔ Cover-Layout Provenance (Sidecar + Resolve).

Sidecar next to a Wrap-PDF: ``{pdf_stem}.cover-link.json``.
Resolution order for ``resolve_wrap_source``:

1. Sibling ``*_kdp_cover.json``
2. Sidecar ``layout_path`` (if file exists)
3. UUID (sidecar / ExifTool / ``production/covers/<uuid>/`` path) →
   registry primary or ``canonical_layout_path`` under that UUID folder
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tools.production_uuid import normalize_uuid

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_COVERS_SEGMENT = "covers"


@dataclass(frozen=True)
class CoverLink:
    production_uuid: str
    layout_path: str
    wrap_pdf: str
    exported_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "production_uuid": self.production_uuid,
            "layout_path": self.layout_path,
            "wrap_pdf": self.wrap_pdf,
            "exported_at": self.exported_at or "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverLink:
        return cls(
            production_uuid=str(data.get("production_uuid") or "").strip(),
            layout_path=str(data.get("layout_path") or "").strip(),
            wrap_pdf=str(data.get("wrap_pdf") or "").strip(),
            exported_at=str(data.get("exported_at") or "").strip(),
        )


def cover_link_path_for_pdf(pdf_path: Path | str) -> Path:
    """``foo_kdp_wrap.pdf`` → ``foo_kdp_wrap.cover-link.json``."""
    pdf = Path(pdf_path)
    return pdf.with_name(f"{pdf.stem}.cover-link.json")


def sibling_layout_path_for_wrap(pdf_path: Path | str) -> Path | None:
    """Guess ``*_kdp_cover.json`` next to ``*_kdp_wrap.pdf``."""
    pdf = Path(pdf_path)
    name = pdf.name
    if name.lower().endswith("_kdp_wrap.pdf"):
        stem = name[: -len("_kdp_wrap.pdf")]
        candidate = pdf.with_name(f"{stem}_kdp_cover.json")
        return candidate
    # Generic: same stem with _kdp_cover.json
    if name.lower().endswith(".pdf"):
        return pdf.with_name(f"{pdf.stem}_kdp_cover.json")
    return None


def uuid_from_covers_path(path: Path | str) -> str | None:
    """Extract UUID from ``…/covers/<uuid>/…`` path segments."""
    parts = Path(path).parts
    for i, part in enumerate(parts):
        if part.casefold() == _COVERS_SEGMENT and i + 1 < len(parts):
            candidate = parts[i + 1]
            if _UUID_RE.match(candidate):
                return normalize_uuid(candidate) or candidate
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_cover_link(
    pdf_path: Path | str,
    *,
    production_uuid: str,
    layout_path: Path | str,
    exported_at: str | None = None,
) -> Path:
    """Write sidecar next to ``pdf_path``. Returns sidecar path."""
    pdf = Path(pdf_path)
    layout = Path(layout_path)
    uid = normalize_uuid(production_uuid) or str(production_uuid or "").strip()
    link = CoverLink(
        production_uuid=uid,
        layout_path=str(layout.resolve()) if layout.exists() else str(layout),
        wrap_pdf=str(pdf.resolve()) if pdf.exists() else str(pdf),
        exported_at=exported_at or _now_iso(),
    )
    out = cover_link_path_for_pdf(pdf)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(link.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out


def read_cover_link(path: Path | str) -> CoverLink | None:
    target = Path(path)
    if not target.is_file():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    link = CoverLink.from_dict(raw)
    if not link.layout_path and not link.production_uuid:
        return None
    return link


def enrich_validation_payload(
    payload: dict[str, Any],
    *,
    production_uuid: str = "",
    layout_path: Path | str | None = None,
) -> dict[str, Any]:
    """Add provenance keys to a validation.json payload."""
    out = dict(payload)
    uid = normalize_uuid(production_uuid) or str(production_uuid or "").strip()
    if uid:
        out["production_uuid"] = uid
    if layout_path is not None and str(layout_path).strip():
        out["layout_path"] = str(Path(layout_path))
    return out


def stamp_wrap_pdf_uuid(
    pdf_path: Path | str,
    production_uuid: str,
    *,
    configured_exiftool: str | Path | None = None,
) -> bool:
    """Stamp Production-UUID into PDF metadata. Returns True on success.

    Missing ExifTool or stamp failure → False (caller may log a warning).
    """
    uid = normalize_uuid(production_uuid)
    if not uid:
        return False
    try:
        from tools.pdf_uuid_exiftool import resolve_exiftool, write_pdf_uuid
    except ImportError:
        return False
    tool = resolve_exiftool(configured_exiftool)
    if tool is None:
        return False
    try:
        write_pdf_uuid(pdf_path, uid, exiftool=tool)
    except (OSError, RuntimeError, ValueError, FileNotFoundError):
        return False
    return True


def _layout_from_uuid(
    uid: str,
    *,
    repo: Path | None = None,
    registry_file: Path | None = None,
) -> Path | None:
    from tools.kdp_cover.cover_registry import resolve_primary_cover

    entry = resolve_primary_cover(uid, path=registry_file)
    if entry is not None and str(entry.cover_path or "").strip():
        p = Path(entry.cover_path)
        if p.is_file():
            return p
    # Scan canonical UUID cover tree for any *_kdp_cover.json
    try:
        from tools.kdp_cover.cover_paths import uuid_cover_root

        root = uuid_cover_root(uid, repo=repo)
    except ValueError:
        return None
    if not root.is_dir():
        return None
    matches = sorted(root.rglob("*_kdp_cover.json"))
    for m in matches:
        if m.is_file():
            return m
    return None


def resolve_wrap_source(
    pdf_path: Path | str,
    *,
    repo: Path | None = None,
    registry_file: Path | None = None,
    configured_exiftool: str | Path | None = None,
) -> Path:
    """Resolve editable ``*_kdp_cover.json`` for a Wrap-PDF.

    Raises:
        FileNotFoundError: PDF missing
        ValueError: no layout can be resolved
    """
    pdf = Path(pdf_path)
    if not pdf.is_file():
        raise FileNotFoundError(f"Wrap-PDF nicht gefunden: {pdf}")

    sibling = sibling_layout_path_for_wrap(pdf)
    if sibling is not None and sibling.is_file():
        return sibling.resolve()

    link = read_cover_link(cover_link_path_for_pdf(pdf))
    if link is not None:
        layout = Path(link.layout_path)
        if layout.is_file():
            return layout.resolve()

    uid = ""
    if link is not None:
        uid = normalize_uuid(link.production_uuid) or link.production_uuid
    if not uid:
        uid = uuid_from_covers_path(pdf) or ""
    if not uid:
        try:
            from tools.pdf_uuid_exiftool import read_pdf_uuid, resolve_exiftool

            tool = resolve_exiftool(configured_exiftool)
            if tool is not None:
                raw = read_pdf_uuid(pdf, exiftool=tool)
                uid = normalize_uuid(raw or "") or ""
        except (OSError, RuntimeError, FileNotFoundError, ValueError):
            uid = ""

    if uid:
        found = _layout_from_uuid(uid, repo=repo, registry_file=registry_file)
        if found is not None:
            return found.resolve()

    raise ValueError(
        "Kein Cover-Layout zur Wrap-PDF gefunden.\n"
        "Erwartet: Sibling *_kdp_cover.json, Sidecar *.cover-link.json "
        "oder Production-UUID (Metadaten / production/covers/<uuid>/)."
    )


__all__ = [
    "CoverLink",
    "cover_link_path_for_pdf",
    "enrich_validation_payload",
    "read_cover_link",
    "resolve_wrap_source",
    "sibling_layout_path_for_wrap",
    "stamp_wrap_pdf_uuid",
    "uuid_from_covers_path",
    "write_cover_link",
]
