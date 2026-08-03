"""Qt-Dialog: Cover-Größe berechnen (Buchrücken-Breite für KDP-Taschenbücher).

Reiner Rechner, keine Datei-I/O -- liest/schreibt nichts am Buchprojekt.
Rechenlogik komplett in ``tools.cover_size.calculator`` (kein UI-Bezug dort).
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tools.cover_size.calculator import (
    CUSTOM_HEIGHT_RANGE_IN,
    CUSTOM_TRIM_SIZE_ID,
    CUSTOM_WIDTH_RANGE_IN,
    DEFAULT_PAPER_TYPE_ID,
    MAX_PAGE_COUNT,
    MIN_PAGE_COUNT,
    PAPER_TYPES,
    TRIM_SIZES,
    calculate_cover_size,
    get_trim_size,
    inch_to_mm,
)
from ui_qt.widgets.help_bar import HelpBar

_DEFAULT_PAGE_COUNT = 200
_DEFAULT_TRIM_SIZE_ID = "6x9"


class CoverSizeQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cover-Größe berechnen (KDP)")
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        HelpBar.create_and_prepend_for_plugin(layout, "cover_size")

        form = QFormLayout()
        form.setSpacing(10)

        self.pages_spin = QSpinBox()
        self.pages_spin.setRange(MIN_PAGE_COUNT, MAX_PAGE_COUNT)
        self.pages_spin.setValue(_DEFAULT_PAGE_COUNT)
        self.pages_spin.setSuffix(" Seiten")
        form.addRow("Seitenzahl:", self.pages_spin)

        self.paper_combo = QComboBox()
        for paper in PAPER_TYPES:
            self.paper_combo.addItem(paper.label, paper.id)
        idx = self.paper_combo.findData(DEFAULT_PAPER_TYPE_ID)
        if idx >= 0:
            self.paper_combo.setCurrentIndex(idx)
        form.addRow("Papierart:", self.paper_combo)

        self.trim_combo = QComboBox()
        for trim in TRIM_SIZES:
            self.trim_combo.addItem(trim.label, trim.id)
        self.trim_combo.addItem("Benutzerdefiniert…", CUSTOM_TRIM_SIZE_ID)
        idx = self.trim_combo.findData(_DEFAULT_TRIM_SIZE_ID)
        if idx >= 0:
            self.trim_combo.setCurrentIndex(idx)
        form.addRow("Trimmgröße:", self.trim_combo)

        custom_row = QHBoxLayout()
        self.custom_width_spin = QDoubleSpinBox()
        self.custom_width_spin.setRange(*CUSTOM_WIDTH_RANGE_IN)
        self.custom_width_spin.setDecimals(2)
        self.custom_width_spin.setSuffix(" in")
        self.custom_width_spin.setValue(CUSTOM_WIDTH_RANGE_IN[0])
        custom_row.addWidget(self.custom_width_spin)
        custom_row.addWidget(QLabel("×"))
        self.custom_height_spin = QDoubleSpinBox()
        self.custom_height_spin.setRange(*CUSTOM_HEIGHT_RANGE_IN)
        self.custom_height_spin.setDecimals(2)
        self.custom_height_spin.setSuffix(" in")
        self.custom_height_spin.setValue(CUSTOM_HEIGHT_RANGE_IN[0])
        custom_row.addWidget(self.custom_height_spin)
        self.custom_width_spin.setVisible(False)
        self.custom_height_spin.setVisible(False)
        form.addRow("", custom_row)

        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#b91c1c;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        self.result_label = QLabel("")
        self.result_label.setObjectName("coverSizeResult")
        self.result_label.setStyleSheet(
            "font-family: 'SF Mono','Consolas',monospace; font-size: 13px;"
        )
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(
            self.result_label.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.result_label)

        bleed_note = QLabel(
            "Beschnittzugabe (3,2mm / 0.125in) ist in Gesamt-Coverbreite/-höhe "
            "bereits eingerechnet."
        )
        bleed_note.setStyleSheet("color:#5b6573; font-size:12px;")
        bleed_note.setWordWrap(True)
        layout.addWidget(bleed_note)

        row = QHBoxLayout()
        self.btn_copy = QPushButton("Werte kopieren")
        self.btn_copy.clicked.connect(self._copy_result)
        row.addWidget(self.btn_copy)
        row.addStretch(1)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)

        self.pages_spin.valueChanged.connect(self._recalculate)
        self.paper_combo.currentIndexChanged.connect(self._recalculate)
        self.trim_combo.currentIndexChanged.connect(self._on_trim_changed)
        self.custom_width_spin.valueChanged.connect(self._recalculate)
        self.custom_height_spin.valueChanged.connect(self._recalculate)

        self._on_trim_changed()

    def _on_trim_changed(self) -> None:
        is_custom = self.trim_combo.currentData() == CUSTOM_TRIM_SIZE_ID
        self.custom_width_spin.setVisible(is_custom)
        self.custom_height_spin.setVisible(is_custom)
        self._recalculate()

    def _current_trim_mm(self) -> tuple[float, float]:
        trim_id = self.trim_combo.currentData()
        if trim_id == CUSTOM_TRIM_SIZE_ID:
            return (
                inch_to_mm(self.custom_width_spin.value()),
                inch_to_mm(self.custom_height_spin.value()),
            )
        trim = get_trim_size(str(trim_id))
        if trim is None:
            return (inch_to_mm(6.0), inch_to_mm(9.0))
        return inch_to_mm(trim.width_in), inch_to_mm(trim.height_in)

    def _recalculate(self, *_args: Any) -> None:
        trim_width_mm, trim_height_mm = self._current_trim_mm()
        try:
            result = calculate_cover_size(
                self.pages_spin.value(),
                str(self.paper_combo.currentData()),
                trim_width_mm,
                trim_height_mm,
            )
        except ValueError as exc:
            self.error_label.setText(str(exc))
            self.error_label.setVisible(True)
            self.result_label.setText("")
            return
        self.error_label.setVisible(False)
        self.result_label.setText(
            f"Buchrücken-Breite:     {result.spine_width_mm:.2f} mm  ({result.spine_width_in:.4f} in)\n"
            f"Gesamt-Coverbreite:    {result.cover_width_mm:.2f} mm  ({result.cover_width_in:.4f} in)\n"
            f"Gesamt-Coverhöhe:      {result.cover_height_mm:.2f} mm  ({result.cover_height_in:.4f} in)\n"
            f"Trimmgröße (fertig):   {result.trim_width_mm:.1f} × {result.trim_height_mm:.1f} mm"
        )

    def _copy_result(self) -> None:
        text = self.result_label.text()
        if text:
            QApplication.clipboard().setText(text)


def open_cover_size_qt(studio: Any = None, parent: Optional[QWidget] = None, **_kwargs: Any) -> None:
    CoverSizeQtDialog(parent).exec()


__all__ = ["CoverSizeQtDialog", "open_cover_size_qt"]
