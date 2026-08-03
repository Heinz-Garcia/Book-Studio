"""Reine Rechenlogik: Buchrücken-Breite + Gesamt-Cover-Maße für ein
KDP-Taschenbuch. Kein UI-Bezug, keine Datei-I/O.

Zahlen kommen aus ``tools.kdp_specs`` (``kdp_specs.json``) — nicht aus
Hardcodes in diesem Modul.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import tools.kdp_specs as kdp_specs

CUSTOM_TRIM_SIZE_ID = "custom"


@dataclass(frozen=True)
class PaperType:
    id: str
    label: str
    mm_per_page: float


@dataclass(frozen=True)
class TrimSize:
    id: str
    label: str
    width_in: float
    height_in: float


@dataclass(frozen=True)
class CoverSizeResult:
    page_count: int
    paper_type: PaperType
    trim_width_mm: float
    trim_height_mm: float
    spine_width_mm: float
    cover_width_mm: float
    cover_height_mm: float
    bleed_mm: float

    @property
    def spine_width_in(self) -> float:
        return mm_to_inch(self.spine_width_mm)

    @property
    def cover_width_in(self) -> float:
        return mm_to_inch(self.cover_width_mm)

    @property
    def cover_height_in(self) -> float:
        return mm_to_inch(self.cover_height_mm)


def _papers() -> tuple[PaperType, ...]:
    return tuple(
        PaperType(
            id=str(p["id"]),
            label=str(p["label"]),
            mm_per_page=float(p["mm_per_page"]),
        )
        for p in kdp_specs.paper_types()
    )


def _trims() -> tuple[TrimSize, ...]:
    return tuple(
        TrimSize(
            id=str(t["id"]),
            label=str(t["label"]),
            width_in=float(t["width"]),
            height_in=float(t["height"]),
        )
        for t in kdp_specs.trim_sizes_in()
    )


def __getattr__(name: str):
    """Dynamische Modul-Attribute aus der geladenen KDP-Config."""
    if name == "BLEED_MM":
        return kdp_specs.bleed_mm()
    if name == "MIN_PAGE_COUNT":
        return kdp_specs.min_page_count()
    if name == "MAX_PAGE_COUNT":
        return kdp_specs.max_page_count()
    if name == "DEFAULT_PAPER_TYPE_ID":
        return kdp_specs.default_paper_type_id()
    if name == "PAPER_TYPES":
        return _papers()
    if name == "TRIM_SIZES":
        return _trims()
    if name == "CUSTOM_WIDTH_RANGE_IN":
        return kdp_specs.custom_width_range_in()
    if name == "CUSTOM_HEIGHT_RANGE_IN":
        return kdp_specs.custom_height_range_in()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_paper_type(paper_type_id: str) -> PaperType:
    papers = _papers()
    for paper in papers:
        if paper.id == paper_type_id:
            return paper
    return papers[0]


def get_trim_size(trim_size_id: str) -> Optional[TrimSize]:
    for trim in _trims():
        if trim.id == trim_size_id:
            return trim
    return None


def mm_to_inch(mm: float) -> float:
    return round(mm / kdp_specs.mm_per_inch(), 4)


def inch_to_mm(inch: float) -> float:
    return round(inch * kdp_specs.mm_per_inch(), 3)


def calculate_spine_width_mm(page_count: int, paper_type_id: str) -> float:
    """Buchrücken-Breite in mm -- `Seitenzahl × Papierdicke-pro-Seite`."""
    lo = kdp_specs.min_page_count()
    hi = kdp_specs.max_page_count()
    if page_count < lo or page_count > hi:
        raise ValueError(
            f"KDP-Taschenbücher brauchen zwischen {lo} und {hi} Seiten "
            f"(gegeben: {page_count})."
        )
    paper = get_paper_type(paper_type_id)
    return round(page_count * paper.mm_per_page, 3)


def calculate_cover_size(
    page_count: int,
    paper_type_id: str,
    trim_width_mm: float,
    trim_height_mm: float,
) -> CoverSizeResult:
    """Buchrücken-Breite + Gesamt-Covermaße inkl. Beschnittzugabe."""
    if trim_width_mm <= 0 or trim_height_mm <= 0:
        raise ValueError("Trimmgröße muss größer als 0 sein.")
    bleed = kdp_specs.bleed_mm()
    spine = calculate_spine_width_mm(page_count, paper_type_id)
    cover_width = bleed + trim_width_mm + spine + trim_width_mm + bleed
    cover_height = trim_height_mm + 2 * bleed
    return CoverSizeResult(
        page_count=page_count,
        paper_type=get_paper_type(paper_type_id),
        trim_width_mm=trim_width_mm,
        trim_height_mm=trim_height_mm,
        spine_width_mm=spine,
        cover_width_mm=round(cover_width, 3),
        cover_height_mm=round(cover_height, 3),
        bleed_mm=bleed,
    )


__all__ = [
    "BLEED_MM",
    "MIN_PAGE_COUNT",
    "MAX_PAGE_COUNT",
    "CUSTOM_TRIM_SIZE_ID",
    "CUSTOM_WIDTH_RANGE_IN",
    "CUSTOM_HEIGHT_RANGE_IN",
    "DEFAULT_PAPER_TYPE_ID",
    "PaperType",
    "PAPER_TYPES",
    "TrimSize",
    "TRIM_SIZES",
    "CoverSizeResult",
    "get_paper_type",
    "get_trim_size",
    "mm_to_inch",
    "inch_to_mm",
    "calculate_spine_width_mm",
    "calculate_cover_size",
]
