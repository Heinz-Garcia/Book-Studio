"""Lädt Snapshot- und Render-Ansichten aus publish_map.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from tools.mapping_manager.models import RenderView, SnapshotView, format_snapshot_label, _format_at_display
from tools.publish_map.store import read_map, refresh_publish_map


def load_snapshots(book_path: Path) -> list[SnapshotView]:
    refresh_publish_map(book_path)
    data = read_map(book_path)
    if not data:
        return []
    views: list[SnapshotView] = []
    for snap in data.get("snapshots") or []:
        if not isinstance(snap, dict):
            continue
        prov = snap.get("provenance") if isinstance(snap.get("provenance"), dict) else {}
        renders = snap.get("renders") or []
        views.append(
            SnapshotView(
                id=str(snap.get("id") or ""),
                label=format_snapshot_label(snap),
                origin=str(snap.get("origin") or ""),
                import_path=str(snap.get("import_path") or ""),
                book_title=str(snap.get("book_title") or ""),
                provenance_model=str(prov.get("llm_model") or ""),
                created_at=str(snap.get("created_at") or ""),
                render_count=len(renders),
            )
        )
    return views


def load_renders(book_path: Path, snapshot_id: str) -> list[RenderView]:
    data = read_map(book_path)
    if not data:
        return []
    snap: Optional[dict[str, Any]] = None
    for item in data.get("snapshots") or []:
        if isinstance(item, dict) and item.get("id") == snapshot_id:
            snap = item
            break
    if snap is None:
        return []

    views: list[RenderView] = []
    for render in snap.get("renders") or []:
        if not isinstance(render, dict):
            continue
        artifact = str(render.get("artifact_path") or "").strip()
        pdf_path = Path(artifact) if artifact else Path()
        views.append(
            RenderView(
                id=str(render.get("id") or ""),
                snapshot_id=snapshot_id,
                pdf_path=pdf_path,
                pdf_name=pdf_path.name if artifact else "(kein Pfad)",
                format=str(render.get("format") or ""),
                template=str(render.get("template") or ""),
                profile_name=str(render.get("profile_name") or ""),
                layout_profile=str(render.get("layout_profile") or ""),
                at=str(render.get("at") or ""),
                at_display=_format_at_display(str(render.get("at") or "")),
                exists=pdf_path.is_file() if artifact else False,
                notes=str(render.get("notes") or ""),
            )
        )
    views.sort(key=lambda r: r.at, reverse=True)
    return views
