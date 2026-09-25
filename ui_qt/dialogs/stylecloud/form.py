"""Formular: Größe, Palette, Form/Maske, Dichte, Packung, Modusabhängige Anzeige.

Mixin von ``StylecloudQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from tools.stylecloud.generator import (
    CUSTOM_SIZE_SENTINEL,
    ICON_HUB,
    ICON_NONE,
    ICON_ORGANIC,
    ICON_RECT,
    StylecloudDependencyError,
    StylecloudOptions,
    clamp_word_density,
    density_for_packing_key,
    free_form_word_budget,
    normalize_free_form_density,
    normalize_free_form_packing,
    normalize_icon_name,
    packing_key_for_density,
)
from ui_qt.dialogs.stylecloud.common import (
    _VCENTER,
    _set_combo_by_data,
)


class FormMixin:
    """Formular: Größe, Palette, Form/Maske, Dichte, Packung, Modusabhängige Anzeige."""

    def _color_field(
        self,
        initial: str = "#c0392b",
        *,
        max_width: int = 90,
        tooltip: str = "Farbe (Hex oder Picker).",
        dialog_title: str = "Farbe wählen",
    ) -> tuple[QWidget, QLineEdit]:
        """Hex field + swatch button → ``QColorDialog`` (same pattern as KDP Cover)."""
        edit = QLineEdit(initial)
        edit.setMaximumWidth(max_width)
        edit.setPlaceholderText("#RRGGBB")
        edit.setToolTip(tooltip)

        btn = QPushButton()
        btn.setFixedSize(28, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Farbe wählen…")

        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(edit, 0, _VCENTER)
        row.addWidget(btn, 0, _VCENTER)

        def _parse() -> QColor:
            raw = edit.text().strip() or initial
            color = QColor(raw)
            if not color.isValid():
                color = QColor(initial)
            if not color.isValid():
                color = QColor("#c0392b")
            return color

        def _sync_swatch() -> None:
            color = _parse()
            border = "#334155" if color.lightness() > 180 else "#94a3b8"
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color.name()}; "
                f"border: 1px solid {border}; border-radius: 3px; }}"
            )

        def _pick() -> None:
            chosen = QColorDialog.getColor(_parse(), self, dialog_title)
            if not chosen.isValid():
                return
            edit.setText(chosen.name())
            _sync_swatch()

        def _normalize_hex() -> None:
            color = _parse()
            # Keep typed names (e.g. "red") if valid; otherwise normalize to #rrggbb.
            raw = edit.text().strip()
            if raw.startswith("#") or not QColor(raw).isValid():
                edit.setText(color.name())
            _sync_swatch()

        btn.clicked.connect(_pick)
        edit.textChanged.connect(lambda *_: _sync_swatch())
        edit.editingFinished.connect(_normalize_hex)
        _sync_swatch()
        return host, edit

    def _set_custom_size_row_visible(self, visible: bool) -> None:
        """Show B×H only for „Benutzerdefiniert“ — hide label + fields together."""
        show = bool(visible)
        form = getattr(self, "_form_form", None)
        if form is not None:
            form.setRowVisible(self._custom_size_host, show)
        else:
            self._custom_size_host.setVisible(show)

    def _on_size_changed(self, *_args) -> None:
        if self._restoring:
            return
        size = self._resolved_size()
        custom = self.size_combo.currentData() == CUSTOM_SIZE_SENTINEL
        self._set_custom_size_row_visible(custom)
        if size is None:
            return
        # Never auto-overwrite Maxima → Schrift here. Size changes used to reset
        # Schrift (e.g. back to 346) on Neu würfeln / spurious combo signals.
        self._size_for_font_suggest = size
        self._update_custom_ratio_label()
        self._update_gradient_items()

    def _on_custom_size_changed(self, *_args) -> None:
        if self._restoring:
            return
        if self.size_combo.currentData() != CUSTOM_SIZE_SENTINEL:
            return
        size = self._resolved_size()
        if size is None:
            return
        self._size_for_font_suggest = size
        self._update_custom_ratio_label()
        self._update_gradient_items()

    def _update_custom_ratio_label(self) -> None:
        width = max(1, int(self.custom_width.value()))
        height = max(1, int(self.custom_height.value()))
        ratio = width / height
        self.custom_ratio_label.setText(f"Ratio: {ratio:.2f}")

    def _resolved_size(self) -> int | tuple[int, int] | None:
        data = self.size_combo.currentData()
        if data == CUSTOM_SIZE_SENTINEL:
            return (int(self.custom_width.value()), int(self.custom_height.value()))
        return data

    def _canvas_is_square(self) -> bool:
        size = self._resolved_size()
        return not (
            isinstance(size, tuple) and len(size) == 2 and int(size[0]) != int(size[1])
        )

    def _uses_font_awesome(self) -> bool:
        """True when Form is a Font Awesome icon (library gradient applies)."""
        if self.mask_path.text().strip():
            return False
        icon = self._resolved_icon_name()
        return icon not in {ICON_HUB, ICON_NONE, ICON_ORGANIC, ICON_RECT, ""}

    def _update_gradient_items(self) -> None:
        """Show FA-Verlauf only for Font Awesome + square canvas."""
        allow = self._uses_font_awesome() and self._canvas_is_square()
        form = getattr(self, "_palette_form", None)
        if form is not None:
            form.setRowVisible(self.gradient_combo, bool(allow))
        self.gradient_combo.setEnabled(bool(allow))
        if not allow and self.gradient_combo.currentData() is not None:
            _set_combo_by_data(self.gradient_combo, None)

    def _clear_swatches(self) -> None:
        while self._swatch_layout.count():
            item = self._swatch_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_palette_preview(self, *_args) -> None:
        """Show sampled palette tones when max colors < 12."""
        if getattr(self, "_restoring", False):
            return
        n = int(self.max_colors.value())
        show = n < 12
        self._swatch_host.setVisible(show)
        self._clear_swatches()
        if not show:
            return
        try:
            from tools.stylecloud.generator import resolve_word_colors

            colors = resolve_word_colors(
                StylecloudOptions(
                    palette=str(
                        self.palette_combo.currentData()
                        or "cartocolors.qualitative.Bold_5"
                    ),
                    max_colors=n,
                )
            )
        except (StylecloudDependencyError, OSError, ValueError, RuntimeError):
            colors = []
        for hex_color in colors:
            swatch = QFrame()
            swatch.setFixedSize(22, 22)
            swatch.setToolTip(hex_color)
            qcolor = QColor(hex_color)
            if not qcolor.isValid():
                qcolor = QColor("#888888")
            border = "#334155" if qcolor.lightness() > 180 else "#94a3b8"
            swatch.setStyleSheet(
                f"QFrame {{ background-color: {qcolor.name()}; "
                f"border: 1px solid {border}; border-radius: 3px; }}"
            )
            self._swatch_layout.addWidget(swatch)
        self._swatch_layout.addStretch(1)

    def _on_mask_path_changed(self, *_args) -> None:
        has_mask = bool(self.mask_path.text().strip())
        self.icon_combo.setEnabled(not has_mask)
        self._update_mode_ui()
        self._update_gradient_items()
        self._update_invert_mask_ui()

    def _on_form_changed(self, *_args) -> None:
        if self._restoring:
            return
        self._update_mode_ui()
        self._update_gradient_items()

    def _resolved_icon_name(self) -> str:
        """Canonical form id from the combo (never confuse Qt's None with FA book)."""
        return normalize_icon_name(self.icon_combo.currentData())

    def _resolved_free_form_density(self) -> str:
        return normalize_free_form_density(self.free_form_density.currentData())

    def _on_word_density_changed(self, value: int) -> None:
        pct = int(value)
        self.word_density_label.setText(f"{pct} % dicht")
        # Keep Cover-dicht packing combo in sync (visual only).
        if not self._restoring:
            key = packing_key_for_density(pct / 100.0)
            if normalize_free_form_packing(self.free_form_packing.currentData()) != key:
                self.free_form_packing.blockSignals(True)
                _set_combo_by_data(self.free_form_packing, key)
                self.free_form_packing.blockSignals(False)
        if self._restoring or self._is_generating:
            return
        if self.word_density_slider.isSliderDown():
            return
        self._layout_regen_timer.start()

    def _on_layout_slider_committed(self) -> None:
        """Regenerate after Orientierungs- oder Dichte-Slider; keep cover_scale."""
        self._layout_regen_timer.stop()
        if self._restoring or self._is_generating:
            return
        has_text = bool(self.text_edit.toPlainText().strip())
        is_hub = (
            not self.mask_path.text().strip()
            and self._resolved_icon_name() == ICON_HUB
        )
        if is_hub:
            if not self.must_word.text().strip():
                return
            if not has_text and self._hub_raw_path is None:
                return
        elif not has_text:
            return
        scale_pct = int(round(self._cover_scale * 100))
        dens_pct = int(self.word_density_slider.value())
        orient_pct = int(self.hub_orient_slider.value())
        self.status.setText(
            f"Layout {orient_pct}% quer / {dens_pct}% dicht — "
            f"erzeuge neu (Einpassen {scale_pct} % bleibt)…"
        )
        self._generate()

    def _set_cover_scale(self, value: float) -> None:
        # Never let a pending Orient/Dichte-Regen steal the ± click.
        self._layout_regen_timer.stop()
        self._cover_scale = max(0.15, min(8.0, float(value)))
        self.cover_scale_label.setText(f"{int(round(self._cover_scale * 100))} %")
        if not self._restoring:
            self._recomposite_hub_to_cover()

    def _nudge_cover_scale(self, factor: float) -> None:
        self._set_cover_scale(self._cover_scale * float(factor))

    def _resolved_prefer_horizontal(self) -> float | None:
        # Shared slider for all forms (cover-ratio auto removed).
        return max(0.0, min(1.0, float(self.hub_orient_slider.value()) / 100.0))

    def _resolved_free_form_packing(self) -> str:
        return normalize_free_form_packing(self.free_form_packing.currentData())

    def _resolved_word_density(self) -> float:
        return clamp_word_density(self.word_density_slider.value() / 100.0)

    def _on_packing_combo_changed(self, *_args) -> None:
        if self._restoring:
            return
        dens = density_for_packing_key(self._resolved_free_form_packing())
        pct = int(round(dens * 100))
        if int(self.word_density_slider.value()) != pct:
            self.word_density_slider.blockSignals(True)
            self.word_density_slider.setValue(pct)
            self.word_density_slider.blockSignals(False)
            self.word_density_label.setText(f"{pct} % dicht")
        self._layout_regen_timer.start()

    def _on_free_form_density_changed(self, *_args) -> None:
        if self._restoring:
            return
        self._update_mode_ui()

    def _update_free_form_words_hint(self, *_args) -> None:
        if not hasattr(self, "free_form_words_hint"):
            return
        density = self._resolved_free_form_density()
        if density == "free":
            self.free_form_words_hint.setText("(→ Maxima → Wörter)")
            return
        budget = free_form_word_budget(density, 1200, 1900)
        self.free_form_words_hint.setText(f"(Ziel: {budget} Wörter)")

    def _update_mode_ui(self) -> None:
        """Show only controls for the active form mode (tab containers)."""
        has_mask = bool(self.mask_path.text().strip())
        icon = self._resolved_icon_name()
        is_hub = (not has_mask) and icon == ICON_HUB
        is_cover = (not has_mask) and icon == ICON_NONE
        is_organic = (not has_mask) and icon == ICON_ORGANIC
        density = self._resolved_free_form_density() if is_cover else ""
        density_uses_maxima = is_cover and density == "free"

        # Form tab: Cover-dicht / Organisch extras vs shared Orient/Einpassen
        self._cover_pack_box.setVisible(bool(is_organic or is_cover))
        self._hub_pack_box.setVisible(True)
        if hasattr(self, "_hub_fit_box"):
            self._hub_fit_box.setVisible(True)
        self.free_form_margin.setVisible(bool(is_organic))
        self.free_form_margin.setEnabled(bool(is_organic))
        self._cover_rand_label.setVisible(bool(is_organic))
        self._dichte_label.setVisible(bool(is_cover))
        self.free_form_density.setVisible(bool(is_cover))
        self.free_form_density.setEnabled(bool(is_cover))
        self.free_form_words_hint.setVisible(bool(is_cover))
        # Packung nur Cover-dicht (Orientierung ist im gemeinsamen Block).
        cover_form = self._cover_pack_box.layout()
        if isinstance(cover_form, QFormLayout) and hasattr(self, "_pack_host"):
            cover_form.setRowVisible(self._pack_host, bool(is_cover))
        self.free_form_packing.setEnabled(bool(is_cover))

        # Kernwort & Farbe: hub gradient XOR palette / overlay
        self._hub_grad_box.setVisible(bool(is_hub))
        self._palette_box.setVisible(not is_hub)
        self._overlay_box.setVisible(not is_hub)
        self.auto_fit.setVisible(True)
        self._on_auto_fit_toggled(self.auto_fit.isChecked())
        self._update_gradient_items()

        if self._must_word_label is not None:
            self._must_word_label.setText("Kernwort:" if is_hub else "Muss-Wort:")
        if getattr(self, "_must_style_label", None) is not None:
            self._must_style_label.setText(
                "Kern-Schrift:" if is_hub else "Muss-Wort Stil:"
            )
        self.must_word.setPlaceholderText(
            "Kernwort — Pflicht für Freie Form"
            if is_hub
            else "Zeile 1 — z. B. BARCELONA"
        )
        self.must_word_size.setToolTip(
            "Schriftgröße des Kernworts (lange Wörter werden begrenzt)."
            if is_hub
            else "Obere Grenze für die Schriftgröße. Die Breite wird an die Form angepasst."
        )
        self.must_word_size.setSuffix(" px" if is_hub else " px max")

        self.max_words.setEnabled((not is_cover) or density_uses_maxima)
        self.max_words_label.setEnabled((not is_cover) or density_uses_maxima)
        if is_hub:
            self.max_words.setToolTip(
                "Begleitwörter um das Kernwort (empfohlen ≥ 80)."
            )
        elif is_cover and not density_uses_maxima:
            self.max_words.setToolTip(
                "Bei Dichte Luftig/Normal/Dicht steuert „Dichte“ die Wortanzahl.\n"
                "Für manuelle Steuerung: Dichte → „Frei (Maxima)“."
            )
        elif is_cover and density_uses_maxima:
            self.max_words.setToolTip(
                "Dichte „Frei“: hier die gewünschte Wortanzahl setzen."
            )
        else:
            self.max_words.setToolTip("Maximale Wortanzahl in der Wolke.")
        self._update_free_form_words_hint()

    def _on_auto_fit_toggled(self, checked: bool) -> None:
        """When Auto-Fit is on, Kern-/Muss-Schrift and Maxima-Schrift are derived."""
        auto = bool(checked)
        is_hub = (
            not self.mask_path.text().strip()
            and self._resolved_icon_name() == ICON_HUB
        )
        self.must_word_size.setEnabled(not auto)
        self.max_font.setEnabled(not auto)
        if hasattr(self, "max_font_label"):
            self.max_font_label.setEnabled(not auto)
        if auto:
            self.must_word_size.setToolTip(
                "Auto-Fit aktiv: Größe wird aus dem Cover berechnet.\n"
                "Checkbox aus, um manuell zu setzen."
            )
            self.max_font.setToolTip(
                "Auto-Fit aktiv: Maxima-Schrift wird automatisch gesetzt.\n"
                "Checkbox aus für manuelle Maxima → Schrift."
            )
        elif is_hub:
            self.must_word_size.setToolTip(
                "Schriftgröße des Kernworts (lange Wörter werden begrenzt)."
            )
            self.max_font.setToolTip(
                "Obere Grenze für Begleitwörter um das Kernwort."
            )
        else:
            self.must_word_size.setToolTip(
                "Obere Grenze für die Schriftgröße. Die Breite wird an die Form angepasst."
            )
            self.max_font.setToolTip(
                "Maximale Begleitwort-Schrift (nicht Muss-Wort)."
            )

    def _update_form_margin_ui(self) -> None:
        """Back-compat alias — prefer ``_update_mode_ui``."""
        self._update_mode_ui()

    def _update_invert_mask_ui(self) -> None:
        """Context-sensitive tooltip for mask vs. Font Awesome invert."""
        has_mask = bool(self.mask_path.text().strip())
        if has_mask:
            self.invert_mask.setToolTip(
                "Hell/dunkel in der Silhouette tauschen.\n"
                "Standard: dunkle Form auf hellem Hintergrund."
            )
        else:
            self.invert_mask.setToolTip(
                "Wörter außerhalb des Font-Awesome-Symbols statt innerhalb."
            )

    def _browse_mask(self) -> None:
        start = self.mask_path.text().strip() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Silhouette / Maskenbild",
            start,
            "Bilder (*.png *.jpg *.jpeg *.webp *.bmp);;Alle Dateien (*.*)",
        )
        if path:
            self.mask_path.setText(path)

    def _clear_mask(self) -> None:
        self.mask_path.clear()
