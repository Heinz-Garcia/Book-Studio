"""Maße: Trimmgröße, Modus (Sicher/Experte), Seitenzahl, Größen-Panel.

Mixin von ``KdpCoverQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from tools.cover_size.calculator import (
    CUSTOM_TRIM_SIZE_ID,
    MAX_PAGE_COUNT,
    MIN_PAGE_COUNT,
    calculate_cover_size,
    get_trim_size,
    inch_to_mm,
)
from tools.kdp_cover.constants import (
    SAFE_ZONE_IN,
)
from tools.kdp_specs import studio_paperback_preset
from ui_qt.dialogs.kdp_cover.common import (
    _STUDIO_PAPERBACK_ID,
)



class DimensionsMixin:
    """Maße: Trimmgröße, Modus (Sicher/Experte), Seitenzahl, Größen-Panel."""

    def _on_trim_changed(self, *_args: Any) -> None:
        is_custom = self.trim_combo.currentData() == CUSTOM_TRIM_SIZE_ID
        self.custom_trim_host.setVisible(is_custom)
        # Zeile inkl. Label ausblenden (Qt 6), sonst bleibt „Breite × Höhe:“ stehen.
        set_row_visible = getattr(self._size_form, "setRowVisible", None)
        if callable(set_row_visible):
            set_row_visible(self.custom_trim_host, is_custom)

    def _sync_free_controls(self) -> None:
        is_free = self.mode_combo.currentData() == "free"
        self.free_box.setEnabled(is_free)
        free_idx = getattr(self, "_free_tab_index", -1)
        if free_idx >= 0 and hasattr(self, "_editor_tabs"):
            self._editor_tabs.setTabEnabled(free_idx, is_free)
        reset_btn = getattr(self, "btn_reset_safe_slots", None)
        if reset_btn is not None:
            reset_btn.setEnabled(is_free)

    def _on_mode_changed(self, *_args: Any) -> None:
        if self._mode_guard:
            return
        new_mode = self.mode_combo.currentData()
        if new_mode == "free":
            reply = QMessageBox.warning(
                self,
                "Modus Experte",
                "Im Experten-Modus kannst du Texte per Offset verschieben. "
                "Safe-Zone und KDP-Regeln werden dann nur noch als Hinweis "
                "geprüft — der Export kann trotz Warnungen/Fehler erfolgen "
                "(nach zweistufiger Bestätigung).\n\n"
                "Trotzdem in den Experten-Modus wechseln?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._mode_guard = True
                idx = self.mode_combo.findData("safe")
                if idx >= 0:
                    self.mode_combo.setCurrentIndex(idx)
                self._mode_guard = False
                self._sync_free_controls()
                return
        else:
            # Zurück zu Sicher: Offsets zurücksetzen
            self._reset_free_offsets()
        self._sync_free_controls()
        self._on_params_changed()

    def _reset_free_offsets(self) -> None:
        for spin in (
            self.title_ox,
            self.title_oy,
            self.author_ox,
            self.author_oy,
            self.spine_oy,
        ):
            spin.setValue(0.0)
        self.title_scale.setValue(1.0)
        self._on_params_changed()

    def _init_page_count(self, *, layout_loaded: bool) -> None:
        """Seitenzahl-Quelle bestimmen; unbekannt → Abfrage beim ersten Anzeigen.

        Gespeichertes Layout hat Vorrang (inkl. Schätz-Markierung). Sonst die
        neueste Innenwerk-PDF des Buchs; fehlt auch die, fragt der Dialog nach.
        """
        from tools.kdp_cover.page_count import interior_pdf_page_count

        self._interior_pages = interior_pdf_page_count(self._book)
        self._page_count_prompt_pending = False
        if not layout_loaded:
            if self._interior_pages is not None:
                self._apply_interior_page_count(self._interior_pages)
            else:
                self._page_count_prompt_pending = True
        self._refresh_page_count_source()

    def _apply_interior_page_count(self, info: Any) -> None:
        pages = max(MIN_PAGE_COUNT, min(MAX_PAGE_COUNT, int(info.pages)))
        self.pages_spin.setValue(pages)
        self.pages_estimated_check.setChecked(False)

    def _take_interior_page_count(self) -> None:
        from tools.kdp_cover.page_count import interior_pdf_page_count

        self._interior_pages = interior_pdf_page_count(self._book)
        if self._interior_pages is None:
            QMessageBox.information(
                self,
                "Seitenzahl",
                "Keine gerenderte Innenwerk-PDF gefunden (export/_book…).\n"
                "Buch rendern (F5) oder die Seitenzahl schätzen.",
            )
            self._refresh_page_count_source()
            return
        self._apply_interior_page_count(self._interior_pages)
        self._refresh_page_count_source()

    def _open_page_count_estimate(self) -> None:
        """Nicht-blockierende Abfrage: ungefähre Seitenzahl + Papierart."""
        from ui_qt.dialogs.kdp_page_count_dialog import PageCountEstimateDialog

        dlg = PageCountEstimateDialog(
            self,
            pages=int(self.pages_spin.value()),
            paper_type_id=str(self.paper_combo.currentData() or ""),
            min_pages=MIN_PAGE_COUNT,
            max_pages=MAX_PAGE_COUNT,
        )
        dlg.accepted.connect(
            lambda d=dlg: self._apply_page_estimate(d.page_count(), d.paper_type_id())
        )
        self._page_count_dialog = dlg
        dlg.open()

    def _apply_page_estimate(self, pages: int, paper_type_id: str) -> None:
        idx = self.paper_combo.findData(paper_type_id)
        if idx >= 0:
            self.paper_combo.setCurrentIndex(idx)
        self.pages_spin.setValue(int(pages))
        self.pages_estimated_check.setChecked(True)
        self._refresh_page_count_source()
        self._on_params_changed()

    def _refresh_page_count_source(self, *_args: Any) -> None:
        label = getattr(self, "pages_source_label", None)
        if label is None:
            return
        info = getattr(self, "_interior_pages", None)
        pages = int(self.pages_spin.value())
        self.btn_pages_from_pdf.setEnabled(self._book is not None)
        if info is not None and int(info.pages) != pages:
            label.setText(
                f"⚠ Innenwerk-PDF hat {info.pages} Seiten ({info.pdf.name}) — "
                "„Aus Innenwerk-PDF“ übernimmt sie."
            )
            label.setStyleSheet("color:#b45309; font-size:11px; font-weight:600;")
            return
        label.setStyleSheet("color:#5b6573; font-size:11px;")
        if self.pages_estimated_check.isChecked():
            label.setText("Geschätzt — Innenwerk noch nicht gerendert.")
        elif info is not None:
            label.setText(f"Aus Innenwerk-PDF: {info.pdf.name}")
        else:
            label.setText("Keine Innenwerk-PDF gefunden — Wert manuell / geschätzt.")

    def _current_trim_mm(self) -> tuple[float, float]:
        trim_id = self.trim_combo.currentData()
        if trim_id == _STUDIO_PAPERBACK_ID:
            preset = studio_paperback_preset()
            t = preset.get("trim_mm") or {}
            return float(t.get("width", 135)), float(t.get("height", 215))
        if trim_id == CUSTOM_TRIM_SIZE_ID:
            return (
                inch_to_mm(self.custom_width_spin.value()),
                inch_to_mm(self.custom_height_spin.value()),
            )
        trim = get_trim_size(str(trim_id))
        if trim is None:
            return 135.0, 215.0
        return inch_to_mm(trim.width_in), inch_to_mm(trim.height_in)

    def _copy_size_result(self) -> None:
        text = self.size_result_label.text().strip()
        if text:
            QApplication.clipboard().setText(text)

    def _update_size_panel(self) -> bool:
        """Aktualisiert die eingebettete Cover-Größen-Anzeige. True = ok."""
        tw, th = self._current_trim_mm()
        try:
            result = calculate_cover_size(
                int(self.pages_spin.value()),
                str(self.paper_combo.currentData()),
                tw,
                th,
            )
        except ValueError as exc:
            self.size_error_label.setText(str(exc))
            self.size_error_label.setVisible(True)
            self.size_result_label.setText("")
            self.btn_copy_size.setEnabled(False)
            return False
        self.size_error_label.setVisible(False)
        self.btn_copy_size.setEnabled(True)
        self.size_result_label.setText(
            f"Buchrücken-Breite:     {result.spine_width_mm:.2f} mm  ({result.spine_width_in:.4f} in)\n"
            f"Gesamt-Coverbreite:    {result.cover_width_mm:.2f} mm  ({result.cover_width_in:.4f} in)\n"
            f"Gesamt-Coverhöhe:      {result.cover_height_mm:.2f} mm  ({result.cover_height_in:.4f} in)\n"
            f"Trimmgröße (fertig):   {result.trim_width_mm:.1f} × {result.trim_height_mm:.1f} mm\n"
            f"Bleed / Safe-Zone:     {result.bleed_mm:g} mm / {inch_to_mm(SAFE_ZONE_IN):.2f} mm"
        )
        return True
