"""Layout ↔ Formular, Speichern/Laden (Layout, Elementset), Fertig-Abfrage.

Mixin von ``KdpCoverQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from tools.cover_size.calculator import (
    CUSTOM_TRIM_SIZE_ID,
    TRIM_SIZES,
    inch_to_mm,
    mm_to_inch,
)
from tools.kdp_cover.binding import (
    resolve_cover_binding,
)
from tools.kdp_cover.constants import (
    SPINE_EDGE_PADDING_MIN_MM,
)
from tools.kdp_cover.model import (
    CoverLayout,
    default_project_path,
    load_layout,
    normalize_front_image_mode,
    save_layout,
)
from tools.kdp_cover.validate import ValidationIssue, ValidationReport, validate_layout
from tools.kdp_specs import studio_paperback_preset
from tools.production_uuid import normalize_uuid
from ui_qt.dialogs.kdp_cover.common import (
    _ELEMENT_SET_FILTER,
    _ELEMENT_SET_SAVE_FILTER,
    _PROJECT_FILTER,
    _STATUS_EXPORT_TOOLTIP,
    _STUDIO_PAPERBACK_ID,
    _qlabel_color_ss,
    _read_quarto_title_author,
)
from ui_qt.dialogs.kdp_cover.dialogs import (
    _CloneFromTemplateDialog,
)


class LayoutIOMixin:
    """Layout ↔ Formular, Speichern/Laden (Layout, Elementset), Fertig-Abfrage."""

    def _resolve_base(self) -> Path:
        return self._book if self._book else Path.cwd()

    def _build_layout(self) -> CoverLayout:
        tw, th = self._current_trim_mm()
        mode = str(self.mode_combo.currentData() or "safe")
        layout = CoverLayout(
            page_count=int(self.pages_spin.value()),
            paper_type_id=str(self.paper_combo.currentData()),
            page_count_estimated=bool(self.pages_estimated_check.isChecked()),
            trim_width_mm=tw,
            trim_height_mm=th,
            mode=mode,  # type: ignore[arg-type]
            front_image=self.front_edit.text().strip(),
            back_image=self.back_edit.text().strip(),
            front_image_mode=self._current_front_image_mode(),
            front_image_zoom=float(self.front_zoom_spin.value()),
            front_image_offset_x_mm=float(self.front_ox_spin.value()),
            front_image_offset_y_mm=float(self.front_oy_spin.value()),
            front_color=self.front_color_edit.text().strip() or "#1e3a5f",
            back_image_scale=max(0.05, min(1.0, float(self.back_scale_spin.value()) / 100.0)),
            back_image_frame=bool(self.back_frame_check.isChecked()),
            back_image_frame_mm=float(self.back_frame_mm_spin.value()),
            back_image_frame_color=self.back_frame_color_edit.text().strip() or "#000000",
            back_image_placement=(
                "free"
                if str(self.back_placement_combo.currentData() or "") == "free"
                else "center"
            ),
            back_image_x_pct=float(self.back_img_x_spin.value()),
            back_image_y_pct=float(self.back_img_y_spin.value()),
            back_image_width_pct=float(self.back_img_width_spin.value()),
            back_color=self.back_color_edit.text().strip() or "#FFFFFF",
            spine_color=self.spine_color_edit.text().strip() or "#222222",
            title=self.title_edit.text().strip(),
            author=self.author_edit.text().strip(),
            spine_text=self.spine_text_edit.text().strip(),
            spine_text_down=self.spine_text_down_edit.text().strip(),
            spine_font=str(self.spine_font_combo.currentData() or "sans"),
            spine_padding_mm=float(self.spine_padding_spin.value()),
            title_color=self.title_color_edit.text().strip() or "#FFFFFF",
            title_offset_x_mm=float(self.title_ox.value()),
            title_offset_y_mm=float(self.title_oy.value()),
            author_offset_x_mm=float(self.author_ox.value()),
            author_offset_y_mm=float(self.author_oy.value()),
            spine_offset_y_mm=float(self.spine_oy.value()),
            title_scale=float(self.title_scale.value()),
            spine_badge=self._collect_spine_badge(),
            front_compose=self._collect_front_compose(),
            back_compose=self._collect_back_compose(),
            wrap_pdf=getattr(self, "_wrap_pdf_rel", "") or "",
            production_uuid=str(getattr(self, "_production_uuid", "") or "").strip(),
            cover_label=str(getattr(self, "_cover_label", "") or "").strip(),
            cover_role=(
                "alternative"
                if str(getattr(self, "_cover_role", "") or "").strip().lower()
                == "alternative"
                else "primary"
            ),
        )
        if mode != "free":
            layout.reset_free_placement()
        return layout

    def _apply_layout(self, layout: CoverLayout, *, project_path: Path | None = None) -> None:
        was_guarded = self._params_guard
        self._params_guard = True
        self._mode_guard = True
        try:
            self.pages_spin.setValue(layout.page_count)
            self.pages_estimated_check.setChecked(
                bool(getattr(layout, "page_count_estimated", False))
            )
            pidx = self.paper_combo.findData(layout.paper_type_id)
            if pidx >= 0:
                self.paper_combo.setCurrentIndex(pidx)

            preset = studio_paperback_preset().get("trim_mm") or {}
            sw = float(preset.get("width", 135))
            sh = float(preset.get("height", 215))
            if abs(layout.trim_width_mm - sw) < 0.05 and abs(layout.trim_height_mm - sh) < 0.05:
                idx = self.trim_combo.findData(_STUDIO_PAPERBACK_ID)
                if idx >= 0:
                    self.trim_combo.setCurrentIndex(idx)
            else:
                matched = False
                for t in TRIM_SIZES:
                    if abs(inch_to_mm(t.width_in) - layout.trim_width_mm) < 0.15 and abs(
                        inch_to_mm(t.height_in) - layout.trim_height_mm
                    ) < 0.15:
                        idx = self.trim_combo.findData(t.id)
                        if idx >= 0:
                            self.trim_combo.setCurrentIndex(idx)
                            matched = True
                            break
                if not matched:
                    idx = self.trim_combo.findData(CUSTOM_TRIM_SIZE_ID)
                    if idx >= 0:
                        self.trim_combo.setCurrentIndex(idx)
                    self.custom_width_spin.setValue(mm_to_inch(layout.trim_width_mm))
                    self.custom_height_spin.setValue(mm_to_inch(layout.trim_height_mm))

            midx = self.mode_combo.findData(layout.mode)
            if midx >= 0:
                self.mode_combo.setCurrentIndex(midx)

            self.front_edit.setText(layout.front_image)
            self.front_color_edit.setText(
                str(getattr(layout, "front_color", "") or "").strip() or "#1e3a5f"
            )
            # Ungültige Front-/Back-Pfade aus altem Projekt nicht behalten
            # (sonst schwarze/fehlschlagende Vorschau ohne erkennbare Ursache).
            front_raw = (layout.front_image or "").strip()
            if front_raw:
                front_p = Path(front_raw)
                if not front_p.is_absolute() and self._book is not None:
                    front_p = (self._book / front_p).resolve()
                if not front_p.is_file():
                    self.front_edit.clear()
                    front_raw = ""
            self._set_front_image_mode_ui(
                normalize_front_image_mode(
                    getattr(layout, "front_image_mode", None),
                    front_image=front_raw or layout.front_image,
                )
            )
            self.back_edit.setText(layout.back_image)
            back_raw = (layout.back_image or "").strip()
            if back_raw:
                back_p = Path(back_raw)
                if not back_p.is_absolute() and self._book is not None:
                    back_p = (self._book / back_p).resolve()
                if not back_p.is_file():
                    self.back_edit.clear()
            self.front_zoom_spin.setValue(
                max(1.0, float(getattr(layout, "front_image_zoom", 1.0) or 1.0))
            )
            self.front_ox_spin.setValue(
                float(getattr(layout, "front_image_offset_x_mm", 0.0) or 0.0)
            )
            self.front_oy_spin.setValue(
                float(getattr(layout, "front_image_offset_y_mm", 0.0) or 0.0)
            )
            try:
                bscale = float(getattr(layout, "back_image_scale", 1.0) or 1.0)
            except (TypeError, ValueError):
                bscale = 1.0
            self.back_scale_spin.setValue(max(5.0, min(100.0, bscale * 100.0)))
            self.back_frame_check.setChecked(bool(getattr(layout, "back_image_frame", False)))
            self.back_frame_mm_spin.setValue(
                max(0.5, float(getattr(layout, "back_image_frame_mm", 2.0) or 2.0))
            )
            self.back_frame_color_edit.setText(
                str(getattr(layout, "back_image_frame_color", "") or "#000000")
            )
            self._sync_back_frame_controls()
            pidx = self.back_placement_combo.findData(
                str(getattr(layout, "back_image_placement", "center") or "center")
            )
            self.back_placement_combo.setCurrentIndex(max(0, pidx))
            self.back_img_x_spin.setValue(float(getattr(layout, "back_image_x_pct", 10.0)))
            self.back_img_y_spin.setValue(float(getattr(layout, "back_image_y_pct", 40.0)))
            self.back_img_width_spin.setValue(
                float(getattr(layout, "back_image_width_pct", 40.0))
            )
            self._sync_back_placement_controls()
            self.back_color_edit.setText(layout.back_color)
            self.spine_color_edit.setText(layout.spine_color)
            self.title_edit.setText(layout.title)
            self.author_edit.setText(layout.author)
            self.spine_text_edit.setText(layout.spine_text)
            self.spine_text_down_edit.setText(
                str(getattr(layout, "spine_text_down", "") or "")
            )
            self._set_font_combo(
                self.spine_font_combo, getattr(layout, "spine_font", "sans")
            )
            try:
                pad = float(getattr(layout, "spine_padding_mm", SPINE_EDGE_PADDING_MIN_MM))
            except (TypeError, ValueError):
                pad = SPINE_EDGE_PADDING_MIN_MM
            self.spine_padding_spin.setValue(max(0.0, pad))
            self.title_color_edit.setText(layout.title_color)
            self.title_ox.setValue(layout.title_offset_x_mm)
            self.title_oy.setValue(layout.title_offset_y_mm)
            self.author_ox.setValue(layout.author_offset_x_mm)
            self.author_oy.setValue(layout.author_offset_y_mm)
            self.spine_oy.setValue(layout.spine_offset_y_mm)
            self.title_scale.setValue(layout.title_scale if layout.title_scale > 0 else 1.0)
            self._apply_spine_badge(getattr(layout, "spine_badge", None))
            self._apply_front_compose(getattr(layout, "front_compose", None))
            self._apply_back_compose(getattr(layout, "back_compose", None))
            self._wrap_pdf_rel = str(getattr(layout, "wrap_pdf", "") or "")
            self._production_uuid = str(
                getattr(layout, "production_uuid", "") or ""
            ).strip()
            self._cover_label = str(getattr(layout, "cover_label", "") or "").strip()
            self._cover_role = (
                "alternative"
                if str(getattr(layout, "cover_role", "") or "").strip().lower()
                == "alternative"
                else "primary"
            )
            self._uuid_origin_label = ""
            self._project_path = project_path
            if project_path:
                self.project_path_label.setText(f"Cover-Layout: {project_path}")
            self._on_trim_changed()
            self._sync_free_controls()
            self._sync_front_image_mode_controls()
            self._refresh_binding_ui()
            self._refresh_uuid_link_ui()
        finally:
            self._mode_guard = False
            self._params_guard = was_guarded

    def _studio_repo(self) -> Path:
        from tools.kdp_cover.uuid_choices import resolve_studio_repo

        return resolve_studio_repo(self._studio)

    def _cover_filename_stem(self) -> str:
        """Der Dateiname dieses Cover-Layouts -- ueber die gemeinsame Regel.

        Frueher stand die Reihenfolge hier ein zweites Mal, und zwar
        andersherum als in ``assign_cover_to_uuid``. Ergebnis war ein
        Registry-Eintrag auf eine Datei, die nie geschrieben wurde.
        """
        from tools.kdp_cover.cover_paths import cover_filename_stem

        return cover_filename_stem(
            book_name=self._book.name if self._book else "",
            title=self.title_edit.text(),
        )

    def _cover_role_name(self) -> str:
        return (
            "alternative"
            if str(self._cover_role or "").strip().lower() == "alternative"
            else "primary"
        )

    def _confirm_canonical_paths(self, *, title: str, paths: list[Path]) -> bool:
        lines = "\n".join(f"• {p}" for p in paths)
        reply = QMessageBox.question(
            self,
            title,
            f"Dateien werden kanonisch abgelegt (kein freies Verzeichnis):\n\n"
            f"{lines}\n\nFortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _suggested_save_path(self) -> tuple[str, str]:
        """Startverzeichnis + Dateiname für Laden (kanonisch wenn UUID gesetzt)."""
        from tools.kdp_cover.cover_paths import uuid_cover_root

        uid = normalize_uuid(self._production_uuid)
        stem_name = f"{self._cover_filename_stem()}_kdp_cover.json"
        if uid:
            try:
                root = uuid_cover_root(uid, repo=self._studio_repo())
                root.mkdir(parents=True, exist_ok=True)
                return str(root.resolve()), stem_name
            except (OSError, ValueError):
                pass
        if self._book:
            suggested = default_project_path(self._book)
            try:
                suggested.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            return str(suggested.parent.resolve()), suggested.name
        if self._project_path:
            p = Path(self._project_path)
            return str(p.parent), p.name
        return str(Path.cwd()), "kdp_cover.json"

    def _suggested_elementset_path(self) -> tuple[str, str]:
        """Startverzeichnis + Dateiname für Elementset (Ableitung aus Buchtitel)."""
        from tools.kdp_cover.compose_front import (
            default_element_set_filename,
            default_element_set_path,
        )

        title = self.title_edit.text().strip()
        if self._book:
            suggested = default_element_set_path(self._book, title=title)
            try:
                suggested.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            return str(suggested.parent.resolve()), suggested.name
        name = default_element_set_filename(title, book_folder_name="")
        return str(Path.cwd()), name

    def _layout_validation_blocks_persist(
        self, layout: CoverLayout
    ) -> ValidationReport | None:
        """Validiert vor Speichern; bei Fehlern zum passenden Tab führen."""
        report = validate_layout(layout, resolve_base=self._resolve_base())
        if report.errors:
            detail = "\n".join(f"• {i.message}" for i in report.errors)
            hint = self._persist_block_hint(report.errors)
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle("Speichern gesperrt — Vorgaben verletzt")
            box.setText(
                "Cover-Layout kann nicht gespeichert werden:\n\n"
                f"{detail}"
            )
            box.setInformativeText(hint)
            open_btn = box.addButton(
                "Einstellungen öffnen", QMessageBox.ButtonRole.AcceptRole
            )
            box.addButton("Schließen", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(open_btn)
            box.exec()
            if box.clickedButton() is open_btn:
                self._focus_editor_for_issues(report.errors)
            return None
        return report

    def _persist_block_hint(self, errors: list[ValidationIssue]) -> str:
        codes = {i.code for i in errors}
        if codes & {
            "front_image_missing",
            "front_image_unreadable",
            "front_image_dpi",
            "front_color",
            "front_image_zoom",
        }:
            return (
                "Öffnet den Tab „Vorderseite · Bild“: Front-Farbe (Default reicht), "
                "optional Bild oder Stylecloud-Wortwolke."
            )
        if any(c.startswith("back_") or "barcode" in c for c in codes):
            return (
                "Öffnet den Tab „Rückseite“: Farbe, optionales Bild, "
                "Safe-Zone und Barcode-Zone."
            )
        if any(c.startswith("spine_") for c in codes):
            return "Öffnet den Tab „Rücken“: Farbe, Text und Badge."
        if codes & {"trim_size", "geometry", "page_count", "paper_type"}:
            return "Öffnet den Tab „Maße“: Trimmgröße, Papier und Seitenzahl."
        return "Der passende Editor-Tab wird geöffnet."

    def _focus_editor_for_issues(self, errors: list[ValidationIssue]) -> None:
        """Zum Tab springen, der zum ersten Fehler gehört."""
        codes = [i.code for i in errors]
        tab_name = "Vorderseite · Bild"
        for code in codes:
            if code.startswith("back_") or "barcode" in code:
                tab_name = "Rückseite"
                break
            if code.startswith("spine_"):
                tab_name = "Rücken"
                break
            if code in {"trim_size", "geometry", "page_count", "paper_type"}:
                tab_name = "Maße"
                break
            if code.startswith("front_") or code == "front_color":
                tab_name = "Vorderseite · Bild"
                break
        tabs = getattr(self, "_editor_tabs", None)
        if tabs is None:
            return
        for idx in range(tabs.count()):
            if tabs.tabText(idx) == tab_name:
                tabs.setCurrentIndex(idx)
                break
        self.raise_()
        self.activateWindow()

    def _save_project(self) -> None:
        """Vollspeichern mit Pfad- und Fertig-Abfrage."""
        self._persist_cover_layout(draft=False)

    def _quick_save_project(self) -> None:
        """Zwischenstand ohne Pfadbestätigung und ohne „Cover fertig?“."""
        self._persist_cover_layout(draft=True)

    def _persist_cover_layout(self, *, draft: bool) -> None:
        """Kanonisch unter production/covers/<uuid>/…; optional Spiegel am Buch."""
        if not self._ensure_uuid_link(force=False):
            return
        layout = self._build_layout()
        if self._layout_validation_blocks_persist(layout) is None:
            return
        from tools.kdp_cover.cover_paths import (
            canonical_layout_path,
            mirror_book_layout_path,
        )

        uid = normalize_uuid(self._production_uuid)
        if not uid:
            QMessageBox.critical(
                self,
                "Speichern gesperrt",
                "Production-UUID fehlt — Cover kann nicht kanonisch abgelegt werden.",
            )
            return
        stem = self._cover_filename_stem()
        role = self._cover_role_name()
        canon = canonical_layout_path(
            uid,
            stem=stem,
            cover_role=role,  # type: ignore[arg-type]
            cover_label=self._cover_label,
            repo=self._studio_repo(),
        )
        mirror: Path | None = None
        if self._book:
            mirror = mirror_book_layout_path(self._book, stem)
        targets = [canon] + ([mirror] if mirror is not None else [])
        if not draft and not self._confirm_canonical_paths(
            title="Cover-Layout speichern", paths=targets
        ):
            return
        try:
            canon.parent.mkdir(parents=True, exist_ok=True)
            save_layout(layout, canon)
            self._register_cover_uuid_link(canon, layout)
            if mirror is not None:
                mirror.parent.mkdir(parents=True, exist_ok=True)
                save_layout(layout, mirror)
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self._project_path = canon
        self.project_path_label.setText(f"Cover-Layout: {canon}")
        self._refresh_binding_ui()
        self._refresh_uuid_link_ui()
        # Ampel nutzt die Buch-Bindung (Spiegel), nicht production/covers/…
        gate_path = mirror if mirror is not None else canon
        if self._book is not None:
            try:
                binding = resolve_cover_binding(self._book)
                if binding.canonical_path:
                    gate_path = Path(binding.canonical_path)
            except (OSError, TypeError, ValueError):
                pass
        if draft:
            self._mark_cover_intermediate(gate_path)
        else:
            self._ask_cover_finished(gate_path)
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            kind = "zwischengespeichert" if draft else "gespeichert"
            log(f"KDP-Cover-Layout {kind}: {canon}", "success")

    def _mark_cover_intermediate(self, layout_path: Path) -> None:
        """Still Zwischenstand: Ampel offen, Designer bleibt geöffnet."""
        if self._book is not None:
            try:
                from services.work_path import mark_cover_finished

                mark_cover_finished(self._book, layout_path, finished=False)
            except (OSError, TypeError, ValueError) as exc:
                QMessageBox.warning(
                    self,
                    "Cover-Status",
                    f"Zwischenstand-Status konnte nicht gespeichert werden:\n{exc}",
                )
                return
        self.status_label.setText(
            "● Cover zwischengespeichert — Ampel bleibt offen"
        )
        self.status_label.setStyleSheet(_qlabel_color_ss("#b45309", weight="600"))
        self._notify_work_path_refresh()

    def _ask_cover_finished(self, layout_path: Path) -> None:
        """Nach Speichern: Ja = Export + Ampel grün; Nein = Zwischenstand."""
        if self._book is None:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Cover fertig?")
        box.setText(
            "Cover-Layout wurde gespeichert.\n\n"
            "Ist das Cover fertig für den nächsten Schritt (Render)?"
        )
        box.setInformativeText(
            "• Ja (Cover wird exportiert) — Wrap-PDF erzeugen, "
            "Ampel „Cover“ wird grün, Designer schließt.\n"
            "• Nein — Zwischenstand, Ampel bleibt offen."
        )
        btn_yes = box.addButton(
            "Ja (Cover wird exportiert)",
            QMessageBox.ButtonRole.YesRole,
        )
        btn_no = box.addButton(
            "Nein — Zwischenstand",
            QMessageBox.ButtonRole.NoRole,
        )
        box.setDefaultButton(btn_no)
        box.exec()
        if box.clickedButton() is not btn_yes:
            try:
                from services.work_path import mark_cover_finished

                mark_cover_finished(self._book, layout_path, finished=False)
            except (OSError, TypeError, ValueError) as exc:
                QMessageBox.warning(
                    self,
                    "Cover-Status",
                    f"Zwischenstand-Status konnte nicht gespeichert werden:\n{exc}",
                )
                return
            self.status_label.setText(
                "● Cover gespeichert (Zwischenstand) — Ampel bleibt offen"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#b45309", weight="600"))
            self._notify_work_path_refresh()
            return

        # Ja: erst exportieren (schreibt Layout ggf. neu), dann Token setzen.
        if not self._export_pdf():
            try:
                from services.work_path import mark_cover_finished

                mark_cover_finished(self._book, layout_path, finished=False)
            except (OSError, TypeError, ValueError):
                pass
            self.status_label.setText(
                "● Export abgebrochen/fehlgeschlagen — Ampel bleibt offen"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#b45309", weight="600"))
            self._notify_work_path_refresh()
            return

        gate_path = layout_path
        try:
            from services.work_path import mark_cover_finished
            from tools.kdp_cover.model import resolve_existing_project_path

            resolved = resolve_existing_project_path(self._book)
            if resolved is not None:
                gate_path = Path(resolved)
            mark_cover_finished(self._book, gate_path, finished=True)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Cover-Status",
                f"Fertig-Status konnte nicht gespeichert werden:\n{exc}",
            )
            return
        self.status_label.setText("● Cover exportiert und fertig — Ampel grün")
        self.status_label.setStyleSheet(_qlabel_color_ss("#15803d", weight="600"))
        self._notify_work_path_refresh()
        self.close()

    def _notify_work_path_refresh(self) -> None:
        studio = self._studio
        if studio is None:
            return
        for name in ("_refresh_work_path", "refresh_work_path"):
            fn = getattr(studio, name, None)
            if callable(fn):
                try:
                    fn()
                except (RuntimeError, TypeError, AttributeError):
                    pass
                return
        host = self.parent()
        while host is not None:
            fn = getattr(host, "_refresh_work_path", None)
            if callable(fn):
                try:
                    fn()
                except (RuntimeError, TypeError, AttributeError):
                    pass
                return
            host = host.parent() if hasattr(host, "parent") else None

    def _load_project(self) -> None:
        start_dir, _start_name = self._suggested_save_path()
        path, _ = QFileDialog.getOpenFileName(
            self, "Cover-Layout laden", start_dir, _PROJECT_FILTER
        )
        if not path:
            return
        self._load_layout_path(Path(path))

    def _save_elementset(self) -> None:
        """Nur front_compose speichern — ohne Maße/Bilder/Layout."""
        from tools.kdp_cover.compose_front import save_element_set

        compose = self._collect_front_compose()
        start_dir, start_name = self._suggested_elementset_path()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Elementset speichern",
            str(Path(start_dir) / start_name),
            _ELEMENT_SET_SAVE_FILTER,
        )
        if not path:
            return
        out = Path(path)
        try:
            save_element_set(compose, out)
        except OSError as exc:
            QMessageBox.critical(self, "Elementset speichern fehlgeschlagen", str(exc))
            return
        self.elementset_path_label.setText(f"Elementset: {out}")
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"KDP-Elementset gespeichert: {out}", "success")

    def _load_elementset(self) -> None:
        """Elementset laden und nur die Compose-UI setzen (Rest bleibt)."""
        from tools.kdp_cover.compose_front import load_element_set

        start_dir, _start_name = self._suggested_elementset_path()
        path, _ = QFileDialog.getOpenFileName(
            self, "Elementset laden", start_dir, _ELEMENT_SET_FILTER
        )
        if not path:
            return
        try:
            compose = load_element_set(Path(path))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Elementset laden fehlgeschlagen", str(exc))
            return
        self._apply_front_compose(compose)
        self.elementset_path_label.setText(f"Elementset: {path}")
        self._on_params_changed()
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"KDP-Elementset geladen: {path}", "success")

    def _load_layout_path(self, path: Path) -> bool:
        """Load cover layout JSON into the dialog. Returns True on success."""
        try:
            layout = load_layout(Path(path))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Laden fehlgeschlagen", str(exc))
            return False
        self._apply_layout(layout, project_path=Path(path))
        self._on_params_changed()
        return True

    def _open_from_wrap_pdf(self) -> None:
        """Druckdatei wählen → bearbeitbare Cover-Layout-Quelle laden."""
        from tools.kdp_cover.cover_link import resolve_wrap_source

        start_dir, _ = self._suggested_save_path()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Bearbeiten aus Wrap-PDF — Druckdatei wählen",
            start_dir,
            "Wrap-PDF / Druckdatei (*.pdf);;Alle Dateien (*.*)",
        )
        if not path:
            return
        try:
            layout_path = resolve_wrap_source(
                path,
                repo=self._studio_repo(),
                configured_exiftool=self._configured_exiftool_path() or None,
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(
                self,
                "Bearbeiten aus Wrap-PDF",
                f"{exc}\n\n"
                "Tipp: Die Druckdatei sollte neben der Layout-Datei liegen "
                "(production/covers/… oder export/kdp_cover/) "
                "oder mit einer Hinweisdatei *.cover-link.json aus dem Deploy stammen.",
            )
            return
        if self._load_layout_path(layout_path):
            self.status_label.setText(
                f"● Quelle geladen: {layout_path.name} (aus Wrap-PDF)"
            )

    def _clone_from_template(self) -> None:
        """Cover-Vorlage klonen: neue UUID, Texte tauschen, Layout öffnen."""
        from tools.kdp_cover.clone_cover import extract_text_snapshot
        from tools.kdp_cover.model import load_layout

        start_dir, _ = self._suggested_save_path()
        initial_source: Path | None = None
        initial_texts = None
        if self._project_path and Path(self._project_path).is_file():
            initial_source = Path(self._project_path)
            try:
                initial_texts = extract_text_snapshot(load_layout(initial_source))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                initial_texts = None
        dlg = _CloneFromTemplateDialog(
            self,
            initial_source=initial_source,
            initial_texts=initial_texts,
            start_dir=start_dir,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        result = dlg.result_clone()
        if result is None:
            return
        if self._load_layout_path(result.layout_path):
            self.status_label.setText(
                f"● Aus Vorlage geklont: {result.planned.title_hint} "
                f"({result.planned.production_uuid[:8]}…)"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#166534", weight="600"))
            log = getattr(self._studio, "log", None) if self._studio else None
            if callable(log):
                log(
                    f"KDP-Cover geklont → {result.layout_path} "
                    f"(UUID {result.planned.production_uuid})",
                    "success",
                )

    def _build_sticky_actions(self, left: QVBoxLayout) -> None:
        """Feste Aktionsleiste: Speichern/Laden, Hilfslinien, Status."""
        sticky = QFrame()
        sticky.setObjectName("kdpCoverStickyActions")
        sticky.setStyleSheet(
            """
            QFrame#kdpCoverStickyActions {
                background: #f7f9fd;
                border: 1px solid #c8d3ec;
                border-radius: 8px;
            }
            """
        )
        sticky_lay = QVBoxLayout(sticky)
        sticky_lay.setContentsMargins(10, 8, 10, 8)
        sticky_lay.setSpacing(6)

        self.show_overlays = QCheckBox(
            "Hilfslinien (Bleed / Trim / Safe / Rückenmitte / Barcode-Zone)"
        )
        self.show_overlays.setChecked(True)
        self.show_overlays.setToolTip(
            "Zeigt u. a. die KDP-Barcode-Reserve unten rechts auf der Rückseite "
            "(gelber Platzhalter — dort nichts Wichtiges platzieren)."
        )
        sticky_lay.addWidget(self.show_overlays)

        # Zwei Zeilen à 3 Buttons — eine Zeile quetscht die Beschriftungen.
        self.btn_quick_save = QPushButton("Zwischenspeichern")
        self.btn_quick_save.setToolTip(
            "Zwischenstand sofort speichern — ohne Pfadbestätigung und ohne "
            "„Cover fertig?“-Abfrage.\n"
            "Gleiche Ablage wie „Cover-Layout speichern…“ "
            "(production/covers/<uuid>/…, optional Spiegel am Buch).\n"
            "Ampel „Cover“ bleibt offen; Designer bleibt geöffnet.\n"
            "Für den finalen Stand und die Ampel-Freigabe: "
            "„Cover-Layout speichern…“."
        )
        self.btn_quick_save.clicked.connect(self._quick_save_project)
        self.btn_save_project = QPushButton("Cover-Layout speichern…")
        self.btn_save_project.setToolTip(
            "Ganzes Cover-Projekt speichern: Maße, Papier, Seitenzahl, "
            "Bilder (Vorder-/Rücken-/Rückseite), Texte und Production-UUID.\n"
            "Ablage unter production/covers/<uuid>/… (optional Spiegel am Buch).\n"
            "Fragt Pfade und danach „Cover fertig?“ "
            "(Ja → Wrap-PDF exportieren, Ampel grün, Designer schließt).\n"
            "Für schnelle Zwischenstände ohne Dialoge: „Zwischenspeichern“.\n"
            "Unterschied zu „Elementset“: hier das komplette Cover, nicht nur "
            "die Vorderseiten-Gestaltung.\n"
            "Bei aktivem Buch mit bekannter UUID entfällt die UUID-Auswahl."
        )
        self.btn_save_project.clicked.connect(self._save_project)
        self.btn_load_project = QPushButton("Cover-Layout laden…")
        self.btn_load_project.setToolTip(
            "Nur Cover-Layouts: *_kdp_cover.json / *_kdp_wrap_project.json "
            "(keine Elementsets oder Validierungs-JSON)."
        )
        self.btn_load_project.clicked.connect(self._load_project)
        self.btn_open_from_wrap = QPushButton("Bearbeiten aus Wrap-PDF…")
        self.btn_open_from_wrap.setToolTip(
            "Du hast nur die Druckdatei (Wrap-PDF)?\n"
            "Hier wählst du die PDF — Book Studio findet die "
            "bearbeitbare Quelle (Cover-Layout) und lädt sie hier.\n\n"
            "Funktioniert für PDFs unter production/covers/…, am Buch "
            "oder aus dem Deploy-Ordner (mit Hinweisdatei *.cover-link.json)."
        )
        self.btn_open_from_wrap.clicked.connect(self._open_from_wrap_pdf)
        self.btn_save_elementset = QPushButton("Elementset speichern…")
        self.btn_save_elementset.setToolTip(
            "Nur die Vorderseiten-Gestaltung speichern: Fade, Band, Titel, "
            "Fußzeile, Ecken-Banner, Badge — wiederverwendbar in anderen Büchern.\n"
            "Ohne Maße, Papier, Seitenzahl, Panel-Bilder und UUID.\n"
            "Unterschied zu „Cover-Layout“: Baustein für die Gestaltung, "
            "kein vollständiges Cover-Projekt.\n"
            "Vorschlag: {Buchtitel}_elementset.json."
        )
        self.btn_save_elementset.clicked.connect(self._save_elementset)
        self.btn_load_elementset = QPushButton("Elementset laden…")
        self.btn_load_elementset.setToolTip(
            "Nur Elementsets: *_elementset.json "
            "(keine Cover-Layouts; Maße/Bilder bleiben erhalten)."
        )
        self.btn_load_elementset.clicked.connect(self._load_elementset)
        self.btn_clone_from_template = QPushButton("Cover aus Vorlage…")
        self.btn_clone_from_template.setObjectName("kdpCoverCloneFromTemplate")
        self.btn_clone_from_template.setToolTip(
            "Fertiges Cover als Vorlage nehmen: neue Production-UUID "
            "(Arbeitstitel), Texte tauschen, Layout unter "
            "production/covers/<uuid>/… speichern und hier öffnen.\n"
            "Gestaltung/Maße/Bilder bleiben — ideal für Serien-Covers."
        )
        self.btn_clone_from_template.clicked.connect(self._clone_from_template)
        io_rows = (
            (
                self.btn_quick_save,
                self.btn_save_project,
                self.btn_load_project,
            ),
            (
                self.btn_open_from_wrap,
                self.btn_save_elementset,
                self.btn_load_elementset,
            ),
            (self.btn_clone_from_template,),
        )
        for row_btns in io_rows:
            row = QHBoxLayout()
            row.setSpacing(6)
            if row_btns and row_btns[0] is self.btn_clone_from_template:
                from ui_qt.widgets.handbook_info_button import (
                    make_handbook_info_button,
                )

                info = make_handbook_info_button(
                    self, anchor="sec-kdp-clone-cover", host=self
                )
                info.setToolTip("Handbuch: Cover aus Vorlage…")
                row.addWidget(info, stretch=0)
            for btn in row_btns:
                btn.setMinimumHeight(28)
                btn.setSizePolicy(
                    QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
                )
                row.addWidget(btn, stretch=1)
            sticky_lay.addLayout(row)

        self.project_path_label = QLabel("(kein Cover-Layout geladen)")
        self.project_path_label.setStyleSheet("color:#64748b; font-size:11px;")
        self.project_path_label.setWordWrap(True)
        sticky_lay.addWidget(self.project_path_label)
        self.elementset_path_label = QLabel("")
        self.elementset_path_label.setStyleSheet("color:#64748b; font-size:11px;")
        self.elementset_path_label.setWordWrap(True)
        sticky_lay.addWidget(self.elementset_path_label)

        self.status_label = QLabel("● bereit")
        self.status_label.setWordWrap(True)
        self.status_label.setToolTip(_STATUS_EXPORT_TOOLTIP)
        sticky_lay.addWidget(self.status_label)

        self.issues_label = QLabel("")
        self.issues_label.setWordWrap(True)
        self.issues_label.setStyleSheet("font-size: 12px;")
        sticky_lay.addWidget(self.issues_label)
        left.addWidget(sticky, stretch=0)

    def _prefill_from_book(self) -> None:
        """Titel/Autor aus _quarto.yml, Deckblatt-Bild aus img/ vorbelegen."""
        if self._book:
            title, author = _read_quarto_title_author(self._book)
            if title:
                self.title_edit.setText(title)
            if author:
                self.author_edit.setText(author)
                if not self.compose_author.text().strip():
                    self.compose_author.setText(author)
            img_dir = self._book / "img"
            if img_dir.is_dir():
                candidates = sorted(img_dir.glob("Deckblatt*.png")) + sorted(
                    img_dir.glob("Deckblatt*.jpg")
                )
                if candidates:
                    self.front_edit.setText(str(candidates[0]))
                    self.front_mode_full.setChecked(True)
