"""KDP-Wrap-Validierung (Phase 1) — Errors/Warnings ohne UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import tools.kdp_specs as kdp_specs
from tools.kdp_cover.constants import (
    MIN_IMAGE_DPI,
    MIN_SPINE_TEXT_PAGE_COUNT,
    SPINE_EDGE_PADDING_MIN_MM,
)
from tools.kdp_cover.geometry import WrapGeometry, build_geometry
from tools.kdp_cover.model import CoverLayout

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok_for_safe_export(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok_for_safe_export": self.ok_for_safe_export,
            "issues": [
                {"code": i.code, "severity": i.severity, "message": i.message}
                for i in self.issues
            ],
        }


def _parse_hex_color(value: str) -> Optional[tuple[int, int, int]]:
    text = (value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def _image_dpi_for_panel(
    image_path: Path,
    panel_width_mm: float,
    panel_height_mm: float,
) -> Optional[float]:
    """Effektive DPI, wenn das Bild das Panel vollflächig füllt (cover-fit Untergrenze)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(image_path) as im:
        w_px, h_px = im.size
    if w_px <= 0 or h_px <= 0 or panel_width_mm <= 0 or panel_height_mm <= 0:
        return None
    # cover-fit: Bild wird so skaliert, dass das Panel voll abgedeckt ist —
    # limitierend ist die kleinere der beiden Achsen-DPIs.
    dpi_w = w_px / (panel_width_mm / 25.4)
    dpi_h = h_px / (panel_height_mm / 25.4)
    return min(dpi_w, dpi_h)


def validate_layout(
    layout: CoverLayout,
    *,
    geometry: Optional[WrapGeometry] = None,
    resolve_base: Optional[Path] = None,
) -> ValidationReport:
    """Prüft Layout gegen KDP-Grundregeln (Phase 1)."""
    report = ValidationReport()
    base = Path(resolve_base) if resolve_base else Path.cwd()

    lo = kdp_specs.min_page_count()
    hi = kdp_specs.max_page_count()
    if layout.page_count < lo or layout.page_count > hi:
        report.issues.append(
            ValidationIssue(
                code="page_count",
                severity="error",
                message=f"Seitenzahl muss zwischen {lo} und {hi} liegen "
                f"(gegeben: {layout.page_count}).",
            )
        )

    if layout.trim_width_mm <= 0 or layout.trim_height_mm <= 0:
        report.issues.append(
            ValidationIssue(
                code="trim_size",
                severity="error",
                message="Trimmgröße muss größer als 0 sein.",
            )
        )
        return report

    try:
        geo = geometry or build_geometry(
            page_count=layout.page_count,
            paper_type_id=layout.paper_type_id,
            trim_width_mm=layout.trim_width_mm,
            trim_height_mm=layout.trim_height_mm,
        )
    except ValueError as exc:
        report.issues.append(
            ValidationIssue(code="geometry", severity="error", message=str(exc))
        )
        return report

    if not layout.front_image.strip():
        report.issues.append(
            ValidationIssue(
                code="front_image_missing",
                severity="error",
                message="Vorderseiten-Bild fehlt.",
            )
        )
    else:
        front_path = Path(layout.front_image)
        if not front_path.is_absolute():
            front_path = (base / front_path).resolve()
        if not front_path.is_file():
            report.issues.append(
                ValidationIssue(
                    code="front_image_missing",
                    severity="error",
                    message=f"Vorderseiten-Bild nicht gefunden: {front_path}",
                )
            )
        else:
            # Panel inkl. Bleed-Überhang in der jeweiligen Achse
            panel_w = geo.trim_width_mm + geo.bleed_mm
            panel_h = geo.trim_height_mm + 2 * geo.bleed_mm
            dpi = _image_dpi_for_panel(front_path, panel_w, panel_h)
            if dpi is not None and dpi + 1e-6 < MIN_IMAGE_DPI:
                report.issues.append(
                    ValidationIssue(
                        code="front_image_dpi",
                        severity="error",
                        message=(
                            f"Vorderseiten-Bild erreicht nur ~{dpi:.0f} DPI "
                            f"(Mindestens {MIN_IMAGE_DPI} DPI für Druck)."
                        ),
                    )
                )

    if layout.back_image.strip():
        back_path = Path(layout.back_image)
        if not back_path.is_absolute():
            back_path = (base / back_path).resolve()
        if not back_path.is_file():
            report.issues.append(
                ValidationIssue(
                    code="back_image_missing",
                    severity="error",
                    message=f"Rückseiten-Bild nicht gefunden: {back_path}",
                )
            )
        else:
            from tools.kdp_cover.panel_images import (
                barcode_reserve_mm,
                compute_back_image_placement,
                rect_contains,
                rects_intersect,
            )

            try:
                from PIL import Image as _PilImage

                with _PilImage.open(back_path) as im:
                    iw, ih = im.size
            except OSError:
                iw, ih = 0, 0
                report.issues.append(
                    ValidationIssue(
                        code="back_image_unreadable",
                        severity="error",
                        message=f"Rückseiten-Bild nicht lesbar: {back_path}",
                    )
                )

            if iw > 0 and ih > 0:
                placement = compute_back_image_placement(
                    layout, geo, image_width_px=iw, image_height_px=ih
                )
                if placement is not None:
                    # Effektive DPI im gezeichneten Rechteck.
                    dpi_eff = min(
                        iw / (placement.image.width / 25.4),
                        ih / (placement.image.height / 25.4),
                    )
                    if dpi_eff + 1e-6 < MIN_IMAGE_DPI:
                        report.issues.append(
                            ValidationIssue(
                                code="back_image_dpi",
                                severity="error",
                                message=(
                                    f"Rückseiten-Bild erreicht nur ~{dpi_eff:.0f} DPI "
                                    f"im Layout (Mindestens {MIN_IMAGE_DPI} DPI)."
                                ),
                            )
                        )
                    if not rect_contains(geo.back_safe, placement.outer):
                        report.issues.append(
                            ValidationIssue(
                                code="back_image_safe_zone",
                                severity="error",
                                message=(
                                    "Rückseiten-Bild (inkl. Rahmen) verletzt die Safe-Zone. "
                                    "Bitte verkleinern oder Rahmen reduzieren."
                                ),
                            )
                        )
                    barcode = barcode_reserve_mm(geo)
                    if rects_intersect(placement.outer, barcode):
                        report.issues.append(
                            ValidationIssue(
                                code="back_image_barcode",
                                severity="error",
                                message=(
                                    "Rückseiten-Bild (inkl. Rahmen) überlappt die "
                                    "KDP-Barcode-Zone (unten rechts). Bitte verkleinern."
                                ),
                            )
                        )
                if bool(getattr(layout, "back_image_frame", False)):
                    fc = str(getattr(layout, "back_image_frame_color", "") or "")
                    if _parse_hex_color(fc) is None:
                        report.issues.append(
                            ValidationIssue(
                                code="back_image_frame_color",
                                severity="error",
                                message=f"Ungültige Rahmenfarbe: {fc!r}",
                            )
                        )
    else:
        if _parse_hex_color(layout.back_color) is None:
            report.issues.append(
                ValidationIssue(
                    code="back_color",
                    severity="error",
                    message=f"Ungültige Rückseiten-Farbe: {layout.back_color!r}",
                )
            )

    try:
        front_zoom = float(getattr(layout, "front_image_zoom", 1.0) or 1.0)
    except (TypeError, ValueError):
        front_zoom = 1.0
    if front_zoom + 1e-9 < 1.0:
        report.issues.append(
            ValidationIssue(
                code="front_image_zoom",
                severity="error",
                message="Vorderseiten-Zoom muss ≥ 1,0 sein (nur Vergrößern).",
            )
        )

    if _parse_hex_color(layout.spine_color) is None:
        report.issues.append(
            ValidationIssue(
                code="spine_color",
                severity="error",
                message=f"Ungültige Rücken-Farbe: {layout.spine_color!r}",
            )
        )

    spine_text = layout.spine_text.strip()
    spine_text_down = str(getattr(layout, "spine_text_down", "") or "").strip()
    badge = getattr(layout, "spine_badge", None)
    badge_active = bool(
        badge is not None
        and getattr(badge, "is_active", lambda: False)()
    )
    if badge_active:
        badge_color = str(getattr(badge, "color", "") or "")
        if _parse_hex_color(badge_color) is None:
            report.issues.append(
                ValidationIssue(
                    code="spine_badge_color",
                    severity="error",
                    message=f"Ungültige Rücken-Badge-Farbe: {badge_color!r}",
                )
            )

    spine_content = bool(spine_text or spine_text_down or badge_active)
    if spine_content and layout.page_count < MIN_SPINE_TEXT_PAGE_COUNT:
        sev: Severity = "error" if layout.mode == "safe" else "warning"
        report.issues.append(
            ValidationIssue(
                code="spine_text_too_few_pages",
                severity=sev,
                message=(
                    f"Rücken-Text/Badge erst ab {MIN_SPINE_TEXT_PAGE_COUNT} Seiten "
                    f"(aktuell {layout.page_count})."
                ),
            )
        )

    try:
        pad_mm = float(getattr(layout, "spine_padding_mm", SPINE_EDGE_PADDING_MIN_MM))
    except (TypeError, ValueError):
        pad_mm = SPINE_EDGE_PADDING_MIN_MM
    if spine_content and pad_mm + 1e-9 < SPINE_EDGE_PADDING_MIN_MM:
        report.issues.append(
            ValidationIssue(
                code="spine_padding_low",
                severity="warning",
                message=(
                    f"Rücken-Padding {pad_mm:.1f} mm unter KDP-Empfehlung "
                    f"({SPINE_EDGE_PADDING_MIN_MM} mm vom Kopf-/Fußrand)."
                ),
            )
        )

    if not layout.title.strip() and not layout.author.strip():
        report.issues.append(
            ValidationIssue(
                code="metadata_empty",
                severity="warning",
                message=(
                    "Titel/Autor leer — optional als PDF-Metadaten und im "
                    "cover_project; erscheinen nicht auf dem Cover-Bild."
                ),
            )
        )

    if layout.mode == "free":
        offs = layout.effective_offsets()
        moved = abs(offs["spine_offset_y_mm"]) > 1e-6
        if moved:
            report.issues.append(
                ValidationIssue(
                    code="free_placement_active",
                    severity="warning",
                    message=(
                        "Freie Rücken-Text-Platzierung aktiv — bitte Hilfslinien prüfen."
                    ),
                )
            )

    return report


__all__ = [
    "Severity",
    "ValidationIssue",
    "ValidationReport",
    "validate_layout",
]
