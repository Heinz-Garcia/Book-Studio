"""Wrap-Geometrie aus ``tools.cover_size`` — reine mm/px-Rechtecke."""

from __future__ import annotations

from dataclasses import dataclass

from tools.cover_size.calculator import CoverSizeResult, calculate_cover_size, inch_to_mm
from tools.kdp_cover.constants import DEFAULT_EXPORT_DPI, SAFE_ZONE_IN


@dataclass(frozen=True)
class RectMm:
    """Achsenparalleles Rechteck in Millimetern (Ursprung links oben)."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def inset(self, mm: float) -> RectMm:
        return RectMm(
            x=self.x + mm,
            y=self.y + mm,
            width=max(0.0, self.width - 2 * mm),
            height=max(0.0, self.height - 2 * mm),
        )

    def to_px(self, dpi: float) -> tuple[int, int, int, int]:
        """(x, y, w, h) in Pixeln, gerundet."""
        scale = dpi / 25.4
        return (
            int(round(self.x * scale)),
            int(round(self.y * scale)),
            max(1, int(round(self.width * scale))),
            max(1, int(round(self.height * scale))),
        )


@dataclass(frozen=True)
class WrapGeometry:
    """Vollständiges Wrap-Layout inkl. Bleed, Trim-Panels und Safe-Zones."""

    page_count: int
    paper_type_id: str
    trim_width_mm: float
    trim_height_mm: float
    spine_width_mm: float
    bleed_mm: float
    cover_width_mm: float
    cover_height_mm: float
    safe_zone_mm: float

    # Panels auf dem Gesamt-Canvas (inkl. Bleed am äußeren Rand).
    canvas: RectMm
    back_panel: RectMm  # Trim-Bereich Rückseite (ohne äußeren Bleed)
    spine_panel: RectMm
    front_panel: RectMm
    back_safe: RectMm
    spine_safe: RectMm
    front_safe: RectMm
    # Äußere Bleed-Streifen (volle Canvas-Ränder).
    bleed_left: RectMm
    bleed_right: RectMm
    bleed_top: RectMm
    bleed_bottom: RectMm

    def canvas_size_px(self, dpi: float = DEFAULT_EXPORT_DPI) -> tuple[int, int]:
        scale = dpi / 25.4
        return (
            max(1, int(round(self.cover_width_mm * scale))),
            max(1, int(round(self.cover_height_mm * scale))),
        )


def build_geometry_from_result(result: CoverSizeResult) -> WrapGeometry:
    """Baut Panel-Rechtecke aus einem ``CoverSizeResult``."""
    bleed = float(result.bleed_mm)
    tw = float(result.trim_width_mm)
    th = float(result.trim_height_mm)
    spine = float(result.spine_width_mm)
    cw = float(result.cover_width_mm)
    ch = float(result.cover_height_mm)
    safe = inch_to_mm(SAFE_ZONE_IN)

    canvas = RectMm(0.0, 0.0, cw, ch)
    # Von links: bleed | back trim | spine | front trim | bleed
    back = RectMm(bleed, bleed, tw, th)
    spine_panel = RectMm(bleed + tw, bleed, spine, th)
    front = RectMm(bleed + tw + spine, bleed, tw, th)

    return WrapGeometry(
        page_count=int(result.page_count),
        paper_type_id=result.paper_type.id,
        trim_width_mm=tw,
        trim_height_mm=th,
        spine_width_mm=spine,
        bleed_mm=bleed,
        cover_width_mm=cw,
        cover_height_mm=ch,
        safe_zone_mm=safe,
        canvas=canvas,
        back_panel=back,
        spine_panel=spine_panel,
        front_panel=front,
        back_safe=back.inset(safe),
        spine_safe=spine_panel.inset(safe) if spine > 2 * safe else spine_panel,
        front_safe=front.inset(safe),
        bleed_left=RectMm(0.0, 0.0, bleed, ch),
        bleed_right=RectMm(cw - bleed, 0.0, bleed, ch),
        bleed_top=RectMm(0.0, 0.0, cw, bleed),
        bleed_bottom=RectMm(0.0, ch - bleed, cw, bleed),
    )


def build_geometry(
    *,
    page_count: int,
    paper_type_id: str,
    trim_width_mm: float,
    trim_height_mm: float,
) -> WrapGeometry:
    """Convenience: ``calculate_cover_size`` + Panel-Geometrie."""
    result = calculate_cover_size(
        page_count=page_count,
        paper_type_id=paper_type_id,
        trim_width_mm=trim_width_mm,
        trim_height_mm=trim_height_mm,
    )
    return build_geometry_from_result(result)


__all__ = [
    "RectMm",
    "WrapGeometry",
    "build_geometry",
    "build_geometry_from_result",
]
