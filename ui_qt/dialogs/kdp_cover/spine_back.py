"""Rücken (Badge), Rückseite (Abbildung, Subtitel, Textblöcke) und Zonenkarte.

Mixin von ``KdpCoverQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from tools.kdp_cover.compose_back import BackComposeSpec
from tools.kdp_cover.constants import (
    SPINE_BADGE_SCALE_STEPS,
    SPINE_EDGE_PADDING_MIN_MM,
)
from tools.kdp_cover.geometry import WrapGeometry
from tools.kdp_cover.model import (
    CoverLayout,
    SpineBadgeSpec,
)
from ui_qt.dialogs.kdp_cover.common import (
    _IMAGE_FILTER,
)
from ui_qt.widgets.collapsible_section import CollapsibleSection


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

    def _build_tab_zones(self) -> None:
        """Tab Zonenkarte: Rück- und Vorderseite nebeneinander."""
        # --- Tab: Zonenkarte (Layout-Hilfe, flächenfüllend) ---
        from ui_qt.widgets.back_cover_zone_map import BackCoverZoneMap
        from ui_qt.widgets.cover_zone_map import CoverZoneMap

        tab_zones, zones_body = self._make_editor_tab(scrollable=False)
        zones_hint = QLabel(
            "Umschlag als Orientierung — links Rückseite, rechts Vorderseite. "
            "Klick springt zum Dialogteil (nicht die Live-Vorschau rechts). "
            "Rückseiten-Zonen folgen den eingestellten Positionen; "
            "gestrichelt = ausgeschaltet (Klick schaltet ein)."
        )
        zones_hint.setWordWrap(True)
        zones_hint.setStyleSheet("color:#5b6573; font-size:12px;")
        zones_body.addWidget(zones_hint)
        maps_row = QHBoxLayout()
        maps_row.setSpacing(6)
        self._back_zone_map = BackCoverZoneMap()
        self._back_zone_map.zone_clicked.connect(self._jump_to_cover_zone)
        self._zone_map = CoverZoneMap()
        self._zone_map.zone_clicked.connect(self._jump_to_cover_zone)
        maps_row.addWidget(self._back_zone_map, 1)
        maps_row.addWidget(self._zone_map, 1)
        zones_body.addLayout(maps_row, stretch=1)
        self._zone_tab_index = self._editor_tabs.addTab(tab_zones, "Zonenkarte")
        self._editor_tabs.setTabToolTip(
            self._zone_tab_index,
            "Visuelle Layout-Hilfe für Rück- und Vorderseite: "
            "Zonen anklicken → Sprung zu den Feldern.",
        )

    def _build_tab_spine(self) -> None:
        """Tab 5 · Rücken: Farbe, Texte, Badge."""
        # --- Tab: Rücken ---
        tab_spine, spine_body = self._make_editor_tab()
        design_spine = QFormLayout()
        design_spine.setSpacing(8)
        spine_body.addLayout(design_spine)

        spine_color_host, self.spine_color_edit = self._color_field(
            "#222222", max_width=100, tooltip="Rückenfarbe"
        )
        design_spine.addRow("Rückenfarbe:", spine_color_host)

        self.spine_text_edit = QLineEdit()
        self.spine_text_edit.setPlaceholderText(
            "unten verankert — Lesrichtung immer unten → oben"
        )
        self.spine_text_edit.setToolTip(
            "Rücken-Text 1: am Fuß des Rückens beginnend, Block wächst nach oben. "
            "Lesrichtung immer von unten nach oben."
        )
        design_spine.addRow("Rücken-Text 1 (unten):", self.spine_text_edit)
        self.spine_text_down_edit = QLineEdit()
        self.spine_text_down_edit.setPlaceholderText(
            "oben verankert — Lesrichtung immer unten → oben"
        )
        self.spine_text_down_edit.setToolTip(
            "Rücken-Text 2: am Kopf des Rückens beginnend, Block wächst nach unten. "
            "Lesrichtung ebenfalls unten → oben. Badge vor/nach diesem Text."
        )
        design_spine.addRow("Rücken-Text 2 (oben):", self.spine_text_down_edit)
        self.spine_font_combo = self._font_family_combo()
        self.spine_font_combo.setMaximumWidth(120)
        self.spine_font_combo.setToolTip(
            "Font für Rücken-Text 1, Text 2 und Badge (Sans / Serif / Mono)."
        )
        design_spine.addRow("Rücken-Font:", self.spine_font_combo)
        self.spine_padding_spin = QDoubleSpinBox()
        self.spine_padding_spin.setRange(0.0, 80.0)
        self.spine_padding_spin.setDecimals(1)
        self.spine_padding_spin.setSingleStep(1.0)
        self.spine_padding_spin.setSuffix(" mm")
        self.spine_padding_spin.setValue(SPINE_EDGE_PADDING_MIN_MM)
        self.spine_padding_spin.setToolTip(
            "Abstand vom Kopf- und Fußrand parallel. "
            "Größer = beide Texte rücken zur Mitte zusammen; "
            "kleiner = sie gehen auseinander zu den Rändern."
        )
        design_spine.addRow("Rücken-Padding:", self.spine_padding_spin)

        self.spine_badge_enabled = QCheckBox("Reihen-/Themen-Badge (an Text 2)")
        self.spine_badge_enabled.setToolTip(
            "Zusätzliches Rechteck mit weißem Text (z. B. MEDIZIN, POLITIK) "
            "vor oder nach Textelement 2. Gleiche Lesrichtung (unten → oben)."
        )
        design_spine.addRow("", self.spine_badge_enabled)
        self.spine_badge_text = QLineEdit()
        self.spine_badge_text.setPlaceholderText("z. B. MEDIZIN")
        self.spine_badge_text.setToolTip("Weiße Schrift auf dem farbigen Rechteck.")
        design_spine.addRow("Badge-Text:", self.spine_badge_text)
        badge_color_host, self.spine_badge_color = self._color_field(
            "#9B2C3E",
            max_width=100,
            tooltip="Hintergrundfarbe des Badge-Rechtecks (frei wählbar).",
        )
        self.spine_badge_color_host = badge_color_host
        design_spine.addRow("Badge-Farbe:", badge_color_host)
        self.spine_badge_position = QComboBox()
        self.spine_badge_position.addItem("Vor Text 2 (Lesbeginn)", "before")
        self.spine_badge_position.addItem("Nach Text 2 (Lesende)", "after")
        self.spine_badge_position.setToolTip(
            "Reihenfolge in Lesrichtung unten → oben: vor = näher am Fuß des Blocks."
        )
        design_spine.addRow("Badge-Position:", self.spine_badge_position)
        self.spine_badge_scale = QComboBox()
        for i, factor in enumerate(SPINE_BADGE_SCALE_STEPS):
            pct = int(round(factor * 100))
            self.spine_badge_scale.addItem(f"{pct} %", i)
        self.spine_badge_scale.setToolTip(
            "Globale Verkleinerung von Badge-Text und Hintergrund in Stufen."
        )
        design_spine.addRow("Badge-Größe:", self.spine_badge_scale)
        self.spine_badge_enabled.toggled.connect(self._sync_spine_badge_controls)
        # title_color bleibt im Layout-Modell für Abwärtskompatibilität, UI entfällt.
        self.title_color_edit = QLineEdit("#FFFFFF")
        self.title_color_edit.hide()
        self._editor_tabs.addTab(tab_spine, "Rücken")
        self._editor_tabs.setTabToolTip(
            self._editor_tabs.count() - 1, "5 · Rücken (Farbe, Text, Badge)"
        )
        self._sync_spine_badge_controls()

    def _build_tab_back(self) -> None:
        """Tab 6 · Rückseite: Abbildung, Subtitel, Klappentext, Bio."""
        # --- Tab: Rückseite ---
        from ui_qt.widgets.kdp_back_editors import SubtitleEditor, TextBlockEditor

        tab_back, back_body = self._make_editor_tab()
        design_back = QFormLayout()
        design_back.setSpacing(8)
        back_body.addLayout(design_back)

        back_color_host, self.back_color_edit = self._color_field(
            "#F5F0E8", max_width=100, tooltip="Rückseiten-Hintergrundfarbe"
        )
        design_back.addRow("Back-Farbe:", back_color_host)

        # Abbildung (PNG/JPG) — zentriert oder frei platziert
        img_sec = CollapsibleSection("Abbildung", expanded=True)
        img_form = self._nested_form(img_sec)
        self.back_edit = QLineEdit()
        self.back_edit.setPlaceholderText("optional — Autor:innenfoto o. Ä. (PNG/JPG)")
        back_row = QHBoxLayout()
        back_row.addWidget(self.back_edit)
        btn_back_asset = QPushButton("Asset…")
        btn_back_asset.setToolTip(
            "Bild aus dem Asset Manager wählen (Pool oder Buch-img/)."
        )
        btn_back_asset.clicked.connect(lambda: self._pick_image_via_asset("back"))
        back_row.addWidget(btn_back_asset)
        btn_back = QPushButton("…")
        btn_back.setFixedWidth(32)
        btn_back.setToolTip("Datei im Dateisystem wählen")
        btn_back.clicked.connect(self._browse_back)
        back_row.addWidget(btn_back)
        img_form.addRow("Bild:", back_row)
        self.back_placement_combo = QComboBox()
        self.back_placement_combo.addItem("Zentriert (Größe in %)", "center")
        self.back_placement_combo.addItem("Frei (Position + Breite)", "free")
        self.back_placement_combo.setToolTip(
            "Zentriert: in der Safe-Zone eingepasst.\n"
            "Frei: linke obere Ecke und Breite in % der Rückseite (ohne Beschnitt); "
            "die Höhe folgt dem Seitenverhältnis. Anschnitt über den Rand ist erlaubt "
            "(Hinweis), die Barcode-Zone muss frei bleiben."
        )
        img_form.addRow("Platzierung:", self.back_placement_combo)
        self.back_scale_spin = QDoubleSpinBox()
        self.back_scale_spin.setRange(5.0, 100.0)
        self.back_scale_spin.setDecimals(0)
        self.back_scale_spin.setSingleStep(5.0)
        self.back_scale_spin.setSuffix(" %")
        self.back_scale_spin.setValue(100.0)
        self.back_scale_spin.setToolTip(
            "Verkleinern relativ zur maximalen Safe-Zone-Größe. "
            "Immer zentriert; Rest = Back-Farbe. Muss die Barcode-Zone freilassen."
        )
        img_form.addRow("Größe (zentriert):", self.back_scale_spin)

        def _pct_spin(lo: float, hi: float, value: float, suffix: str, tip: str) -> QDoubleSpinBox:
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setDecimals(1)
            spin.setSingleStep(1.0)
            spin.setValue(value)
            spin.setSuffix(suffix)
            spin.setToolTip(tip)
            return spin

        self.back_img_x_spin = _pct_spin(
            -20.0, 120.0, 10.0, " %X", "Linke Kante (% der Rückseiten-Breite)."
        )
        self.back_img_y_spin = _pct_spin(
            -20.0, 120.0, 40.0, " %Y", "Oberkante (% der Rückseiten-Höhe)."
        )
        self.back_img_width_spin = _pct_spin(
            5.0, 120.0, 40.0, " %B", "Bildbreite (% der Rückseiten-Breite)."
        )
        img_form.addRow(
            "Position X / Y (frei):",
            self._pair(self.back_img_x_spin, self.back_img_y_spin),
        )
        img_form.addRow("Breite (frei):", self.back_img_width_spin)
        self.back_frame_check = QCheckBox("Rahmen um Rückseiten-Bild")
        img_form.addRow("", self.back_frame_check)
        self.back_frame_mm_spin = QDoubleSpinBox()
        self.back_frame_mm_spin.setRange(0.5, 20.0)
        self.back_frame_mm_spin.setDecimals(1)
        self.back_frame_mm_spin.setSingleStep(0.5)
        self.back_frame_mm_spin.setSuffix(" mm")
        self.back_frame_mm_spin.setValue(2.0)
        img_form.addRow("Rahmenstärke:", self.back_frame_mm_spin)
        frame_color_host, self.back_frame_color_edit = self._color_field(
            "#000000", max_width=100, tooltip="Rahmenfarbe"
        )
        self.back_frame_color_host = frame_color_host
        img_form.addRow("Rahmenfarbe:", frame_color_host)
        self.back_frame_check.toggled.connect(self._sync_back_frame_controls)
        self.back_placement_combo.currentIndexChanged.connect(
            self._sync_back_placement_controls
        )
        self._sync_back_frame_controls()
        self._sync_back_placement_controls()
        back_body.addWidget(img_sec)
        self._back_sec_image = img_sec

        # Subtitel — gleiche Parameter wie auf der Vorderseite
        sub_sec = CollapsibleSection("Subtitel", expanded=False)
        self.back_subtitle_editor = SubtitleEditor(
            color_field=self._color_field, font_combo=self._font_family_combo
        )
        sub_sec.body_layout().addWidget(self.back_subtitle_editor)
        back_body.addWidget(sub_sec)
        self._back_sec_subtitle = sub_sec

        # Klappentext + Kurzbiografie — Fließtext
        blurb_sec = CollapsibleSection("Klappentext", expanded=False)
        self.back_blurb_editor = TextBlockEditor(
            label="Klappentext anzeigen",
            placeholder="Klappentext … (Leerzeile = neuer Absatz)",
            color_field=self._color_field,
            font_combo=self._font_family_combo,
        )
        blurb_sec.body_layout().addWidget(self.back_blurb_editor)
        back_body.addWidget(blurb_sec)
        self._back_sec_blurb = blurb_sec

        bio_sec = CollapsibleSection("Autor-Kurzbiografie", expanded=False)
        self.back_bio_editor = TextBlockEditor(
            label="Kurzbiografie anzeigen",
            placeholder="Über den Autor / die Autorin …",
            color_field=self._color_field,
            font_combo=self._font_family_combo,
        )
        bio_sec.body_layout().addWidget(self.back_bio_editor)
        back_body.addWidget(bio_sec)
        self._back_sec_bio = bio_sec
        for editor in (self.back_subtitle_editor, self.back_blurb_editor, self.back_bio_editor):
            editor.changed.connect(self._on_params_changed)
        self._apply_back_compose(None)

        self._back_tab_index = self._editor_tabs.addTab(tab_back, "Rückseite")
        self._editor_tabs.setTabToolTip(
            self._back_tab_index,
            "6 · Rückseite (Farbe, Abbildung, Subtitel, Klappentext, Kurzbiografie)",
        )
