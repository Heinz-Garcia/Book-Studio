"""Placement helpers for front/back cover images (shared by render + validate)."""

from __future__ import annotations

from dataclasses import dataclass

from tools.cover_size.calculator import inch_to_mm
from tools.kdp_cover.constants import (
    BARCODE_HEIGHT_IN,
    BARCODE_MARGIN_IN,
    BARCODE_WIDTH_IN,
)
from tools.kdp_cover.geometry import RectMm, WrapGeometry
from tools.kdp_cover.model import CoverLayout


@dataclass(frozen=True)
class BackImagePlacement:
    """Rect of the back image (+ optional frame), centered or free."""

    image: RectMm
    outer: RectMm  # image inkl. Rahmen
    frame_mm: float


def barcode_reserve_mm(geo: WrapGeometry) -> RectMm:
    """KDP-Barcode-Reserve auf der Rückseite (unten rechts im Trim-Panel)."""
    bw = inch_to_mm(BARCODE_WIDTH_IN)
    bh = inch_to_mm(BARCODE_HEIGHT_IN)
    margin = inch_to_mm(BARCODE_MARGIN_IN)
    panel = geo.back_panel
    x = panel.right - margin - bw
    y = panel.bottom - margin - bh
    return RectMm(x, y, bw, bh)


def rects_intersect(a: RectMm, b: RectMm, *, epsilon: float = 1e-6) -> bool:
    return not (
        a.right <= b.x + epsilon
        or b.right <= a.x + epsilon
        or a.bottom <= b.y + epsilon
        or b.bottom <= a.y + epsilon
    )


def rect_contains(outer: RectMm, inner: RectMm, *, epsilon: float = 1e-6) -> bool:
    return (
        inner.x + epsilon >= outer.x
        and inner.y + epsilon >= outer.y
        and inner.right <= outer.right + epsilon
        and inner.bottom <= outer.bottom + epsilon
    )


def _float_attr(layout: CoverLayout, name: str, default: float) -> float:
    try:
        return float(getattr(layout, name, default))
    except (TypeError, ValueError):
        return default


def compute_back_image_placement(
    layout: CoverLayout,
    geo: WrapGeometry,
    *,
    image_width_px: int,
    image_height_px: int,
) -> BackImagePlacement | None:
    """Rechteck des Rückseitenbilds (+ optional Rahmen) in Canvas-mm.

    ``center`` (Default/Legacy): Contain-Skalierung, zentriert im Back-Trim;
    ``back_image_scale`` (0..1) relativ zur maximalen Contain-Größe innerhalb
    von ``back_safe``.
    ``free``: linke obere Ecke ``back_image_x_pct``/``back_image_y_pct`` und
    Breite ``back_image_width_pct`` in % des Back-Trims; Höhe folgt dem
    Seitenverhältnis des Bildes.
    """
    if image_width_px <= 0 or image_height_px <= 0:
        return None
    aspect = image_width_px / float(image_height_px)
    panel = geo.back_panel

    if str(getattr(layout, "back_image_placement", "center") or "") == "free":
        width_pct = max(5.0, min(120.0, _float_attr(layout, "back_image_width_pct", 40.0)))
        x_pct = _float_attr(layout, "back_image_x_pct", 10.0)
        y_pct = _float_attr(layout, "back_image_y_pct", 40.0)
        iw = panel.width * width_pct / 100.0
        ih = iw / aspect
        ix = panel.x + panel.width * x_pct / 100.0
        iy = panel.y + panel.height * y_pct / 100.0
        image = RectMm(ix, iy, iw, ih)
    else:
        scale = _float_attr(layout, "back_image_scale", 1.0) or 1.0
        scale = max(0.05, min(1.0, scale))

        fit = geo.back_safe
        max_w = fit.width * scale
        max_h = fit.height * scale
        if max_w <= 0 or max_h <= 0:
            return None

        # Contain in (max_w, max_h)
        if max_w / aspect <= max_h:
            iw = max_w
            ih = max_w / aspect
        else:
            ih = max_h
            iw = max_h * aspect

        # Zentriert im Trim-Panel (nicht nur Safe), damit das Foto optisch mittig sitzt.
        ix = panel.x + (panel.width - iw) / 2.0
        iy = panel.y + (panel.height - ih) / 2.0
        image = RectMm(ix, iy, iw, ih)

    frame_on = bool(getattr(layout, "back_image_frame", False))
    try:
        frame_mm = float(getattr(layout, "back_image_frame_mm", 2.0) or 0.0)
    except (TypeError, ValueError):
        frame_mm = 2.0
    frame_mm = max(0.0, frame_mm) if frame_on else 0.0
    outer = (
        RectMm(
            image.x - frame_mm,
            image.y - frame_mm,
            image.width + 2 * frame_mm,
            image.height + 2 * frame_mm,
        )
        if frame_mm > 0
        else image
    )
    return BackImagePlacement(image=image, outer=outer, frame_mm=frame_mm)


__all__ = [
    "BackImagePlacement",
    "barcode_reserve_mm",
    "rects_intersect",
    "rect_contains",
    "compute_back_image_placement",
]
