"""Cover aus Vorlage klonen: Layout kopieren, Texte tauschen, neue geplante UUID.

Siehe ``.doc/Mittwoch_23.md`` / ``.doc/cover-planned-uuid.md``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.kdp_cover.cover_registry import upsert_cover_link
from tools.kdp_cover.model import CoverLayout, load_layout, save_layout
from tools.kdp_cover.planned_uuid import (
    SOURCE_KIND_PLANNED,
    PlannedCoverUuid,
    create_planned_cover_uuid,
)
from tools.production_uuid import normalize_uuid


@dataclass
class CoverTextOverrides:
    """Texte für die geklonte Variante (leer = Feld leeren, nicht Vorlage behalten)."""

    # PDF-/Layout-Metadaten + Rücken
    title: str = ""
    author: str = ""
    spine_text: str = ""
    spine_text_down: str = ""
    # Vorderseiten-Compose (Titelzeilen)
    compose_series: str = ""
    compose_main: str = ""
    compose_claim: str = ""
    compose_author: str = ""
    compose_sub1: str = ""
    compose_sub2: str = ""


@dataclass(frozen=True)
class CloneCoverResult:
    planned: PlannedCoverUuid
    layout_path: Path
    layout: CoverLayout
    source_path: Path
    source_uuid: str


def extract_text_snapshot(layout: CoverLayout) -> CoverTextOverrides:
    """Aktuelle Texte aus einem Layout (für Dialog-Vorbelegung)."""
    compose = layout.front_compose if isinstance(layout.front_compose, dict) else {}
    titles = compose.get("titles") if isinstance(compose.get("titles"), dict) else {}
    series = titles.get("series") if isinstance(titles.get("series"), dict) else {}
    main = titles.get("main") if isinstance(titles.get("main"), dict) else {}
    claim_raw = titles.get("claim") if "claim" in titles else titles.get("accent")
    claim = claim_raw if isinstance(claim_raw, dict) else {}
    author_c = titles.get("author") if isinstance(titles.get("author"), dict) else {}
    sub = titles.get("subtitle") if isinstance(titles.get("subtitle"), dict) else {}
    line1 = sub.get("line1") if isinstance(sub.get("line1"), dict) else {}
    line2 = sub.get("line2") if isinstance(sub.get("line2"), dict) else {}
    return CoverTextOverrides(
        title=str(layout.title or ""),
        author=str(layout.author or ""),
        spine_text=str(layout.spine_text or ""),
        spine_text_down=str(getattr(layout, "spine_text_down", "") or ""),
        compose_series=str(series.get("text") or ""),
        compose_main=str(main.get("text") or ""),
        compose_claim=str(claim.get("text") or ""),
        compose_author=str(author_c.get("text") or ""),
        compose_sub1=str(line1.get("text") or ""),
        compose_sub2=str(line2.get("text") or ""),
    )


def _set_line_text(bucket: dict[str, Any], key: str, text: str) -> None:
    raw = bucket.get(key)
    line = dict(raw) if isinstance(raw, dict) else {}
    line["text"] = str(text)
    bucket[key] = line


def apply_text_overrides(layout: CoverLayout, texts: CoverTextOverrides) -> CoverLayout:
    """Mutiert eine Kopie des Layouts: Meta-, Rücken- und Compose-Texte."""
    data = deepcopy(layout.to_dict())
    data["title"] = str(texts.title or "")
    data["author"] = str(texts.author or "")
    data["spine_text"] = str(texts.spine_text or "")
    data["spine_text_down"] = str(texts.spine_text_down or "")
    data["wrap_pdf"] = ""

    compose = data.get("front_compose")
    if isinstance(compose, dict):
        compose = deepcopy(compose)
        titles = compose.get("titles")
        if not isinstance(titles, dict):
            titles = {"enabled": True}
        else:
            titles = dict(titles)
        titles["enabled"] = True
        _set_line_text(titles, "series", texts.compose_series)
        _set_line_text(titles, "main", texts.compose_main)
        # Claim: sowohl claim als auch accent setzen (SSOT-Leser)
        _set_line_text(titles, "accent", texts.compose_claim)
        titles["claim"] = dict(titles.get("accent") or {})
        _set_line_text(titles, "author", texts.compose_author)
        sub = titles.get("subtitle")
        if not isinstance(sub, dict):
            sub = {"enabled": bool(texts.compose_sub1 or texts.compose_sub2)}
        else:
            sub = dict(sub)
        if texts.compose_sub1 or texts.compose_sub2:
            sub["enabled"] = True
        line1 = dict(sub.get("line1") or {}) if isinstance(sub.get("line1"), dict) else {}
        line2 = dict(sub.get("line2") or {}) if isinstance(sub.get("line2"), dict) else {}
        line1["text"] = str(texts.compose_sub1 or "")
        line2["text"] = str(texts.compose_sub2 or "")
        sub["line1"] = line1
        sub["line2"] = line2
        titles["subtitle"] = sub
        compose["titles"] = titles
        compose["enabled"] = True
        data["front_compose"] = compose

    return CoverLayout.from_dict(data)


def clone_cover_from_template(
    source_path: Path | str,
    *,
    title_hint: str,
    texts: CoverTextOverrides,
    series_id: str = "",
    cover_label: str = "",
    repo: Path | None = None,
    registry_file: Path | None = None,
) -> CloneCoverResult:
    """Vorlage laden → neue geplante UUID → Texte → Layout speichern.

    Bilder/Maße/Farben bleiben; Production-UUID und Texte sind neu.
    """
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(f"Vorlage nicht gefunden: {src}")
    source_layout = load_layout(src)
    src_uid = normalize_uuid(source_layout.production_uuid) or ""

    planned = create_planned_cover_uuid(
        title_hint=title_hint,
        series_id=series_id,
        cover_label=cover_label or "Hauptcover",
        repo=repo,
        registry_file=registry_file,
    )

    cloned = apply_text_overrides(source_layout, texts)
    cloned.production_uuid = planned.production_uuid
    cloned.cover_label = planned.entry.cover_label or "Hauptcover"
    cloned.cover_role = "primary"
    cloned.wrap_pdf = ""

    out_path = Path(planned.cover_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_layout(cloned, out_path)

    kinds = [SOURCE_KIND_PLANNED, "cloned_cover"]
    if src_uid:
        kinds.append(f"cloned_from:{src_uid}")
    upsert_cover_link(
        production_uuid=planned.production_uuid,
        cover_path=out_path,
        book_path="",
        cover_label=cloned.cover_label,
        cover_role="primary",
        title_hint=planned.title_hint,
        series_id=planned.series_id,
        source_kinds=kinds,
        path=registry_file,
    )

    return CloneCoverResult(
        planned=planned,
        layout_path=out_path,
        layout=cloned,
        source_path=src,
        source_uuid=src_uid,
    )


__all__ = [
    "CloneCoverResult",
    "CoverTextOverrides",
    "apply_text_overrides",
    "clone_cover_from_template",
    "extract_text_snapshot",
]
