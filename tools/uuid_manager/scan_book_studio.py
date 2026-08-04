"""Scanner für Book-Studio-Bücher und Render-Artefakte."""

# pylint: disable=no-name-in-module

from __future__ import annotations

from pathlib import Path
from typing import Any

import app_config as _app_config
from tools.book_projects.catalog import list_books
from tools.pdf_uuid_exiftool import read_pdf_uuid, resolve_exiftool
from tools.production_uuid import normalize_uuid, read_book_uuid
from tools.publish_map.metadata import provenance_summary, read_book_metadata
from tools.publish_map.store import read_map
from tools.uuid_manager.model import BookRecord, PdfRecord


def _configured_exiftool_path(book_studio_repo: Path) -> str:
    try:
        cfg = _app_config.read_config(book_studio_repo / "app_config.json")
    except (OSError, TypeError, ValueError):
        cfg = {}
    return str(cfg.get("exiftool_path") or "").strip()


def _latest_render(data: dict[str, Any]) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    latest_at = ""
    for snap in data.get("snapshots") or []:
        if not isinstance(snap, dict):
            continue
        for render in snap.get("renders") or []:
            if not isinstance(render, dict):
                continue
            at = str(render.get("at") or "")
            if latest is None or at > latest_at:
                latest = render
                latest_at = at
    return latest


def _read_pdf_record(
    book_studio_repo: Path,
    render: dict[str, Any] | None,
) -> PdfRecord | None:
    if not isinstance(render, dict):
        return None
    artifact = str(render.get("artifact_path") or "").strip()
    if not artifact:
        return None
    path = Path(artifact)
    exists = path.is_file()
    configured = _configured_exiftool_path(book_studio_repo)
    tool = resolve_exiftool(configured)
    pdf_uuid = ""
    verified = False
    if exists and tool is not None:
        read_back = read_pdf_uuid(path, exiftool=tool)
        if read_back is not None:
            pdf_uuid = read_back
            verified = True
    source_archive = str(render.get("source_archive_path") or "").strip()
    return PdfRecord(
        pdf_path=path,
        rendered_at=str(render.get("at") or ""),
        exists=exists,
        pdf_uuid=pdf_uuid,
        verified=verified,
        source_archive_path=Path(source_archive) if source_archive else None,
    )


def scan_books(*, book_studio_repo: Path) -> list[BookRecord]:
    """Liest Bücher mit UUID und letztem Render."""
    records: list[BookRecord] = []
    for info in list_books(repo=book_studio_repo):
        uid = read_book_uuid(info.path)
        if not uid:
            continue
        meta = read_book_metadata(info.path)
        prov = provenance_summary(info.path)
        data = read_map(info.path) or {}
        latest = _latest_render(data)
        records.append(
            BookRecord(
                uuid=uid,
                book_path=info.path.resolve(),
                title=str(meta.get("title") or info.name),
                author=str(meta.get("author") or ""),
                exported_at=str(prov.get("exported_at") or ""),
                import_path=str(prov.get("import_path") or ""),
                source_kind=str(prov.get("source") or ""),
                market_variant=str(prov.get("market_variant") or "").strip().lower(),
                pdf=_read_pdf_record(book_studio_repo, latest),
            )
        )
    return records


def scan_orphan_pdfs(*, book_studio_repo: Path) -> list[PdfRecord]:
    """PDFs mit lesbarer UUID, die keinem Buch-UUID-Mapping zugeordnet werden koennen."""
    known = {rec.uuid for rec in scan_books(book_studio_repo=book_studio_repo)}
    configured = _configured_exiftool_path(book_studio_repo)
    tool = resolve_exiftool(configured)
    if tool is None:
        return []
    out: list[PdfRecord] = []
    seen: set[Path] = set()
    for info in list_books(repo=book_studio_repo):
        export_dir = info.path / "export"
        if not export_dir.is_dir():
            continue
        for pdf in export_dir.rglob("*.pdf"):
            resolved = pdf.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            value = read_pdf_uuid(pdf, exiftool=tool)
            normalized = normalize_uuid(value) if value else None
            if normalized and normalized not in known:
                out.append(
                    PdfRecord(
                        pdf_path=resolved,
                        exists=True,
                        pdf_uuid=normalized,
                        verified=True,
                    )
                )
    return out


__all__ = ["scan_books", "scan_orphan_pdfs"]
