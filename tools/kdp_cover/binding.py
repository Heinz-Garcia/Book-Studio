"""Buch ↔ kanonisches Cover-Layout (SSOT für Status/Doktor/GUI).

Kanal-Flag: ``bookconfig/distribution.json``.
Layout-Datei: ``export/kdp_cover/{Buchname}_kdp_cover.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tools.distribution.book_store import is_kdp_paperback
from tools.kdp_cover.model import (
    default_project_path,
    resolve_existing_project_path,
)

CoverBindingStatus = Literal["off", "ready", "missing"]


@dataclass(frozen=True)
class CoverBinding:
    book_root: Path
    kdp_enabled: bool
    canonical_path: Path
    cover_project_exists: bool
    status: CoverBindingStatus

    @property
    def book_name(self) -> str:
        return self.book_root.name


def resolve_cover_binding(book_root: Path) -> CoverBinding:
    root = Path(book_root)
    enabled = is_kdp_paperback(root)
    canonical = default_project_path(root)
    existing = resolve_existing_project_path(root)
    exists = existing is not None
    if not enabled:
        status: CoverBindingStatus = "off"
    elif exists:
        status = "ready"
    else:
        status = "missing"
    return CoverBinding(
        book_root=root,
        kdp_enabled=enabled,
        canonical_path=canonical,
        cover_project_exists=exists,
        status=status,
    )


def binding_status_label(binding: CoverBinding) -> str:
    """Kurzer deutscher Status für GUI-Banner."""
    if binding.status == "off":
        return "KDP aus — Cover-Layout optional"
    if binding.status == "ready":
        existing = resolve_existing_project_path(binding.book_root)
        shown = existing if existing is not None else binding.canonical_path
        return f"KDP an · Cover-Layout: {shown.name}"
    return (
        f"KDP an · noch kein {binding.canonical_path.name} — "
        "Cover-Layout speichern oder Designer nutzen"
    )


def doctor_missing_cover_warning(binding: CoverBinding) -> str | None:
    """Warning-Text für Buch-Doktor, oder None wenn kein Hinweis nötig."""
    if binding.status != "missing":
        return None
    rel = f"export/kdp_cover/{binding.canonical_path.name}"
    return (
        "⚠️ KDP-Taschenbuch aktiv, aber kein Cover-Layout unter " f"{rel}"
    )


__all__ = [
    "CoverBinding",
    "CoverBindingStatus",
    "resolve_cover_binding",
    "binding_status_label",
    "doctor_missing_cover_warning",
]
