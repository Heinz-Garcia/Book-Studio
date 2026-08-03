"""Dialog: Amazon-KDP-Spezifikationen (``kdp_specs.json``) bearbeiten."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import tools.kdp_specs as kdp_specs


def _spin_float(value: float, *, minimum: float = 0.0, maximum: float = 1e6, decimals: int = 4) -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setRange(minimum, maximum)
    w.setDecimals(decimals)
    w.setValue(float(value))
    return w


def _spin_int(value: int, *, minimum: int = 0, maximum: int = 10_000) -> QSpinBox:
    w = QSpinBox()
    w.setRange(minimum, maximum)
    w.setValue(int(value))
    return w


class KdpSpecsDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], config_path: Optional[Path] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("KDP-Spezifikationen")
        self.setMinimumSize(720, 640)
        self.resize(800, 720)
        self.config_path = Path(config_path) if config_path else kdp_specs.specs_path()
        self.data: dict[str, Any] = kdp_specs.load_specs(self.config_path)

        root = QVBoxLayout(self)
        tip = QLabel(
            f"SSOT: {self.config_path}\n"
            "Werte gelten für Cover-Rechner, Druck-Freigabe und Paperback-/Bleed-Profile."
        )
        tip.setStyleSheet("color:#5b6573;")
        tip.setWordWrap(True)
        root.addWidget(tip)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(12)

        body_layout.addWidget(self._build_general_group())
        body_layout.addWidget(self._build_paper_group())
        body_layout.addWidget(self._build_trim_group())
        body_layout.addWidget(self._build_inside_group())
        body_layout.addWidget(self._build_paperback_group())
        body_layout.addWidget(self._build_bod_group())
        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        reset = QPushButton("Defaults wiederherstellen")
        reset.clicked.connect(self._reset_defaults)
        buttons.addButton(reset, QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_general_group(self) -> QGroupBox:
        box = QGroupBox("Allgemein")
        form = QFormLayout(box)
        pb = self.data.get("paperback") or {}
        typst = (self.data.get("typst_defaults") or {}).get("margin_in") or {}
        self.bleed = _spin_float(self.data.get("bleed_mm", 3.2), maximum=20.0, decimals=2)
        self.mm_per_inch = _spin_float(self.data.get("mm_per_inch", 25.4), maximum=100.0, decimals=4)
        self.min_pages = _spin_int(pb.get("min_page_count", 24), minimum=1, maximum=2000)
        self.max_pages = _spin_int(pb.get("max_page_count", 828), minimum=1, maximum=5000)
        self.min_outer = _spin_float(pb.get("min_outer_margin_in", 0.25), maximum=2.0, decimals=3)
        self.typst_x = _spin_float(typst.get("x", 1.25), maximum=5.0, decimals=3)
        self.typst_y = _spin_float(typst.get("y", 1.25), maximum=5.0, decimals=3)
        self.default_paper = QLineEdit(str(self.data.get("default_paper_type_id") or "white_bw"))
        form.addRow("Bleed (mm):", self.bleed)
        form.addRow("mm pro Zoll:", self.mm_per_inch)
        form.addRow("Min. Seiten:", self.min_pages)
        form.addRow("Max. Seiten:", self.max_pages)
        form.addRow("Äußerer Mindestrand (in):", self.min_outer)
        form.addRow("Typst-Default-Rand X (in):", self.typst_x)
        form.addRow("Typst-Default-Rand Y (in):", self.typst_y)
        form.addRow("Default-Papierart-ID:", self.default_paper)
        return box

    def _fill_table(self, table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(str(text)))

    def _table_rows(self, table: QTableWidget) -> list[list[str]]:
        rows: list[list[str]] = []
        for r in range(table.rowCount()):
            cells: list[str] = []
            empty = True
            for c in range(table.columnCount()):
                item = table.item(r, c)
                text = item.text().strip() if item else ""
                if text:
                    empty = False
                cells.append(text)
            if not empty:
                rows.append(cells)
        return rows

    def _build_paper_group(self) -> QGroupBox:
        box = QGroupBox("Papierarten")
        layout = QVBoxLayout(box)
        self.paper_table = QTableWidget(0, 3)
        self.paper_table.setHorizontalHeaderLabels(["ID", "Label", "mm/Seite"])
        self.paper_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        rows = [
            [str(p.get("id", "")), str(p.get("label", "")), str(p.get("mm_per_page", ""))]
            for p in self.data.get("paper_types") or []
        ]
        self._fill_table(self.paper_table, rows)
        layout.addWidget(self.paper_table)
        layout.addLayout(self._table_buttons(self.paper_table))
        return box

    def _build_trim_group(self) -> QGroupBox:
        box = QGroupBox("Trimmgrößen (Zoll)")
        layout = QVBoxLayout(box)
        custom = self.data.get("custom_trim_in") or {}
        wr = custom.get("width_range") or [4.0, 8.5]
        hr = custom.get("height_range") or [6.0, 11.69]
        form = QFormLayout()
        self.custom_w_min = _spin_float(wr[0], maximum=20.0, decimals=2)
        self.custom_w_max = _spin_float(wr[1], maximum=20.0, decimals=2)
        self.custom_h_min = _spin_float(hr[0], maximum=20.0, decimals=2)
        self.custom_h_max = _spin_float(hr[1], maximum=20.0, decimals=2)
        form.addRow("Custom-Breite min (in):", self.custom_w_min)
        form.addRow("Custom-Breite max (in):", self.custom_w_max)
        form.addRow("Custom-Höhe min (in):", self.custom_h_min)
        form.addRow("Custom-Höhe max (in):", self.custom_h_max)
        layout.addLayout(form)
        self.trim_table = QTableWidget(0, 4)
        self.trim_table.setHorizontalHeaderLabels(["ID", "Label", "Breite (in)", "Höhe (in)"])
        self.trim_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        rows = [
            [
                str(t.get("id", "")),
                str(t.get("label", "")),
                str(t.get("width", "")),
                str(t.get("height", "")),
            ]
            for t in self.data.get("trim_sizes_in") or []
        ]
        self._fill_table(self.trim_table, rows)
        layout.addWidget(self.trim_table)
        layout.addLayout(self._table_buttons(self.trim_table))
        return box

    def _build_inside_group(self) -> QGroupBox:
        box = QGroupBox("Innenränder (Seiten bis N → mm)")
        layout = QVBoxLayout(box)
        self.inside_table = QTableWidget(0, 2)
        self.inside_table.setHorizontalHeaderLabels(["Seiten bis", "Min. Innenrand (mm)"])
        self.inside_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        rows = [
            [str(a), str(b)] for a, b in (self.data.get("inside_margin_mm_by_max_pages") or [])
        ]
        self._fill_table(self.inside_table, rows)
        layout.addWidget(self.inside_table)
        layout.addLayout(self._table_buttons(self.inside_table))
        return box

    def _build_paperback_group(self) -> QGroupBox:
        box = QGroupBox("Studio-Paperback (paperback / paperback-bleed)")
        form = QFormLayout(box)
        preset = (self.data.get("studio_presets") or {}).get("paperback") or {}
        trim = preset.get("trim_mm") or {}
        margin = preset.get("page_margin_mm") or {}
        self.pb_w = _spin_float(trim.get("width", 135), maximum=500.0, decimals=1)
        self.pb_h = _spin_float(trim.get("height", 215), maximum=500.0, decimals=1)
        self.pb_inside = _spin_float(margin.get("inside", 20), maximum=80.0, decimals=1)
        self.pb_outside = _spin_float(margin.get("outside", 16), maximum=80.0, decimals=1)
        self.pb_top = _spin_float(margin.get("top", 19), maximum=80.0, decimals=1)
        self.pb_bottom = _spin_float(margin.get("bottom", 20), maximum=80.0, decimals=1)
        self.pb_lines = _spin_int(preset.get("lines_per_page", 36), maximum=100)
        self.pb_chars = _spin_int(preset.get("chars_per_line", 62), maximum=200)
        form.addRow("Trim-Breite (mm):", self.pb_w)
        form.addRow("Trim-Höhe (mm):", self.pb_h)
        form.addRow("Rand innen (mm):", self.pb_inside)
        form.addRow("Rand außen (mm):", self.pb_outside)
        form.addRow("Rand oben (mm):", self.pb_top)
        form.addRow("Rand unten (mm):", self.pb_bottom)
        form.addRow("Zeilen/Seite:", self.pb_lines)
        form.addRow("Zeichen/Zeile:", self.pb_chars)
        return box

    def _build_bod_group(self) -> QGroupBox:
        box = QGroupBox("Studio-Taschenbuch/BoD (taschenbuch-bod)")
        form = QFormLayout(box)
        preset = (self.data.get("studio_presets") or {}).get("taschenbuch_bod") or {}
        margin = preset.get("page_margin_mm") or {}
        self.bod_papersize = QLineEdit(str(preset.get("papersize") or "a5"))
        self.bod_inside = _spin_float(margin.get("inside", 20), maximum=80.0, decimals=1)
        self.bod_outside = _spin_float(margin.get("outside", 16), maximum=80.0, decimals=1)
        self.bod_top = _spin_float(margin.get("top", 18), maximum=80.0, decimals=1)
        self.bod_bottom = _spin_float(margin.get("bottom", 20), maximum=80.0, decimals=1)
        form.addRow("Papersize:", self.bod_papersize)
        form.addRow("Rand innen (mm):", self.bod_inside)
        form.addRow("Rand außen (mm):", self.bod_outside)
        form.addRow("Rand oben (mm):", self.bod_top)
        form.addRow("Rand unten (mm):", self.bod_bottom)
        return box

    def _table_buttons(self, table: QTableWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        add = QPushButton("Zeile +")
        rem = QPushButton("Zeile −")

        def _add() -> None:
            r = table.rowCount()
            table.insertRow(r)
            for c in range(table.columnCount()):
                table.setItem(r, c, QTableWidgetItem(""))

        def _rem() -> None:
            r = table.currentRow()
            if r >= 0:
                table.removeRow(r)

        add.clicked.connect(_add)
        rem.clicked.connect(_rem)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        return row

    def _collect(self) -> dict[str, Any]:
        data = kdp_specs.default_specs()
        data["bleed_mm"] = float(self.bleed.value())
        data["mm_per_inch"] = float(self.mm_per_inch.value())
        data["paperback"] = {
            "min_page_count": int(self.min_pages.value()),
            "max_page_count": int(self.max_pages.value()),
            "min_outer_margin_in": float(self.min_outer.value()),
        }
        data["default_paper_type_id"] = self.default_paper.text().strip() or "white_bw"
        data["typst_defaults"] = {
            "margin_in": {"x": float(self.typst_x.value()), "y": float(self.typst_y.value())},
            "fallback_papersize": "us-letter",
        }
        papers: list[dict[str, Any]] = []
        for cells in self._table_rows(self.paper_table):
            if len(cells) < 3 or not cells[0]:
                continue
            try:
                mm = float(cells[2].replace(",", "."))
            except ValueError:
                continue
            papers.append({"id": cells[0], "label": cells[1] or cells[0], "mm_per_page": mm})
        if papers:
            data["paper_types"] = papers

        trims: list[dict[str, Any]] = []
        for cells in self._table_rows(self.trim_table):
            if len(cells) < 4 or not cells[0]:
                continue
            try:
                w = float(cells[2].replace(",", "."))
                h = float(cells[3].replace(",", "."))
            except ValueError:
                continue
            trims.append(
                {"id": cells[0], "label": cells[1] or cells[0], "width": w, "height": h}
            )
        if trims:
            data["trim_sizes_in"] = trims
        data["custom_trim_in"] = {
            "width_range": [float(self.custom_w_min.value()), float(self.custom_w_max.value())],
            "height_range": [float(self.custom_h_min.value()), float(self.custom_h_max.value())],
        }

        tiers: list[list[float]] = []
        for cells in self._table_rows(self.inside_table):
            if len(cells) < 2:
                continue
            try:
                tiers.append([int(float(cells[0])), float(cells[1].replace(",", "."))])
            except ValueError:
                continue
        if tiers:
            data["inside_margin_mm_by_max_pages"] = tiers

        data["studio_presets"] = {
            "paperback": {
                "trim_mm": {"width": float(self.pb_w.value()), "height": float(self.pb_h.value())},
                "page_margin_mm": {
                    "inside": float(self.pb_inside.value()),
                    "outside": float(self.pb_outside.value()),
                    "top": float(self.pb_top.value()),
                    "bottom": float(self.pb_bottom.value()),
                },
                "lines_per_page": int(self.pb_lines.value()),
                "chars_per_line": int(self.pb_chars.value()),
            },
            "taschenbuch_bod": {
                "papersize": self.bod_papersize.text().strip() or "a5",
                "page_margin_mm": {
                    "inside": float(self.bod_inside.value()),
                    "outside": float(self.bod_outside.value()),
                    "top": float(self.bod_top.value()),
                    "bottom": float(self.bod_bottom.value()),
                },
            },
        }
        # meta beibehalten
        if isinstance(self.data.get("meta"), dict):
            data["meta"] = self.data["meta"]
        return data

    def _reset_defaults(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Defaults",
                "Eingebaute Defaults in die Formularfelder laden?\n"
                "(Erst Speichern schreibt die Datei.)",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.data = kdp_specs.default_specs()
        self.bleed.setValue(float(self.data["bleed_mm"]))
        self.mm_per_inch.setValue(float(self.data["mm_per_inch"]))
        pb = self.data["paperback"]
        self.min_pages.setValue(int(pb["min_page_count"]))
        self.max_pages.setValue(int(pb["max_page_count"]))
        self.min_outer.setValue(float(pb["min_outer_margin_in"]))
        typst = self.data["typst_defaults"]["margin_in"]
        self.typst_x.setValue(float(typst["x"]))
        self.typst_y.setValue(float(typst["y"]))
        self.default_paper.setText(str(self.data["default_paper_type_id"]))
        self._fill_table(
            self.paper_table,
            [
                [str(p["id"]), str(p["label"]), str(p["mm_per_page"])]
                for p in self.data["paper_types"]
            ],
        )
        self._fill_table(
            self.trim_table,
            [
                [str(t["id"]), str(t["label"]), str(t["width"]), str(t["height"])]
                for t in self.data["trim_sizes_in"]
            ],
        )
        wr = self.data["custom_trim_in"]["width_range"]
        hr = self.data["custom_trim_in"]["height_range"]
        self.custom_w_min.setValue(float(wr[0]))
        self.custom_w_max.setValue(float(wr[1]))
        self.custom_h_min.setValue(float(hr[0]))
        self.custom_h_max.setValue(float(hr[1]))
        self._fill_table(
            self.inside_table,
            [[str(a), str(b)] for a, b in self.data["inside_margin_mm_by_max_pages"]],
        )
        preset = self.data["studio_presets"]["paperback"]
        trim = preset["trim_mm"]
        margin = preset["page_margin_mm"]
        self.pb_w.setValue(float(trim["width"]))
        self.pb_h.setValue(float(trim["height"]))
        self.pb_inside.setValue(float(margin["inside"]))
        self.pb_outside.setValue(float(margin["outside"]))
        self.pb_top.setValue(float(margin["top"]))
        self.pb_bottom.setValue(float(margin["bottom"]))
        self.pb_lines.setValue(int(preset["lines_per_page"]))
        self.pb_chars.setValue(int(preset["chars_per_line"]))
        bod = self.data["studio_presets"]["taschenbuch_bod"]
        self.bod_papersize.setText(str(bod["papersize"]))
        bm = bod["page_margin_mm"]
        self.bod_inside.setValue(float(bm["inside"]))
        self.bod_outside.setValue(float(bm["outside"]))
        self.bod_top.setValue(float(bm["top"]))
        self.bod_bottom.setValue(float(bm["bottom"]))

    def _save(self) -> None:
        try:
            data = self._collect()
            kdp_specs.save_specs(data, self.config_path)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self.accept()
