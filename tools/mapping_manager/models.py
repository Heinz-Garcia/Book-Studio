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
    notes: str = ""


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


def layout_profile_label(layout_profile_id: str) -> str:
    """Löst eine Layout-Profil-ID (z. B. "paperback") in ihr Anzeige-Label
    (z. B. "(Pb) Paperback") auf — für die "Layout"-Spalte im Mapping
    Manager, damit BoD-/Paperback-Renders derselben Produktionslinie auf
    einen Blick unterscheidbar sind (waren vorher nur über Datum/Reihen-
    folge zu erkennen, da `profile_name` ein anderes Feld ist: Quartos
    eigenes `--profile-name`, unabhängig vom Layout-Profil)."""
    if not layout_profile_id:
        return "—"
    from tools.layout_profiles.catalog import get_profile

    return get_profile(layout_profile_id).label
