"""Visual front-cover zone map — click jumps to editor sections."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QSizePolicy, QWidget


@dataclass(frozen=True)
class CoverZone:
    """Hotspot id + axis-aligned box in cover fractions (0..1)."""

    id: str
    x: float
    y: float
    w: float
    h: float
    priority: int


# Hit boxes (painting may be more detailed than the box).
COVER_ZONES: tuple[CoverZone, ...] = (
    CoverZone("corner", 0.0, 0.0, 0.32, 0.18, 40),
    CoverZone("badge", 0.55, 0.42, 0.42, 0.22, 40),
    CoverZone("header", 0.0, 0.0, 1.0, 0.09, 25),
    CoverZone("image", 0.0, 0.09, 1.0, 0.28, 25),
    CoverZone("title", 0.05, 0.38, 0.90, 0.11, 25),
    CoverZone("subtitle", 0.0, 0.50, 1.0, 0.09, 25),
    CoverZone("claim", 0.08, 0.60, 0.84, 0.055, 25),
    CoverZone("author", 0.10, 0.67, 0.80, 0.06, 25),
    CoverZone("footer", 0.0, 0.86, 1.0, 0.14, 25),
    CoverZone("ground", 0.0, 0.37, 1.0, 0.63, 5),
)

ZONE_TOOLTIPS: dict[str, str] = {
    "corner": "Ecken-Banner",
    "badge": "Badge / Stempel",
    "header": "Oberes Band (Kopfleiste)",
    "image": "Titelbild (goldener Schnitt)",
    "title": "Titelzeilen",
    "subtitle": "Subtitel (mit Band)",
    "claim": "Claim / Tagline",
    "author": "Autor",
    "footer": "Fußzeile",
    "ground": "Front-Farbe / Hintergrund",
}


def hit_test_zone(xf: float, yf: float, zones: tuple[CoverZone, ...] = COVER_ZONES) -> str | None:
    """Return zone id for fractional coords inside the cover (0..1), or None."""
    # Corner: top-left triangle (diagonal ribbon)
    if xf + yf < 0.28 and xf < 0.32 and yf < 0.18:
        return "corner"
    # Badge: ellipse around stamp center
    bx, by, bw, bh = 0.55, 0.42, 0.42, 0.22
    cx, cy = bx + bw / 2, by + bh / 2
    rx, ry = bw / 2, bh / 2
    if rx > 0 and ry > 0:
        nx = (xf - cx) / rx
        ny = (yf - cy) / ry
        if nx * nx + ny * ny <= 1.0:
            return "badge"

    hits = [
        z
        for z in zones
        if z.id not in ("corner", "badge")
        and z.x <= xf <= z.x + z.w
        and z.y <= yf <= z.y + z.h
    ]
    if not hits:
        return None
    hits.sort(key=lambda z: (-z.priority, z.w * z.h))
    return hits[0].id


class CoverZoneMap(QWidget):
    """Full-size schematic front cover; click emits ``zone_clicked(zone_id)``."""

    zone_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("kdpCoverZoneMap")
        self.setToolTip("")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(220, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._hover_id: str | None = None
        self.setMouseTracking(True)

    def _cover_rect(self) -> QRect:
        """Letterboxed paperback front inside the widget."""
        margin = 12
        avail = self.rect().adjusted(margin, margin, -margin, -margin - 22)
        target_ratio = 0.66  # width / height
        w = avail.width()
        h = int(w / target_ratio)
        if h > avail.height():
            h = avail.height()
            w = int(h * target_ratio)
        x = avail.x() + (avail.width() - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        return QRect(x, y, max(40, w), max(60, h))

    def _fr(self, cover: QRect, x: float, y: float, w: float, h: float) -> QRectF:
        return QRectF(
            cover.x() + x * cover.width(),
            cover.y() + y * cover.height(),
            w * cover.width(),
            h * cover.height(),
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#e8eef7"))
        cover = self._cover_rect()

        # Shadow
        shadow = cover.adjusted(4, 6, 4, 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 40))
        painter.drawRoundedRect(shadow, 4, 4)

        # Ground (night blue) — full cover base
        painter.setBrush(QColor("#0f2744"))
        painter.setPen(QPen(QColor("#0b1a2e"), 2))
        painter.drawRoundedRect(cover, 3, 3)
        painter.setClipRect(cover)

        hover = self._hover_id
        self._paint_image(painter, cover, hover == "image")
        self._paint_header(painter, cover, hover == "header")
        self._paint_title(painter, cover, hover == "title")
        self._paint_subtitle(painter, cover, hover == "subtitle")
        self._paint_claim(painter, cover, hover == "claim")
        self._paint_author(painter, cover, hover == "author")
        self._paint_footer(painter, cover, hover == "footer")
        self._paint_badge(painter, cover, hover == "badge")
        self._paint_corner(painter, cover, hover == "corner")

        # Hover outline for ground (empty lower area)
        if hover == "ground":
            painter.setClipping(False)
            painter.setPen(QPen(QColor("#38bdf8"), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(cover.adjusted(1, 1, -1, -1), 3, 3)

        painter.setClipping(False)
        caption = QFont(self.font())
        caption.setPointSize(9)
        painter.setFont(caption)
        painter.setPen(QColor("#475569"))
        painter.drawText(
            self.rect().adjusted(10, 0, -10, -6),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
            "Klick auf ein Element → Sprung  ·  Layout-Hilfe, keine Live-Vorschau",
        )
        painter.end()

    def _paint_image(self, p: QPainter, cover: QRect, hot: bool) -> None:
        r = self._fr(cover, 0.0, 0.09, 1.0, 0.28)
        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0.0, QColor("#6b7c93"))
        grad.setColorAt(0.55, QColor("#8a9bb0"))
        grad.setColorAt(1.0, QColor("#4a5568"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRect(r)
        # Fake skyline / mountains (silhouette)
        skyline = QPolygonF(
            [
                QPointF(r.left(), r.bottom()),
                QPointF(r.left(), r.top() + r.height() * 0.55),
                QPointF(r.left() + r.width() * 0.12, r.top() + r.height() * 0.35),
                QPointF(r.left() + r.width() * 0.22, r.top() + r.height() * 0.50),
                QPointF(r.left() + r.width() * 0.35, r.top() + r.height() * 0.28),
                QPointF(r.left() + r.width() * 0.48, r.top() + r.height() * 0.45),
                QPointF(r.left() + r.width() * 0.62, r.top() + r.height() * 0.32),
                QPointF(r.left() + r.width() * 0.78, r.top() + r.height() * 0.48),
                QPointF(r.left() + r.width() * 0.92, r.top() + r.height() * 0.38),
                QPointF(r.right(), r.top() + r.height() * 0.52),
                QPointF(r.right(), r.bottom()),
            ]
        )
        p.setBrush(QColor(30, 41, 59, 160))
        p.drawPolygon(skyline)
        # Warm window accents
        p.setBrush(QColor("#fbbf24"))
        for i in range(5):
            wx = r.left() + r.width() * (0.15 + i * 0.14)
            wy = r.top() + r.height() * 0.62
            p.drawRect(QRectF(wx, wy, r.width() * 0.03, r.height() * 0.06))
        if hot:
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)

    def _paint_header(self, p: QPainter, cover: QRect, hot: bool) -> None:
        r = self._fr(cover, 0.0, 0.0, 1.0, 0.09)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#0c2340"))
        p.drawRect(r)
        # Text as white bars (not labels)
        p.setBrush(QColor("#f8fafc"))
        mid_y = r.center().y()
        bar_h = max(2.0, r.height() * 0.22)
        total_w = r.width() * 0.72
        x0 = r.center().x() - total_w / 2
        for frac_w, gap in ((0.22, 0.04), (0.18, 0.04), (0.14, 0.04), (0.10, 0.0)):
            bw = total_w * frac_w
            p.drawRoundedRect(QRectF(x0, mid_y - bar_h / 2, bw, bar_h), 1, 1)
            x0 += bw + total_w * gap
        if hot:
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)

    def _paint_title(self, p: QPainter, cover: QRect, hot: bool) -> None:
        r = self._fr(cover, 0.06, 0.38, 0.88, 0.11)
        p.setPen(Qt.PenStyle.NoPen)
        # Two title lines as bold white slabs (serif weight via height)
        p.setBrush(QColor("#f1f5f9"))
        line1 = QRectF(r.left() + r.width() * 0.08, r.top() + r.height() * 0.08, r.width() * 0.84, r.height() * 0.32)
        line2 = QRectF(r.left(), r.top() + r.height() * 0.48, r.width(), r.height() * 0.48)
        p.drawRoundedRect(line1, 2, 2)
        p.drawRoundedRect(line2, 2, 2)
        if hot:
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 2, 2)

    def _paint_subtitle(self, p: QPainter, cover: QRect, hot: bool) -> None:
        r = self._fr(cover, 0.0, 0.50, 1.0, 0.09)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(71, 85, 105, 200))
        p.drawRect(r)
        p.setBrush(QColor("#e2e8f0"))
        for i, (fw, fy) in enumerate(((0.55, 0.22), (0.38, 0.58))):
            bw = r.width() * fw
            bh = r.height() * 0.18
            p.drawRoundedRect(
                QRectF(r.center().x() - bw / 2, r.top() + r.height() * fy, bw, bh),
                1,
                1,
            )
        if hot:
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)

    def _paint_claim(self, p: QPainter, cover: QRect, hot: bool) -> None:
        r = self._fr(cover, 0.12, 0.605, 0.76, 0.045)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#cbd5e1"))
        bw = r.width() * 0.85
        bh = max(2.0, r.height() * 0.35)
        p.drawRoundedRect(
            QRectF(r.center().x() - bw / 2, r.center().y() - bh / 2, bw, bh),
            1,
            1,
        )
        if hot:
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 2, 2)

    def _paint_author(self, p: QPainter, cover: QRect, hot: bool) -> None:
        r = self._fr(cover, 0.15, 0.67, 0.70, 0.055)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e2e8f0"))
        bw = r.width() * 0.55
        bh = max(2.0, r.height() * 0.32)
        p.drawRoundedRect(
            QRectF(r.center().x() - bw / 2, r.center().y() - bh / 2, bw, bh),
            1,
            1,
        )
        if hot:
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 2, 2)

    def _paint_footer(self, p: QPainter, cover: QRect, hot: bool) -> None:
        r = self._fr(cover, 0.0, 0.86, 1.0, 0.14)
        # Divider + compass
        cy = r.top() + r.height() * 0.22
        p.setPen(QPen(QColor("#e2e8f0"), 1.5))
        p.drawLine(QPointF(r.left() + r.width() * 0.08, cy), QPointF(r.right() - r.width() * 0.08, cy))
        # Small compass diamond
        cx = r.center().x()
        s = r.height() * 0.12
        diamond = QPolygonF(
            [
                QPointF(cx, cy - s),
                QPointF(cx + s, cy),
                QPointF(cx, cy + s),
                QPointF(cx - s, cy),
            ]
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f8fafc"))
        p.drawPolygon(diamond)
        # Publisher / URL bars
        p.setBrush(QColor("#e2e8f0"))
        for fy, fw in ((0.45, 0.55), (0.68, 0.40)):
            bw = r.width() * fw
            bh = r.height() * 0.10
            p.drawRoundedRect(
                QRectF(r.center().x() - bw / 2, r.top() + r.height() * fy, bw, bh),
                1,
                1,
            )
        # Crest stub bottom-left
        crest = self._fr(cover, 0.06, 0.92, 0.10, 0.06)
        p.setBrush(QColor("#94a3b8"))
        p.drawEllipse(crest)
        if hot:
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)

    def _paint_badge(self, p: QPainter, cover: QRect, hot: bool) -> None:
        r = self._fr(cover, 0.58, 0.43, 0.36, 0.20)
        p.save()
        p.translate(r.center())
        p.rotate(-22)
        outer = QRectF(-r.width() / 2, -r.height() / 2, r.width(), r.height())
        p.setPen(QPen(QColor("#b45309"), 2.5, Qt.PenStyle.DashLine))
        p.setBrush(QColor("#d97706"))
        p.drawEllipse(outer)
        inner = outer.adjusted(4, 4, -4, -4)
        p.setPen(QPen(QColor("#fde68a"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(inner)
        # Stamp text as arc of short bars
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#fffbeb"))
        for ang in (-50, -25, 0, 25, 50):
            rad = math.radians(ang)
            rr = min(outer.width(), outer.height()) * 0.28
            bx = math.sin(rad) * rr - 8
            by = -math.cos(rad) * rr * 0.35 - 2
            p.drawRoundedRect(QRectF(bx, by, 16, 3.5), 1, 1)
        if hot:
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(outer.adjusted(-2, -2, 2, 2))
        p.restore()

    def _paint_corner(self, p: QPainter, cover: QRect, hot: bool) -> None:
        # Top-left diagonal ribbon (triangle)
        s = min(cover.width(), cover.height()) * 0.22
        tri = QPolygonF(
            [
                QPointF(cover.left(), cover.top()),
                QPointF(cover.left() + s, cover.top()),
                QPointF(cover.left(), cover.top() + s),
            ]
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#eab308"))
        p.drawPolygon(tri)
        # Fold shade
        fold = QPolygonF(
            [
                QPointF(cover.left() + s * 0.55, cover.top()),
                QPointF(cover.left() + s, cover.top()),
                QPointF(cover.left(), cover.top() + s),
                QPointF(cover.left(), cover.top() + s * 0.55),
            ]
        )
        p.setBrush(QColor(120, 53, 15, 50))
        p.drawPolygon(fold)
        # Text along diagonal as black bars
        p.save()
        p.translate(cover.left() + s * 0.22, cover.top() + s * 0.22)
        p.rotate(-45)
        p.setBrush(QColor("#1c1917"))
        p.setPen(Qt.PenStyle.NoPen)
        for i, w in enumerate((28, 22, 18)):
            p.drawRoundedRect(QRectF(-w / 2, -6 + i * 7, w, 4), 1, 1)
        p.restore()
        if hot:
            p.setPen(QPen(QColor("#38bdf8"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolygon(tri)

    def _fraction_at(self, pos: QPoint) -> tuple[float, float] | None:
        cover = self._cover_rect()
        if not cover.contains(pos):
            return None
        xf = (pos.x() - cover.x()) / cover.width()
        yf = (pos.y() - cover.y()) / cover.height()
        return xf, yf

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        frac = self._fraction_at(event.position().toPoint())
        new_id = hit_test_zone(*frac) if frac else None
        if new_id != self._hover_id:
            self._hover_id = new_id
            tip = ZONE_TOOLTIPS.get(new_id or "", "")
            self.setToolTip(tip)
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
            frac = self._fraction_at(event.position().toPoint())
            if frac is not None:
                zone_id = hit_test_zone(*frac)
                if zone_id:
                    self.zone_clicked.emit(zone_id)
                    event.accept()
                    return
        super().mousePressEvent(event)


__all__ = [
    "COVER_ZONES",
    "CoverZone",
    "CoverZoneMap",
    "ZONE_TOOLTIPS",
    "hit_test_zone",
]
