"""Editoren für die KDP-Cover-Rückseite: Subtitel und Fließtextblöcke.

Die Widgets kennen den Dialog nicht; Farbfeld und Font-Combo kommen als
Fabriken herein (``KdpCoverQtDialog._color_field`` / ``_font_family_combo``),
damit Pipette, Swatch und Font-Liste identisch zur Vorderseite bleiben.
Jede Änderung meldet ``changed`` (Freitext entprellt).
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)

from tools.kdp_cover.compose_back import (
    LINE_SPACING_RANGE,
    POS_PCT_RANGE,
    TEXT_SIZE_PT_RANGE,
    WIDTH_PCT_RANGE,
    BackTextBlockSpec,
)
from tools.kdp_cover.compose_front.model import SubtitleSpec, TextBandSpec, TitleLineSpec

ColorFieldFactory = Callable[..., tuple[QWidget, QLineEdit]]
FontComboFactory = Callable[[], QComboBox]

_TEXT_DEBOUNCE_MS = 350


def _row(*widgets: QWidget) -> QWidget:
    host = QWidget()
    lay = QHBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    for w in widgets:
        lay.addWidget(w)
    return host


def _spin(
    lo: float, hi: float, value: float, *, suffix: str, step: float = 1.0, decimals: int = 1
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(lo, hi)
    spin.setDecimals(decimals)
    spin.setSingleStep(step)
    spin.setValue(value)
    spin.setSuffix(suffix)
    return spin


def _set_combo_data(combo: QComboBox, value: str) -> None:
    idx = combo.findData(value)
    combo.setCurrentIndex(idx if idx >= 0 else 0)


class _EditorBase(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._guard = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_TEXT_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._emit)

    def _emit(self, *_args: object) -> None:
        if not self._guard:
            self.changed.emit()

    def _emit_later(self, *_args: object) -> None:
        if not self._guard:
            self._debounce.start()

    def _wire(self, *widgets: QWidget) -> None:
        for w in widgets:
            if isinstance(w, QCheckBox):
                w.toggled.connect(self._emit)
            elif isinstance(w, QDoubleSpinBox):
                w.valueChanged.connect(self._emit)
            elif isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self._emit)
            elif isinstance(w, QLineEdit):
                w.textChanged.connect(self._emit_later)
            elif isinstance(w, QPlainTextEdit):
                w.textChanged.connect(self._emit_later)


class SubtitleEditor(_EditorBase):
    """Zweizeiliger Subtitel — dieselben Parameter wie auf der Vorderseite.

    Dazu eigene Ausrichtung und X-Versatz (vorne teilt der Subtitel diese mit
    den Titelzeilen). Prozentwerte beziehen sich auf den Rückseiten-Trim.
    """

    def __init__(
        self,
        *,
        color_field: ColorFieldFactory,
        font_combo: FontComboFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.enabled_check = QCheckBox("Subtitel auf der Rückseite")
        self.top_spin = _spin(0.0, 100.0, 6.0, suffix=" %Y")
        self.top_spin.setToolTip("Startposition von oben (% der Rückseiten-Höhe).")
        self.gap_spin = _spin(-4.0, 8.0, 0.8, suffix=" %H", step=0.2)
        self.gap_spin.setToolTip(
            "Abstand zwischen Zeile 1 und 2 (% der Höhe); negativ = enger."
        )
        self.align_combo = QComboBox()
        self.align_combo.addItem("Links", "left")
        self.align_combo.addItem("Zentriert", "center")
        self.align_combo.addItem("Rechts", "right")
        self.align_combo.setCurrentIndex(1)
        self.offset_spin = _spin(-45.0, 45.0, 0.0, suffix=" %X")
        self.offset_spin.setToolTip(
            "Horizontaler Versatz nach der Ausrichtung (% der Rückseiten-Breite)."
        )
        self.band_check = QCheckBox("Band hinterlegen")
        self.band_check.setToolTip(
            "Band über die volle Rückseitenbreite (inkl. Beschnitt) hinter dem Subtitel."
        )
        band_color_host, self.band_color = color_field(
            "#1E3A5F", tooltip="Bandfarbe hinter dem Subtitel"
        )
        self.band_pad_top = _spin(0.0, 12.0, 1.2, suffix=" %H", step=0.2)
        self.band_pad_bottom = _spin(0.0, 12.0, 1.2, suffix=" %H", step=0.2)

        self.lines: list[dict[str, QWidget]] = []
        line_rows: list[tuple[QWidget, QWidget]] = []
        for idx in (1, 2):
            text = QLineEdit()
            text.setPlaceholderText(f"Subtitel Zeile {idx}")
            color_host, color = color_field("#1E293B")
            size = _spin(1.0, 12.0, 3.2, suffix=" %H", step=0.5)
            font = font_combo()
            bold = QCheckBox("Fett")
            italic = QCheckBox("Kursiv")
            self.lines.append(
                {"text": text, "color": color, "size": size, "font": font, "bold": bold, "italic": italic}
            )
            line_rows.append((text, _row(color_host, size, font, bold, italic)))
            self._wire(text, size, font, bold, italic)

        form.addRow(self.enabled_check)
        form.addRow("Position:", self.top_spin)
        form.addRow("Abstand 1↔2:", self.gap_spin)
        form.addRow("Ausrichtung:", _row(self.align_combo, self.offset_spin))
        form.addRow("Band:", _row(self.band_check, band_color_host))
        form.addRow("Band Abstand oben/unten:", _row(self.band_pad_top, self.band_pad_bottom))
        for idx, (text, fmt) in enumerate(line_rows, start=1):
            form.addRow(f"Subtitel {idx}:", text)
            form.addRow(f"Format {idx}:", fmt)

        self._wire(
            self.enabled_check,
            self.top_spin,
            self.gap_spin,
            self.align_combo,
            self.offset_spin,
            self.band_check,
            self.band_pad_top,
            self.band_pad_bottom,
        )

    @property
    def first_text(self) -> QLineEdit:
        return self.lines[0]["text"]  # type: ignore[return-value]

    def _line_spec(self, idx: int) -> TitleLineSpec:
        w = self.lines[idx]
        return TitleLineSpec(
            text=w["text"].text().strip(),  # type: ignore[attr-defined]
            color=w["color"].text().strip() or "#1E293B",  # type: ignore[attr-defined]
            size_pct=float(w["size"].value()),  # type: ignore[attr-defined]
            font=str(w["font"].currentData() or "sans"),  # type: ignore[attr-defined]
            bold=w["bold"].isChecked(),  # type: ignore[attr-defined]
            italic=w["italic"].isChecked(),  # type: ignore[attr-defined]
        )

    def to_spec(self) -> tuple[SubtitleSpec, str, float]:
        """``(SubtitleSpec, align, offset_x_pct)``."""
        spec = SubtitleSpec(
            enabled=self.enabled_check.isChecked(),
            line1=self._line_spec(0),
            line2=self._line_spec(1),
            top_pct=float(self.top_spin.value()),
            gap_pct=float(self.gap_spin.value()),
            band=TextBandSpec(
                enabled=self.band_check.isChecked(),
                color=self.band_color.text().strip() or "#1E3A5F",
                padding_top_pct=float(self.band_pad_top.value()),
                padding_bottom_pct=float(self.band_pad_bottom.value()),
            ),
        )
        align = str(self.align_combo.currentData() or "center")
        return spec, align, float(self.offset_spin.value())

    def set_spec(self, spec: SubtitleSpec, *, align: str, offset_x_pct: float) -> None:
        self._guard = True
        try:
            self.enabled_check.setChecked(bool(spec.enabled))
            self.top_spin.setValue(float(spec.top_pct))
            self.gap_spin.setValue(float(spec.gap_pct))
            _set_combo_data(self.align_combo, align)
            self.offset_spin.setValue(float(offset_x_pct))
            self.band_check.setChecked(bool(spec.band.enabled))
            self.band_color.setText(spec.band.color)
            self.band_pad_top.setValue(float(spec.band.padding_top_pct))
            self.band_pad_bottom.setValue(float(spec.band.padding_bottom_pct))
            for w, line in zip(self.lines, (spec.line1, spec.line2), strict=True):
                w["text"].setText(line.text)  # type: ignore[attr-defined]
                w["color"].setText(line.color)  # type: ignore[attr-defined]
                w["size"].setValue(float(line.size_pct))  # type: ignore[attr-defined]
                _set_combo_data(w["font"], line.font)  # type: ignore[arg-type]
                w["bold"].setChecked(bool(line.bold))  # type: ignore[attr-defined]
                w["italic"].setChecked(bool(line.italic))  # type: ignore[attr-defined]
        finally:
            self._guard = False


class TextBlockEditor(_EditorBase):
    """Fließtextblock: Text, Font, Farbe, Größe (pt), Platzierung, Ausrichtung."""

    def __init__(
        self,
        *,
        label: str,
        placeholder: str,
        color_field: ColorFieldFactory,
        font_combo: FontComboFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.enabled_check = QCheckBox(label)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(placeholder)
        self.text_edit.setMinimumHeight(110)
        self.text_edit.setToolTip("Leerzeile = neuer Absatz.")
        self.font_combo = font_combo()
        color_host, self.color_edit = color_field("#1E293B", tooltip="Textfarbe")
        self.size_spin = _spin(*TEXT_SIZE_PT_RANGE, 10.0, suffix=" pt", step=0.5)
        self.size_spin.setToolTip("Schriftgröße in Punkt (Druckmaß).")
        self.bold_check = QCheckBox("Fett")
        self.italic_check = QCheckBox("Kursiv")
        self.align_combo = QComboBox()
        self.align_combo.addItem("Links", "left")
        self.align_combo.addItem("Zentriert", "center")
        self.align_combo.addItem("Rechts", "right")
        self.align_combo.addItem("Blocksatz", "justify")
        self.line_spacing_spin = _spin(
            *LINE_SPACING_RANGE, 1.35, suffix=" ×", step=0.05, decimals=2
        )
        self.line_spacing_spin.setToolTip("Zeilenabstand als Vielfaches der Schriftgröße.")
        self.x_spin = _spin(*POS_PCT_RANGE, 10.0, suffix=" %X")
        self.x_spin.setToolTip("Linke Kante (% der Rückseiten-Breite, ohne Beschnitt).")
        self.y_spin = _spin(*POS_PCT_RANGE, 20.0, suffix=" %Y")
        self.y_spin.setToolTip("Oberkante (% der Rückseiten-Höhe, ohne Beschnitt).")
        self.width_spin = _spin(*WIDTH_PCT_RANGE, 80.0, suffix=" %B")
        self.width_spin.setToolTip(
            "Satzbreite (% der Rückseiten-Breite). Die Höhe ergibt sich aus dem Umbruch."
        )

        form.addRow(self.enabled_check)
        form.addRow(self.text_edit)
        form.addRow(
            "Schrift:",
            _row(self.font_combo, color_host, self.size_spin, self.bold_check, self.italic_check),
        )
        form.addRow("Ausrichtung:", _row(self.align_combo, self.line_spacing_spin))
        form.addRow("Position X / Y:", _row(self.x_spin, self.y_spin))
        form.addRow("Breite:", self.width_spin)

        self._wire(
            self.enabled_check,
            self.text_edit,
            self.font_combo,
            self.size_spin,
            self.bold_check,
            self.italic_check,
            self.align_combo,
            self.line_spacing_spin,
            self.x_spin,
            self.y_spin,
            self.width_spin,
        )

    def to_spec(self) -> BackTextBlockSpec:
        return BackTextBlockSpec(
            enabled=self.enabled_check.isChecked(),
            text=self.text_edit.toPlainText().strip(),
            font=str(self.font_combo.currentData() or "serif"),
            size_pt=float(self.size_spin.value()),
            color=self.color_edit.text().strip() or "#1E293B",
            bold=self.bold_check.isChecked(),
            italic=self.italic_check.isChecked(),
            align=str(self.align_combo.currentData() or "justify"),
            line_spacing=float(self.line_spacing_spin.value()),
            x_pct=float(self.x_spin.value()),
            y_pct=float(self.y_spin.value()),
            width_pct=float(self.width_spin.value()),
        )

    def set_spec(self, spec: BackTextBlockSpec) -> None:
        self._guard = True
        try:
            self.enabled_check.setChecked(bool(spec.enabled))
            if self.text_edit.toPlainText() != spec.text:
                self.text_edit.setPlainText(spec.text)
            _set_combo_data(self.font_combo, spec.font)
            self.color_edit.setText(spec.color)
            self.size_spin.setValue(float(spec.size_pt))
            self.bold_check.setChecked(bool(spec.bold))
            self.italic_check.setChecked(bool(spec.italic))
            _set_combo_data(self.align_combo, spec.align)
            self.line_spacing_spin.setValue(float(spec.line_spacing))
            self.x_spin.setValue(float(spec.x_pct))
            self.y_spin.setValue(float(spec.y_pct))
            self.width_spin.setValue(float(spec.width_pct))
        finally:
            self._guard = False


__all__ = ["SubtitleEditor", "TextBlockEditor"]
