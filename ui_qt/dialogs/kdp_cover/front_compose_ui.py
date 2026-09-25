"""Formular der Vorderseiten-Ebenen (Fade, Band, Titel, Subtitel, Fuß, Banner, Badge) und deren Verdrahtung.

Mixin von ``FrontMixin`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.widgets.collapsible_section import CollapsibleSection


class FrontComposeUiMixin:
    """Formular der Vorderseiten-Ebenen (Fade, Band, Titel, Subtitel, Fuß, Banner, Badge) und deren Verdrahtung."""

    def _build_compose_front_group(self) -> QWidget:
        """Vorderseiten-Gestaltung (Layer über Farbe/Bild)."""
        box = QWidget()
        box.setToolTip(
            "Layer über der Vorderseite: Fade, Band, Titel, Fuß, Ecken-Banner, Badge. "
            "Jeder Block hat eigenen An/Aus-Schalter — ohne Master-Kill-Switch."
        )
        root = QVBoxLayout(box)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        top = QFormLayout()
        top.setSpacing(6)
        top.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        root.addLayout(top)

        # Kein sichtbarer „Layer aktiv“-Schalter: leeres Deckblatt ist kein Use-Case.
        # JSON-Feld ``enabled`` bleibt True beim Speichern aus dieser UI.
        self.compose_enabled = QCheckBox("Layer aktiv")
        self.compose_enabled.setChecked(True)
        self.compose_enabled.hide()

        fade_sec = CollapsibleSection("Fade (oben / unten)", expanded=False)
        fade_form = self._nested_form(fade_sec)
        from tools.kdp_cover.compose_front import (
            FADE_SOFT_WHITE_COLOR,
            FADE_SOFT_WHITE_HEIGHT_PCT,
            FADE_SOFT_WHITE_OPACITY,
        )

        self.compose_fade_enabled = QCheckBox("Fade oben")
        self.compose_fade_enabled.setChecked(False)
        self.compose_fade_enabled.setToolTip(
            "Vollfarbe am oberen Rand (nach unten auslaufend).\n"
            "Bei „Bild im goldenen Schnitt“ beginnt der Fade erst an der "
            "Unterkante des Bildbands.\n"
            "Aus = keine obere Verlaufsschicht."
        )
        # Vollfarbe-Defaults (nicht Weiß — Weiß ist nur Autofade-Gegenseite)
        fade_color_host, self.compose_fade_color = self._color_field("#1E3A5F")
        self.compose_fade_height = QDoubleSpinBox()
        self.compose_fade_height.setRange(5.0, 80.0)
        self.compose_fade_height.setValue(40.0)
        self.compose_fade_height.setSuffix(" %H")
        self.compose_fade_opacity = QDoubleSpinBox()
        self.compose_fade_opacity.setRange(0.0, 1.0)
        self.compose_fade_opacity.setSingleStep(0.05)
        self.compose_fade_opacity.setDecimals(2)
        self.compose_fade_opacity.setValue(1.0)
        fade_form.addRow(self.compose_fade_enabled)
        fade_form.addRow(
            "Oben Farbe/Höhe/α:",
            self._pair(
                fade_color_host,
                self._pair(self.compose_fade_height, self.compose_fade_opacity),
            ),
        )

        self.compose_fade_bottom_enabled = QCheckBox("Fade unten")
        self.compose_fade_bottom_enabled.setChecked(False)
        self.compose_fade_bottom_enabled.setToolTip(
            "Vollfarbe am unteren Rand (nach oben auslaufend).\n"
            "Aus = keine untere Verlaufsschicht."
        )
        fade_bottom_color_host, self.compose_fade_bottom_color = self._color_field(
            "#1E3A5F"
        )
        self.compose_fade_bottom_height = QDoubleSpinBox()
        self.compose_fade_bottom_height.setRange(5.0, 80.0)
        self.compose_fade_bottom_height.setValue(40.0)
        self.compose_fade_bottom_height.setSuffix(" %H")
        self.compose_fade_bottom_opacity = QDoubleSpinBox()
        self.compose_fade_bottom_opacity.setRange(0.0, 1.0)
        self.compose_fade_bottom_opacity.setSingleStep(0.05)
        self.compose_fade_bottom_opacity.setDecimals(2)
        self.compose_fade_bottom_opacity.setValue(1.0)
        fade_form.addRow(self.compose_fade_bottom_enabled)
        fade_form.addRow(
            "Unten Farbe/Höhe/α:",
            self._pair(
                fade_bottom_color_host,
                self._pair(
                    self.compose_fade_bottom_height,
                    self.compose_fade_bottom_opacity,
                ),
            ),
        )

        _fade_link_qss = (
            "QPushButton { color:#64748b; font-size:11px; padding:2px 6px; "
            "text-decoration: underline; border: none; background: transparent; }"
            "QPushButton:hover { color:#334155; }"
        )
        self.btn_fade_autofade = QPushButton("Autofade")
        self.btn_fade_autofade.setFlat(True)
        self.btn_fade_autofade.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fade_autofade.setStyleSheet(_fade_link_qss)
        self.btn_fade_autofade.setToolTip(
            "Setze zuerst die Vollfarbe oben oder unten (Haken an).\n"
            "Dann: minimales Autofade nach Weiß auf der Gegenseite "
            f"(α={FADE_SOFT_WHITE_OPACITY:.2f}, "
            f"{FADE_SOFT_WHITE_HEIGHT_PCT:.0f} %H, {FADE_SOFT_WHITE_COLOR})."
        )
        self.btn_fade_autofade.clicked.connect(self._apply_fade_autofade)
        # Alias for older tests / callers
        self.btn_fade_soft_white = self.btn_fade_autofade

        self.btn_fade_invert = QPushButton("Invert Fading Direction")
        self.btn_fade_invert.setFlat(True)
        self.btn_fade_invert.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fade_invert.setStyleSheet(_fade_link_qss)
        self.btn_fade_invert.setToolTip(
            "Tauscht Fade oben ↔ unten (Farbe, Höhe, α und An/Aus)."
        )
        self.btn_fade_invert.clicked.connect(self._invert_fade_direction)

        fade_links_row = QWidget()
        fade_links_layout = QHBoxLayout(fade_links_row)
        fade_links_layout.setContentsMargins(0, 4, 0, 0)
        fade_links_layout.setSpacing(12)
        fade_links_layout.addStretch(1)
        fade_links_layout.addWidget(self.btn_fade_autofade)
        fade_links_layout.addWidget(self.btn_fade_invert)
        fade_form.addRow(fade_links_row)
        root.addWidget(fade_sec)
        self._compose_sec_fade = fade_sec

        band_sec = CollapsibleSection("Band", expanded=False)
        band_form = self._nested_form(band_sec)
        self.compose_band_enabled = QCheckBox("Band")
        self.compose_band_y = QDoubleSpinBox()
        self.compose_band_y.setRange(0.0, 100.0)
        self.compose_band_y.setValue(55.0)
        self.compose_band_y.setSuffix(" %Y")
        self.compose_band_h = QDoubleSpinBox()
        self.compose_band_h.setRange(1.0, 40.0)
        self.compose_band_h.setValue(8.0)
        self.compose_band_h.setSuffix(" %H")
        band_color_host, self.compose_band_color = self._color_field(
            "#E8A0B0",
            tooltip="Bandfarbe (voll deckend, ohne Transparenz)",
        )
        self.compose_band_text = QLineEdit()
        self.compose_band_text.setPlaceholderText("Band-Text (immer mittig)")
        band_text_color_host, self.compose_band_text_color = self._color_field(
            "#FFFFFF",
            tooltip="Textfarbe auf dem Band",
        )
        self.compose_band_text_size = QDoubleSpinBox()
        self.compose_band_text_size.setRange(10.0, 100.0)
        self.compose_band_text_size.setValue(55.0)
        self.compose_band_text_size.setSuffix(" %")
        self.compose_band_text_size.setToolTip(
            "Schriftgröße relativ zur Bandhöhe (100 % = Bandhöhe)."
        )
        self.compose_band_font = self._font_family_combo()
        band_form.addRow(self.compose_band_enabled)
        band_form.addRow(
            "Band Farbe/Pos:",
            self._pair(
                band_color_host,
                self._pair(self.compose_band_y, self.compose_band_h),
            ),
        )
        band_form.addRow(
            "Band-Text:",
            self._pair(
                self.compose_band_text,
                self._pair(
                    band_text_color_host,
                    self._pair(self.compose_band_text_size, self.compose_band_font),
                ),
            ),
        )
        root.addWidget(band_sec)
        self._compose_sec_band = band_sec

        titles_sec = CollapsibleSection("Titelzeilen", expanded=False)
        titles_form = self._nested_form(titles_sec)
        self.compose_titles_enabled = QCheckBox("Titelzeilen")
        self.compose_titles_enabled.setChecked(True)
        self.compose_series = QLineEdit()
        self.compose_series.setPlaceholderText("Titelzeile 1")
        series_color_host, self.compose_series_color = self._color_field("#1E3A5F")
        self.compose_main = QLineEdit()
        self.compose_main.setPlaceholderText("Titelzeile 2")
        main_color_host, self.compose_main_color = self._color_field("#1E3A5F")
        self.compose_lines_size = QDoubleSpinBox()
        self.compose_lines_size.setRange(1.0, 12.0)
        self.compose_lines_size.setDecimals(1)
        self.compose_lines_size.setSingleStep(0.5)
        self.compose_lines_size.setValue(4.5)
        self.compose_lines_size.setSuffix(" %H")
        self.compose_lines_size.setToolTip(
            "Gemeinsame Schriftgröße für Titelzeile 1 und 2 (% der Front-Höhe)."
        )
        self.compose_lines_bold = QCheckBox("Fett")
        self.compose_lines_bold.setToolTip("Titelzeile 1 und 2 fett darstellen")
        self.compose_lines_font = self._font_family_combo()
        self.compose_lines_gap = QDoubleSpinBox()
        self.compose_lines_gap.setRange(-4.0, 8.0)
        self.compose_lines_gap.setDecimals(1)
        self.compose_lines_gap.setSingleStep(0.2)
        self.compose_lines_gap.setValue(1.2)
        self.compose_lines_gap.setSuffix(" %H")
        self.compose_lines_gap.setToolTip(
            "Abstand zwischen Titelzeile 1 und 2 (% der Front-Höhe).\n"
            "0 = direkt aneinander; negativ = noch enger (Zeilen fließen zusammen)."
        )
        self.compose_titles_top = QDoubleSpinBox()
        self.compose_titles_top.setRange(0.0, 100.0)
        self.compose_titles_top.setDecimals(1)
        self.compose_titles_top.setSingleStep(1.0)
        self.compose_titles_top.setValue(6.0)
        self.compose_titles_top.setSuffix(" %Y")
        self.compose_titles_top.setToolTip(
            "Gemeinsame Startposition von Titelzeile 1 und 2 von oben (% der Front-Höhe)."
        )
        self.compose_accent = QLineEdit()
        self.compose_accent.setPlaceholderText("Claim")
        accent_color_host, self.compose_accent_color = self._color_field("#9B2C3E")
        self.compose_accent_size = QDoubleSpinBox()
        self.compose_accent_size.setRange(1.0, 12.0)
        self.compose_accent_size.setDecimals(1)
        self.compose_accent_size.setSingleStep(0.5)
        self.compose_accent_size.setValue(5.5)
        self.compose_accent_size.setSuffix(" %H")
        self.compose_accent_size.setToolTip("Schriftgröße Claim (% der Front-Höhe).")
        self.compose_accent_top = QDoubleSpinBox()
        self.compose_accent_top.setRange(0.0, 100.0)
        self.compose_accent_top.setDecimals(1)
        self.compose_accent_top.setSingleStep(1.0)
        self.compose_accent_top.setValue(18.0)
        self.compose_accent_top.setSuffix(" %Y")
        self.compose_accent_top.setToolTip(
            "Eigene Startposition des Claims von oben (% der Front-Höhe)."
        )
        self.compose_accent_bold = QCheckBox("Fett")
        self.compose_accent_bold.setToolTip("Claim fett darstellen")
        self.compose_accent_italic = QCheckBox("Kursiv")
        self.compose_accent_italic.setToolTip("Claim kursiv darstellen")
        self.compose_accent_font = self._font_family_combo()
        titles_form.addRow(self.compose_titles_enabled)
        titles_form.addRow("Position 1+2:", self.compose_titles_top)
        self.compose_titles_align = QComboBox()
        self.compose_titles_align.addItem("Links", "left")
        self.compose_titles_align.addItem("Zentriert", "center")
        self.compose_titles_align.addItem("Rechts", "right")
        self.compose_titles_align.setCurrentIndex(1)
        self.compose_titles_align.setToolTip(
            "Horizontale Ausrichtung für Titelzeile 1+2, Subtitel, Claim und Autor "
            "(Seitenrand ≈ 5 % der Vorderseitenbreite)."
        )
        self.compose_titles_offset_x = QDoubleSpinBox()
        self.compose_titles_offset_x.setRange(-45.0, 45.0)
        self.compose_titles_offset_x.setDecimals(1)
        self.compose_titles_offset_x.setSingleStep(1.0)
        self.compose_titles_offset_x.setValue(0.0)
        self.compose_titles_offset_x.setSuffix(" %X")
        self.compose_titles_offset_x.setToolTip(
            "Horizontaler Versatz nach der Ausrichtung "
            "(negativ = nach links, positiv = nach rechts; % der Vorderseitenbreite)."
        )
        titles_form.addRow(
            "Ausrichtung:",
            self._pair(self.compose_titles_align, self.compose_titles_offset_x),
        )
        titles_form.addRow(
            "Titelzeile 1:",
            self._pair(self.compose_series, series_color_host),
        )
        titles_form.addRow(
            "Titelzeile 2:",
            self._pair(self.compose_main, main_color_host),
        )
        titles_form.addRow(
            "Größe 1+2:",
            self._pair(
                self.compose_lines_size,
                self._pair(self.compose_lines_font, self.compose_lines_bold),
            ),
        )
        titles_form.addRow("Abstand 1↔2:", self.compose_lines_gap)

        # --- Subtitel (2 Zeilen, je Farbe/Font/Größe) ---
        self.compose_subtitle_enabled = QCheckBox("Subtitel")
        self.compose_subtitle_enabled.setToolTip(
            "Zweizeiliger Subtitel; Farbe, Fonttyp und Größe je Zeile getrennt."
        )
        self.compose_subtitle_top = QDoubleSpinBox()
        self.compose_subtitle_top.setRange(0.0, 100.0)
        self.compose_subtitle_top.setDecimals(1)
        self.compose_subtitle_top.setSingleStep(1.0)
        self.compose_subtitle_top.setValue(28.0)
        self.compose_subtitle_top.setSuffix(" %Y")
        self.compose_subtitle_top.setToolTip(
            "Startposition Subtitel von oben (% der Front-Höhe)."
        )
        self.compose_subtitle_gap = QDoubleSpinBox()
        self.compose_subtitle_gap.setRange(-4.0, 8.0)
        self.compose_subtitle_gap.setDecimals(1)
        self.compose_subtitle_gap.setSingleStep(0.2)
        self.compose_subtitle_gap.setValue(0.8)
        self.compose_subtitle_gap.setSuffix(" %H")
        self.compose_subtitle_gap.setToolTip(
            "Abstand zwischen Subtitel Zeile 1 und 2 (% der Front-Höhe).\n"
            "0 = direkt aneinander; negativ = noch enger (Zeilen fließen zusammen)."
        )
        self.compose_sub1 = QLineEdit()
        self.compose_sub1.setPlaceholderText("Subtitel Zeile 1")
        sub1_color_host, self.compose_sub1_color = self._color_field("#FFFFFF")
        self.compose_sub1_size = QDoubleSpinBox()
        self.compose_sub1_size.setRange(1.0, 12.0)
        self.compose_sub1_size.setDecimals(1)
        self.compose_sub1_size.setSingleStep(0.5)
        self.compose_sub1_size.setValue(3.2)
        self.compose_sub1_size.setSuffix(" %H")
        self.compose_sub1_font = self._font_family_combo()
        self.compose_sub1_bold = QCheckBox("Fett")
        self.compose_sub1_italic = QCheckBox("Kursiv")
        self.compose_sub2 = QLineEdit()
        self.compose_sub2.setPlaceholderText("Subtitel Zeile 2")
        sub2_color_host, self.compose_sub2_color = self._color_field("#FFFFFF")
        self.compose_sub2_size = QDoubleSpinBox()
        self.compose_sub2_size.setRange(1.0, 12.0)
        self.compose_sub2_size.setDecimals(1)
        self.compose_sub2_size.setSingleStep(0.5)
        self.compose_sub2_size.setValue(3.2)
        self.compose_sub2_size.setSuffix(" %H")
        self.compose_sub2_font = self._font_family_combo()
        self.compose_sub2_bold = QCheckBox("Fett")
        self.compose_sub2_italic = QCheckBox("Kursiv")
        titles_form.addRow(self.compose_subtitle_enabled)
        titles_form.addRow("Subtitel Position:", self.compose_subtitle_top)
        titles_form.addRow("Subtitel Abstand 1↔2:", self.compose_subtitle_gap)
        self.compose_subtitle_band_enabled = QCheckBox("Band hinterlegen")
        self.compose_subtitle_band_enabled.setToolTip(
            "Vollbreites Band hinter dem Subtitel "
            "(immer von links nach rechts über die ganze Vorderseite).\n"
            "Das Band zentriert sich an den Glyphen; Abstände oben/unten getrennt."
        )
        sub_band_color_host, self.compose_subtitle_band_color = self._color_field(
            "#1E3A5F",
            tooltip="Bandfarbe hinter dem Subtitel",
        )
        self.compose_subtitle_band_pad_top = QDoubleSpinBox()
        self.compose_subtitle_band_pad_top.setRange(0.0, 12.0)
        self.compose_subtitle_band_pad_top.setDecimals(1)
        self.compose_subtitle_band_pad_top.setSingleStep(0.2)
        self.compose_subtitle_band_pad_top.setValue(1.2)
        self.compose_subtitle_band_pad_top.setSuffix(" %H")
        self.compose_subtitle_band_pad_top.setToolTip(
            "Abstand Band-Oberkante → Subtitel-Text (% der Front-Höhe)."
        )
        self.compose_subtitle_band_pad_bottom = QDoubleSpinBox()
        self.compose_subtitle_band_pad_bottom.setRange(0.0, 12.0)
        self.compose_subtitle_band_pad_bottom.setDecimals(1)
        self.compose_subtitle_band_pad_bottom.setSingleStep(0.2)
        self.compose_subtitle_band_pad_bottom.setValue(1.2)
        self.compose_subtitle_band_pad_bottom.setSuffix(" %H")
        self.compose_subtitle_band_pad_bottom.setToolTip(
            "Abstand Subtitel-Text → Band-Unterkante (% der Front-Höhe)."
        )
        # Alias für ältere Tests / Aufrufer (oben = „das“ Padding)
        self.compose_subtitle_band_pad = self.compose_subtitle_band_pad_top
        titles_form.addRow(
            "Subtitel-Band:",
            self._pair(
                self.compose_subtitle_band_enabled,
                sub_band_color_host,
            ),
        )
        titles_form.addRow(
            "Band Abstand oben/unten:",
            self._pair(
                self.compose_subtitle_band_pad_top,
                self.compose_subtitle_band_pad_bottom,
            ),
        )
        titles_form.addRow(
            "Subtitel 1:",
            self._pair(
                self.compose_sub1,
                self._pair(
                    sub1_color_host,
                    self._pair(
                        self.compose_sub1_size,
                        self._pair(
                            self.compose_sub1_font,
                            self._pair(self.compose_sub1_bold, self.compose_sub1_italic),
                        ),
                    ),
                ),
            ),
        )
        titles_form.addRow(
            "Subtitel 2:",
            self._pair(
                self.compose_sub2,
                self._pair(
                    sub2_color_host,
                    self._pair(
                        self.compose_sub2_size,
                        self._pair(
                            self.compose_sub2_font,
                            self._pair(self.compose_sub2_bold, self.compose_sub2_italic),
                        ),
                    ),
                ),
            ),
        )

        titles_form.addRow(
            "Claim:",
            self._pair(self.compose_accent, accent_color_host),
        )
        titles_form.addRow(
            "Claim Pos/Größe:",
            self._pair(
                self.compose_accent_top,
                self._pair(
                    self.compose_accent_size,
                    self._pair(
                        self.compose_accent_font,
                        self._pair(self.compose_accent_bold, self.compose_accent_italic),
                    ),
                ),
            ),
        )

        self.compose_author = QLineEdit()
        self.compose_author.setPlaceholderText("Autor")
        author_color_host, self.compose_author_color = self._color_field("#FFFFFF")
        self.compose_author_size = QDoubleSpinBox()
        self.compose_author_size.setRange(1.0, 12.0)
        self.compose_author_size.setDecimals(1)
        self.compose_author_size.setSingleStep(0.5)
        self.compose_author_size.setValue(3.5)
        self.compose_author_size.setSuffix(" %H")
        self.compose_author_size.setToolTip("Schriftgröße Autor (% der Front-Höhe).")
        self.compose_author_top = QDoubleSpinBox()
        self.compose_author_top.setRange(0.0, 100.0)
        self.compose_author_top.setDecimals(1)
        self.compose_author_top.setSingleStep(1.0)
        self.compose_author_top.setValue(26.0)
        self.compose_author_top.setSuffix(" %Y")
        self.compose_author_top.setToolTip(
            "Startposition Autor von oben (% der Front-Höhe)."
        )
        self.compose_author_bold = QCheckBox("Fett")
        self.compose_author_bold.setToolTip("Autor fett darstellen")
        self.compose_author_italic = QCheckBox("Kursiv")
        self.compose_author_italic.setToolTip("Autor kursiv darstellen")
        self.compose_author_font = self._font_family_combo()
        titles_form.addRow(
            "Autor:",
            self._pair(self.compose_author, author_color_host),
        )
        titles_form.addRow(
            "Autor Pos/Größe:",
            self._pair(
                self.compose_author_top,
                self._pair(
                    self.compose_author_size,
                    self._pair(
                        self.compose_author_font,
                        self._pair(self.compose_author_bold, self.compose_author_italic),
                    ),
                ),
            ),
        )
        root.addWidget(titles_sec)
        self._compose_sec_titles = titles_sec

        footer_sec = CollapsibleSection("Fußzeile", expanded=False)
        footer_form = self._nested_form(footer_sec)
        self.compose_footer_enabled = QCheckBox("Fußzeile")
        self.compose_footer_line1 = QLineEdit()
        self.compose_footer_line1.setPlaceholderText("Fußzeile 1")
        self.compose_footer_line2 = QLineEdit()
        self.compose_footer_line2.setPlaceholderText("Fußzeile 2")
        footer_color_host, self.compose_footer_color = self._color_field("#FFFFFF")
        self.compose_footer_bottom = QDoubleSpinBox()
        self.compose_footer_bottom.setRange(0.0, 100.0)
        self.compose_footer_bottom.setDecimals(1)
        self.compose_footer_bottom.setSingleStep(1.0)
        self.compose_footer_bottom.setValue(4.0)
        self.compose_footer_bottom.setSuffix(" %Y")
        self.compose_footer_bottom.setToolTip(
            "Abstand der Fußzeile vom unteren Rand (% der Front-Höhe)."
        )
        self.compose_footer_align = QComboBox()
        self.compose_footer_align.addItem("Links", "left")
        self.compose_footer_align.addItem("Zentriert", "center")
        self.compose_footer_align.addItem("Rechts", "right")
        self.compose_footer_align.setCurrentIndex(1)
        self.compose_footer_align.setToolTip(
            "Horizontale Ausrichtung der Fußzeile "
            "(Seitenrand ≈ 5 % der Vorderseitenbreite)."
        )
        self.compose_footer_offset_x = QDoubleSpinBox()
        self.compose_footer_offset_x.setRange(-45.0, 45.0)
        self.compose_footer_offset_x.setDecimals(1)
        self.compose_footer_offset_x.setSingleStep(1.0)
        self.compose_footer_offset_x.setValue(0.0)
        self.compose_footer_offset_x.setSuffix(" %X")
        self.compose_footer_offset_x.setToolTip(
            "Horizontaler Versatz nach der Ausrichtung "
            "(negativ = nach links, positiv = nach rechts)."
        )
        self.compose_footer_font = self._font_family_combo()
        footer_form.addRow(self.compose_footer_enabled)
        footer_form.addRow("Fußzeile 1:", self.compose_footer_line1)
        footer_form.addRow("Fußzeile 2:", self.compose_footer_line2)
        footer_form.addRow(
            "Farbe / Position:",
            self._pair(
                footer_color_host,
                self._pair(self.compose_footer_bottom, self.compose_footer_font),
            ),
        )
        footer_form.addRow(
            "Ausrichtung:",
            self._pair(self.compose_footer_align, self.compose_footer_offset_x),
        )
        self.compose_footer_band_enabled = QCheckBox("Band hinterlegen")
        self.compose_footer_band_enabled.setToolTip(
            "Vollbreites Band hinter der Fußzeile "
            "(immer von links nach rechts über die ganze Vorderseite).\n"
            "Das Band zentriert sich an den Glyphen; Abstände oben/unten getrennt."
        )
        footer_band_color_host, self.compose_footer_band_color = self._color_field(
            "#1E3A5F",
            tooltip="Bandfarbe hinter der Fußzeile",
        )
        self.compose_footer_band_pad_top = QDoubleSpinBox()
        self.compose_footer_band_pad_top.setRange(0.0, 12.0)
        self.compose_footer_band_pad_top.setDecimals(1)
        self.compose_footer_band_pad_top.setSingleStep(0.2)
        self.compose_footer_band_pad_top.setValue(1.2)
        self.compose_footer_band_pad_top.setSuffix(" %H")
        self.compose_footer_band_pad_top.setToolTip(
            "Abstand Band-Oberkante → Fußzeilen-Text (% der Front-Höhe)."
        )
        self.compose_footer_band_pad_bottom = QDoubleSpinBox()
        self.compose_footer_band_pad_bottom.setRange(0.0, 12.0)
        self.compose_footer_band_pad_bottom.setDecimals(1)
        self.compose_footer_band_pad_bottom.setSingleStep(0.2)
        self.compose_footer_band_pad_bottom.setValue(1.2)
        self.compose_footer_band_pad_bottom.setSuffix(" %H")
        self.compose_footer_band_pad_bottom.setToolTip(
            "Abstand Fußzeilen-Text → Band-Unterkante (% der Front-Höhe)."
        )
        self.compose_footer_band_pad = self.compose_footer_band_pad_top
        footer_form.addRow(
            "Fußzeilen-Band:",
            self._pair(
                self.compose_footer_band_enabled,
                footer_band_color_host,
            ),
        )
        footer_form.addRow(
            "Band Abstand oben/unten:",
            self._pair(
                self.compose_footer_band_pad_top,
                self.compose_footer_band_pad_bottom,
            ),
        )
        root.addWidget(footer_sec)
        self._compose_sec_footer = footer_sec

        corner_sec = CollapsibleSection("Ecken-Banner", expanded=False)
        corner_form = self._nested_form(corner_sec)
        self.compose_corner_enabled = QCheckBox("Ecken-Banner")
        self.compose_corner_enabled.setToolTip(
            "Dreieckige Ecken-Markierung mit Download-Icon und konfigurierbarem Text."
        )
        self.compose_corner_text = QLineEdit("Inkl. Bonus-Material")
        self.compose_corner_text.setPlaceholderText("z. B. Inkl. Bonus-Material")
        self.compose_corner_text.setToolTip(
            "Wird zweizeilig zentriert gesetzt: „Inkl. Bonus“ / „Material“. "
            "Eigenen Umbruch mit \\n möglich."
        )
        corner_color_host, self.compose_corner_color = self._color_field(
            "#3DBDB0",
            tooltip="Farbe der Ecken-Markierung",
        )
        corner_text_color_host, self.compose_corner_text_color = self._color_field(
            "#FFFFFF",
            tooltip="Farbe von Icon und Schriftzug",
        )
        self.compose_corner_size = QDoubleSpinBox()
        self.compose_corner_size.setRange(8.0, 35.0)
        self.compose_corner_size.setDecimals(1)
        self.compose_corner_size.setValue(13.0)
        self.compose_corner_size.setSuffix(" %")
        self.compose_corner_size.setToolTip(
            "Schenkel-Länge relativ zur kürzeren Cover-Kante (kleiner = dezenter)."
        )
        self.compose_corner_font = QDoubleSpinBox()
        self.compose_corner_font.setRange(50.0, 250.0)
        self.compose_corner_font.setDecimals(0)
        self.compose_corner_font.setSingleStep(10.0)
        self.compose_corner_font.setValue(100.0)
        self.compose_corner_font.setSuffix(" %")
        self.compose_corner_font.setToolTip(
            "Schriftgröße im Banner (nur Größe — Ausrichtung bleibt unverändert). "
            "120- und 300-DPI-Vorschau sollen dieselbe relative Größe zeigen; "
            "hier gezielt nachjustieren."
        )
        self.compose_corner_font_family = self._font_family_combo()
        self.compose_corner_pos = QComboBox()
        self.compose_corner_pos.addItem("Oben rechts", "top_right")
        self.compose_corner_pos.addItem("Unten rechts", "bottom_right")
        self.compose_corner_pos.setToolTip("Platzierung der Ecken-Markierung")
        self.compose_corner_offset_x = QDoubleSpinBox()
        self.compose_corner_offset_x.setRange(0.0, 30.0)
        self.compose_corner_offset_x.setDecimals(1)
        self.compose_corner_offset_x.setSingleStep(0.5)
        self.compose_corner_offset_x.setValue(0.0)
        self.compose_corner_offset_x.setSuffix(" %X")
        self.compose_corner_offset_x.setToolTip(
            "Abstand vom rechten Rand (% der Vorderseitenbreite)."
        )
        self.compose_corner_offset_y = QDoubleSpinBox()
        self.compose_corner_offset_y.setRange(0.0, 30.0)
        self.compose_corner_offset_y.setDecimals(1)
        self.compose_corner_offset_y.setSingleStep(0.5)
        self.compose_corner_offset_y.setValue(0.0)
        self.compose_corner_offset_y.setSuffix(" %Y")
        self.compose_corner_offset_y.setToolTip(
            "Abstand vom oberen Rand (bei „Oben rechts“) bzw. unteren Rand "
            "(bei „Unten rechts“); % der Vorderseitenhöhe."
        )
        self.compose_corner_text_pad = QDoubleSpinBox()
        self.compose_corner_text_pad.setRange(0.0, 40.0)
        self.compose_corner_text_pad.setDecimals(0)
        self.compose_corner_text_pad.setSingleStep(2.0)
        self.compose_corner_text_pad.setValue(10.0)
        self.compose_corner_text_pad.setSuffix(" %")
        self.compose_corner_text_pad.setToolTip(
            "Innenabstand vom Text zum umgebenden Dreieck "
            "(relativ zur Bandhöhe; höher = mehr Luft um den Text)."
        )
        self.compose_corner_icon = QCheckBox("Download-Icon")
        self.compose_corner_icon.setChecked(True)
        self.compose_corner_icon.setToolTip("Weißes Download-Symbol im Banner anzeigen")
        corner_form.addRow(self.compose_corner_enabled)
        corner_form.addRow("Banner-Text:", self.compose_corner_text)
        corner_form.addRow(
            "Banner-Farbe / Textfarbe:",
            self._pair(corner_color_host, corner_text_color_host),
        )
        corner_form.addRow(
            "Banner-Größe / Position:",
            self._pair(self.compose_corner_size, self.compose_corner_pos),
        )
        corner_form.addRow(
            "Offset rechts / oben:",
            self._pair(self.compose_corner_offset_x, self.compose_corner_offset_y),
        )
        corner_form.addRow(
            "Schrift / Text-Padding:",
            self._pair(
                self._pair(self.compose_corner_font_family, self.compose_corner_font),
                self.compose_corner_text_pad,
            ),
        )
        corner_form.addRow("", self.compose_corner_icon)
        root.addWidget(corner_sec)
        self._compose_sec_corner = corner_sec

        badge_sec = CollapsibleSection("Badge / Stempel", expanded=False)
        badge_form = self._nested_form(badge_sec)
        self.compose_badge_enabled = QCheckBox("Badge/Stempel")
        self._add_compose_badge_rows(
            badge_form,
            enabled_cb=self.compose_badge_enabled,
            image_attr="compose_badge_image",
            text_attr="compose_badge_text",
            text_color_attr="compose_badge_text_color",
            bold_attr="compose_badge_bold",
            x_attr="compose_badge_x",
            y_attr="compose_badge_y",
            scale_attr="compose_badge_scale",
            rot_attr="compose_badge_rot",
            asset_key="badge",
            default_x=70.0,
            default_y=75.0,
        )

        self.compose_badge2_enabled = QCheckBox("Badge/Stempel 2")
        self._add_compose_badge_rows(
            badge_form,
            enabled_cb=self.compose_badge2_enabled,
            image_attr="compose_badge2_image",
            text_attr="compose_badge2_text",
            text_color_attr="compose_badge2_text_color",
            bold_attr="compose_badge2_bold",
            x_attr="compose_badge2_x",
            y_attr="compose_badge2_y",
            scale_attr="compose_badge2_scale",
            rot_attr="compose_badge2_rot",
            asset_key="badge2",
            default_x=30.0,
            default_y=75.0,
        )
        root.addWidget(badge_sec)
        self._compose_sec_badge = badge_sec

        return box

    def _add_compose_badge_rows(
        self,
        form: QFormLayout,
        *,
        enabled_cb: QCheckBox,
        image_attr: str,
        text_attr: str,
        text_color_attr: str,
        bold_attr: str,
        x_attr: str,
        y_attr: str,
        scale_attr: str,
        rot_attr: str,
        asset_key: str,
        default_x: float,
        default_y: float,
    ) -> None:
        """Gemeinsame Badge/Stempel-Zeilen (identische Steuerelemente)."""
        image_edit = QLineEdit()
        image_edit.setPlaceholderText("PNG-Overlay…")
        setattr(self, image_attr, image_edit)

        btn_asset = QPushButton("Asset…")
        btn_asset.setToolTip("Badge-Bild aus dem Asset Manager wählen")
        btn_asset.clicked.connect(lambda: self._pick_image_via_asset(asset_key))
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(lambda: self._browse_compose_badge(asset_key))
        img_row = QWidget()
        img_l = QHBoxLayout(img_row)
        img_l.setContentsMargins(0, 0, 0, 0)
        img_l.addWidget(image_edit)
        img_l.addWidget(btn_asset)
        img_l.addWidget(btn_browse)

        text_edit = QLineEdit()
        text_edit.setPlaceholderText("Stempel-Text")
        setattr(self, text_attr, text_edit)
        text_color_host, text_color_edit = self._color_field(
            "#1E3A5F",
            tooltip="Farbe des Badge-/Stempel-Texts",
        )
        setattr(self, text_color_attr, text_color_edit)
        bold_cb = QCheckBox("Fett")
        bold_cb.setToolTip("Badge-Text fett darstellen")
        setattr(self, bold_attr, bold_cb)
        font_combo = self._font_family_combo()
        font_attr = bold_attr.replace("_bold", "_font")
        setattr(self, font_attr, font_combo)

        x_spin = QDoubleSpinBox()
        x_spin.setRange(0.0, 100.0)
        x_spin.setDecimals(2)
        x_spin.setValue(default_x)
        x_spin.setSuffix(" %X")
        setattr(self, x_attr, x_spin)
        y_spin = QDoubleSpinBox()
        y_spin.setRange(0.0, 100.0)
        y_spin.setDecimals(2)
        y_spin.setValue(default_y)
        y_spin.setSuffix(" %Y")
        setattr(self, y_attr, y_spin)
        scale_spin = QDoubleSpinBox()
        scale_spin.setRange(5.0, 80.0)
        scale_spin.setDecimals(2)
        scale_spin.setValue(25.0)
        scale_spin.setSuffix(" %")
        setattr(self, scale_attr, scale_spin)
        rot_spin = QDoubleSpinBox()
        rot_spin.setRange(-90.0, 90.0)
        rot_spin.setDecimals(2)
        rot_spin.setValue(-18.0)
        rot_spin.setSuffix(" °")
        setattr(self, rot_attr, rot_spin)

        form.addRow(enabled_cb)
        form.addRow("Badge-Bild:", img_row)
        form.addRow(
            "Badge-Text:",
            self._pair(
                text_edit,
                self._pair(text_color_host, self._pair(font_combo, bold_cb)),
            ),
        )
        form.addRow("Badge X/Y:", self._pair(x_spin, y_spin))
        form.addRow("Badge Größe/Drehung:", self._pair(scale_spin, rot_spin))

    def _wire_compose_front_signals(self) -> None:
        for w in (
            self.compose_enabled,
            self.compose_fade_enabled,
            self.compose_fade_bottom_enabled,
            self.compose_band_enabled,
            self.compose_titles_enabled,
            self.compose_footer_enabled,
            self.compose_corner_enabled,
            self.compose_corner_icon,
            self.compose_badge_enabled,
            self.compose_badge_bold,
            self.compose_badge2_enabled,
            self.compose_badge2_bold,
            self.compose_accent_italic,
            self.compose_accent_bold,
            self.compose_author_italic,
            self.compose_author_bold,
            self.compose_lines_bold,
            self.compose_subtitle_enabled,
            self.compose_subtitle_band_enabled,
            self.compose_sub1_bold,
            self.compose_sub1_italic,
            self.compose_sub2_bold,
            self.compose_sub2_italic,
            self.compose_footer_band_enabled,
        ):
            w.toggled.connect(self._on_params_changed)
        self.compose_enabled.toggled.connect(
            lambda *_: self._sync_compose_front_tab_visibility()
        )
        for w in (
            self.compose_fade_height,
            self.compose_fade_opacity,
            self.compose_fade_bottom_height,
            self.compose_fade_bottom_opacity,
            self.compose_band_y,
            self.compose_band_h,
            self.compose_band_text_size,
            self.compose_lines_size,
            self.compose_lines_gap,
            self.compose_titles_top,
            self.compose_accent_size,
            self.compose_accent_top,
            self.compose_author_size,
            self.compose_author_top,
            self.compose_subtitle_top,
            self.compose_subtitle_gap,
            self.compose_subtitle_band_pad_top,
            self.compose_subtitle_band_pad_bottom,
            self.compose_sub1_size,
            self.compose_sub2_size,
            self.compose_footer_bottom,
            self.compose_footer_band_pad_top,
            self.compose_footer_band_pad_bottom,
            self.compose_corner_size,
            self.compose_corner_font,
            self.compose_corner_offset_x,
            self.compose_corner_offset_y,
            self.compose_corner_text_pad,
            self.compose_badge_x,
            self.compose_badge_y,
            self.compose_badge_scale,
            self.compose_badge_rot,
            self.compose_badge2_x,
            self.compose_badge2_y,
            self.compose_badge2_scale,
            self.compose_badge2_rot,
        ):
            w.valueChanged.connect(self._on_params_changed)
        self.compose_corner_pos.currentIndexChanged.connect(self._on_params_changed)
        self.compose_titles_align.currentIndexChanged.connect(self._on_params_changed)
        self.compose_titles_offset_x.valueChanged.connect(self._on_params_changed)
        self.compose_sub1_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_sub2_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_lines_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_accent_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_author_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_band_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_footer_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_corner_font_family.currentIndexChanged.connect(
            self._on_params_changed
        )
        self.compose_badge_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_badge2_font.currentIndexChanged.connect(self._on_params_changed)
        self.compose_footer_align.currentIndexChanged.connect(self._on_params_changed)
        self.compose_footer_offset_x.valueChanged.connect(self._on_params_changed)
        for w in (
            self.compose_band_text,
            self.compose_series,
            self.compose_main,
            self.compose_accent,
            self.compose_author,
            self.compose_sub1,
            self.compose_sub2,
            self.compose_footer_line1,
            self.compose_footer_line2,
            self.compose_corner_text,
            self.compose_badge_image,
            self.compose_badge_text,
            self.compose_badge2_image,
            self.compose_badge2_text,
        ):
            w.editingFinished.connect(self._on_params_changed)
