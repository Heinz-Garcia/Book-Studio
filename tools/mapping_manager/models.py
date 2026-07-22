"""Datenmodelle für den Mapping Manager."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class SnapshotView:
    id: str
    label: str
    origin: str
    import_path: str
    book_title: str
    provenance_model: str
    created_at: str
    render_count: int


@dataclass(frozen=True)
class RenderView:
    id: str
    snapshot_id: str
    pdf_path: Path
    pdf_name: str
    format: str
    template: str
    profile_name: str
    layout_profile: str
    at: str
    at_display: str
    exists: bool


def format_snapshot_label(snap: dict[str, Any]) -> str:
    title = str(snap.get("book_title") or "Buch")
    created = str(snap.get("created_at") or "")[:10]
    origin = snap.get("origin", "")
    prov = snap.get("provenance") if isinstance(snap.get("provenance"), dict) else {}
    model = str(prov.get("llm_model") or "").strip()
    if origin == "grammargraph_import":
        prefix = "GG-Import"
    else:
        prefix = "Lokal"
    parts = [f"{created} · {prefix} · {title}"]
    if model:
        parts.append(model)
    return " · ".join(parts)


def _format_at_display(at: str) -> str:
    if not at:
        return "—"
    try:
        normalized = at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return at[:16]
