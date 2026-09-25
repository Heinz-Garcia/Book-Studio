"""Gemeinsame Konstanten und Hilfen des KDP-Cover-Designers."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from tools.kdp_cover.geometry import WrapGeometry

_STUDIO_PAPERBACK_ID = "studio_paperback"
# Bildschirm-Vorschau (Export bleibt DEFAULT_EXPORT_DPI / clamp_print_dpi ≥ 300).
# 300 DPI hier → mehrfaches Smooth-Skalieren bei jedem resizeEvent = sichtbares Gezucke.
_PREVIEW_DPI = 120.0
_PREVIEW_ZOOM_MIN = 0.25
_PREVIEW_ZOOM_MAX = 4.0
_PREVIEW_ZOOM_STEP = 1.15
_PREVIEW_DEBOUNCE_MS = 120
_PREVIEW_FIT_DEBOUNCE_MS = 60
_IMAGE_FILTER = "Bilder (*.png *.jpg *.jpeg *.tif *.tiff *.webp);;Alle Dateien (*.*)"
_PROJECT_FILTER = (
    "Cover-Layout (*_kdp_cover.json);;"
    "Cover-Layout Wrap (*_kdp_wrap_project.json);;"
    "Legacy (cover_project.json);;"
    "Alle Dateien (*.*)"
)
_ELEMENT_SET_FILTER = "Elementset (*_elementset.json);;Alle Dateien (*.*)"
_PROJECT_SAVE_FILTER = "Cover-Layout (*_kdp_cover.json);;Alle Dateien (*.*)"
_ELEMENT_SET_SAVE_FILTER = "Elementset (*_elementset.json);;Alle Dateien (*.*)"
_STATUS_EXPORT_TOOLTIP = (
    "Status der Live-Validierung (validate_layout) — nicht der Ampel „Cover“.\n\n"
    "• OK — bereit zum Export: keine Fehler und keine Warnungen.\n"
    "• Warnungen: Export möglich (Bestätigung beim Klick).\n"
    "• Fehler: im Sicher-Modus Export gesperrt; im Experten-Modus "
    "trotzdem möglich nach Bestätigung.\n\n"
    "Geprüft u. a.: Seitenzahl, Trimmgröße/Geometrie, Front-Farbe "
    "(wenn kein Bild), Bildpfade/DPI, Safe-Zone, Barcode-Zone.\n"
    "Nicht geprüft: ob gespeichert, ob Ampel grün, ob UUID gesetzt, "
    "ob das Design „fertig“ wirkt."
)

def _qlabel_color_ss(
    color: str,
    *,
    size_px: int | None = None,
    weight: str | None = None,
) -> str:
    """Label-Farbe scoped — bare ``color:`` würde den QToolTip mitfärben."""
    parts = [f"color:{color};"]
    if size_px is not None:
        parts.append(f"font-size:{size_px}px;")
    if weight is not None:
        parts.append(f"font-weight:{weight};")
    return f"QLabel {{ {' '.join(parts)} }}"


def _book_root(studio: Any) -> Path | None:
    raw = getattr(studio, "current_book", None) if studio else None
    if raw is None and studio is not None:
        facade = getattr(studio, "facade", None)
        raw = getattr(facade, "current_book", None) if facade else None
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def _read_quarto_title_author(book: Path) -> tuple[str, str]:
    yml = book / "_quarto.yml"
    if not yml.is_file():
        return "", ""
    try:
        import yaml

        data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, TypeError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    title = str(data.get("title") or "").strip()
    author = data.get("author") or data.get("authors") or ""
    if isinstance(author, list):
        parts: list[str] = []
        for item in author:
            if isinstance(item, dict):
                parts.append(str(item.get("name") or item.get("family") or "").strip())
            else:
                parts.append(str(item).strip())
        author_s = ", ".join(p for p in parts if p)
    else:
        author_s = str(author).strip()
    book_block = data.get("book") if isinstance(data.get("book"), dict) else {}
    if not title:
        title = str(book_block.get("title") or "").strip()
    if not author_s:
        author_s = str(book_block.get("author") or "").strip()
    return title, author_s


def _pil_to_qpixmap(image) -> QPixmap:
    rgb = image.convert("RGB")
    w, h = rgb.size
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def _draw_overlays(pixmap: QPixmap, geo: WrapGeometry, dpi: float) -> QPixmap:
    from tools.kdp_cover.panel_images import barcode_reserve_mm

    out = QPixmap(pixmap)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    scale = dpi / 25.4

    def _rect(r) -> tuple[float, float, float, float]:
        return r.x * scale, r.y * scale, r.width * scale, r.height * scale

    painter.setPen(QPen(QColor(220, 38, 38, 200), 1, Qt.PenStyle.DashLine))
    painter.drawRect(0, 0, out.width() - 1, out.height() - 1)

    painter.setPen(QPen(QColor(37, 99, 235, 220), 1, Qt.PenStyle.SolidLine))
    for panel in (geo.back_panel, geo.spine_panel, geo.front_panel):
        x, y, w, h = _rect(panel)
        painter.drawRect(int(x), int(y), int(w), int(h))

    painter.setPen(QPen(QColor(22, 163, 74, 220), 1, Qt.PenStyle.DotLine))
    for panel in (geo.back_safe, geo.front_safe):
        x, y, w, h = _rect(panel)
        if w > 2 and h > 2:
            painter.drawRect(int(x), int(y), int(w), int(h))

    painter.setPen(QPen(QColor(100, 116, 139, 180), 1, Qt.PenStyle.DashDotLine))
    sx, sy, sw, sh = _rect(geo.spine_panel)
    cx = int(sx + sw / 2)
    painter.drawLine(cx, int(sy), cx, int(sy + sh))

    # KDP-Barcode-Reserve (unten rechts auf der Rückseite) — Platzhalter.
    barcode = barcode_reserve_mm(geo)
    bx, by, bw, bh = _rect(barcode)
    if bw > 2 and bh > 2:
        painter.fillRect(
            int(bx),
            int(by),
            int(bw),
            int(bh),
            QColor(250, 204, 21, 110),  # amber, semi-transparent
        )
        painter.setPen(QPen(QColor(180, 83, 9, 230), 2, Qt.PenStyle.DashLine))
        painter.drawRect(int(bx), int(by), int(bw), int(bh))
        painter.setPen(QColor(120, 53, 15, 240))
        font = QFont()
        font.setPointSize(max(7, int(round(min(bw, bh) / 8))))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            int(bx),
            int(by),
            int(bw),
            int(bh),
            int(Qt.AlignmentFlag.AlignCenter),
            "KDP-Barcode\n(freihalten)",
        )

    painter.end()
    return out
