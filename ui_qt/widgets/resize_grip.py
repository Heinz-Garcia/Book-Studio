"""Visible window resize grip (diagonal dots) for Qt dialogs.

Windows native ``QSizeGrip`` painting is often invisible; this widget
draws a clear red Norm-style dot pattern and resizes its window by drag.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class DiagonalDotsSizeGrip(QWidget):
    """Resize grip in the SE corner: red background + diagonal dot rows."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._drag_origin: QPoint | None = None
        self._start_size: tuple[int, int] | None = None
        self.setFixedSize(22, 22)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setToolTip("Fenstergröße ändern (an den Punkten ziehen)")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.raise_()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        # Nur die roten Punkte — kein Rahmen, kein Hintergrund
        painter.setBrush(QBrush(QColor("#dc2626")))
        painter.setPen(Qt.NoPen)
        dots = (
            (17, 5),
            (17, 10), (12, 10),
            (17, 15), (12, 15), (7, 15),
        )
        for x, y in dots:
            painter.drawRect(x, y, 3, 3)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
            self._start_size = (self._window.width(), self._window.height())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_origin is None or self._start_size is None:
            return
        if not (event.buttons() & Qt.LeftButton):
            return
        delta = event.globalPosition().toPoint() - self._drag_origin
        min_w = max(self._window.minimumWidth(), 400)
        min_h = max(self._window.minimumHeight(), 300)
        new_w = max(min_w, self._start_size[0] + delta.x())
        new_h = max(min_h, self._start_size[1] + delta.y())
        self._window.resize(new_w, new_h)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_origin = None
            self._start_size = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


def attach_resize_grip(dialog: QWidget) -> DiagonalDotsSizeGrip:
    """Install a SE-corner resize grip on ``dialog`` and keep it positioned."""
    grip = DiagonalDotsSizeGrip(dialog)

    def _reposition() -> None:
        m = 2
        grip.move(
            max(0, dialog.width() - grip.width() - m),
            max(0, dialog.height() - grip.height() - m),
        )
        grip.raise_()
        grip.show()

    _orig_resize = dialog.resizeEvent
    _orig_show = dialog.showEvent

    def _resize_event(event: object) -> None:
        _orig_resize(event)
        _reposition()

    def _show_event(event: object) -> None:
        _orig_show(event)
        _reposition()

    dialog.resizeEvent = _resize_event  # type: ignore[method-assign]
    dialog.showEvent = _show_event  # type: ignore[method-assign]
    _reposition()
    return grip
