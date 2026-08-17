"""Qt-Dialog: konfigurierbare Cover-Schlagwortwolken (stylecloud)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QThread, Signal
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
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tools.stylecloud.generator import (
    DEFAULT_PRINT_SIZE_LABEL,
    GRADIENT_CHOICES,
    ICON_PRESETS,
    PALETTE_PRESETS,
    PRINT_DPI,
    SIZE_PRESETS,
    StylecloudDependencyError,
    StylecloudOptions,
    format_file_size,
    generate_stylecloud,
    suggested_max_font_size,
    suggested_must_word_gap,
    suggested_must_word_max_font,
)
from tools.stylecloud.noun_filter import SpacyNounFilterError
from tools.stylecloud.settings import load_settings, resolve_window_size, save_settings
from tools.stylecloud.text_sources import collect_book_text, default_output_path
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


class StylecloudQtDialog(QDialog):
    def __init__(self, studio: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._studio = studio
        self._preview_pixmap: QPixmap | None = None
        self._worker: _GenerateWorker | None = None
        self._restoring = False
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
        left_layout.setSpacing(0)
        form = QFormLayout()
        form.setSpacing(4)
        form.setHorizontalSpacing(10)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.source_combo = QComboBox()
        self.source_combo.addItem("Aktuelles Buch (content/*.md)", "book")
        self.source_combo.addItem("Textdatei…", "file")
        self.source_combo.addItem("Freitext", "paste")
        form.addRow("Textquelle:", self.source_combo)

        src_row = QHBoxLayout()
        src_row.setContentsMargins(0, 0, 0, 0)
        src_row.setSpacing(8)
        self.source_path = QLineEdit()
        self.source_path.setPlaceholderText("Pfad zur .txt / .md / .csv")
        self.btn_browse_source = QPushButton("Datei…")
        self.btn_browse_source.clicked.connect(self._browse_source)
        self.btn_load = QPushButton("Text laden")
        self.btn_load.clicked.connect(self._load_text)
        src_row.addWidget(self.source_path, 1)
        src_row.addWidget(self.btn_browse_source)
        src_row.addWidget(self.btn_load)
        form.addRow("Quelldatei:", src_row)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Schlagwörter / Fließtext für die Wolke…\n"
            "„Text laden“ übernimmt Buchinhalt oder Datei."
        )
        self.text_edit.setMinimumHeight(48)
        self.text_edit.setMaximumHeight(80)
        form.addRow("Text:", self.text_edit)

        out_row = QHBoxLayout()
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.setSpacing(8)
        book = getattr(studio, "current_book", None)
        self.output_path = QLineEdit(
            str(default_output_path(Path(book) if book else None))
        )
        self.btn_browse_out = QPushButton("Speichern unter…")
        self.btn_browse_out.clicked.connect(self._browse_output)
        out_row.addWidget(self.output_path, 1)
        out_row.addWidget(self.btn_browse_out)
        form.addRow("Ausgabe-PNG:", out_row)

        self.size_combo = QComboBox()
        for label, value in SIZE_PRESETS.items():
            self.size_combo.addItem(label, value)
        idx = self.size_combo.findText(DEFAULT_PRINT_SIZE_LABEL)
        if idx >= 0:
            self.size_combo.setCurrentIndex(idx)
        self.size_combo.setToolTip(
            "Ausgabe-Auflösung für Buchdruck.\n"
            f"Presets mit „300 dpi“ sind drucktauglich (ca. {PRINT_DPI} dpi Trim).\n"
            "„Entwurf“ nur zur schnellen Vorschau — nicht für den Druck verwenden."
        )
        form.addRow("Auflösung (Druck):", self.size_combo)
        self.size_combo.currentIndexChanged.connect(self._on_size_changed)

        self.icon_combo = QComboBox()
        for label, icon in ICON_PRESETS:
            self.icon_combo.addItem(label, icon)
        form.addRow("Form (Font Awesome):", self.icon_combo)

        mask_row = QHBoxLayout()
        mask_row.setContentsMargins(0, 0, 0, 0)
        mask_row.setSpacing(8)
        self.mask_path = QLineEdit()
        self.mask_path.setPlaceholderText(
            "Optional: Silhouette-PNG (z. B. Sagrada Família) — ersetzt FA-Form"
        )
        self.btn_browse_mask = QPushButton("Maske…")
        self.btn_browse_mask.clicked.connect(self._browse_mask)
        self.btn_clear_mask = QPushButton("Leeren")
        self.btn_clear_mask.clicked.connect(self._clear_mask)
        self.invert_mask = QCheckBox("Maske invertieren")
        self.invert_mask.setChecked(False)
        mask_row.addWidget(self.mask_path, 1)
        mask_row.addWidget(self.btn_browse_mask)
        mask_row.addWidget(self.btn_clear_mask)
        mask_row.addWidget(self.invert_mask)
        form.addRow("Form aus Bild:", mask_row)
        self.mask_path.textChanged.connect(self._on_mask_path_changed)

        self.palette_combo = QComboBox()
        self.palette_combo.setToolTip("Farbpalette der Wörter in der Wolke.")
        self.palette_combo.setMinimumWidth(220)
        self.palette_combo.setMaxVisibleItems(12)
        self.palette_combo.view().setMinimumWidth(280)
        for label, palette in PALETTE_PRESETS:
            self.palette_combo.addItem(label, palette)
        self.max_colors = QSpinBox()
        self.max_colors.setRange(2, 12)
        self.max_colors.setValue(5)
        self.max_colors.setToolTip(
            "Höchstens so viele Wortfarben aus der gewählten Palette "
            "(gleichmäßige ColorBrewer-Stichprobe).\n"
            "Unter 12 Tönen erscheint die Vorschau darunter."
        )
        palette_row = QHBoxLayout()
        palette_row.setContentsMargins(0, 0, 0, 0)
        palette_row.setSpacing(8)
        palette_row.addWidget(self.palette_combo, 1)
        palette_row.addWidget(QLabel("Max.:"))
        palette_row.addWidget(self.max_colors)
        form.addRow("Palette:", palette_row)

        self._swatch_host = QWidget()
        self._swatch_layout = QHBoxLayout(self._swatch_host)
        self._swatch_layout.setContentsMargins(0, 2, 0, 2)
        self._swatch_layout.setSpacing(4)
        self._swatch_layout.addStretch(1)
        form.addRow("Töne:", self._swatch_host)

        self.gradient_combo = QComboBox()
        self.gradient_combo.setMinimumWidth(160)
        self.gradient_combo.setToolTip(
            "Zufallsfarben: Wörter zufällig aus den Tönen.\n"
            "Verlauf: nur bei quadratischer FA-Form (nicht bei Bildmaske/Hochformat)."
        )
        for label, grad in GRADIENT_CHOICES:
            self.gradient_combo.addItem(label, grad)
        bg_host, self.bg_edit = self._color_field(
            "white",
            max_width=90,
            tooltip="Hintergrundfarbe der Wolke (Hex oder Picker).",
            dialog_title="Hintergrundfarbe",
        )
        dist_row = QHBoxLayout()
        dist_row.setContentsMargins(0, 0, 0, 0)
        dist_row.setSpacing(8)
        dist_row.addWidget(self.gradient_combo, 1)
        dist_row.addWidget(QLabel("BK:"))
        dist_row.addWidget(bg_host)
        form.addRow("Verteilung:", dist_row)

        self.palette_combo.currentIndexChanged.connect(self._refresh_palette_preview)
        self.max_colors.valueChanged.connect(self._refresh_palette_preview)

        self.max_words = QSpinBox()
        self.max_words.setRange(20, 2000)
        self.max_words.setValue(400)
        self.max_font = QSpinBox()
        self.max_font.setRange(40, 2000)
        self.max_font.setValue(suggested_max_font_size(self.size_combo.currentData() or 1024))
        self.max_font.setToolTip(
            "Maximale Wortgröße in Pixeln. Wird beim Wechsel der Auflösung "
            "automatisch auf Druckmaß angepasst."
        )
        words_font_row = QHBoxLayout()
        words_font_row.setContentsMargins(0, 0, 0, 0)
        words_font_row.setSpacing(8)
        words_font_row.addWidget(QLabel("Wörter:"))
        words_font_row.addWidget(self.max_words)
        words_font_row.addWidget(QLabel("Schrift:"))
        words_font_row.addWidget(self.max_font)
        words_font_row.addStretch(1)
        form.addRow("Maxima:", words_font_row)

        png_row = QHBoxLayout()
        png_row.setContentsMargins(0, 0, 0, 0)
        png_row.setSpacing(8)
        self.png_compress = QSpinBox()
        self.png_compress.setRange(0, 9)
        self.png_compress.setValue(6)
        self.png_compress.setToolTip(
            "PNG-Kompression ist verlustfrei (0 = schnell/groß, 9 = klein/langsamer).\n"
            "Die Druckqualität hängt von der Auflösung ab, nicht von diesem Wert."
        )
        png_row.addWidget(self.png_compress)
        self.png_optimize = QCheckBox("PNG optimieren")
        self.png_optimize.setChecked(True)
        self.png_optimize.setToolTip(
            "Verlustfreie PNG-Optimierung (etwas langsamer, meist kleinere Datei)."
        )
        png_row.addWidget(self.png_optimize)
        self.png_dpi = QSpinBox()
        self.png_dpi.setRange(72, 600)
        self.png_dpi.setValue(PRINT_DPI)
        self.png_dpi.setSuffix(" dpi")
        self.png_dpi.setToolTip(
            "DPI-Metadaten in der PNG (Druckstandard: 300). "
            "Ändert nicht die Pixelzahl — nur die Kennzeichnung für Layout-Software."
        )
        png_row.addWidget(self.png_dpi)
        png_row.addStretch(1)
        form.addRow("PNG / Druck:", png_row)

        self.german_stop = QCheckBox("Deutsche Stoppwörter filtern")
        self.german_stop.setChecked(True)

        self.nouns_only = QCheckBox("Nur Substantive (spaCy POS)")
        self.nouns_only.setChecked(False)
        self.nouns_only.setToolTip(
            "Filtert den Text mit spaCy (de_core_news_sm) auf NOUN/PROPN-Lemmata.\n"
            "Benötigt: pip install spacy && python -m spacy download de_core_news_sm"
        )

        self.collocations = QCheckBox("Wortpaare (Bigramme) erlauben")
        self.collocations.setChecked(False)

        # 2×2 grid so columns line up vertically under each other.
        opts_grid = QGridLayout()
        opts_grid.setContentsMargins(0, 0, 0, 0)
        opts_grid.setHorizontalSpacing(16)
        opts_grid.setVerticalSpacing(4)
        opts_grid.addWidget(self.german_stop, 0, 0)
        opts_grid.addWidget(self.nouns_only, 0, 1)
        opts_grid.addWidget(self.collocations, 1, 0, 1, 2)
        opts_grid.setColumnStretch(0, 1)
        opts_grid.setColumnStretch(1, 1)
        form.addRow("Optionen:", opts_grid)

        self.extra_stop = QLineEdit()
        self.extra_stop.setPlaceholderText("zusätzliche Stoppwörter, kommagetrennt")
        form.addRow("Extra-Stoppwörter:", self.extra_stop)

        must_lines = QHBoxLayout()
        must_lines.setContentsMargins(0, 0, 0, 0)
        must_lines.setSpacing(8)
        self.must_word = QLineEdit()
        self.must_word.setPlaceholderText("Zeile 1 — z. B. BARCELONA")
        self.must_word_line2 = QLineEdit()
        self.must_word_line2.setPlaceholderText("Zeile 2 (optional)")
        self.must_word_line2.setToolTip(
            "Zweite Zeile unter der Form. Mit aktiver Checkbox erhält sie eine "
            "eigene Schriftgröße, sodass sie genauso breit wirkt wie Zeile 1."
        )
        must_lines.addWidget(self.must_word, 1)
        must_lines.addWidget(self.must_word_line2, 1)
        form.addRow("Muss-Wort:", must_lines)

        self.must_word_match_width = QCheckBox(
            "Zeile 2 auf Breite von Zeile 1 skalieren"
        )
        self.must_word_match_width.setChecked(True)
        self.must_word_match_width.setToolTip(
            "An: Zeile 1 füllt die Formbreite; Zeile 2 bekommt eine eigene "
            "Schriftgröße und wird auf dieselbe visuelle Breite skaliert.\n"
            "Aus: Beide Zeilen teilen sich dieselbe Schriftgröße."
        )

        must_row = QHBoxLayout()
        must_row.setContentsMargins(0, 0, 0, 0)
        must_row.setSpacing(8)
        self.must_word_size = QSpinBox()
        self.must_word_size.setRange(24, 2000)
        self.must_word_size.setValue(
            suggested_must_word_max_font(self.size_combo.currentData() or 1024)
        )
        self.must_word_size.setSuffix(" px max")
        self.must_word_size.setToolTip(
            "Obere Grenze für die Schriftgröße. "
            "Die Breite wird an die Form angepasst."
        )
        must_row.addWidget(self.must_word_size)

        self.must_word_gap = QSpinBox()
        self.must_word_gap.setRange(0, 500)
        self.must_word_gap.setValue(
            suggested_must_word_gap(self.size_combo.currentData() or 1024)
        )
        self.must_word_gap.setSuffix(" px")
        self.must_word_gap.setToolTip("Abstand zwischen Formunterkante und Muss-Wort.")
        must_row.addWidget(QLabel("Abstand:"))
        must_row.addWidget(self.must_word_gap)

        color_host, self.must_word_color = self._color_field(
            "#c0392b",
            tooltip="Muss-Wort-Farbe (Hex oder Picker).",
            dialog_title="Muss-Wort-Farbe",
        )
        must_row.addWidget(color_host)

        self.must_word_angle = QComboBox()
        from tools.stylecloud.must_word import MUST_WORD_ORIENTATIONS

        for label, angle in MUST_WORD_ORIENTATIONS:
            self.must_word_angle.addItem(label, angle)
        self.must_word_angle.setToolTip(
            "Ausrichtung unter der Form (Breitenanpassung bei Horizontal)."
        )
        must_row.addWidget(self.must_word_angle, 1)
        form.addRow("Muss-Wort Stil:", must_row)
        form.addRow("", self.must_word_match_width)

        left_layout.addLayout(form)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setWidget(left)
        left_scroll.setMinimumWidth(420)
        left_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        body.addWidget(left_scroll, 3)

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
        row.setSpacing(8)
        self.btn_generate = QPushButton("Wolke erzeugen")
        self.btn_generate.setDefault(True)
        self.btn_generate.clicked.connect(self._generate)
        row.addWidget(self.btn_generate)
        self.btn_open = QPushButton("Ordner öffnen")
        self.btn_open.clicked.connect(self._open_folder)
        row.addWidget(self.btn_open)
        row.addStretch(1)
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
        self._restore_settings()
        self._on_source_changed()
        self._on_mask_path_changed()
        self._refresh_palette_preview()

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
        row.addWidget(edit)
        row.addWidget(btn)

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

    def _on_size_changed(self, *_args) -> None:
        if self._restoring:
            return
        size = self.size_combo.currentData()
        if size is None:
            return
        self.max_font.setValue(suggested_max_font_size(size))
        self.must_word_size.setValue(suggested_must_word_max_font(size))
        self.must_word_gap.setValue(suggested_must_word_gap(size))
        self._update_gradient_items()

    def _canvas_is_square(self) -> bool:
        size = self.size_combo.currentData()
        return not (
            isinstance(size, tuple) and len(size) == 2 and int(size[0]) != int(size[1])
        )

    def _update_gradient_items(self) -> None:
        """Keep „Zufallsfarben“ always usable; lock only FA-square gradients."""
        self.gradient_combo.setEnabled(True)
        has_mask = bool(self.mask_path.text().strip())
        square = self._canvas_is_square()
        allow_gradient = (not has_mask) and square
        model = self.gradient_combo.model()
        for index in range(self.gradient_combo.count()):
            data = self.gradient_combo.itemData(index)
            item = model.item(index) if hasattr(model, "item") else None
            enabled = data is None or allow_gradient
            if item is not None:
                item.setEnabled(enabled)
        if not allow_gradient and self.gradient_combo.currentData() is not None:
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
        self._update_gradient_items()
        self._update_invert_mask_ui()

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
        size = self.size_combo.currentData()
        return {
            "source_mode": str(self.source_combo.currentData() or "book"),
            "source_path": self.source_path.text().strip(),
            "output_path": self.output_path.text().strip(),
            "size": size if size is not None else 1024,
            "icon_name": str(self.icon_combo.currentData() or "fas fa-book"),
            "mask_path": self.mask_path.text().strip(),
            "palette": str(
                self.palette_combo.currentData() or "cartocolors.qualitative.Bold_5"
            ),
            "gradient": self.gradient_combo.currentData(),
            "background_color": self.bg_edit.text().strip() or "white",
            "max_colors": int(self.max_colors.value()),
            "max_words": int(self.max_words.value()),
            "max_font_size": int(self.max_font.value()),
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
            "png_compress_level": int(self.png_compress.value()),
            "png_optimize": self.png_optimize.isChecked(),
            "png_dpi": int(self.png_dpi.value()),
            "window_width": int(self.width()),
            "window_height": int(self.height()),
        }

    def _persist_settings(self) -> None:
        try:
            save_settings(self._collect_settings())
        except OSError as exc:
            self._log(f"[stylecloud] Einstellungen nicht speicherbar: {exc}", "warning")

    def _restore_settings(self) -> None:
        data = load_settings()
        self._restoring = True
        try:
            self._restore_settings_body(data)
        finally:
            self._restoring = False
            self._on_mask_path_changed()

    def _restore_settings_body(self, data: dict) -> None:
        from tools.stylecloud.generator import DEFAULT_PRINT_SIZE

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
        if size in (512, 1024) or size == [1024] or size == [512]:
            size = DEFAULT_PRINT_SIZE
        if not _set_combo_by_data(self.size_combo, size):
            _set_combo_by_data(self.size_combo, DEFAULT_PRINT_SIZE)
        _set_combo_by_data(self.icon_combo, data.get("icon_name"))
        mask = str(data.get("mask_path") or "").strip()
        if mask:
            self.mask_path.setText(mask)
        _set_combo_by_data(self.palette_combo, data.get("palette"))
        _set_combo_by_data(self.gradient_combo, data.get("gradient"))

        bg = str(data.get("background_color") or "white").strip()
        self.bg_edit.setText(bg or "white")
        size_data = self.size_combo.currentData() or DEFAULT_PRINT_SIZE
        self.max_colors.setValue(int(data.get("max_colors") or 5))
        self.max_words.setValue(int(data.get("max_words") or 500))
        self.max_font.setValue(
            int(data.get("max_font_size") or suggested_max_font_size(size_data))
        )
        if int(self.max_font.value()) < suggested_max_font_size(size_data) // 2:
            self.max_font.setValue(suggested_max_font_size(size_data))
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
        size = self.size_combo.currentData()
        out = self.output_path.text().strip()
        if not out:
            raise ValueError("Bitte einen Ausgabe-Pfad angeben.")
        text = self.text_edit.toPlainText().strip()
        must = self.must_word.text().strip() or self.must_word_line2.text().strip()
        if not text:
            # Auto-load from book/file so "Wolke erzeugen" works without
            # an extra "Text laden" click after choosing a source file.
            mode = self.source_combo.currentData()
            if mode in ("book", "file"):
                text = self._read_source_text().strip()
                self.text_edit.setPlainText(text)
        if not text and not must:
            raise ValueError(
                "Kein Text für die Schlagwortwolke.\n"
                "Bitte Text laden oder ein Muss-Wort eingeben."
            )
        return StylecloudOptions(
            text=text,
            output_path=Path(out),
            size=size if size is not None else 1024,
            icon_name=str(self.icon_combo.currentData() or "fas fa-book"),
            mask_path=(
                Path(self.mask_path.text().strip())
                if self.mask_path.text().strip()
                else None
            ),
            palette=str(
                self.palette_combo.currentData() or "cartocolors.qualitative.Bold_5"
            ),
            background_color=self.bg_edit.text().strip() or "white",
            max_colors=int(self.max_colors.value()),
            gradient=(
                None
                if self.mask_path.text().strip()
                else self.gradient_combo.currentData()
            ),
            max_font_size=int(self.max_font.value()),
            max_words=int(self.max_words.value()),
            use_german_stopwords=self.german_stop.isChecked(),
            extra_stopwords=self.extra_stop.text(),
            nouns_only=self.nouns_only.isChecked(),
            collocations=self.collocations.isChecked(),
            invert_mask=self.invert_mask.isChecked(),
            random_state=42,
            must_word=self.must_word.text().strip(),
            must_word_line2=self.must_word_line2.text().strip(),
            must_word_font_size=int(self.must_word_size.value()),
            must_word_color=self.must_word_color.text().strip() or "#c0392b",
            must_word_angle=int(self.must_word_angle.currentData() or 0),
            must_word_gap=int(self.must_word_gap.value()),
            must_word_match_line1_width=self.must_word_match_width.isChecked(),
            png_compress_level=int(self.png_compress.value()),
            png_optimize=self.png_optimize.isChecked(),
            png_dpi=int(self.png_dpi.value()),
        )

    def _generate(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        try:
            options = self._build_options()
        except ValueError as exc:
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

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.btn_generate.setEnabled(not busy)
        self.btn_open.setEnabled(not busy)
        self.btn_close.setEnabled(not busy)

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


def open_stylecloud_qt(studio: Any, parent: Optional[QWidget] = None) -> None:
    dialog = StylecloudQtDialog(studio, parent)
    dialog.exec()
