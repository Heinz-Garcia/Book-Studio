"""Vorderseite: Bildmodus und Compose-Layer (Fade, Band, Titel, Fuß, Banner, Badge).

Mixin von ``KdpCoverQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QWidget,
)

from tools.kdp_cover.model import (
    FrontImageMode,
)
from ui_qt.dialogs.kdp_cover.common import (
    _IMAGE_FILTER,
    _qlabel_color_ss,
)
from ui_qt.dialogs.kdp_cover.front_compose_ui import FrontComposeUiMixin


class FrontMixin(FrontComposeUiMixin):
    """Vorderseite: Bildmodus und Compose-Layer (Fade, Band, Titel, Fuß, Banner, Badge)."""

    def apply_front_image(
        self,
        path: str | Path | None,
        *,
        disable_compose: bool = False,
    ) -> bool:
        """Set front image path and refresh preview.

        ``disable_compose`` ist veraltet (kein Master-Kill mehr) und wird ignoriert.
        Returns True when the file exists and was applied.
        """
        if path is None or not str(path).strip():
            return False
        resolved = Path(str(path)).expanduser().resolve()
        if not resolved.is_file():
            return False
        self.front_edit.setText(str(resolved))
        self._ensure_front_image_mode_for_path()
        if not self._params_guard:
            self._preview_timer.stop()
            self._refresh_preview()
        return True

    def _apply_initial_front_image(self) -> None:
        """Optional Prefill (z. B. Stylecloud-Übergabe) — überschreibt Deckblatt/Projekt."""
        raw = self._initial_front_image
        if raw is None or not str(raw).strip():
            return
        # Schlagwortwolke = Hintergrund; Projekt-Layer (Titel/Bänder) bleiben darüber.
        ok = self.apply_front_image(raw, disable_compose=False)
        if not ok and hasattr(self, "status_label"):
            self.status_label.setText(
                f"● Übergabe-Bild nicht gefunden: {raw}"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#b91c1c", weight="600"))

    def _browse_compose_badge(self, asset_key: str = "badge") -> None:
        start = str(self._book / "img") if self._book else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Badge-/Overlay-Bild", start, _IMAGE_FILTER
        )
        if not path:
            return
        if asset_key == "badge2":
            self.compose_badge2_image.setText(path)
        else:
            self.compose_badge_image.setText(path)
        self._on_params_changed()

    def _apply_fade_autofade(self) -> None:
        """Vollfarbe oben/unten → minimales Soft-Weiß auf der Gegenseite."""
        from tools.kdp_cover.compose_front import FadeSpec, resolve_autofade_side

        side = resolve_autofade_side(
            top_enabled=self.compose_fade_enabled.isChecked(),
            bottom_enabled=self.compose_fade_bottom_enabled.isChecked(),
            top_color=self.compose_fade_color.text(),
            bottom_color=self.compose_fade_bottom_color.text(),
        )
        if side is None:
            QMessageBox.information(
                self,
                "Autofade",
                "Zuerst die Vollfarbe oben oder unten aktivieren "
                "(Haken an), dann Autofade — der Softener nach Weiß "
                "kommt auf die Gegenseite.",
            )
            return
        soft = FadeSpec.soft_white(enabled=True)
        if side == "bottom":
            self.compose_fade_bottom_enabled.setChecked(True)
            self.compose_fade_bottom_color.setText(soft.color)
            self.compose_fade_bottom_height.setValue(soft.height_pct)
            self.compose_fade_bottom_opacity.setValue(soft.opacity)
        else:
            self.compose_fade_enabled.setChecked(True)
            self.compose_fade_color.setText(soft.color)
            self.compose_fade_height.setValue(soft.height_pct)
            self.compose_fade_opacity.setValue(soft.opacity)
        self._on_params_changed()

    def _apply_fade_soft_white_preset(self) -> None:
        """Alias — historischer Name; gleiche Aktion wie Autofade."""
        self._apply_fade_autofade()

    def _invert_fade_direction(self) -> None:
        """Swap Fade oben ↔ unten (enabled, color, height, opacity)."""
        top = (
            self.compose_fade_enabled.isChecked(),
            self.compose_fade_color.text(),
            float(self.compose_fade_height.value()),
            float(self.compose_fade_opacity.value()),
        )
        bottom = (
            self.compose_fade_bottom_enabled.isChecked(),
            self.compose_fade_bottom_color.text(),
            float(self.compose_fade_bottom_height.value()),
            float(self.compose_fade_bottom_opacity.value()),
        )
        self.compose_fade_enabled.setChecked(bottom[0])
        self.compose_fade_color.setText(bottom[1])
        self.compose_fade_height.setValue(bottom[2])
        self.compose_fade_opacity.setValue(bottom[3])
        self.compose_fade_bottom_enabled.setChecked(top[0])
        self.compose_fade_bottom_color.setText(top[1])
        self.compose_fade_bottom_height.setValue(top[2])
        self.compose_fade_bottom_opacity.setValue(top[3])
        self._on_params_changed()

    def _collect_front_compose(self) -> dict[str, Any]:
        from tools.kdp_cover.compose_front.model import FrontComposeSpec

        raw = {
            "enabled": True,
            "fade": {
                "enabled": self.compose_fade_enabled.isChecked(),
                "color": self.compose_fade_color.text().strip() or "#FFFFFF",
                "height_pct": float(self.compose_fade_height.value()),
                "opacity": float(self.compose_fade_opacity.value()),
            },
            "fade_bottom": {
                "enabled": self.compose_fade_bottom_enabled.isChecked(),
                "color": self.compose_fade_bottom_color.text().strip() or "#FFFFFF",
                "height_pct": float(self.compose_fade_bottom_height.value()),
                "opacity": float(self.compose_fade_bottom_opacity.value()),
            },
            "band": {
                "enabled": self.compose_band_enabled.isChecked(),
                "y_pct": float(self.compose_band_y.value()),
                "height_pct": float(self.compose_band_h.value()),
                "color": self.compose_band_color.text().strip() or "#E8A0B0",
                "opacity": 1.0,
                "text": self.compose_band_text.text().strip(),
                "text_color": self.compose_band_text_color.text().strip() or "#FFFFFF",
                "text_size_pct": float(self.compose_band_text_size.value()),
                "font": str(self.compose_band_font.currentData() or "sans"),
            },
            "titles": {
                "enabled": self.compose_titles_enabled.isChecked(),
                "align": str(self.compose_titles_align.currentData() or "center"),
                "offset_x_pct": float(self.compose_titles_offset_x.value()),
                "lines_size_pct": float(self.compose_lines_size.value()),
                "lines_bold": self.compose_lines_bold.isChecked(),
                "lines_font": str(self.compose_lines_font.currentData() or "sans"),
                "lines_gap_pct": float(self.compose_lines_gap.value()),
                "series": {
                    "text": self.compose_series.text().strip(),
                    "color": self.compose_series_color.text().strip() or "#1E3A5F",
                },
                "main": {
                    "text": self.compose_main.text().strip(),
                    "color": self.compose_main_color.text().strip() or "#1E3A5F",
                },
                "subtitle": {
                    "enabled": self.compose_subtitle_enabled.isChecked(),
                    "top_pct": float(self.compose_subtitle_top.value()),
                    "gap_pct": float(self.compose_subtitle_gap.value()),
                    "band": {
                        "enabled": self.compose_subtitle_band_enabled.isChecked(),
                        "color": self.compose_subtitle_band_color.text().strip()
                        or "#1E3A5F",
                        "padding_top_pct": float(
                            self.compose_subtitle_band_pad_top.value()
                        ),
                        "padding_bottom_pct": float(
                            self.compose_subtitle_band_pad_bottom.value()
                        ),
                    },
                    "line1": {
                        "text": self.compose_sub1.text().strip(),
                        "color": self.compose_sub1_color.text().strip() or "#FFFFFF",
                        "size_pct": float(self.compose_sub1_size.value()),
                        "font": str(self.compose_sub1_font.currentData() or "sans"),
                        "bold": self.compose_sub1_bold.isChecked(),
                        "italic": self.compose_sub1_italic.isChecked(),
                    },
                    "line2": {
                        "text": self.compose_sub2.text().strip(),
                        "color": self.compose_sub2_color.text().strip() or "#FFFFFF",
                        "size_pct": float(self.compose_sub2_size.value()),
                        "font": str(self.compose_sub2_font.currentData() or "sans"),
                        "bold": self.compose_sub2_bold.isChecked(),
                        "italic": self.compose_sub2_italic.isChecked(),
                    },
                },
                "accent": {
                    "text": self.compose_accent.text().strip(),
                    "color": self.compose_accent_color.text().strip() or "#9B2C3E",
                    "size_pct": float(self.compose_accent_size.value()),
                    "italic": self.compose_accent_italic.isChecked(),
                    "bold": self.compose_accent_bold.isChecked(),
                    "font": str(self.compose_accent_font.currentData() or "sans"),
                },
                "author": {
                    "text": self.compose_author.text().strip(),
                    "color": self.compose_author_color.text().strip() or "#FFFFFF",
                    "size_pct": float(self.compose_author_size.value()),
                    "italic": self.compose_author_italic.isChecked(),
                    "bold": self.compose_author_bold.isChecked(),
                    "font": str(self.compose_author_font.currentData() or "sans"),
                },
                "top_pct": float(self.compose_titles_top.value()),
                "accent_top_pct": float(self.compose_accent_top.value()),
                "author_top_pct": float(self.compose_author_top.value()),
            },
            "footer": {
                "enabled": self.compose_footer_enabled.isChecked(),
                "line1": self.compose_footer_line1.text().strip(),
                "line2": self.compose_footer_line2.text().strip(),
                "color": self.compose_footer_color.text().strip() or "#FFFFFF",
                "bottom_pct": float(self.compose_footer_bottom.value()),
                "align": str(self.compose_footer_align.currentData() or "center"),
                "offset_x_pct": float(self.compose_footer_offset_x.value()),
                "font": str(self.compose_footer_font.currentData() or "sans"),
                "band": {
                    "enabled": self.compose_footer_band_enabled.isChecked(),
                    "color": self.compose_footer_band_color.text().strip()
                    or "#1E3A5F",
                    "padding_top_pct": float(self.compose_footer_band_pad_top.value()),
                    "padding_bottom_pct": float(
                        self.compose_footer_band_pad_bottom.value()
                    ),
                },
            },
            "corner_ribbon": {
                "enabled": self.compose_corner_enabled.isChecked(),
                "text": self.compose_corner_text.text().strip(),
                "color": self.compose_corner_color.text().strip() or "#3DBDB0",
                "text_color": self.compose_corner_text_color.text().strip() or "#FFFFFF",
                "size_pct": float(self.compose_corner_size.value()),
                "font_scale": float(self.compose_corner_font.value()) / 100.0,
                "font": str(self.compose_corner_font_family.currentData() or "sans"),
                "show_icon": self.compose_corner_icon.isChecked(),
                "corner": str(self.compose_corner_pos.currentData() or "top_right"),
                "offset_x_pct": float(self.compose_corner_offset_x.value()),
                "offset_y_pct": float(self.compose_corner_offset_y.value()),
                "text_padding_pct": float(self.compose_corner_text_pad.value()),
            },
            "badge": {
                "enabled": self.compose_badge_enabled.isChecked(),
                "image": self.compose_badge_image.text().strip(),
                "text": self.compose_badge_text.text().strip(),
                "text_color": self.compose_badge_text_color.text().strip() or "#1E3A5F",
                "bold": self.compose_badge_bold.isChecked(),
                "font": str(self.compose_badge_font.currentData() or "sans"),
                "x_pct": float(self.compose_badge_x.value()),
                "y_pct": float(self.compose_badge_y.value()),
                "scale_pct": float(self.compose_badge_scale.value()),
                "rotation_deg": float(self.compose_badge_rot.value()),
            },
            "badge2": {
                "enabled": self.compose_badge2_enabled.isChecked(),
                "image": self.compose_badge2_image.text().strip(),
                "text": self.compose_badge2_text.text().strip(),
                "text_color": self.compose_badge2_text_color.text().strip() or "#1E3A5F",
                "bold": self.compose_badge2_bold.isChecked(),
                "font": str(self.compose_badge2_font.currentData() or "sans"),
                "x_pct": float(self.compose_badge2_x.value()),
                "y_pct": float(self.compose_badge2_y.value()),
                "scale_pct": float(self.compose_badge2_scale.value()),
                "rotation_deg": float(self.compose_badge2_rot.value()),
            },
        }
        return FrontComposeSpec.from_dict(raw).to_dict()

    def _apply_front_compose(self, data: dict[str, Any] | None) -> None:
        from tools.kdp_cover.compose_front.model import FrontComposeSpec

        was_guarded = self._params_guard
        self._params_guard = True
        try:
            spec = FrontComposeSpec.from_dict(data if isinstance(data, dict) else None)
            # UI malt immer über Einzellayer — Master-Flag nicht mehr als Falle.
            self.compose_enabled.setChecked(True)
            self.compose_fade_enabled.setChecked(spec.fade.enabled)
            self.compose_fade_color.setText(spec.fade.color)
            self.compose_fade_height.setValue(spec.fade.height_pct)
            self.compose_fade_opacity.setValue(spec.fade.opacity)
            self.compose_fade_bottom_enabled.setChecked(spec.fade_bottom.enabled)
            self.compose_fade_bottom_color.setText(spec.fade_bottom.color)
            self.compose_fade_bottom_height.setValue(spec.fade_bottom.height_pct)
            self.compose_fade_bottom_opacity.setValue(spec.fade_bottom.opacity)
            self.compose_band_enabled.setChecked(spec.band.enabled)
            self.compose_band_y.setValue(spec.band.y_pct)
            self.compose_band_h.setValue(spec.band.height_pct)
            self.compose_band_color.setText(spec.band.color)
            self.compose_band_text.setText(spec.band.text)
            self.compose_band_text_color.setText(spec.band.text_color)
            self.compose_band_text_size.setValue(spec.band.text_size_pct)
            self._set_font_combo(
                self.compose_band_font, getattr(spec.band, "font", "sans")
            )
            self.compose_titles_enabled.setChecked(spec.titles.enabled)
            align = str(getattr(spec.titles, "align", "center") or "center")
            ai = self.compose_titles_align.findData(align)
            self.compose_titles_align.setCurrentIndex(ai if ai >= 0 else 1)
            self.compose_titles_offset_x.setValue(
                float(getattr(spec.titles, "offset_x_pct", 0.0) or 0.0)
            )
            self.compose_titles_top.setValue(spec.titles.top_pct)
            self.compose_series.setText(spec.titles.series.text)
            self.compose_series_color.setText(spec.titles.series.color)
            self.compose_main.setText(spec.titles.main.text)
            self.compose_main_color.setText(spec.titles.main.color)
            self.compose_lines_size.setValue(spec.titles.lines_size_pct)
            self.compose_lines_bold.setChecked(spec.titles.lines_bold)
            self._set_font_combo(
                self.compose_lines_font, getattr(spec.titles, "lines_font", "sans")
            )
            self.compose_lines_gap.setValue(
                float(getattr(spec.titles, "lines_gap_pct", 1.2) or 1.2)
            )
            self.compose_accent.setText(spec.titles.accent.text)
            self.compose_accent_color.setText(spec.titles.accent.color)
            self.compose_accent_size.setValue(spec.titles.accent.size_pct)
            self.compose_accent_top.setValue(spec.titles.accent_top_pct)
            self.compose_accent_bold.setChecked(spec.titles.accent.bold)
            self.compose_accent_italic.setChecked(spec.titles.accent.italic)
            self._set_font_combo(
                self.compose_accent_font, getattr(spec.titles.accent, "font", "sans")
            )
            author = getattr(spec.titles, "author", None)
            if author is None:
                self.compose_author.clear()
                self.compose_author_color.setText("#FFFFFF")
                self.compose_author_size.setValue(3.5)
                self.compose_author_top.setValue(26.0)
                self.compose_author_bold.setChecked(False)
                self.compose_author_italic.setChecked(False)
                self._set_font_combo(self.compose_author_font, "sans")
            else:
                self.compose_author.setText(author.text)
                self.compose_author_color.setText(author.color)
                self.compose_author_size.setValue(author.size_pct)
                self.compose_author_top.setValue(
                    float(getattr(spec.titles, "author_top_pct", 26.0) or 26.0)
                )
                self.compose_author_bold.setChecked(bool(author.bold))
                self.compose_author_italic.setChecked(bool(author.italic))
                self._set_font_combo(
                    self.compose_author_font, getattr(author, "font", "sans")
                )
            sub = getattr(spec.titles, "subtitle", None)
            if sub is None:
                self.compose_subtitle_enabled.setChecked(False)
                self.compose_subtitle_band_enabled.setChecked(False)
            else:
                self.compose_subtitle_enabled.setChecked(bool(sub.enabled))
                self.compose_subtitle_top.setValue(float(sub.top_pct))
                self.compose_subtitle_gap.setValue(float(sub.gap_pct))
                sub_band = getattr(sub, "band", None)
                if sub_band is None:
                    self.compose_subtitle_band_enabled.setChecked(False)
                else:
                    self.compose_subtitle_band_enabled.setChecked(bool(sub_band.enabled))
                    self.compose_subtitle_band_color.setText(sub_band.color)
                    self.compose_subtitle_band_pad_top.setValue(
                        float(
                            getattr(
                                sub_band,
                                "padding_top_pct",
                                getattr(sub_band, "padding_pct", 1.2),
                            )
                        )
                    )
                    self.compose_subtitle_band_pad_bottom.setValue(
                        float(
                            getattr(
                                sub_band,
                                "padding_bottom_pct",
                                getattr(sub_band, "padding_pct", 1.2),
                            )
                        )
                    )
                self.compose_sub1.setText(sub.line1.text)
                self.compose_sub1_color.setText(sub.line1.color)
                self.compose_sub1_size.setValue(sub.line1.size_pct)
                self._set_font_combo(
                    self.compose_sub1_font, getattr(sub.line1, "font", "sans")
                )
                self.compose_sub1_bold.setChecked(bool(sub.line1.bold))
                self.compose_sub1_italic.setChecked(bool(sub.line1.italic))
                self.compose_sub2.setText(sub.line2.text)
                self.compose_sub2_color.setText(sub.line2.color)
                self.compose_sub2_size.setValue(sub.line2.size_pct)
                self._set_font_combo(
                    self.compose_sub2_font, getattr(sub.line2, "font", "sans")
                )
                self.compose_sub2_bold.setChecked(bool(sub.line2.bold))
                self.compose_sub2_italic.setChecked(bool(sub.line2.italic))
            self.compose_footer_enabled.setChecked(spec.footer.enabled)
            self.compose_footer_line1.setText(spec.footer.line1)
            self.compose_footer_line2.setText(spec.footer.line2)
            self.compose_footer_color.setText(spec.footer.color)
            self.compose_footer_bottom.setValue(spec.footer.bottom_pct)
            self._set_font_combo(
                self.compose_footer_font, getattr(spec.footer, "font", "sans")
            )
            f_align = str(getattr(spec.footer, "align", "center") or "center")
            fai = self.compose_footer_align.findData(f_align)
            self.compose_footer_align.setCurrentIndex(fai if fai >= 0 else 1)
            self.compose_footer_offset_x.setValue(
                float(getattr(spec.footer, "offset_x_pct", 0.0) or 0.0)
            )
            foot_band = getattr(spec.footer, "band", None)
            if foot_band is None:
                self.compose_footer_band_enabled.setChecked(False)
            else:
                self.compose_footer_band_enabled.setChecked(bool(foot_band.enabled))
                self.compose_footer_band_color.setText(foot_band.color)
                self.compose_footer_band_pad_top.setValue(
                    float(
                        getattr(
                            foot_band,
                            "padding_top_pct",
                            getattr(foot_band, "padding_pct", 1.2),
                        )
                    )
                )
                self.compose_footer_band_pad_bottom.setValue(
                    float(
                        getattr(
                            foot_band,
                            "padding_bottom_pct",
                            getattr(foot_band, "padding_pct", 1.2),
                        )
                    )
                )
            self.compose_corner_enabled.setChecked(spec.corner_ribbon.enabled)
            self.compose_corner_text.setText(spec.corner_ribbon.text)
            self.compose_corner_color.setText(spec.corner_ribbon.color)
            self.compose_corner_text_color.setText(spec.corner_ribbon.text_color)
            self.compose_corner_size.setValue(spec.corner_ribbon.size_pct)
            self.compose_corner_font.setValue(
                float(getattr(spec.corner_ribbon, "font_scale", 1.0) or 1.0) * 100.0
            )
            self._set_font_combo(
                self.compose_corner_font_family,
                getattr(spec.corner_ribbon, "font", "sans"),
            )
            self.compose_corner_icon.setChecked(spec.corner_ribbon.show_icon)
            cidx = self.compose_corner_pos.findData(spec.corner_ribbon.corner)
            if cidx >= 0:
                self.compose_corner_pos.setCurrentIndex(cidx)
            self.compose_corner_offset_x.setValue(
                float(getattr(spec.corner_ribbon, "offset_x_pct", 0.0) or 0.0)
            )
            self.compose_corner_offset_y.setValue(
                float(getattr(spec.corner_ribbon, "offset_y_pct", 0.0) or 0.0)
            )
            self.compose_corner_text_pad.setValue(
                float(getattr(spec.corner_ribbon, "text_padding_pct", 10.0) or 10.0)
            )
            self.compose_badge_enabled.setChecked(spec.badge.enabled)
            self.compose_badge_image.setText(spec.badge.image)
            self.compose_badge_text.setText(spec.badge.text)
            self.compose_badge_text_color.setText(spec.badge.text_color)
            self.compose_badge_bold.setChecked(spec.badge.bold)
            self._set_font_combo(
                self.compose_badge_font, getattr(spec.badge, "font", "sans")
            )
            self.compose_badge_x.setValue(spec.badge.x_pct)
            self.compose_badge_y.setValue(spec.badge.y_pct)
            self.compose_badge_scale.setValue(spec.badge.scale_pct)
            self.compose_badge_rot.setValue(spec.badge.rotation_deg)
            self.compose_badge2_enabled.setChecked(spec.badge2.enabled)
            self.compose_badge2_image.setText(spec.badge2.image)
            self.compose_badge2_text.setText(spec.badge2.text)
            self.compose_badge2_text_color.setText(spec.badge2.text_color)
            self.compose_badge2_bold.setChecked(spec.badge2.bold)
            self._set_font_combo(
                self.compose_badge2_font, getattr(spec.badge2, "font", "sans")
            )
            self.compose_badge2_x.setValue(spec.badge2.x_pct)
            self.compose_badge2_y.setValue(spec.badge2.y_pct)
            self.compose_badge2_scale.setValue(spec.badge2.scale_pct)
            self.compose_badge2_rot.setValue(spec.badge2.rotation_deg)
        finally:
            self._params_guard = was_guarded
        self._sync_compose_front_tab_visibility()

    def _current_front_image_mode(self) -> FrontImageMode:
        if self.front_mode_top_third.isChecked():
            return "top_third"
        if self.front_mode_full.isChecked():
            return "full"
        return "none"

    def _set_front_image_mode_ui(self, mode: FrontImageMode) -> None:
        if mode == "top_third":
            self.front_mode_top_third.setChecked(True)
        elif mode == "full":
            self.front_mode_full.setChecked(True)
        else:
            self.front_mode_none.setChecked(True)

    def _sync_front_image_mode_controls(self) -> None:
        """Bildpfad/Zoom/Pan nur bei Bildmodi aktiv; Farbe immer."""
        image_on = not self.front_mode_none.isChecked()
        for w in (
            self.front_edit,
            self._btn_front_asset,
            self._btn_front_browse,
            self._btn_stylecloud,
            self.front_zoom_spin,
            self.front_ox_spin,
            self.front_oy_spin,
        ):
            w.setEnabled(image_on)

    def _on_front_image_mode_changed(self, *_args: Any) -> None:
        if self._params_guard:
            return
        self._sync_front_image_mode_controls()
        self._on_params_changed()

    def _ensure_front_image_mode_for_path(self) -> None:
        """Nach Bildwahl: „Kein Bild“ → Vollfläche, damit die Auswahl sichtbar wird."""
        if self.front_mode_none.isChecked():
            self.front_mode_full.setChecked(True)
        self._sync_front_image_mode_controls()

    def _sync_compose_front_tab_visibility(self) -> None:
        """Tab „Vorderseite · Layout“ bei Flag/Default oder aktivem Layer zeigen."""
        idx = getattr(self, "_layer_tab_index", -1)
        tabs = getattr(self, "_editor_tabs", None)
        if idx < 0 or tabs is None:
            return
        from tools.kdp_cover.compose_front.flags import is_compose_front_ui_enabled

        project_on = True  # Layout-UI aktiv → Layer immer an (Einzellayer steuern)
        show = is_compose_front_ui_enabled(project_enabled=project_on)
        set_visible = getattr(tabs, "setTabVisible", None)
        if callable(set_visible):
            set_visible(idx, show)
        else:
            tabs.setTabEnabled(idx, show)

    def _open_gestaltung_tab(self) -> None:
        """Zum Tab Vorderseite · Layout springen (Texte/Layer)."""
        idx = getattr(self, "_layer_tab_index", -1)
        tabs = getattr(self, "_editor_tabs", None)
        if idx < 0 or tabs is None:
            return
        # Sicher sichtbar machen, falls Flag aus war.
        set_visible = getattr(tabs, "setTabVisible", None)
        if callable(set_visible):
            set_visible(idx, True)
        else:
            tabs.setTabEnabled(idx, True)
        tabs.setCurrentIndex(idx)
        self.raise_()
        self.activateWindow()

    def _browse_front(self) -> None:
        start = str(self._book / "img") if self._book else ""
        path, _ = QFileDialog.getOpenFileName(self, "Vorderseiten-Bild", start, _IMAGE_FILTER)
        if path:
            self.front_edit.setText(path)
            self._ensure_front_image_mode_for_path()
            self._on_params_changed()

    def _open_stylecloud_for_front(self) -> None:
        """Stylecloud öffnen — Wortwolke kann danach an diesen Dialog übergeben werden."""
        try:
            from ui_qt.dialogs.stylecloud_dialog import open_stylecloud_qt
        except ImportError:
            QMessageBox.information(
                self,
                "Stylecloud",
                "Stylecloud ist nicht verfügbar.",
            )
            return
        open_stylecloud_qt(self._studio, self)

    def _build_tab_front(self) -> None:
        """Tab 3 · Vorderseite · Bild."""
        # --- Tab: Vorderseite ---
        tab_front, front_body = self._make_editor_tab()
        front_hint = QLabel(
            "Bildmodus wählbar: nur Farbe, goldener Schnitt oder vollflächig. "
            "Wortwolke: Stylecloud → Übergabe hierher."
        )
        front_hint.setWordWrap(True)
        front_hint.setStyleSheet("color:#64748b; font-size:12px;")
        front_body.addWidget(front_hint)
        design_front = QFormLayout()
        design_front.setSpacing(8)
        front_body.addLayout(design_front)

        front_color_host, self.front_color_edit = self._color_field(
            "#1e3a5f",
            max_width=100,
            tooltip=(
                "Vorderseiten-Farbe: allein bei „Kein Bild“, "
                "unter dem Bildband bei „goldener Schnitt“, "
                "Unterlage bei Vollbild/Wortwolke."
            ),
        )
        design_front.addRow("Front-Farbe:", front_color_host)

        self.front_mode_none = QRadioButton("Kein Bild (nur Farbe)")
        self.front_mode_top_third = QRadioButton("Bild im goldenen Schnitt")
        self.front_mode_full = QRadioButton("Bild vollflächig")
        self.front_mode_none.setToolTip(
            "Nur Front-Farbe — Bildpfad bleibt erhalten, wird aber nicht gezeichnet."
        )
        self.front_mode_top_third.setToolTip(
            "Bild füllt die oberen ~38,2 % (goldener Schnitt; Zoom/Verschieben "
            "möglich); darunter die Front-Farbe."
        )
        self.front_mode_full.setToolTip(
            "Bild deckt die gesamte Vorderseite ab (Cover-Fit + Zoom/Verschieben)."
        )
        self.front_mode_none.setChecked(True)
        self.front_mode_group = QButtonGroup(self)
        self.front_mode_group.addButton(self.front_mode_none, 0)
        self.front_mode_group.addButton(self.front_mode_top_third, 1)
        self.front_mode_group.addButton(self.front_mode_full, 2)
        front_mode_row = QHBoxLayout()
        front_mode_row.setContentsMargins(0, 0, 0, 0)
        front_mode_row.setSpacing(12)
        front_mode_row.addWidget(self.front_mode_none)
        front_mode_row.addWidget(self.front_mode_top_third)
        front_mode_row.addWidget(self.front_mode_full)
        front_mode_row.addStretch(1)
        front_mode_host = QWidget()
        front_mode_host.setLayout(front_mode_row)
        design_front.addRow("Bildmodus:", front_mode_host)

        self.front_edit = QLineEdit()
        self.front_edit.setPlaceholderText(
            "Optional: Foto oder Stylecloud-Wortwolke…"
        )
        front_row = QHBoxLayout()
        front_row.addWidget(self.front_edit)
        self._btn_front_asset = QPushButton("Asset…")
        self._btn_front_asset.setToolTip(
            "Bild aus dem Asset Manager wählen (Pool oder Buch-img/)."
        )
        self._btn_front_asset.clicked.connect(
            lambda: self._pick_image_via_asset("front")
        )
        front_row.addWidget(self._btn_front_asset)
        self._btn_front_browse = QPushButton("…")
        self._btn_front_browse.setFixedWidth(32)
        self._btn_front_browse.setToolTip("Datei im Dateisystem wählen")
        self._btn_front_browse.clicked.connect(self._browse_front)
        front_row.addWidget(self._btn_front_browse)
        design_front.addRow("Bild / Wortwolke:", front_row)

        self._btn_stylecloud = QPushButton("Wortwolke (Stylecloud)…")
        self._btn_stylecloud.setToolTip(
            "Öffnet Stylecloud. Nach dem Erzeugen: „An KDP Cover übergeben“."
        )
        self._btn_stylecloud.clicked.connect(self._open_stylecloud_for_front)
        design_front.addRow("", self._btn_stylecloud)

        btn_gestalten = QPushButton("Layout öffnen…")
        btn_gestalten.setToolTip(
            "Tab „Vorderseite · Layout“: Titel, Band, Fade, Fußzeile, Banner, Badge "
            "(je Block ein/aus)."
        )
        btn_gestalten.clicked.connect(self._open_gestaltung_tab)
        design_front.addRow("", btn_gestalten)

        self.front_zoom_spin = QDoubleSpinBox()
        self.front_zoom_spin.setRange(1.0, 4.0)
        self.front_zoom_spin.setDecimals(2)
        self.front_zoom_spin.setSingleStep(0.05)
        self.front_zoom_spin.setValue(1.0)
        self.front_zoom_spin.setToolTip(
            "Vergrößern über Cover-Fit (≥ 1,0). Danach Ausschnitt mit Offset "
            "verschieben — gilt für goldenen Schnitt und Vollfläche."
        )
        design_front.addRow("Front-Zoom:", self.front_zoom_spin)
        self.front_ox_spin = self._mm_spin()
        self.front_oy_spin = self._mm_spin()
        self.front_ox_spin.setToolTip(
            "Horizontal (X): Bild nach rechts (+) / links (−) verschieben. "
            "Freie Ränder bleiben Front-Farbe."
        )
        self.front_oy_spin.setToolTip(
            "Vertikal (Y): Bild nach unten (+) / oben (−) verschieben. "
            "Freie Ränder bleiben Front-Farbe."
        )
        design_front.addRow(
            "Front-Verschiebung (X / Y):",
            self._pair(self.front_ox_spin, self.front_oy_spin),
        )
        self._editor_tabs.addTab(tab_front, "Vorderseite · Bild")
        self._front_tab_index = self._editor_tabs.count() - 1
        self._editor_tabs.setTabToolTip(
            self._front_tab_index,
            "3 · Vorderseite · Bild (Farbe, Bildmodus, Bild oder Stylecloud)",
        )

    def _build_tab_front_layout(self) -> None:
        """Tab 4 · Vorderseite · Layout (Compose-Layer)."""
        # --- Tab: Vorderseite · Layout (Layer über Farbe/Bild) ---
        tab_layer, layer_body = self._make_editor_tab()
        layer_body.addWidget(self._build_compose_front_group())
        self._layer_tab_index = self._editor_tabs.addTab(
            tab_layer, "Vorderseite · Layout"
        )
        self._editor_tabs.setTabToolTip(
            self._layer_tab_index,
            "4 · Vorderseite · Layout (Fade, Band, Titel, Fuß, Banner, Badge).",
        )
        self._sync_compose_front_tab_visibility()
