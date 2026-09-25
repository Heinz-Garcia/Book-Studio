"""Einstellungen und Presets: sammeln, speichern, wiederherstellen.

Mixin von ``StylecloudQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QInputDialog,
    QMessageBox,
)

from tools.stylecloud.generator import (
    CUSTOM_SIZE_SENTINEL,
    DEFAULT_WORD_DENSITY,
    ICON_HUB,
    PRINT_DPI,
    density_for_packing_key,
    normalize_free_form_density,
    normalize_free_form_packing,
    normalize_icon_name,
    suggested_must_word_gap,
    suggested_must_word_max_font,
)
from tools.stylecloud.preset_store import (
    FACTORY_FREEFORM_PRESET_NAME,
    list_presets,
    load_factory_freeform_preset,
    load_preset,
    save_preset,
)
from tools.stylecloud.settings import load_settings, resolve_window_size, save_settings
from ui_qt.dialogs.stylecloud.common import (
    _set_combo_by_data,
)
from ui_qt.dialogs.stylecloud_preset_manager_dialog import StylecloudPresetManagerDialog


class SettingsMixin:
    """Einstellungen und Presets: sammeln, speichern, wiederherstellen."""

    def _collect_settings(self) -> dict:
        size = self._resolved_size()
        icon_name = self._resolved_icon_name()
        return {
            "source_mode": str(self.source_combo.currentData() or "book"),
            "source_path": self.source_path.text().strip(),
            "output_path": self.output_path.text().strip(),
            "size": size if size is not None else 1024,
            "icon_name": icon_name,
            "mask_path": self.mask_path.text().strip(),
            "free_form_margin_pct": float(self.free_form_margin.value()),
            "free_form_density": self._resolved_free_form_density(),
            "free_form_packing": self._resolved_free_form_packing(),
            # Orientation SSOT is hub_orient_pct; keep legacy keys in sync.
            "free_form_orient_auto": False,
            "free_form_orient_pct": int(self.hub_orient_slider.value()),
            "palette": str(
                self.palette_combo.currentData() or "cartocolors.qualitative.Bold_5"
            ),
            "gradient": self.gradient_combo.currentData(),
            "hub_gradient": self._hub_gradient_stops(),
            "background_color": self.bg_edit.text().strip() or "white",
            "max_colors": int(self.max_colors.value()),
            "max_words": int(self.max_words.value()),
            "max_font_size": int(self.max_font.value()),
            "user_font_size": self._user_font_size,
            "use_german_stopwords": self.german_stop.isChecked(),
            "nouns_only": self.nouns_only.isChecked(),
            "collocations": self.collocations.isChecked(),
            "invert_mask": self.invert_mask.isChecked(),
            "extra_stopwords": self.extra_stop.text(),
            "must_word": self.must_word.text().strip(),
            "must_word_line2": self.must_word_line2.text().strip(),
            "must_word_font_size": int(self.must_word_size.value()),
            "must_word_color": self.must_word_color.text().strip() or "#c0392b",
            "must_word_angle": int(self.must_word_angle.currentData() or 0),
            "must_word_gap": int(self.must_word_gap.value()),
            "must_word_match_line1_width": self.must_word_match_width.isChecked(),
            "auto_fit": bool(self.auto_fit.isChecked()),
            "cover_scale": float(self._cover_scale),
            "hub_orient_pct": int(self.hub_orient_slider.value()),
            "word_density_pct": int(self.word_density_slider.value()),
            "save_svg": bool(self.save_svg.isChecked()),
            "png_compress_level": int(self.png_compress.value()),
            "png_optimize": self.png_optimize.isChecked(),
            "png_dpi": int(self.png_dpi.value()),
            "migrated_none_to_hub": True,
            "window_width": int(self.width()),
            "window_height": int(self.height()),
        }

    def _persist_settings(self) -> None:
        try:
            save_settings(self._collect_settings())
        except OSError as exc:
            self._log(f"[stylecloud] Einstellungen nicht speicherbar: {exc}", "warning")

    def _persist_font_size_immediately(self, value: int) -> None:
        """Save a user-selected font size before a generation can reload settings."""
        if self._restoring or self._is_generating:
            return
        self._user_font_size = int(value)
        try:
            settings = load_settings()
            settings["max_font_size"] = int(value)
            settings["user_font_size"] = int(value)
            save_settings(settings)
        except OSError as exc:
            self._log(
                f"[stylecloud] Schriftgröße nicht speicherbar: {exc}", "warning"
            )

    def _refresh_preset_combo(self, select_name: str | None = None) -> None:
        current = select_name or self.preset_combo.currentData()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("— Preset wählen —", "")
        for info in list_presets():
            self.preset_combo.addItem(info.name, info.name)
        if current:
            _set_combo_by_data(self.preset_combo, current)
        else:
            _set_combo_by_data(self.preset_combo, FACTORY_FREEFORM_PRESET_NAME)
        self.preset_combo.blockSignals(False)
        has_any = self.preset_combo.count() > 1
        self.btn_preset_load.setEnabled(has_any)

    def _apply_preset_settings(self, data: dict) -> None:
        """Apply a preset without changing the dialog window size."""
        self._restoring = True
        try:
            self._restore_settings_body(data, apply_geometry=False)
        finally:
            self._restoring = False
            self._on_mask_path_changed()
            self._on_source_changed()

    def _focus_after_freeform_preset(self) -> None:
        """Jump to Kernwort so the user only fills the hub word."""
        for index in range(self.tabs.count()):
            if "Kernwort" in self.tabs.tabText(index):
                self.tabs.setCurrentIndex(index)
                break
        self.must_word.setFocus()
        self.must_word.selectAll()

    def _load_factory_freeform_preset(self) -> None:
        try:
            settings = load_factory_freeform_preset()
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Freie Form laden", str(exc))
            self._refresh_preset_combo()
            return
        self._apply_preset_settings(settings)
        self._refresh_preset_combo(select_name=FACTORY_FREEFORM_PRESET_NAME)
        self._focus_after_freeform_preset()
        self.status.setText(
            "★ Freie Form · Verlauf geladen — Kernwort setzen, Text laden, erzeugen."
        )

    def _load_selected_preset(self) -> None:
        name = str(self.preset_combo.currentData() or "").strip()
        if not name:
            QMessageBox.information(
                self,
                "Preset laden",
                "Bitte zuerst ein Preset in der Liste auswählen.\n\n"
                f"Tipp: Button „{FACTORY_FREEFORM_PRESET_NAME}“ für Ein-Klick-Hub.",
            )
            return
        try:
            settings = load_preset(name)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Preset laden", str(exc))
            self._refresh_preset_combo()
            return
        self._apply_preset_settings(settings)
        if name == FACTORY_FREEFORM_PRESET_NAME:
            self._focus_after_freeform_preset()
        self.status.setText(f"Preset „{name}“ geladen.")

    def _save_preset_as(self) -> None:
        suggested = str(self.preset_combo.currentData() or "").strip()
        name, ok = QInputDialog.getText(
            self,
            "Preset speichern",
            "Name des Presets:",
            text=suggested,
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Preset speichern", "Bitte einen Namen angeben.")
            return
        existing = {p.name.casefold() for p in list_presets()}
        if name.casefold() in existing:
            answer = QMessageBox.question(
                self,
                "Preset überschreiben?",
                f"Preset „{name}“ existiert bereits. Überschreiben?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            save_preset(name, self._collect_settings())
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Preset speichern", str(exc))
            return
        self._refresh_preset_combo(select_name=name)
        self.status.setText(f"Preset „{name}“ gespeichert.")

    def _open_preset_manager(self) -> None:
        dlg = StylecloudPresetManagerDialog(
            collect_settings=self._collect_settings,
            apply_settings=self._apply_preset_settings,
            parent=self,
        )
        dlg.exec()
        select = dlg.loaded_preset_name or str(self.preset_combo.currentData() or "")
        self._refresh_preset_combo(select_name=select or None)

    def _restore_settings(self) -> None:
        data = load_settings()
        self._restoring = True
        try:
            self._restore_settings_body(data, apply_geometry=True)
        finally:
            self._restoring = False
            self._on_mask_path_changed()

    def _restore_settings_body(
        self, data: dict, *, apply_geometry: bool = True
    ) -> None:
        from tools.stylecloud.generator import DEFAULT_PRINT_SIZE

        if apply_geometry:
            width, height = resolve_window_size(data)
            self.resize(width, height)
            self._loaded_size = (width, height)

        mode = str(data.get("source_mode") or "book")
        _set_combo_by_data(self.source_combo, mode)

        source_path = str(data.get("source_path") or "").strip()
        if source_path:
            self.source_path.setText(source_path)

        output_path = str(data.get("output_path") or "").strip()
        if output_path:
            self.output_path.setText(output_path)

        size = data.get("size", DEFAULT_PRINT_SIZE)
        # Legacy only: bare list [512]/[1024] from broken saves — never rewrite
        # the live SIZE_PRESETS value ``1024`` (Entwurf 1:1).
        if size == [1024] or size == [512]:
            size = DEFAULT_PRINT_SIZE
        if isinstance(size, list) and len(size) == 2:
            try:
                size = (int(size[0]), int(size[1]))
            except (TypeError, ValueError):
                size = DEFAULT_PRINT_SIZE
        if not _set_combo_by_data(self.size_combo, size):
            if isinstance(size, tuple) and len(size) == 2:
                _set_combo_by_data(self.size_combo, CUSTOM_SIZE_SENTINEL)
                self.custom_width.setValue(max(256, int(size[0])))
                self.custom_height.setValue(max(256, int(size[1])))
            else:
                _set_combo_by_data(self.size_combo, DEFAULT_PRINT_SIZE)
        self._set_custom_size_row_visible(
            self.size_combo.currentData() == CUSTOM_SIZE_SENTINEL
        )
        self._update_custom_ratio_label()
        icon_name = normalize_icon_name(data.get("icon_name", ICON_HUB))
        if not _set_combo_by_data(self.icon_combo, icon_name):
            _set_combo_by_data(self.icon_combo, ICON_HUB)
        raw_margin = data.get("free_form_margin_pct", 14)
        try:
            self.free_form_margin.setValue(int(raw_margin))
        except (TypeError, ValueError):
            self.free_form_margin.setValue(14)
        _set_combo_by_data(
            self.free_form_density,
            normalize_free_form_density(data.get("free_form_density")),
        )
        _set_combo_by_data(
            self.free_form_packing,
            normalize_free_form_packing(data.get("free_form_packing")),
        )
        orient_auto = bool(data.get("free_form_orient_auto", False))
        self.orient_auto.setChecked(False)
        try:
            legacy_orient = int(data.get("free_form_orient_pct") or 50)
        except (TypeError, ValueError):
            legacy_orient = 50
        self.orient_pct.setValue(legacy_orient)
        self._set_hub_gradient_stops(data.get("hub_gradient"))
        self.auto_fit.setChecked(bool(data.get("auto_fit", True)))
        try:
            self._cover_scale = float(data.get("cover_scale") or 1.0)
        except (TypeError, ValueError):
            self._cover_scale = 1.0
        self._cover_scale = max(0.15, min(8.0, self._cover_scale))
        self.cover_scale_label.setText(f"{int(round(self._cover_scale * 100))} %")
        try:
            if "hub_orient_pct" in data:
                orient = int(data.get("hub_orient_pct") or 50)
            elif not orient_auto:
                orient = legacy_orient
            else:
                orient = 50
        except (TypeError, ValueError):
            orient = 50
        self.hub_orient_slider.setValue(max(0, min(100, orient)))
        self._on_hub_orient_changed(self.hub_orient_slider.value())
        try:
            if "word_density_pct" in data:
                dens_pct = int(data.get("word_density_pct") or 55)
            else:
                dens_pct = int(
                    round(
                        density_for_packing_key(
                            normalize_free_form_packing(data.get("free_form_packing"))
                        )
                        * 100
                    )
                )
        except (TypeError, ValueError):
            dens_pct = int(round(DEFAULT_WORD_DENSITY * 100))
        dens_pct = max(0, min(100, dens_pct))
        self.word_density_slider.setValue(dens_pct)
        self._on_word_density_changed(dens_pct)
        self.save_svg.setChecked(bool(data.get("save_svg", False)))
        self._update_mode_ui()
        mask = str(data.get("mask_path") or "").strip()
        if mask:
            self.mask_path.setText(mask)
            for index in range(self.tabs.count()):
                if self.tabs.tabText(index) == "Erweitert":
                    self.tabs.setCurrentIndex(index)
                    break
        _set_combo_by_data(self.palette_combo, data.get("palette"))
        _set_combo_by_data(self.gradient_combo, data.get("gradient"))

        bg = str(data.get("background_color") or "white").strip()
        self.bg_edit.setText(bg or "white")
        size_data = self._resolved_size() or DEFAULT_PRINT_SIZE
        self.max_colors.setValue(int(data.get("max_colors") or 5))
        self.max_words.setValue(int(data.get("max_words") or 500))
        saved_font = data.get("user_font_size")
        if saved_font is None:
            saved_font = data.get("max_font_size")
        try:
            self._user_font_size = int(saved_font) if saved_font is not None else None
        except (TypeError, ValueError):
            self._user_font_size = None
        # Never invent a fantasy Schrift (e.g. 346) — only restore what was saved,
        # otherwise keep the spinbox default from construction.
        if self._user_font_size is not None:
            self.max_font.setValue(int(self._user_font_size))
        self._size_for_font_suggest = size_data
        self.png_compress.setValue(int(data.get("png_compress_level") or 6))
        self.png_optimize.setChecked(bool(data.get("png_optimize", True)))
        self.png_dpi.setValue(int(data.get("png_dpi") or PRINT_DPI))
        self.german_stop.setChecked(bool(data.get("use_german_stopwords", True)))
        self.nouns_only.setChecked(bool(data.get("nouns_only", False)))
        self.collocations.setChecked(bool(data.get("collocations", False)))
        self.invert_mask.setChecked(bool(data.get("invert_mask", False)))
        self.extra_stop.setText(str(data.get("extra_stopwords") or ""))
        self.must_word.setText(str(data.get("must_word") or ""))
        self.must_word_line2.setText(str(data.get("must_word_line2") or ""))
        self.must_word_match_width.setChecked(
            bool(data.get("must_word_match_line1_width", True))
        )
        self.must_word_size.setValue(
            int(
                data.get("must_word_font_size")
                or suggested_must_word_max_font(size_data)
            )
        )
        self.must_word_color.setText(
            str(data.get("must_word_color") or "#c0392b").strip() or "#c0392b"
        )
        self.must_word_gap.setValue(
            int(data.get("must_word_gap") or suggested_must_word_gap(size_data))
        )
        _set_combo_by_data(self.must_word_angle, int(data.get("must_word_angle") or 0))

        try:
            if mode in {"file", "book"}:
                text = self._read_source_text()
                if text.strip():
                    self.text_edit.setPlainText(text)
                    if mode == "file":
                        self.status.setText(
                            f"Letzte Quelldatei wiederhergestellt "
                            f"({Path(source_path).name}, {len(text)} Zeichen)."
                        )
                    else:
                        self.status.setText(
                            f"Einstellungen wiederhergestellt; Buchtext geladen "
                            f"({len(text)} Zeichen)."
                        )
                else:
                    self.status.setText("Einstellungen wiederhergestellt.")
            else:
                self.status.setText("Einstellungen wiederhergestellt.")
        except (ValueError, OSError):
            self.status.setText(
                "Einstellungen wiederhergestellt "
                "(Quelltext bitte erneut laden)."
            )
