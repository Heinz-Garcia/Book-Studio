"""Pipette: Farbe aus Referenzbild lesen und als Hex in die Zwischenablage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui_qt.autonomous_window import (
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)

_LOG = logging.getLogger(__name__)

_IMAGE_FILTER = "Bilder (*.png *.jpg *.jpeg *.tif *.tiff *.webp *.bmp);;Alle Dateien (*.*)"

_active: list["ColorPipetteDialog"] = []

_WINDOW_FLAGS = (
    Qt.WindowType.Window
    | Qt.WindowType.WindowTitleHint
    | Qt.WindowType.WindowSystemMenuHint
    | Qt.WindowType.WindowCloseButtonHint
    | Qt.WindowType.WindowMinMaxButtonsHint
    | Qt.WindowType.WindowStaysOnTopHint
)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """``#RRGGBB`` (uppercase)."""
    return f"#{int(r) & 0xFF:02X}{int(g) & 0xFF:02X}{int(b) & 0xFF:02X}"


def hex_at_image_pixel(image: QImage, x: int, y: int) -> str | None:
    """Sample one pixel; ``None`` if out of bounds or invalid."""
    if image is None or image.isNull():
        return None
    if x < 0 or y < 0 or x >= image.width() or y >= image.height():
        return None
    c = QColor(image.pixelColor(x, y))
    if not c.isValid():
        return None
    return rgb_to_hex(c.red(), c.green(), c.blue())


class _PickCanvas(QLabel):
    """Shows a scaled image; click samples the underlying pixel."""

    colorPicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setStyleSheet(
            "QLabel { background:#1e293b; border:1px solid #64748b; }"
        )
        self.setToolTip("Klicken = Farbe aufnehmen und Hex kopieren")
        self._source: QImage | None = None
        self._disp_w = 0
        self._disp_h = 0
        self._off_x = 0
        self._off_y = 0

    def set_source_image(self, image: QImage) -> None:
        self._source = image.copy() if not image.isNull() else None
        self._refit()

    def has_image(self) -> bool:
        return self._source is not None and not self._source.isNull()

    def _refit(self) -> None:
        if self._source is None or self._source.isNull():
            self.clear()
            self._disp_w = self._disp_h = 0
            return
        avail_w = max(1, self.width() - 4)
        avail_h = max(1, self.height() - 4)
        pix = QPixmap.fromImage(self._source)
        scaled = pix.scaled(
            avail_w,
            avail_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self._disp_w = scaled.width()
        self._disp_h = scaled.height()
        self._off_x = max(0, (self.width() - self._disp_w) // 2)
        self._off_y = max(0, (self.height() - self._disp_h) // 2)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refit()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        if self._source is None or self._disp_w <= 0 or self._disp_h <= 0:
            return
        lx = int(event.position().x()) - self._off_x
        ly = int(event.position().y()) - self._off_y
        if lx < 0 or ly < 0 or lx >= self._disp_w or ly >= self._disp_h:
            return
        sx = int(lx * self._source.width() / self._disp_w)
        sy = int(ly * self._source.height() / self._disp_h)
        hex_color = hex_at_image_pixel(self._source, sx, sy)
        if hex_color:
            self.colorPicked.emit(hex_color)


class ColorPipetteDialog(QDialog):
    """Always-on-top: Referenzbild laden, Pipette, Hex → Zwischenablage."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        initial_image: str | Path | None = None,
        start_dir: str | Path | None = None,
    ) -> None:
        super().__init__(None)
        self.setWindowTitle("Pipette — Farbe aus Bild")
        self.setMinimumSize(480, 420)
        self._start_dir = self._resolve_start_dir(start_dir)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Referenzbild laden, dann klicken: Hex-Code wird in die "
            "Zwischenablage kopiert (Strg+V in Farbfelder)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b; font-size:12px;")
        layout.addWidget(hint)

        tools = QHBoxLayout()
        self.btn_load = QPushButton("Bild laden…")
        self.btn_load.clicked.connect(self._load_image)
        tools.addWidget(self.btn_load)
        self.btn_copy = QPushButton("Hex erneut kopieren")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy_again)
        tools.addWidget(self.btn_copy)
        tools.addStretch(1)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.close)
        tools.addWidget(close_btn)
        layout.addLayout(tools)

        self.canvas = _PickCanvas()
        self.canvas.colorPicked.connect(self._on_color_picked)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.canvas)
        layout.addWidget(scroll, 1)

        status_row = QHBoxLayout()
        self.swatch = QLabel()
        self.swatch.setFixedSize(36, 28)
        self.swatch.setStyleSheet(
            "background:#ffffff; border:1px solid #94a3b8; border-radius:3px;"
        )
        status_row.addWidget(self.swatch)
        self.hex_label = QLabel("—")
        self.hex_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.hex_label.setStyleSheet("font-weight:600; font-size:14px;")
        status_row.addWidget(self.hex_label)
        status_row.addStretch(1)
        self.clip_status = QLabel("")
        self.clip_status.setStyleSheet("color:#15803d; font-size:12px;")
        status_row.addWidget(self.clip_status)
        layout.addLayout(status_row)

        self._last_hex = ""
        prepare_autonomous_window(self, parent)
        # Always on top — after prepare so we keep Window flags + stay-on-top.
        self.setWindowFlags(_WINDOW_FLAGS)
        self.setModal(False)

        if initial_image is not None and str(initial_image).strip():
            self._try_load_path(Path(str(initial_image)))

    @staticmethod
    def _resolve_start_dir(start_dir: str | Path | None) -> str:
        if start_dir is not None and str(start_dir).strip():
            p = Path(str(start_dir)).expanduser()
            if p.is_dir():
                return str(p.resolve())
            if p.parent.is_dir():
                return str(p.parent.resolve())
        return ""

    def set_start_dir(self, start_dir: str | Path | None) -> None:
        self._start_dir = self._resolve_start_dir(start_dir)

    def _try_load_path(self, path: Path) -> bool:
        resolved = path.expanduser()
        if not resolved.is_file():
            return False
        image = QImage(str(resolved))
        if image.isNull():
            return False
        self.canvas.set_source_image(image.convertToFormat(QImage.Format.Format_RGB32))
        self.clip_status.setText(str(resolved.name))
        self.clip_status.setStyleSheet("color:#5b6785; font-size:12px;")
        return True

    def _load_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Referenzbild für Pipette",
            self._start_dir,
            _IMAGE_FILTER,
        )
        if not path:
            return
        if not self._try_load_path(Path(path)):
            QMessageBox.warning(
                self, "Pipette", f"Bild nicht lesbar:\n{path}"
            )

    def _on_color_picked(self, hex_color: str) -> None:
        self._last_hex = hex_color
        self.hex_label.setText(hex_color)
        self.btn_copy.setEnabled(True)
        border = "#334155"
        self.swatch.setStyleSheet(
            f"background:{hex_color}; border:1px solid {border}; border-radius:3px;"
        )
        self._copy_to_clipboard(hex_color)

    def _copy_again(self) -> None:
        if self._last_hex:
            self._copy_to_clipboard(self._last_hex)

    def _copy_to_clipboard(self, hex_color: str) -> None:
        try:
            QApplication.clipboard().setText(hex_color)
        except RuntimeError as exc:
            _LOG.debug("clipboard failed: %s", exc)
            self.clip_status.setText("Zwischenablage fehlgeschlagen")
            self.clip_status.setStyleSheet("color:#b91c1c; font-size:12px;")
            return
        self.clip_status.setText(f"{hex_color} kopiert")
        self.clip_status.setStyleSheet("color:#15803d; font-size:12px;")


def open_color_pipette(
    parent: Optional[QWidget] = None,
    *,
    initial_image: str | Path | None = None,
    start_dir: str | Path | None = None,
    **kwargs: Any,
) -> int:
    """Open the always-on-top pipette (single instance)."""
    _ = kwargs
    existing = raise_if_open(_active, lambda _d: True)
    if existing is not None:
        if start_dir is not None:
            existing.set_start_dir(start_dir)
        if initial_image is not None and str(initial_image).strip():
            existing._try_load_path(Path(str(initial_image)))
        return 0
    dlg = ColorPipetteDialog(
        parent, initial_image=initial_image, start_dir=start_dir
    )
    show_autonomous_window(dlg, _active)
    return 0


__all__ = [
    "ColorPipetteDialog",
    "hex_at_image_pixel",
    "open_color_pipette",
    "rgb_to_hex",
]
