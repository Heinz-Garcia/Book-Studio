"""Reine Rechenlogik: Buchrücken-Breite + Gesamt-Cover-Maße für ein
KDP-Taschenbuch. Kein UI-Bezug, keine Datei-I/O.

Formel und alle Zahlenwerte NICHT aus dem Gedächtnis, sondern gegen die
KDP-Hilfe verifiziert (Stand 2026-08-02):
- https://kdp.amazon.com/de_DE/help/topic/G201953020 (Taschenbuchcover erstellen)
- https://kdp.amazon.com/de_DE/help/topic/GVBQ3CMEQW3W2VL6 (Format, Beschnitt und Ränder)
- https://kdp.amazon.com/de_DE/help/topic/G201834180 (Druckoptionen / Trimmgrößen)

Wie bei der Innenrand-Tabelle in ``tools/layout_profiles/catalog.py``:
KDP kann diese Werte jederzeit ändern -- vor produktivem Einsatz gegen
KDPs aktuelle Doku gegenchecken, nicht blind vertrauen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from tools.kdp_specs import BLEED_MM

_MM_PER_INCH = 25.4

# KDP-Seitenzahl-Grenzen für ein Taschenbuch (alle Papier-/Farbvarianten
# teilen sich denselben Bereich laut KDP-Tabelle).
MIN_PAGE_COUNT = 24
MAX_PAGE_COUNT = 828


@dataclass(frozen=True)
class PaperType:
    id: str
    label: str
    mm_per_page: float


# Dicke pro Seite je Papier-/Druckart (mm), aus G201953020.
PAPER_TYPES: tuple[PaperType, ...] = (
    PaperType("white_bw", "Weiß (Schwarz/Weiß-Druck)", 0.0572),
    PaperType("cream_bw", "Cremefarben (Schwarz/Weiß-Druck)", 0.0635),
    PaperType("standard_color", "Standardfarbe", 0.0572),
    PaperType("premium_color", "Premiumfarbe", 0.0596),
)

DEFAULT_PAPER_TYPE_ID = "white_bw"


def get_paper_type(paper_type_id: str) -> PaperType:
    for paper in PAPER_TYPES:
        if paper.id == paper_type_id:
            return paper
    return PAPER_TYPES[0]


@dataclass(frozen=True)
class TrimSize:
    id: str
    label: str
    width_in: float
    height_in: float


# Standard-Trimmgrößen laut G201834180 -- Auswahlliste fürs UI. Wer eine
# nicht gelistete (aber laut KDP gültige) Größe braucht, kann Breite/Höhe
# stattdessen frei eingeben (KDP erlaubt "custom": 4-8.5in Breite,
# 6-11.69in Höhe).
TRIM_SIZES: tuple[TrimSize, ...] = (
    TrimSize("5x8", "5\" × 8\"", 5.0, 8.0),
    TrimSize("5.06x7.81", "5,06\" × 7,81\"", 5.06, 7.81),
    TrimSize("5.25x8", "5,25\" × 8\"", 5.25, 8.0),
    TrimSize("5.5x8.5", "5,5\" × 8,5\"", 5.5, 8.5),
    TrimSize("6x9", "6\" × 9\" (am weitesten verbreitet)", 6.0, 9.0),
    TrimSize("6.14x9.21", "6,14\" × 9,21\"", 6.14, 9.21),
    TrimSize("6.69x9.61", "6,69\" × 9,61\"", 6.69, 9.61),
    TrimSize("7x10", "7\" × 10\"", 7.0, 10.0),
    TrimSize("7.44x9.69", "7,44\" × 9,69\"", 7.44, 9.69),
    TrimSize("7.5x9.25", "7,5\" × 9,25\"", 7.5, 9.25),
    TrimSize("8x10", "8\" × 10\"", 8.0, 10.0),
    TrimSize("8.25x6", "8,25\" × 6\"", 8.25, 6.0),
    TrimSize("8.25x8.25", "8,25\" × 8,25\"", 8.25, 8.25),
    TrimSize("8.5x8.5", "8,5\" × 8,5\"", 8.5, 8.5),
    TrimSize("8.5x11", "8,5\" × 11\"", 8.5, 11.0),
    TrimSize("8.27x11.69", "8,27\" × 11,69\" (A4)", 8.27, 11.69),
)

CUSTOM_TRIM_SIZE_ID = "custom"
# KDP-Grenzen für ein frei gewähltes ("custom") Format, siehe G201834180.
CUSTOM_WIDTH_RANGE_IN = (4.0, 8.5)
CUSTOM_HEIGHT_RANGE_IN = (6.0, 11.69)


def get_trim_size(trim_size_id: str) -> Optional[TrimSize]:
    for trim in TRIM_SIZES:
        if trim.id == trim_size_id:
            return trim
    return None


def mm_to_inch(mm: float) -> float:
    return round(mm / _MM_PER_INCH, 4)


def inch_to_mm(inch: float) -> float:
    return round(inch * _MM_PER_INCH, 3)


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


def calculate_spine_width_mm(page_count: int, paper_type_id: str) -> float:
    """Buchrücken-Breite in mm -- `Seitenzahl × Papierdicke-pro-Seite`."""
    if page_count < MIN_PAGE_COUNT or page_count > MAX_PAGE_COUNT:
        raise ValueError(
            f"KDP-Taschenbücher brauchen zwischen {MIN_PAGE_COUNT} und "
            f"{MAX_PAGE_COUNT} Seiten (gegeben: {page_count})."
        )
    paper = get_paper_type(paper_type_id)
    return round(page_count * paper.mm_per_page, 3)


def calculate_cover_size(
    page_count: int,
    paper_type_id: str,
    trim_width_mm: float,
    trim_height_mm: float,
) -> CoverSizeResult:
    """Buchrücken-Breite + Gesamt-Covermaße inkl. Beschnittzugabe.

    Formel (KDP-Hilfe, G201953020): Coverbreite = Beschnittzugabe +
    Breite hintere Coverseite + Buchrückenbreite + Breite vordere
    Coverseite + Beschnittzugabe. Coverhöhe = Trimhöhe + 2 ×
    Beschnittzugabe (oben + unten).
    """
    if trim_width_mm <= 0 or trim_height_mm <= 0:
        raise ValueError("Trimmgröße muss größer als 0 sein.")
    spine = calculate_spine_width_mm(page_count, paper_type_id)
    cover_width = BLEED_MM + trim_width_mm + spine + trim_width_mm + BLEED_MM
    cover_height = trim_height_mm + 2 * BLEED_MM
    return CoverSizeResult(
        page_count=page_count,
        paper_type=get_paper_type(paper_type_id),
        trim_width_mm=trim_width_mm,
        trim_height_mm=trim_height_mm,
        spine_width_mm=spine,
        cover_width_mm=round(cover_width, 3),
        cover_height_mm=round(cover_height, 3),
        bleed_mm=BLEED_MM,
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
