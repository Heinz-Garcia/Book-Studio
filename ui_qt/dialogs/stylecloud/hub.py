"""Hub-Wolke: Verlaufsfelder, Ausrichtung, Einpassen und Aufbringen aufs Cover.

Mixin von ``StylecloudQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QPushButton,
)

from tools.stylecloud.generator import (
    DEFAULT_HUB_GRADIENT,
    ICON_HUB,
    PRINT_DPI,
    StylecloudOptions,
    composite_hub_raw_on_cover,
    finalize_png,
    normalize_hub_gradient,
    resolve_pack_raw_path,
)


class HubMixin:
    """Hub-Wolke: Verlaufsfelder, Ausrichtung, Einpassen und Aufbringen aufs Cover."""

    def _make_hub_swatch(self, hex_color: str) -> QPushButton:
        """Flat color button → QColorDialog for hub gradient stops."""
        btn = QPushButton()
        btn.setFixedSize(48, 28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("hub_hex", hex_color)
        btn.setToolTip("Klicken zum Wählen der Verlaufsfarbe")
        self._paint_hub_swatch(btn)
        btn.clicked.connect(lambda *_a, b=btn: self._pick_hub_swatch(b))
        return btn

    def _paint_hub_swatch(self, btn: QPushButton) -> None:
        hex_color = str(btn.property("hub_hex") or "#888888")
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {hex_color}; "
            f"border: 1px solid #444; border-radius: 4px; }}"
        )

    def _pick_hub_swatch(self, btn: QPushButton) -> None:
        current = QColor(str(btn.property("hub_hex") or "#888888"))
        chosen = QColorDialog.getColor(current, self, "Verlaufsfarbe wählen")
        if chosen.isValid():
            btn.setProperty("hub_hex", chosen.name(QColor.NameFormat.HexRgb))
            self._paint_hub_swatch(btn)
            self._update_hub_gradient_preview()

    def _hub_gradient_stops(self) -> list[str]:
        return normalize_hub_gradient(
            [
                str(self._hub_swatch_a.property("hub_hex") or DEFAULT_HUB_GRADIENT[0]),
                str(self._hub_swatch_b.property("hub_hex") or DEFAULT_HUB_GRADIENT[1]),
                str(self._hub_swatch_c.property("hub_hex") or DEFAULT_HUB_GRADIENT[2]),
            ]
        )

    def _set_hub_gradient_stops(self, stops: object) -> None:
        parts = normalize_hub_gradient(stops)
        for btn, hex_color in zip(
            (self._hub_swatch_a, self._hub_swatch_b, self._hub_swatch_c),
            parts,
            strict=True,
        ):
            btn.setProperty("hub_hex", hex_color)
            self._paint_hub_swatch(btn)
        self._update_hub_gradient_preview()

    def _update_hub_gradient_preview(self) -> None:
        a, b, c = self._hub_gradient_stops()
        self._hub_grad_preview.setStyleSheet(
            f"border:1px solid #666; border-radius:4px; "
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            f"stop:0 {a}, stop:0.5 {b}, stop:1 {c});"
        )

    def _on_hub_orient_changed(self, value: int) -> None:
        quer = int(value)
        hoch = 100 - quer
        self.hub_orient_label.setText(f"{quer} % quer · {hoch} % hoch")
        if self._restoring or self._is_generating:
            return
        if self.hub_orient_slider.isSliderDown():
            return
        self._layout_regen_timer.start()

    def _on_hub_orient_committed(self) -> None:
        """Back-compat alias."""
        self._on_layout_slider_committed()

    def _set_hub_fit_enabled(self, enabled: bool) -> None:
        for w in (
            self.btn_scale_down,
            self.btn_scale_up,
            self.btn_scale_reset,
            self.cover_scale_label,
        ):
            w.setEnabled(bool(enabled))

    def _prefer_hub_raw(self) -> bool:
        return (
            not self.mask_path.text().strip()
            and self._resolved_icon_name() == ICON_HUB
        )

    def _recomposite_hub_to_cover(self) -> None:
        """Re-place packed cloud onto cover with current scale — no re-pack."""
        out = self._last_output_path
        if out is None:
            return
        raw = resolve_pack_raw_path(out, prefer_hub=self._prefer_hub_raw())
        if raw is None or not raw.is_file():
            raw = self._hub_raw_path
        if raw is None or out is None or not raw.is_file():
            return
        if self._is_generating:
            return
        try:
            size = self._resolved_size()
            opts = StylecloudOptions(
                text=".",
                output_path=out,
                size=size if size is not None else 1024,
                icon_name=self._resolved_icon_name(),
                mask_path=(
                    Path(self.mask_path.text().strip())
                    if self.mask_path.text().strip()
                    else None
                ),
                background_color=self.bg_edit.text().strip() or "white",
                cover_scale=float(self._cover_scale),
                png_compress_level=int(self.png_compress.value()),
                png_optimize=self.png_optimize.isChecked(),
                png_dpi=int(self.png_dpi.value()),
            )
            composite_hub_raw_on_cover(raw, out, opts)
            finalize_png(
                out,
                compress_level=opts.png_compress_level,
                optimize=opts.png_optimize,
                dpi=int(opts.png_dpi or PRINT_DPI),
            )
            if self.save_svg.isChecked():
                from tools.stylecloud.generator import export_stylecloud_svg

                opts.save_svg = True
                opts.cover_scale = float(self._cover_scale)
                export_stylecloud_svg(opts, out)
            self._hub_raw_path = raw
            pix = QPixmap(str(out))
            if not pix.isNull():
                self._preview_pixmap = pix
                self._refresh_preview_pixmap()
            self.status.setText(
                f"Einpassen {int(round(self._cover_scale * 100))} % — "
                f"ohne Neu-Berechnung."
            )
        except (OSError, ValueError, FileNotFoundError) as exc:
            self.status.setText(f"Einpassen fehlgeschlagen: {exc}")
