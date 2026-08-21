"""Qt-Dialog: konfigurierbare Cover-Schlagwortwolken (stylecloud)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tools.stylecloud.generator import (
    CUSTOM_SIZE_SENTINEL,
    DEFAULT_HUB_GRADIENT,
    DEFAULT_PRINT_SIZE,
    DEFAULT_PRINT_SIZE_LABEL,
    DEFAULT_WORD_DENSITY,
    FREE_FORM_DENSITY_PRESETS,
    FREE_FORM_PACKING_PRESETS,
    GRADIENT_CHOICES,
    ICON_HUB,
    ICON_NONE,
    ICON_ORGANIC,
    ICON_PRESETS,
    ICON_RECT,
    PALETTE_PRESETS,
    PRINT_DPI,
    SIZE_PRESETS,
    StylecloudDependencyError,
    StylecloudOptions,
    clamp_word_density,
    composite_hub_raw_on_cover,
    density_for_packing_key,
    finalize_png,
    format_file_size,
    free_form_word_budget,
    generate_stylecloud,
    normalize_free_form_density,
    normalize_free_form_packing,
    normalize_hub_gradient,
    normalize_icon_name,
    packing_key_for_density,
    resolve_pack_raw_path,
    suggested_max_font_size,
    suggested_must_word_gap,
    suggested_must_word_max_font,
)
from tools.stylecloud.noun_filter import SpacyNounFilterError
from tools.stylecloud.preset_store import (
    FACTORY_FREEFORM_PRESET_NAME,
    list_presets,
    load_factory_freeform_preset,
    load_preset,
    save_preset,
)
from tools.stylecloud.settings import load_settings, resolve_window_size, save_settings
from tools.stylecloud.text_sources import collect_book_text, default_output_path
from ui_qt.dialogs.stylecloud_preset_manager_dialog import StylecloudPresetManagerDialog
from ui_qt.widgets.help_bar import HelpBar


class _GenerateWorker(QThread):
    """Runs ``generate_stylecloud`` off the UI thread."""

    progress = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str, str)  # kind, message

    def __init__(self, options: StylecloudOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._options = options

    def run(self) -> None:
        try:

            def _cb(percent: int, message: str) -> None:
                self.progress.emit(percent, message)

            path = generate_stylecloud(self._options, progress=_cb)
            self.succeeded.emit(path)
        except StylecloudDependencyError as exc:
            self.failed.emit("dependency", str(exc))
        except SpacyNounFilterError as exc:
            self.failed.emit("spacy", str(exc))
        except ValueError as exc:
            self.failed.emit("value", str(exc))
        except OSError as exc:
            self.failed.emit("os", str(exc))
        except RuntimeError as exc:
            self.failed.emit("runtime", str(exc))
        except Exception as exc:  # pragma: no cover - unexpected library errors
            self.failed.emit("runtime", str(exc))


def _set_combo_by_data(combo: QComboBox, value: object) -> bool:
    """Select combo item whose userData equals *value* (tuple/list tolerant)."""
    normalized = tuple(value) if isinstance(value, list) else value
    for index in range(combo.count()):
        data = combo.itemData(index)
        if data == normalized:
            combo.setCurrentIndex(index)
            return True
        if isinstance(data, tuple) and isinstance(normalized, tuple) and data == normalized:
            combo.setCurrentIndex(index)
            return True
    return False


_VCENTER = Qt.AlignmentFlag.AlignVCenter


def _tune_form(form: QFormLayout, *, margins: tuple[int, int, int, int] = (8, 12, 8, 8)) -> None:
    """Consistent form label/field vertical centering (avoids Windows baseline drift)."""
    form.setSpacing(8)
    form.setHorizontalSpacing(12)
    form.setContentsMargins(*margins)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setLabelAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    form.setFormAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
    )


def _hrow(
    *parts: QWidget | tuple[QWidget, int],
    spacing: int = 8,
    stretch_end: bool = False,
) -> QWidget:
    """Horizontal field host: zero margins, widgets vertically centered."""
    host = QWidget()
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(spacing)
    for part in parts:
        if isinstance(part, tuple):
            widget, stretch = part
            row.addWidget(widget, int(stretch), _VCENTER)
        else:
            row.addWidget(part, 0, _VCENTER)
    if stretch_end:
        row.addStretch(1)
    return host


class StylecloudQtDialog(QDialog):
    def __init__(self, studio: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._studio = studio
        self._preview_pixmap: QPixmap | None = None
        self._worker: _GenerateWorker | None = None
        self._restoring = False
        self._is_generating = False
        self._generation_max_font_size: int | None = None
        self._user_font_size: int | None = None
        self._cover_scale = 1.0
        self._hub_raw_path: Path | None = None
        self._last_output_path: Path | None = None
        self._layout_regen_timer = QTimer(self)
        self._layout_regen_timer.setSingleShot(True)
        self._layout_regen_timer.setInterval(350)
        self._layout_regen_timer.timeout.connect(self._on_layout_slider_committed)
        # Back-compat alias used by older handlers.
        self._orient_regen_timer = self._layout_regen_timer
        self.setWindowTitle("Cover-Schlagwortwolke (stylecloud)")
        self.setMinimumSize(860, 480)
        # Native window edges resize; corner grip is placed in the button row
        # (avoids overlapping „Schließen“).
        self.setSizeGripEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        HelpBar.create_and_prepend_for_plugin(layout, "stylecloud")

        body = QHBoxLayout()
        body.setSpacing(10)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        left_layout.addWidget(self.tabs, 1)

        # ---- Tab: Text ----
        tab_text = QWidget()
        form_text = QFormLayout(tab_text)
        _tune_form(form_text)
        self._form_layout = form_text

        self.source_combo = QComboBox()
        self.source_combo.addItem("Aktuelles Buch (content/*.md)", "book")
        self.source_combo.addItem("Textdatei…", "file")
        self.source_combo.addItem("Freitext", "paste")
        form_text.addRow("Textquelle:", self.source_combo)

        self.source_path = QLineEdit()
        self.source_path.setPlaceholderText("Pfad zur .txt / .md / .csv")
        self.btn_browse_source = QPushButton("Datei…")
        self.btn_browse_source.clicked.connect(self._browse_source)
        self.btn_load = QPushButton("Text laden")
        self.btn_load.clicked.connect(self._load_text)
        form_text.addRow(
            "Quelldatei:",
            _hrow(self.source_path, self.btn_browse_source, self.btn_load),
        )

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Schlagwörter / Fließtext…\n„Text laden“ übernimmt Buch oder Datei."
        )
        self.text_edit.setMinimumHeight(120)
        form_text.addRow("Text:", self.text_edit)

        book = getattr(studio, "current_book", None)
        self.output_path = QLineEdit(
            str(default_output_path(Path(book) if book else None))
        )
        self.btn_browse_out = QPushButton("Speichern unter…")
        self.btn_browse_out.clicked.connect(self._browse_output)
        form_text.addRow("Ausgabe-PNG:", _hrow((self.output_path, 1), self.btn_browse_out))
        self.save_svg = QCheckBox("Auch als SVG speichern")
        self.save_svg.setChecked(False)
        self.save_svg.setToolTip(
            "Schreibt neben der PNG eine .svg-Datei.\n"
            "Freie Form: echte Vektor-Texte.\n"
            "Andere Formen: PNG in SVG eingebettet."
        )
        form_text.addRow("", self.save_svg)
        self.tabs.addTab(tab_text, "Text")

        # ---- Tab: Form & Cover ----
        tab_form = QWidget()
        form_form = QFormLayout(tab_form)
        _tune_form(form_form)

        self.size_combo = QComboBox()
        for label, value in SIZE_PRESETS.items():
            self.size_combo.addItem(label, value)
        self.size_combo.addItem(
            "Benutzerdefiniert (freie Breite × Höhe) …",
            CUSTOM_SIZE_SENTINEL,
        )
        idx = self.size_combo.findText(DEFAULT_PRINT_SIZE_LABEL)
        if idx >= 0:
            self.size_combo.setCurrentIndex(idx)
        self.size_combo.setToolTip(
            "Cover-Auflösung / Seitenverhältnis (Druck).\n"
            f"Druck-Presets: ≥ {PRINT_DPI} dpi inkl. KDP-Bleed "
            "(Vorderseiten-Panel druckfertig)."
        )
        form_form.addRow("Auflösung:", self.size_combo)
        self.size_combo.currentIndexChanged.connect(self._on_size_changed)

        self.custom_width = QSpinBox()
        self.custom_width.setRange(256, 8000)
        self.custom_width.setValue(int(DEFAULT_PRINT_SIZE[0]))
        self.custom_width.setSuffix(" px")
        self.custom_height = QSpinBox()
        self.custom_height.setRange(256, 8000)
        self.custom_height.setValue(int(DEFAULT_PRINT_SIZE[1]))
        self.custom_height.setSuffix(" px")
        self.custom_ratio_label = QLabel("Ratio: –")
        self._custom_size_host = _hrow(
            QLabel("B:"),
            self.custom_width,
            QLabel("H:"),
            self.custom_height,
            self.custom_ratio_label,
            stretch_end=True,
        )
        form_form.addRow("Frei (px):", self._custom_size_host)
        self._form_form = form_form
        form_form.setRowVisible(self._custom_size_host, False)
        self.custom_width.valueChanged.connect(self._on_custom_size_changed)
        self.custom_height.valueChanged.connect(self._on_custom_size_changed)

        self.icon_combo = QComboBox()
        self.icon_combo.setMaxVisibleItems(12)
        self.icon_combo.view().setMinimumWidth(480)
        for label, icon in ICON_PRESETS:
            self.icon_combo.addItem(label, icon)
        self.icon_combo.setToolTip(
            "• Freie Form = organische Hub-Wolke um Kernwort\n"
            "• Cover-dicht = WordCloud auf Cover\n"
            "• Organisch / Rechteck / Font Awesome\n"
            "• Bildmaske (Tab Erweitert) hat Vorrang"
        )
        form_form.addRow("Form:", self.icon_combo)
        self.icon_combo.currentIndexChanged.connect(self._on_form_changed)
        self.icon_combo.setCurrentIndex(0)

        self._cover_pack_box = QGroupBox("Cover-dicht / Organisch")
        cover_pack_form = QFormLayout(self._cover_pack_box)
        _tune_form(cover_pack_form, margins=(8, 8, 8, 8))
        cover_pack_form.setSpacing(6)
        self.free_form_margin = QSpinBox()
        self.free_form_margin.setRange(5, 40)
        self.free_form_margin.setValue(14)
        self.free_form_margin.setSuffix(" %")
        self.free_form_margin.setToolTip("Rand um organische Silhouette.")
        self._cover_rand_label = QLabel("Cover-Rand")
        cover_pack_form.addRow(self._cover_rand_label, self.free_form_margin)

        self.free_form_density = QComboBox()
        for label, key in FREE_FORM_DENSITY_PRESETS:
            self.free_form_density.addItem(label, key)
        self.free_form_density.setToolTip("Wortbudget für Cover-dicht.")
        self.free_form_density.currentIndexChanged.connect(
            self._on_free_form_density_changed
        )
        self.free_form_words_hint = QLabel("")
        self.free_form_words_hint.setStyleSheet("color:#5b6573;")
        dens_host = _hrow((self.free_form_density, 1), self.free_form_words_hint)
        self._dichte_label = QLabel("Wortbudget")
        cover_pack_form.addRow(self._dichte_label, dens_host)

        self.free_form_packing = QComboBox()
        for label, key in FREE_FORM_PACKING_PRESETS:
            self.free_form_packing.addItem(label, key)
        _set_combo_by_data(self.free_form_packing, "tight")
        self.free_form_packing.setToolTip(
            "Schnellwahl für Packdichte (synchron mit Slider „Dichte“ unten)."
        )
        self.free_form_packing.currentIndexChanged.connect(self._on_packing_combo_changed)
        # Kept for session back-compat; orientation lives in the shared slider below.
        self.orient_auto = QCheckBox("Auto (Ratio)")
        self.orient_auto.setChecked(False)
        self.orient_auto.setVisible(False)
        self.orient_pct = QSpinBox()
        self.orient_pct.setRange(0, 100)
        self.orient_pct.setValue(50)
        self.orient_pct.setVisible(False)
        pack_host = _hrow(self.free_form_packing)
        cover_pack_form.addRow("Packung:", pack_host)
        self._pack_host = pack_host
        form_form.addRow(self._cover_pack_box)
        self._free_margin_host = self._cover_pack_box
        self._pack_orient_host = self._cover_pack_box

        self._hub_pack_box = QGroupBox("Orientierung, Dichte & Cover-Einpassen")
        hub_pack_form = QFormLayout(self._hub_pack_box)
        _tune_form(hub_pack_form, margins=(8, 8, 8, 8))
        self.hub_orient_slider = QSlider(Qt.Orientation.Horizontal)
        self.hub_orient_slider.setRange(0, 100)
        self.hub_orient_slider.setValue(50)
        self.hub_orient_slider.setToolTip(
            "Anteil Wörter quer (horizontal) vs. hochkant (vertikal).\n"
            "Gilt für alle Formen (außer Font-Awesome-Icons ohne Steuerung).\n"
            "Nach Loslassen: Wolke wird neu erzeugt (Einpassfaktor bleibt)."
        )
        self.hub_orient_label = QLabel("50 % quer · 50 % hoch")
        self.hub_orient_slider.valueChanged.connect(self._on_hub_orient_changed)
        self.hub_orient_slider.sliderReleased.connect(self._on_layout_slider_committed)
        hub_pack_form.addRow("Orientierung:", self.hub_orient_slider)
        hub_pack_form.addRow("", self.hub_orient_label)

        self.word_density_slider = QSlider(Qt.Orientation.Horizontal)
        self.word_density_slider.setRange(0, 100)
        self.word_density_slider.setValue(int(round(DEFAULT_WORD_DENSITY * 100)))
        self.word_density_slider.setToolTip(
            "Packdichte der Wörter: links locker, rechts eng verschachtelt.\n"
            "Nach Loslassen: Wolke wird neu erzeugt (Einpassfaktor bleibt)."
        )
        self.word_density_label = QLabel("55 % dicht")
        self.word_density_slider.valueChanged.connect(self._on_word_density_changed)
        self.word_density_slider.sliderReleased.connect(self._on_layout_slider_committed)
        hub_pack_form.addRow("Dichte:", self.word_density_slider)
        hub_pack_form.addRow("", self.word_density_label)

        self.btn_scale_down = QPushButton("−")
        self.btn_scale_down.setFixedWidth(40)
        self.btn_scale_down.setToolTip("Wolke verkleinern (mehr Rand, kein Neu-Packen)")
        self.btn_scale_up = QPushButton("+")
        self.btn_scale_up.setFixedWidth(40)
        self.btn_scale_up.setToolTip(
            "Wolke vergrößern (füllt Cover; bei zu groß Abschneiden möglich)"
        )
        self.cover_scale_label = QLabel("100 %")
        self.cover_scale_label.setMinimumWidth(56)
        self.cover_scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_scale_reset = QPushButton("Passend")
        self.btn_scale_reset.setToolTip("Einpassen: Wolke vollständig sichtbar (100 %)")
        self.btn_scale_down.clicked.connect(lambda: self._nudge_cover_scale(1 / 1.12))
        self.btn_scale_up.clicked.connect(lambda: self._nudge_cover_scale(1.12))
        self.btn_scale_reset.clicked.connect(lambda: self._set_cover_scale(1.0))
        fit_host = _hrow(
            self.btn_scale_down,
            self.cover_scale_label,
            self.btn_scale_up,
            self.btn_scale_reset,
            stretch_end=True,
        )
        hub_pack_form.addRow("Cover-Einpassen:", fit_host)
        self._hub_fit_box = self._hub_pack_box
        self._set_hub_fit_enabled(False)
        form_form.addRow(self._hub_pack_box)

        self.tabs.addTab(tab_form, "Form")

        # ---- Tab: Kernwort & Farben ----
        tab_style = QWidget()
        form_style = QFormLayout(tab_style)
        _tune_form(form_style)

        self.must_word = QLineEdit()
        self.must_word.setPlaceholderText("z. B. BARCELONA")
        form_style.addRow("Kernwort:", self.must_word)
        self._must_word_label = form_style.labelForField(self.must_word)
        self._must_lines_host = self.must_word

        self.auto_fit = QCheckBox(
            "Auto-Fit — Schriftgrößen automatisch (Pack-/Cover-Maßstab)"
        )
        self.auto_fit.setChecked(True)
        self.auto_fit.setToolTip(
            "Freie Form: Schrift aus der festen Pack-Fläche (Cover wird beim Packen "
            "ignoriert — Einpassen danach mit − / + unter Orientierung).\n"
            "Andere Formen: Maxima-/Muss-Schrift aus Cover-Auflösung; "
            "danach ebenfalls − / + Cover-Einpassen.\n"
            "Aus: manuelle Kern-/Muss-Schrift und Maxima → Schrift."
        )
        self.auto_fit.toggled.connect(self._on_auto_fit_toggled)
        form_style.addRow(self.auto_fit)

        self.must_word_size = QSpinBox()
        self.must_word_size.setRange(24, 2000)
        self.must_word_size.setValue(
            suggested_must_word_max_font(self.size_combo.currentData() or 1024)
        )
        self.must_word_size.setSuffix(" px")
        form_style.addRow("Kern-Schrift:", self.must_word_size)
        self._must_style_host = self.must_word_size
        self._must_style_label = form_style.labelForField(self.must_word_size)
        self._form_style = form_style

        self._overlay_box = QGroupBox("Muss-Wort Overlay (nicht Hub)")
        overlay_form = QFormLayout(self._overlay_box)
        _tune_form(overlay_form, margins=(8, 8, 8, 8))
        self.must_word_line2 = QLineEdit()
        self.must_word_line2.setPlaceholderText("Zeile 2 (optional)")
        overlay_form.addRow("Zeile 2:", self.must_word_line2)
        self.must_word_gap = QSpinBox()
        self.must_word_gap.setRange(0, 500)
        self.must_word_gap.setValue(
            suggested_must_word_gap(self.size_combo.currentData() or 1024)
        )
        self.must_word_gap.setSuffix(" px")
        self._must_gap_label = QLabel("Abstand")
        overlay_form.addRow(self._must_gap_label, self.must_word_gap)
        color_host, self.must_word_color = self._color_field(
            "#c0392b",
            tooltip="Muss-Wort-Farbe",
            dialog_title="Muss-Wort-Farbe",
        )
        self._must_color_host = color_host
        overlay_form.addRow("Farbe:", color_host)
        self.must_word_angle = QComboBox()
        from tools.stylecloud.must_word import MUST_WORD_ORIENTATIONS

        for label, angle in MUST_WORD_ORIENTATIONS:
            self.must_word_angle.addItem(label, angle)
        overlay_form.addRow("Winkel:", self.must_word_angle)
        self.must_word_match_width = QCheckBox("Zeile 2 auf Breite von Zeile 1")
        self.must_word_match_width.setChecked(True)
        overlay_form.addRow(self.must_word_match_width)
        form_style.addRow(self._overlay_box)
        self._hub_grad_box = QGroupBox("Farbverlauf (Freie Form / Hub)")
        hub_lay = QHBoxLayout(self._hub_grad_box)
        hub_lay.setContentsMargins(8, 8, 8, 8)
        hub_lay.setSpacing(8)
        self._hub_swatch_a = self._make_hub_swatch(DEFAULT_HUB_GRADIENT[0])
        self._hub_swatch_b = self._make_hub_swatch(DEFAULT_HUB_GRADIENT[1])
        self._hub_swatch_c = self._make_hub_swatch(DEFAULT_HUB_GRADIENT[2])
        for sw in (self._hub_swatch_a, self._hub_swatch_b, self._hub_swatch_c):
            hub_lay.addWidget(sw, 0, _VCENTER)
        self._hub_grad_preview = QLabel()
        self._hub_grad_preview.setFixedHeight(28)
        self._hub_grad_preview.setMinimumWidth(140)
        hub_lay.addWidget(self._hub_grad_preview, 1, _VCENTER)
        form_style.addRow(self._hub_grad_box)
        self._hub_grad_host = self._hub_grad_box
        self._update_hub_gradient_preview()

        self._palette_box = QGroupBox("Palette (andere Formen)")
        pal_form = QFormLayout(self._palette_box)
        _tune_form(pal_form, margins=(8, 8, 8, 8))
        self.palette_combo = QComboBox()
        for label, palette in PALETTE_PRESETS:
            self.palette_combo.addItem(label, palette)
        self.max_colors = QSpinBox()
        self.max_colors.setRange(2, 12)
        self.max_colors.setValue(5)
        self._palette_host = _hrow(
            (self.palette_combo, 1), QLabel("Max.:"), self.max_colors
        )
        pal_form.addRow("Palette:", self._palette_host)
        self._swatch_host = QWidget()
        self._swatch_layout = QHBoxLayout(self._swatch_host)
        self._swatch_layout.setContentsMargins(0, 0, 0, 0)
        self._swatch_layout.setSpacing(4)
        self._swatch_layout.addStretch(1)
        pal_form.addRow("Töne:", self._swatch_host)
        self.gradient_combo = QComboBox()
        for label, grad in GRADIENT_CHOICES:
            self.gradient_combo.addItem(label, grad)
        self.gradient_combo.setToolTip(
            "Nur bei Font-Awesome-Form und quadratischer Auflösung "
            "(Einschränkung der stylecloud-Bibliothek)."
        )
        bg_host, self.bg_edit = self._color_field(
            "white",
            max_width=90,
            tooltip="Hintergrundfarbe",
            dialog_title="Hintergrundfarbe",
        )
        pal_form.addRow("FA-Verlauf:", self.gradient_combo)
        pal_form.addRow("Hintergrund:", bg_host)
        self._palette_form = pal_form
        self._dist_host = self.gradient_combo
        form_style.addRow(self._palette_box)
        self.palette_combo.currentIndexChanged.connect(self._refresh_palette_preview)
        self.max_colors.valueChanged.connect(self._refresh_palette_preview)

        self.tabs.addTab(tab_style, "Kernwort & Farbe")

        # ---- Tab: Maxima ----
        tab_opt = QWidget()
        form_opt = QFormLayout(tab_opt)
        _tune_form(form_opt)

        self.max_words = QSpinBox()
        self.max_words.setRange(20, 2000)
        self.max_words.setValue(200)
        self.max_words_label = QLabel("Wörter")
        self.max_font = QSpinBox()
        self.max_font.setRange(40, 2000)
        self.max_font.setValue(
            suggested_max_font_size(self.size_combo.currentData() or 1024)
        )
        self.max_font.setToolTip("Maximale Begleitwort-Schrift (nicht Kernwort).")
        self.max_font.valueChanged.connect(self._preserve_generation_font)
        self.max_font_label = QLabel("Schrift:")
        maxima_host = _hrow(
            self.max_words_label,
            self.max_words,
            self.max_font_label,
            self.max_font,
            stretch_end=True,
        )
        form_opt.addRow("Maxima:", maxima_host)

        self.german_stop = QCheckBox("Deutsche Stoppwörter filtern")
        self.german_stop.setChecked(True)
        self.nouns_only = QCheckBox("Nur Substantive (spaCy)")
        self.nouns_only.setChecked(False)
        self.collocations = QCheckBox("Wortpaare (Bigramme)")
        self.collocations.setChecked(False)
        opts_grid = QGridLayout()
        opts_grid.setContentsMargins(0, 0, 0, 0)
        opts_grid.setHorizontalSpacing(12)
        opts_grid.setVerticalSpacing(6)
        opts_grid.addWidget(self.german_stop, 0, 0, _VCENTER)
        opts_grid.addWidget(self.nouns_only, 0, 1, _VCENTER)
        opts_grid.addWidget(self.collocations, 1, 0, 1, 2, _VCENTER)
        self._opts_host = QWidget()
        self._opts_host.setLayout(opts_grid)
        form_opt.addRow("Filter:", self._opts_host)
        self._opts_label = None

        self.extra_stop = QLineEdit()
        self.extra_stop.setPlaceholderText("zusätzliche Stoppwörter, kommagetrennt")
        form_opt.addRow("Extra-Stoppwörter:", self.extra_stop)

        self.tabs.addTab(tab_opt, "Maxima")

        # ---- Tab: Erweitert ----
        tab_adv = QWidget()
        form_adv = QFormLayout(tab_adv)
        _tune_form(form_adv)

        self.mask_path = QLineEdit()
        self.mask_path.setPlaceholderText("Silhouette-PNG — ersetzt Form-Auswahl")
        self.btn_browse_mask = QPushButton("Maske…")
        self.btn_browse_mask.clicked.connect(self._browse_mask)
        self.btn_clear_mask = QPushButton("Leeren")
        self.btn_clear_mask.clicked.connect(self._clear_mask)
        self.invert_mask = QCheckBox("Invertieren")
        form_adv.addRow(
            "Bildmaske:",
            _hrow(
                (self.mask_path, 1),
                self.btn_browse_mask,
                self.btn_clear_mask,
                self.invert_mask,
            ),
        )
        self.mask_path.textChanged.connect(self._on_mask_path_changed)

        self.png_compress = QSpinBox()
        self.png_compress.setRange(0, 9)
        self.png_compress.setValue(6)
        self.png_optimize = QCheckBox("PNG optimieren")
        self.png_optimize.setChecked(True)
        self.png_dpi = QSpinBox()
        self.png_dpi.setRange(PRINT_DPI, 600)
        self.png_dpi.setValue(PRINT_DPI)
        self.png_dpi.setSuffix(" dpi")
        self.png_dpi.setToolTip(
            f"PNG-Metadaten-DPI — mindestens {PRINT_DPI} (Druckqualität)."
        )
        form_adv.addRow(
            "PNG:",
            _hrow(
                QLabel("Kompression:"),
                self.png_compress,
                self.png_optimize,
                self.png_dpi,
                stretch_end=True,
            ),
        )

        self.tabs.addTab(tab_adv, "Erweitert")

        body.addWidget(left, 3)

        preview_box = QGroupBox("Vorschau")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        self.preview = QLabel("Vorschau erscheint nach dem Erzeugen.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumWidth(280)
        self.preview.setMinimumHeight(160)
        self.preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.preview.setStyleSheet(
            "background:#f4f6f8; border:1px solid #c5cad3; border-radius:6px;"
        )
        self.preview.setScaledContents(False)
        preview_layout.addWidget(self.preview, 1)

        body.addWidget(preview_box, 2)

        layout.addLayout(body, 1)


        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#5b6573;")
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.btn_factory_freeform = QPushButton(FACTORY_FREEFORM_PRESET_NAME)
        self.btn_factory_freeform.setToolTip(
            "Ein Klick: Freie Form (Hub), Cover DE Paperback, Farbverlauf.\n"
            "Danach nur Kernwort setzen, Text laden, Wolke erzeugen."
        )
        self.btn_factory_freeform.clicked.connect(self._load_factory_freeform_preset)
        row.addWidget(self.btn_factory_freeform)
        row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setFixedWidth(280)
        self.preset_combo.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.preset_combo.setToolTip(
            "Gespeicherte Einstellungs-Presets (Auflösung, Form, Farben, …)."
        )
        row.addWidget(self.preset_combo)
        self.btn_preset_load = QPushButton("📥 Laden")
        self.btn_preset_load.setToolTip("Ausgewähltes Preset laden")
        self.btn_preset_load.clicked.connect(self._load_selected_preset)
        row.addWidget(self.btn_preset_load)
        self.btn_preset_save = QPushButton("💾 Speichern…")
        self.btn_preset_save.setToolTip("Aktuelle Einstellungen als Preset speichern")
        self.btn_preset_save.clicked.connect(self._save_preset_as)
        row.addWidget(self.btn_preset_save)
        self.btn_preset_manage = QPushButton("⚙️ Verwalten…")
        self.btn_preset_manage.setToolTip("Presets verwalten (laden, umbenennen, löschen)")
        self.btn_preset_manage.clicked.connect(self._open_preset_manager)
        row.addWidget(self.btn_preset_manage)

        row.addStretch(1)

        self.btn_generate = QPushButton("Wolke erzeugen")
        self.btn_generate.setDefault(True)
        self.btn_generate.clicked.connect(self._generate)
        row.addWidget(self.btn_generate)
        self.btn_reset = QPushButton("Neu würfeln")
        self.btn_reset.setToolTip(
            "Gleiche Einstellungen, neues Zufalls-Layout (nur neu erzeugen)."
        )
        self.btn_reset.clicked.connect(self._reshuffle_generate)
        row.addWidget(self.btn_reset)
        self.btn_open = QPushButton("Ordner öffnen")
        self.btn_open.clicked.connect(self._open_folder)
        row.addWidget(self.btn_open)
        self.btn_handoff_kdp = QPushButton("An KDP Cover übergeben")
        self.btn_handoff_kdp.setToolTip(
            "Öffnet den KDP Cover-Designer und setzt die Ausgabe-PNG als Vorderseite "
            "(Hintergrund). Cover-Layer (Titel, Bänder, Badges) bleiben aktiv und "
            "zeichnen darüber."
        )
        self.btn_handoff_kdp.clicked.connect(self._handoff_to_kdp_cover)
        row.addWidget(self.btn_handoff_kdp)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        self.btn_close = close
        row.addWidget(close)
        # Standard corner size-grip (dotted) — own cell, not over the button.
        grip = QSizeGrip(self)
        grip.setFixedSize(16, 16)
        row.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        layout.addLayout(row)

        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self._refresh_preset_combo()
        self._restore_settings()
        self._on_source_changed()
        self._on_mask_path_changed()
        self._update_mode_ui()
        self._refresh_palette_preview()
        self.max_font.valueChanged.connect(self._persist_font_size_immediately)
        self.output_path.textChanged.connect(lambda *_a: self._update_handoff_button())
        self._update_handoff_button()

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

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Bitte warten",
                "Die Schlagwortwolke wird noch erzeugt.",
            )
            event.ignore()
            return
        self._persist_settings()
        super().closeEvent(event)

    def accept(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Bitte warten",
                "Die Schlagwortwolke wird noch erzeugt.",
            )
            return
        self._persist_settings()
        super().accept()

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Bitte warten",
                "Die Schlagwortwolke wird noch erzeugt.",
            )
            return
        self._persist_settings()
        super().reject()

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

    def _on_hub_orient_changed(self, value: int) -> None:
        quer = int(value)
        hoch = 100 - quer
        self.hub_orient_label.setText(f"{quer} % quer · {hoch} % hoch")
        if self._restoring or self._is_generating:
            return
        if self.hub_orient_slider.isSliderDown():
            return
        self._layout_regen_timer.start()

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

    def _on_hub_orient_committed(self) -> None:
        """Back-compat alias."""
        self._on_layout_slider_committed()

    def _set_cover_scale(self, value: float) -> None:
        # Never let a pending Orient/Dichte-Regen steal the ± click.
        self._layout_regen_timer.stop()
        self._cover_scale = max(0.15, min(8.0, float(value)))
        self.cover_scale_label.setText(f"{int(round(self._cover_scale * 100))} %")
        if not self._restoring:
            self._recomposite_hub_to_cover()

    def _nudge_cover_scale(self, factor: float) -> None:
        self._set_cover_scale(self._cover_scale * float(factor))

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

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._refresh_preview_pixmap()

    def _refresh_preview_pixmap(self) -> None:
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        self.preview.setPixmap(
            self._preview_pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _log(self, msg: str, level: str = "info") -> None:
        log = getattr(self._studio, "log", None)
        if callable(log):
            log(msg, level)

    def _on_source_changed(self) -> None:
        mode = self.source_combo.currentData()
        file_mode = mode == "file"
        self.source_path.setEnabled(file_mode)
        self.btn_browse_source.setEnabled(file_mode)

    def _browse_source(self) -> None:
        start = self.source_path.text().strip() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Textdatei für Schlagwortwolke",
            start,
            "Text (*.txt *.md *.qmd *.csv);;Alle Dateien (*.*)",
        )
        if path:
            self.source_path.setText(path)
            self.source_combo.setCurrentIndex(self.source_combo.findData("file"))
            self._load_text()

    def _browse_output(self) -> None:
        start = self.output_path.text().strip() or str(Path.home() / "cover_stylecloud.png")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Cover-Wolke speichern",
            start,
            "PNG (*.png)",
        )
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            self.output_path.setText(path)

    def _read_source_text(self) -> str:
        """Load text from the selected source (book / file / editor).

        Raises ``ValueError`` with a German message when nothing usable is found.
        """
        mode = self.source_combo.currentData()
        if mode == "book":
            book = getattr(self._studio, "current_book", None)
            if not book:
                raise ValueError("Bitte zuerst ein Buchprojekt öffnen.")
            text = collect_book_text(Path(book))
            if not text.strip():
                raise ValueError(
                    "Im Buchordner wurden keine nutzbaren Markdown-Texte gefunden."
                )
            return text
        if mode == "file":
            raw = self.source_path.text().strip()
            if not raw:
                raise ValueError("Bitte eine Quelldatei wählen.")
            path = Path(raw).expanduser().resolve()
            if not path.is_file():
                raise ValueError(f"Datei nicht gefunden:\n{path}")
            if path.suffix.lower() in {".md", ".qmd"}:
                from tools.stylecloud.text_sources import extract_markdown_body

                text = extract_markdown_body(path)
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                raise ValueError(f"Die Datei ist leer:\n{path}")
            return text
        # Freitext
        text = self.text_edit.toPlainText()
        if not text.strip():
            raise ValueError(
                "Kein Text für die Schlagwortwolke.\n"
                "Bitte Freitext eingeben oder Textquelle auf Buch/Datei stellen."
            )
        return text

    def _load_text(self) -> None:
        mode = self.source_combo.currentData()
        try:
            if mode == "paste":
                self.status.setText("Freitext-Modus — Text im Editor bearbeiten.")
                return
            text = self._read_source_text()
            self.text_edit.setPlainText(text)
            if mode == "book":
                book = getattr(self._studio, "current_book", None)
                name = Path(book).name if book else "?"
                self.status.setText(
                    f"Buchtext geladen ({len(text)} Zeichen) aus {name}."
                )
                self._log(f"[stylecloud] Buchtext geladen: {name}")
            else:
                path = Path(self.source_path.text().strip()).expanduser()
                self.status.setText(
                    f"Datei geladen: {path.name} ({len(text)} Zeichen)."
                )
                self._log(f"[stylecloud] Datei geladen: {path}")
        except ValueError as exc:
            QMessageBox.warning(self, "Text laden", str(exc))
        except OSError as exc:
            QMessageBox.critical(self, "Lesen fehlgeschlagen", str(exc))

    def _build_options(self) -> StylecloudOptions:
        size = self._resolved_size()
        out = self.output_path.text().strip()
        if not out:
            raise ValueError("Bitte einen Ausgabe-Pfad angeben.")
        text = self.text_edit.toPlainText().strip()
        if not text:
            # Auto-load from book/file so "Wolke erzeugen" works without
            # an extra "Text laden" click after choosing a source file.
            mode = self.source_combo.currentData()
            if mode in ("book", "file"):
                text = self._read_source_text().strip()
                self.text_edit.setPlainText(text)
            elif mode == "paste":
                # Recover: Freitext leer, aber Quelldatei-Pfad noch gesetzt.
                raw = self.source_path.text().strip()
                if raw:
                    path = Path(raw).expanduser().resolve()
                    if path.is_file():
                        if path.suffix.lower() in {".md", ".qmd"}:
                            from tools.stylecloud.text_sources import extract_markdown_body

                            text = extract_markdown_body(path).strip()
                        else:
                            text = path.read_text(
                                encoding="utf-8", errors="replace"
                            ).strip()
                        if text:
                            self.text_edit.setPlainText(text)
                            self.source_combo.blockSignals(True)
                            _set_combo_by_data(self.source_combo, "file")
                            self.source_combo.blockSignals(False)
                            self.status.setText(
                                f"Leerer Freitext — Quelldatei geladen: {path.name}"
                            )
        if not text:
            has_must = bool(
                self.must_word.text().strip() or self.must_word_line2.text().strip()
            )
            is_hub = (
                self._resolved_icon_name() == ICON_HUB
                and not self.mask_path.text().strip()
            )
            if is_hub or not has_must:
                raise ValueError(
                    "Kein Text für die Schlagwortwolke.\n"
                    "Bitte Text laden (Buch/Datei) oder einfügen.\n"
                    + (
                        "Freie Form braucht Begleitwörter zusätzlich zum Kernwort."
                        if is_hub
                        else "Tipp: Mit Muss-Wort allein (ohne Freie Form) geht’s auch."
                    )
                )
            # Non-hub + Muss-Wort: blank canvas + overlay (generator path).
        icon_name = self._resolved_icon_name()
        return StylecloudOptions(
            text=text,
            output_path=Path(out),
            size=size if size is not None else 1024,
            icon_name=icon_name,
            mask_path=(
                Path(self.mask_path.text().strip())
                if self.mask_path.text().strip()
                else None
            ),
            free_form_margin_pct=float(self.free_form_margin.value()),
            free_form_density=self._resolved_free_form_density(),
            free_form_packing=self._resolved_free_form_packing(),
            word_density=self._resolved_word_density(),
            free_form_prefer_horizontal=self._resolved_prefer_horizontal(),
            palette=str(
                self.palette_combo.currentData() or "cartocolors.qualitative.Bold_5"
            ),
            background_color=self.bg_edit.text().strip() or "white",
            max_colors=int(self.max_colors.value()),
            gradient=(
                self.gradient_combo.currentData()
                if self._uses_font_awesome() and self._canvas_is_square()
                else None
            ),
            hub_gradient=self._hub_gradient_stops(),
            max_font_size=int(self.max_font.value()),
            max_words=int(self.max_words.value()),
            use_german_stopwords=self.german_stop.isChecked(),
            extra_stopwords=self.extra_stop.text(),
            nouns_only=self.nouns_only.isChecked(),
            collocations=self.collocations.isChecked(),
            invert_mask=self.invert_mask.isChecked(),
            random_state=int(getattr(self, "_layout_seed", 42)),
            must_word=self.must_word.text().strip(),
            must_word_line2=self.must_word_line2.text().strip(),
            must_word_font_size=int(self.must_word_size.value()),
            must_word_color=self.must_word_color.text().strip() or "#c0392b",
            must_word_angle=int(self.must_word_angle.currentData() or 0),
            must_word_gap=int(self.must_word_gap.value()),
            must_word_match_line1_width=self.must_word_match_width.isChecked(),
            auto_fit=bool(self.auto_fit.isChecked()),
            cover_scale=float(self._cover_scale),
            save_svg=bool(self.save_svg.isChecked()),
            png_compress_level=int(self.png_compress.value()),
            png_optimize=self.png_optimize.isChecked(),
            png_dpi=int(self.png_dpi.value()),
        )

    def _generate(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not hasattr(self, "_layout_seed"):
            self._layout_seed = 42
        self._generation_max_font_size = int(self.max_font.value())
        self._is_generating = True
        try:
            options = self._build_options()
        except ValueError as exc:
            self._is_generating = False
            self._generation_max_font_size = None
            QMessageBox.warning(self, "Eingabe", str(exc))
            return

        self._set_busy(True)
        self.progress.setValue(0)
        self.progress.setFormat("Start…")
        self.status.setText("Erzeuge Schlagwortwolke…")

        worker = _GenerateWorker(options, self)
        self._worker = worker
        worker.progress.connect(self._on_generate_progress)
        worker.succeeded.connect(self._on_generate_succeeded)
        worker.failed.connect(self._on_generate_failed)
        worker.finished.connect(self._on_generate_finished)
        worker.start()

    def _preserve_generation_font(self, value: int) -> None:
        """Reject stale UI updates while a generation is using this font size."""
        expected = self._generation_max_font_size
        if not self._is_generating or expected is None or int(value) == expected:
            return
        self.max_font.blockSignals(True)
        self.max_font.setValue(expected)
        self.max_font.blockSignals(False)

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.btn_generate.setEnabled(not busy)
        self.btn_reset.setEnabled(not busy)
        self.btn_open.setEnabled(not busy)
        self.btn_handoff_kdp.setEnabled(False if busy else bool(self._resolve_handoff_png()))
        self.btn_close.setEnabled(not busy)
        self.btn_preset_load.setEnabled(not busy and self.preset_combo.count() > 1)
        self.btn_preset_save.setEnabled(not busy)
        self.btn_preset_manage.setEnabled(not busy)
        self.btn_factory_freeform.setEnabled(not busy)
        self.preset_combo.setEnabled(not busy)
        self.max_font.setEnabled(not busy)
        self.hub_orient_slider.setEnabled(not busy)
        self.word_density_slider.setEnabled(not busy)
        # ± usable when a packed raw sidecar exists and we are idle.
        if busy:
            self._set_hub_fit_enabled(False)
            self.free_form_packing.setEnabled(False)
        else:
            is_cover = (
                not self.mask_path.text().strip()
                and self._resolved_icon_name() == ICON_NONE
            )
            self.free_form_packing.setEnabled(bool(is_cover))
            self._set_hub_fit_enabled(bool(self._hub_raw_path))
            # Restore Auto-Fit lock on Schrift (busy path enables max_font).
            self._on_auto_fit_toggled(self.auto_fit.isChecked())

    def _reshuffle_generate(self) -> None:
        """Same settings, new random layout — does not wipe the form or Schrift."""
        if self._worker is not None and self._worker.isRunning():
            return
        import random

        self._layout_seed = random.randint(1, 2_147_483_647)
        self._generate()

    def _on_generate_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(int(percent))
        self.progress.setFormat(f"{int(percent)}% — {message}")
        self.status.setText(message)

    def _on_generate_succeeded(self, path: object) -> None:
        out = Path(str(path))
        meta = ""
        try:
            from PIL import Image

            with Image.open(out) as img:
                w, h = img.size
                dpi = img.info.get("dpi") or (self.png_dpi.value(), self.png_dpi.value())
                dpi_x = int(round(float(dpi[0]))) if dpi else int(self.png_dpi.value())
            meta = f" · {w}×{h} px · {dpi_x} dpi · {format_file_size(out.stat().st_size)}"
        except OSError:
            try:
                meta = f" · {format_file_size(out.stat().st_size)}"
            except OSError:
                meta = ""
        self.status.setText(f"Gespeichert: {out}{meta}")
        self._log(f"[stylecloud] Cover-Wolke erzeugt: {out}{meta}", "success")
        svg = out.with_suffix(".svg")
        if self.save_svg.isChecked() and svg.is_file():
            self.status.setText(f"Gespeichert: {out}{meta} · SVG: {svg.name}")
            self._log(f"[stylecloud] SVG: {svg}", "success")
        # Persist exactly the Schrift the user has set — never invent a value.
        self._user_font_size = int(self.max_font.value())
        self._last_output_path = out
        raw = resolve_pack_raw_path(out, prefer_hub=self._prefer_hub_raw())
        self._hub_raw_path = raw
        self._set_hub_fit_enabled(bool(self._hub_raw_path))
        self.btn_handoff_kdp.setEnabled(True)
        self._persist_settings()
        pix = QPixmap(str(out))
        if not pix.isNull():
            self._preview_pixmap = pix
            self._refresh_preview_pixmap()
        else:
            self._preview_pixmap = None
            self.preview.setText(f"Datei erzeugt:\n{out}")

    def _on_generate_failed(self, kind: str, message: str) -> None:
        titles = {
            "dependency": "stylecloud fehlt",
            "spacy": "spaCy fehlt",
            "value": "Eingabe",
            "os": "Erzeugung fehlgeschlagen",
            "runtime": "Erzeugung fehlgeschlagen",
        }
        title = titles.get(kind, "Fehler")
        if kind == "value":
            QMessageBox.warning(self, title, message)
        else:
            QMessageBox.critical(self, title, message)
            self._log(f"[stylecloud] Fehler: {message}", "error")
        self.status.setText(message)

    def _on_generate_finished(self) -> None:
        self._is_generating = False
        self._generation_max_font_size = None
        self._set_busy(False)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self._worker = None

    def _open_folder(self) -> None:
        raw = self.output_path.text().strip()
        if not raw:
            return
        folder = Path(raw).expanduser().resolve().parent
        if not folder.is_dir():
            QMessageBox.information(self, "Ordner", f"Ordner existiert noch nicht:\n{folder}")
            return
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _resolve_handoff_png(self) -> Path | None:
        return resolve_stylecloud_handoff_png(
            last_output=self._last_output_path,
            output_field=self.output_path.text().strip(),
        )

    def _update_handoff_button(self) -> None:
        if self._is_generating:
            self.btn_handoff_kdp.setEnabled(False)
            return
        self.btn_handoff_kdp.setEnabled(bool(self._resolve_handoff_png()))

    def _handoff_to_kdp_cover(self) -> None:
        png = self._resolve_handoff_png()
        if png is None:
            QMessageBox.warning(
                self,
                "KDP Cover",
                "Keine Ausgabe-PNG gefunden.\n"
                "Bitte zuerst eine Schlagwortwolke erzeugen.",
            )
            return
        from ui_qt.dialogs.kdp_cover_dialog import open_kdp_cover_qt

        self.status.setText(f"Übergabe an KDP Cover: {png.name}")
        self._log(f"[stylecloud] An KDP Cover übergeben: {png}", "success")
        # Parent = Studio-Hauptfenster (nicht Stylecloud), vermeidet Nested-Modal-Probleme.
        parent = getattr(self._studio, "root", None) or self.window() or self
        open_kdp_cover_qt(
            self._studio,
            parent=parent,
            front_image=png,
            disable_compose=False,
        )


def resolve_stylecloud_handoff_png(
    *,
    last_output: Path | str | None,
    output_field: str | None,
) -> Path | None:
    """Resolve PNG for KDP handoff: last generated file, else output path field."""
    candidates: list[Path] = []
    if last_output is not None and str(last_output).strip():
        candidates.append(Path(str(last_output)).expanduser())
    if output_field and str(output_field).strip():
        candidates.append(Path(str(output_field).strip()).expanduser())
    seen: set[str] = set()
    for raw in candidates:
        try:
            path = raw.resolve()
        except OSError:
            continue
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file() and path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}:
            return path
    return None


def open_stylecloud_qt(
    studio: Any,
    parent: Optional[QWidget] = None,
    *,
    force_hub: bool = False,
) -> None:
    dialog = StylecloudQtDialog(studio, parent)
    if force_hub:
        if not _set_combo_by_data(dialog.icon_combo, ICON_HUB):
            dialog.icon_combo.setCurrentIndex(0)
        dialog._update_mode_ui()
        dialog.status.setText(
            "Freie Form (Hub) — Kernwort setzen, Text laden, Wolke erzeugen."
        )
    dialog.exec()
