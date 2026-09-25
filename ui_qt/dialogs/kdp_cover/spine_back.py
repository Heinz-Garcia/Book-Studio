"""Rücken (Badge), Rückseite (Abbildung, Subtitel, Textblöcke) und Zonenkarte.

Mixin von ``KdpCoverQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
)

from tools.kdp_cover.constants import (
    SPINE_BADGE_SCALE_STEPS,
)
from tools.kdp_cover.compose_back import BackComposeSpec
from tools.kdp_cover.geometry import WrapGeometry
from tools.kdp_cover.model import (
    CoverLayout,
    SpineBadgeSpec,
)
from ui_qt.dialogs.kdp_cover.common import (
    _IMAGE_FILTER,
)



class SpineBackMixin:
    """Rücken (Badge), Rückseite (Abbildung, Subtitel, Textblöcke) und Zonenkarte."""

    def _sync_back_frame_controls(self) -> None:
        on = bool(self.back_frame_check.isChecked())
        self.back_frame_mm_spin.setEnabled(on)
        self.back_frame_color_host.setEnabled(on)

    def _sync_back_placement_controls(self, *_args: Any) -> None:
        free = str(self.back_placement_combo.currentData() or "center") == "free"
        self.back_scale_spin.setEnabled(not free)
        for w in (self.back_img_x_spin, self.back_img_y_spin, self.back_img_width_spin):
            w.setEnabled(free)

    def _collect_back_compose(self) -> dict[str, Any] | None:
        """Rückseiten-Elemente → Layout-Dict; ``None`` solange nichts erfasst ist."""
        subtitle, align, offset = self.back_subtitle_editor.to_spec()
        spec = BackComposeSpec(
            subtitle=subtitle,
            subtitle_align=align,
            subtitle_offset_x_pct=offset,
            blurb=self.back_blurb_editor.to_spec(),
            bio=self.back_bio_editor.to_spec(),
        )
        has_text = any(
            (
                subtitle.line1.text,
                subtitle.line2.text,
                spec.blurb.text,
                spec.bio.text,
            )
        )
        if spec.is_empty and not has_text:
            return None
        return spec.to_dict()

    def _apply_back_compose(self, data: dict[str, Any] | None) -> None:
        spec = BackComposeSpec.from_dict(data)
        self.back_subtitle_editor.set_spec(
            spec.subtitle,
            align=spec.subtitle_align,
            offset_x_pct=spec.subtitle_offset_x_pct,
        )
        self.back_blurb_editor.set_spec(spec.blurb)
        self.back_bio_editor.set_spec(spec.bio)

    def _refresh_zone_maps(self, layout: CoverLayout, geo: WrapGeometry) -> None:
        """Zonenkarte: Seitenverhältnis + echte Positionen der Rückseiten-Elemente."""
        back_map = getattr(self, "_back_zone_map", None)
        if back_map is None:
            return
        from ui_qt.widgets.back_cover_zone_map import back_zones_for_layout

        aspect = geo.trim_width_mm / geo.trim_height_mm if geo.trim_height_mm else 0.66
        self._zone_map.set_aspect(aspect)
        back_path: Path | None = None
        raw = (layout.back_image or "").strip()
        if raw:
            back_path = Path(raw)
            if not back_path.is_absolute():
                back_path = (self._resolve_base() / back_path).resolve()
        try:
            zones, barcode = back_zones_for_layout(layout, geo, back_image_path=back_path)
        except OSError:
            return
        back_map.set_zones(
            zones, barcode=barcode, ground_color=layout.back_color, aspect=aspect
        )

    def _jump_to_cover_zone(self, zone_id: str) -> None:
        """Zonenkarte → Tab + Abschnitt + Fokus (Layout-Hilfe)."""
        tabs = getattr(self, "_editor_tabs", None)
        if tabs is None:
            return

        def _expand(sec: Any) -> None:
            if sec is not None and hasattr(sec, "set_expanded"):
                sec.set_expanded(True)

        def _focus(widget: Any) -> None:
            if widget is None:
                return
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
            QTimer.singleShot(0, lambda w=widget: self._scroll_editor_to_widget(w))

        if zone_id.startswith("back_"):
            self._jump_to_back_zone(zone_id, _expand, _focus)
            return

        front_idx = getattr(self, "_front_tab_index", -1)

        if zone_id == "image":
            if front_idx >= 0:
                tabs.setCurrentIndex(front_idx)
            self.front_mode_top_third.setChecked(True)
            self._sync_front_image_mode_controls()
            _focus(self.front_mode_top_third)
            return

        if zone_id == "ground":
            if front_idx >= 0:
                tabs.setCurrentIndex(front_idx)
            _focus(self.front_color_edit)
            return

        self._open_gestaltung_tab()
        if zone_id == "header":
            _expand(getattr(self, "_compose_sec_band", None))
            _focus(self.compose_band_text)
        elif zone_id == "title":
            _expand(getattr(self, "_compose_sec_titles", None))
            _focus(self.compose_main)
        elif zone_id == "subtitle":
            _expand(getattr(self, "_compose_sec_titles", None))
            self.compose_subtitle_enabled.setChecked(True)
            self.compose_subtitle_band_enabled.setChecked(True)
            _focus(self.compose_sub1)
        elif zone_id == "claim":
            _expand(getattr(self, "_compose_sec_titles", None))
            _focus(self.compose_accent)
        elif zone_id == "author":
            _expand(getattr(self, "_compose_sec_titles", None))
            _focus(self.compose_author)
        elif zone_id == "footer":
            _expand(getattr(self, "_compose_sec_footer", None))
            _focus(self.compose_footer_line1)
        elif zone_id == "corner":
            _expand(getattr(self, "_compose_sec_corner", None))
            _focus(self.compose_corner_text)
        elif zone_id == "badge":
            _expand(getattr(self, "_compose_sec_badge", None))
            _focus(self.compose_badge_text)
        else:
            _expand(getattr(self, "_compose_sec_fade", None))
            _focus(self.compose_fade_enabled)

    def _jump_to_back_zone(self, zone_id: str, expand: Any, focus: Any) -> None:
        """Rückseiten-Zone → Tab Rückseite; abgeschaltete Elemente einschalten."""
        idx = getattr(self, "_back_tab_index", -1)
        if idx >= 0:
            self._editor_tabs.setCurrentIndex(idx)
        if zone_id == "back_image":
            expand(self._back_sec_image)
            if not self.back_edit.text().strip():
                focus(self.back_edit)
            elif str(self.back_placement_combo.currentData() or "") == "free":
                focus(self.back_img_x_spin)
            else:
                focus(self.back_placement_combo)
        elif zone_id == "back_subtitle":
            expand(self._back_sec_subtitle)
            self.back_subtitle_editor.enabled_check.setChecked(True)
            focus(self.back_subtitle_editor.first_text)
        elif zone_id in ("back_blurb", "back_bio"):
            editor = self.back_blurb_editor if zone_id == "back_blurb" else self.back_bio_editor
            expand(self._back_sec_blurb if zone_id == "back_blurb" else self._back_sec_bio)
            editor.enabled_check.setChecked(True)
            focus(editor.text_edit)
        else:
            focus(self.back_color_edit)

    def _sync_spine_badge_controls(self) -> None:
        on = bool(self.spine_badge_enabled.isChecked())
        for w in (
            self.spine_badge_text,
            self.spine_badge_color_host,
            self.spine_badge_position,
            self.spine_badge_scale,
        ):
            w.setEnabled(on)

    def _collect_spine_badge(self) -> SpineBadgeSpec:
        pos = str(self.spine_badge_position.currentData() or "before")
        if pos not in ("before", "after"):
            pos = "before"
        try:
            step = int(self.spine_badge_scale.currentData())
        except (TypeError, ValueError):
            step = 0
        max_step = max(0, len(SPINE_BADGE_SCALE_STEPS) - 1)
        step = max(0, min(max_step, step))
        return SpineBadgeSpec(
            enabled=bool(self.spine_badge_enabled.isChecked()),
            text=self.spine_badge_text.text().strip(),
            color=self.spine_badge_color.text().strip() or "#9B2C3E",
            text_color="#FFFFFF",
            position=pos,  # type: ignore[arg-type]
            scale_step=step,
        )

    def _apply_spine_badge(self, badge: SpineBadgeSpec | dict[str, Any] | None) -> None:
        spec = (
            badge
            if isinstance(badge, SpineBadgeSpec)
            else SpineBadgeSpec.from_dict(badge if isinstance(badge, dict) else None)
        )
        self.spine_badge_enabled.setChecked(bool(spec.enabled))
        self.spine_badge_text.setText(spec.text)
        self.spine_badge_color.setText(spec.color or "#9B2C3E")
        idx = self.spine_badge_position.findData(
            "after" if spec.position == "after" else "before"
        )
        if idx >= 0:
            self.spine_badge_position.setCurrentIndex(idx)
        sidx = self.spine_badge_scale.findData(int(spec.scale_step))
        if sidx >= 0:
            self.spine_badge_scale.setCurrentIndex(sidx)
        else:
            self.spine_badge_scale.setCurrentIndex(0)
        self._sync_spine_badge_controls()

    def _browse_back(self) -> None:
        start = str(self._book / "img") if self._book else ""
        path, _ = QFileDialog.getOpenFileName(self, "Rückseiten-Bild", start, _IMAGE_FILTER)
        if path:
            self.back_edit.setText(path)
            self._on_params_changed()
