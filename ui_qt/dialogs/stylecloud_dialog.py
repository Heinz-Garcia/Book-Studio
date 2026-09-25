"""Qt-Dialog: konfigurierbare Cover-Schlagwortwolken (stylecloud)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
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
    ICON_PRESETS,
    PALETTE_PRESETS,
    PRINT_DPI,
    SIZE_PRESETS,
    suggested_max_font_size,
    suggested_must_word_gap,
    suggested_must_word_max_font,
)
from tools.stylecloud.preset_store import (
    FACTORY_FREEFORM_PRESET_NAME,
)
from tools.stylecloud.text_sources import default_output_path
from ui_qt.autonomous_window import (
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)
from ui_qt.widgets.help_bar import HelpBar
from ui_qt.dialogs.stylecloud.common import (  # noqa: F401
    _GenerateWorker,
    _VCENTER,
    _set_combo_by_data,
    resolve_stylecloud_handoff_png,
)
from ui_qt.dialogs.stylecloud.hub import HubMixin
from ui_qt.dialogs.stylecloud.form import FormMixin
from ui_qt.dialogs.stylecloud.settings import SettingsMixin
from ui_qt.dialogs.stylecloud.generate import GenerateMixin

_active: list["StylecloudQtDialog"] = []


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


class StylecloudQtDialog(
    HubMixin, FormMixin, SettingsMixin, GenerateMixin,
    QDialog,
):
    def __init__(self, studio: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(None)
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
        self.nouns_only.setToolTip(
            "Nur Substantive/Eigennamen (spaCy POS) — gilt für alle Formen "
            "inkl. Freie Form.\n"
            "Deutsch: de_core_news_sm · Englisch: en_core_web_sm "
            "(Sprache wird automatisch erkannt)."
        )
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
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(row, tool_key="stylecloud", host=self)
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
        prepare_autonomous_window(self, parent)

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

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._refresh_preview_pixmap()

def open_stylecloud_qt(
    studio: Any,
    parent: Optional[QWidget] = None,
    *,
    force_hub: bool = False,
) -> None:
    existing = raise_if_open(_active, lambda _d: True)
    if existing is not None:
        return
    dialog = StylecloudQtDialog(studio, parent)
    if force_hub:
        if not _set_combo_by_data(dialog.icon_combo, ICON_HUB):
            dialog.icon_combo.setCurrentIndex(0)
        dialog._update_mode_ui()
        dialog.status.setText(
            "Freie Form (Hub) — Kernwort setzen, Text laden, Wolke erzeugen."
        )
    show_autonomous_window(dialog, _active)
