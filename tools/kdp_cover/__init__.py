"""KDP Wrap-Cover-Tool (Phase 1): Geometrie, Validierung, CLI-PDF-Export.

Autonom unter ``tools/kdp_cover/`` — kein Import aus ``export_manager``,
``services/`` oder ``ui_qt``. Nutzt ``tools.kdp_specs`` und
``tools.cover_size.calculator`` als Maß-SSOT.

Siehe ``.doc/kdp-cover-designer-konzept.md``.
"""

from __future__ import annotations

from tools.kdp_cover.constants import (
    DEFAULT_EXPORT_DPI,
    MIN_IMAGE_DPI,
    MIN_SPINE_TEXT_PAGE_COUNT,
    SAFE_ZONE_IN,
)
from tools.kdp_cover.geometry import RectMm, WrapGeometry, build_geometry, build_geometry_from_result
from tools.kdp_cover.binding import (
    CoverBinding,
    binding_status_label,
    doctor_missing_cover_warning,
    resolve_cover_binding,
)
from tools.kdp_cover.model import CoverLayout, load_layout, save_layout, cover_export_dir, default_project_path
from tools.kdp_cover.validate import ValidationIssue, ValidationReport, validate_layout

__all__ = [
    "DEFAULT_EXPORT_DPI",
    "MIN_IMAGE_DPI",
    "MIN_SPINE_TEXT_PAGE_COUNT",
    "SAFE_ZONE_IN",
    "RectMm",
    "WrapGeometry",
    "build_geometry",
    "build_geometry_from_result",
    "CoverLayout",
    "load_layout",
    "save_layout",
    "cover_export_dir",
    "default_project_path",
    "CoverBinding",
    "resolve_cover_binding",
    "binding_status_label",
    "doctor_missing_cover_warning",
    "ValidationIssue",
    "ValidationReport",
    "validate_layout",
]
