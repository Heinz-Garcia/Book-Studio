"""Zonenkarte der Rückseite — folgt den echten Element-Positionen.

Anders als die Vorderseiten-Karte (feste Schema-Zonen) zeichnet diese Karte
Subtitel, Klappentext, Bio und Abbildung dort, wo sie im Layout tatsächlich
liegen (Rechtecke aus ``compose_back.back_element_rects_mm``, als Anteile
0..1 des Rückseiten-Trims). Abgeschaltete Elemente erscheinen gestrichelt an
ihrer eingestellten Position — ein Klick schaltet sie im Dialog frei.
Die KDP-Barcode-Reserve ist als Sperrzone schraffiert.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

#: Zeichen- und Klick-Reihenfolge (oben liegend zuerst getroffen).
BACK_ZONE_ORDER: tuple[str, ...] = (
    "back_subtitle",
    "back_image",
    "back_blurb",
    "back_bio",
)

BACK_ZONE_TOOLTIPS: dict[str, str] = {
    "back_subtitle": "Subtitel (Rückseite)",
    "back_blurb": "Klappentext",
    "back_bio": "Autor-Kurzbiografie",
    "back_image": "Abbildung (frei platzierbar)",
    "back_barcode": "KDP-Barcode-Reserve — freihalten",
    "back_ground": "Rückseiten-Farbe / Hintergrund",
}


@dataclass(frozen=True)
class BackZone:
    """Zone in Trim-Anteilen (0..1); ``active`` = Element ist sichtbar."""

    id: str
    x: float
    y: float
    w: float
    h: float
    active: bool = True

    def contains(self, xf: float, yf: float) -> bool:
        return self.x <= xf <= self.x + self.w and self.y <= yf <= self.y + self.h


def back_zones_for_layout(
    layout: object,
    geo: object,
    *,
    back_image_path: Path | None = None,
) -> tuple[dict[str, BackZone], BackZone]:
    """Zonen (Trim-Anteile) + Barcode-Reserve aus Layout und Wrap-Geometrie."""
    from tools.kdp_cover.compose_back import back_compose_spec, back_element_rects_mm
    from tools.kdp_cover.panel_images import barcode_reserve_mm

    panel = geo.back_panel  # type: ignore[attr-defined]

    def _frac(rect: object, zone_id: str, active: bool) -> BackZone:
        return BackZone(
            zone_id,
            (rect.x - panel.x) / panel.width,  # type: ignore[attr-defined]
            (rect.y - panel.y) / panel.height,  # type: ignore[attr-defined]
            rect.width / panel.width,  # type: ignore[attr-defined]
            rect.height / panel.height,  # type: ignore[attr-defined]
            active,
        )

    image_size: tuple[int, int] | None = None
    if back_image_path is not None and back_image_path.is_file():
        try:
            from PIL import Image

            with Image.open(back_image_path) as im:
                image_size = im.size
        except OSError:
            image_size = None
    spec = back_compose_spec(layout)
    rects = back_element_rects_mm(
        layout, geo, dpi=72.0, image_size_px=image_size, include_inactive=True
    )
    active = {
        "subtitle": spec.subtitle.enabled and bool(
            spec.subtitle.line1.text.strip() or spec.subtitle.line2.text.strip()
        ),
        "blurb": spec.blurb.is_active,
        "bio": spec.bio.is_active,
        "image": True,
    }
    zones = {f"back_{key}": _frac(rect, f"back_{key}", active[key]) for key, rect in rects.items()}
    if "back_image" not in zones:
        # Kein Bild gewählt: Platzhalter an der freien Position (bzw. Mitte).
        free = getattr(layout, "back_image_placement", "center") == "free"
        x = float(getattr(layout, "back_image_x_pct", 10.0)) / 100.0 if free else 0.3
        y = float(getattr(layout, "back_image_y_pct", 40.0)) / 100.0 if free else 0.35
        w = float(getattr(layout, "back_image_width_pct", 40.0)) / 100.0 if free else 0.4
        aspect = panel.width / panel.height
        zones["back_image"] = BackZone("back_image", x, y, w, w * 1.2 * aspect, False)
    barcode = _frac(barcode_reserve_mm(geo), "back_barcode", True)  # type: ignore[arg-type]
    return zones, barcode


def hit_test_back_zone(
    xf: float,
    yf: float,
    zones: dict[str, BackZone],
    *,
    barcode: BackZone | None = None,
) -> str | None:
    """Zone-ID für Trim-Anteile (0..1); außerhalb → None, Leerfläche → Hintergrund."""
    if not (0.0 <= xf <= 1.0 and 0.0 <= yf <= 1.0):
        return None
    # Aktive Elemente vor gestrichelten Platzhaltern
    for want_active in (True, False):
        for zone_id in BACK_ZONE_ORDER:
            zone = zones.get(zone_id)
            if zone is not None and zone.active == want_active and zone.contains(xf, yf):
                return zone_id
    if barcode is not None and barcode.contains(xf, yf):
        return "back_barcode"
    return "back_ground"


class BackCoverZoneMap(QWidget):
    """Schematische Rückseite; Klick emittiert ``zone_clicked(zone_id)``."""

    zone_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("kdpBackCoverZoneMap")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(200, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._hover_id: str | None = None
        self._zones: dict[str, BackZone] = {}
        self._barcode: BackZone | None = None
        self._ground = QColor("#F5F0E8")
        self._aspect = 0.66  # width / height

    # --- Daten -----------------------------------------------------------
    def set_zones(
        self,
        zones: dict[str, BackZone],
        *,
        barcode: BackZone | None,
        ground_color: str,
        aspect: float,
    ) -> None:
        self._zones = dict(zones)
        self._barcode = barcode
        color = QColor(ground_color)
        self._ground = color if color.isValid() else QColor("#F5F0E8")
        if aspect > 0:
            self._aspect = float(aspect)
        self.update()

    def zones(self) -> dict[str, BackZone]:
        return dict(self._zones)

    # --- Geometrie -------------------------------------------------------
    def _cover_rect(self) -> QRect:
        margin = 12
        avail = self.rect().adjusted(margin, margin, -margin, -margin - 22)
        w = avail.width()
        h = int(w / self._aspect)
        if h > avail.height():
            h = avail.height()
            w = int(h * self._aspect)
        x = avail.x() + (avail.width() - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        return QRect(x, y, max(40, w), max(60, h))

    @staticmethod
    def _zone_rect(cover: QRect, zone: BackZone) -> QRectF:
        return QRectF(
            cover.x() + zone.x * cover.width(),
            cover.y() + zone.y * cover.height(),
            zone.w * cover.width(),
            zone.h * cover.height(),
        )

    def _fraction_at(self, pos: QPoint) -> tuple[float, float] | None:
        cover = self._cover_rect()
        if not cover.contains(pos):
            return None
        return (
            (pos.x() - cover.x()) / cover.width(),
            (pos.y() - cover.y()) / cover.height(),
        )

    # --- Malen -----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#e8eef7"))
        cover = self._cover_rect()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(15, 23, 42, 40))
        p.drawRoundedRect(cover.adjusted(4, 6, 4, 6), 4, 4)
        p.setBrush(self._ground)
        p.setPen(QPen(QColor("#94a3b8"), 2))
        p.drawRoundedRect(cover, 3, 3)
        p.setClipRect(cover)

        dark_ground = self._ground.lightness() < 128
        ink = QColor("#f1f5f9") if dark_ground else QColor("#334155")

        if self._barcode is not None:
            self._paint_barcode(p, self._zone_rect(cover, self._barcode))
        # Unten liegende zuerst malen
        for zone_id in reversed(BACK_ZONE_ORDER):
            zone = self._zones.get(zone_id)
            if zone is None:
                continue
            r = self._zone_rect(cover, zone)
            if not zone.active:
                self._paint_placeholder(p, r, zone_id)
            elif zone_id == "back_image":
                self._paint_image(p, r)
            elif zone_id == "back_subtitle":
                self._paint_lines(p, r, ink, rows=2, widths=(0.8, 0.6), centered=True)
            elif zone_id == "back_blurb":
                self._paint_lines(p, r, ink, rows=0, widths=(1.0,), centered=False)
            elif zone_id == "back_bio":
                self._paint_lines(p, r, ink, rows=0, widths=(1.0,), centered=False, light=True)
            if self._hover_id == zone_id:
                p.setPen(QPen(QColor("#38bdf8"), 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(r)

        if self._hover_id == "back_ground":
            p.setClipping(False)
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(cover.adjusted(1, 1, -1, -1), 3, 3)

        p.setClipping(False)
        caption = QFont(self.font())
        caption.setPointSize(9)
        p.setFont(caption)
        p.setPen(QColor("#475569"))
        p.drawText(
            self.rect().adjusted(10, 0, -10, -6),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
            "Rückseite · Positionen wie im Layout",
        )
        p.end()

    def _paint_barcode(self, p: QPainter, r: QRectF) -> None:
        p.setPen(QPen(QColor("#b91c1c"), 1.5, Qt.PenStyle.DashLine))
        p.setBrush(QBrush(QColor(185, 28, 28, 70), Qt.BrushStyle.BDiagPattern))
        p.drawRect(r)
        font = QFont(self.font())
        font.setPointSize(7)
        p.setFont(font)
        p.setPen(QColor("#991b1b"))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Barcode")

    def _paint_placeholder(self, p: QPainter, r: QRectF, zone_id: str) -> None:
        p.setPen(QPen(QColor("#64748b"), 1.2, Qt.PenStyle.DashLine))
        p.setBrush(QColor(255, 255, 255, 60))
        p.drawRect(r)
        font = QFont(self.font())
        font.setPointSize(7)
        p.setFont(font)
        p.setPen(QColor("#64748b"))
        label = BACK_ZONE_TOOLTIPS.get(zone_id, "").split(" (")[0]
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, f"{label} (aus)")

    def _paint_image(self, p: QPainter, r: QRectF) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#8a9bb0"))
        p.drawRect(r)
        # Stilisiertes Porträt: Kopf + Schultern
        p.setBrush(QColor("#e2e8f0"))
        head = min(r.width(), r.height()) * 0.26
        p.drawEllipse(
            QRectF(r.center().x() - head / 2, r.top() + r.height() * 0.22, head, head)
        )
        p.drawChord(
            QRectF(
                r.left() + r.width() * 0.18,
                r.top() + r.height() * 0.58,
                r.width() * 0.64,
                r.height() * 0.8,
            ),
            0,
            180 * 16,
        )

    @staticmethod
    def _paint_lines(
        p: QPainter,
        r: QRectF,
        ink: QColor,
        *,
        rows: int,
        widths: tuple[float, ...],
        centered: bool,
        light: bool = False,
    ) -> None:
        color = QColor(ink)
        if light:
            color.setAlpha(150)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        bar_h = max(1.5, min(4.0, r.height() * 0.12 if rows else 3.0))
        step = bar_h * 2.1
        n = rows or max(1, int(r.height() / step))
        for i in range(n):
            frac = widths[i % len(widths)]
            if not rows and i == n - 1 and n > 1:
                frac = 0.55  # letzte Absatzzeile kürzer
            bw = r.width() * frac
            x = r.center().x() - bw / 2 if centered else r.left()
            y = r.top() + (r.height() - n * step) / 2 + i * step if rows else r.top() + i * step
            p.drawRoundedRect(QRectF(x, y, bw, bar_h), 1, 1)

    # --- Maus ------------------------------------------------------------
    def _hit(self, pos: QPoint) -> str | None:
        frac = self._fraction_at(pos)
        if frac is None:
            return None
        return hit_test_back_zone(*frac, self._zones, barcode=self._barcode)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        new_id = self._hit(event.position().toPoint())
        if new_id != self._hover_id:
            self._hover_id = new_id
            self.setToolTip(BACK_ZONE_TOOLTIPS.get(new_id or "", ""))
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover_id is not None:
            self._hover_id = None
            self.setToolTip("")
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            zone_id = self._hit(event.position().toPoint())
            if zone_id and zone_id != "back_barcode":
                self.zone_clicked.emit(zone_id)
                event.accept()
                return
        super().mousePressEvent(event)


__all__ = [
    "BACK_ZONE_ORDER",
    "BACK_ZONE_TOOLTIPS",
    "BackCoverZoneMap",
    "BackZone",
    "back_zones_for_layout",
    "hit_test_back_zone",
]
