"""Qt-Dialog: KDP Wrap-Cover-Designer (Phase 2–5).

Geschäftslogik in ``tools.kdp_cover``. Persistenz: Cover-Zwischenstand,
Kanal-Flag in ``bookconfig/distribution.json``, zweistufige Export-Bestätigung.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
    mm_to_inch,
)
from tools.distribution.book_store import is_kdp_paperback, set_kdp_paperback
from tools.kdp_cover.binding import (
    binding_status_label,
    resolve_cover_binding,
)
from tools.kdp_cover.constants import (
    DEFAULT_EXPORT_DPI,
    SAFE_ZONE_IN,
    SPINE_BADGE_SCALE_STEPS,
    SPINE_EDGE_PADDING_MIN_MM,
)
from tools.kdp_cover.export_pdf import export_wrap_pdf, render_wrap_image
from tools.kdp_cover.geometry import WrapGeometry, build_geometry
from tools.kdp_cover.model import (
    CoverLayout,
    SpineBadgeSpec,
    default_project_path,
    default_wrap_pdf_path,
    load_layout,
    resolve_existing_project_path,
    save_layout,
)
from tools.kdp_cover.settings import load_settings, resolve_window_size, save_settings
from tools.kdp_cover.validate import ValidationReport, validate_layout
from tools.kdp_specs import format_bleed_note, studio_paperback_preset
from ui_qt.widgets.collapsible_section import CollapsibleSection
from ui_qt.widgets.help_bar import HelpBar
from ui_qt.widgets.resize_grip import attach_resize_grip

_STUDIO_PAPERBACK_ID = "studio_paperback"
# Bildschirm-Vorschau (Export bleibt DEFAULT_EXPORT_DPI / clamp_print_dpi ≥ 300).
# 300 DPI hier → mehrfaches Smooth-Skalieren bei jedem resizeEvent = sichtbares Gezucke.
_PREVIEW_DPI = 120.0
_PREVIEW_ZOOM_MIN = 0.25
_PREVIEW_ZOOM_MAX = 4.0
_PREVIEW_ZOOM_STEP = 1.15
_PREVIEW_DEBOUNCE_MS = 120
_PREVIEW_FIT_DEBOUNCE_MS = 60
_IMAGE_FILTER = "Bilder (*.png *.jpg *.jpeg *.tif *.tiff *.webp);;Alle Dateien (*.*)"
_PROJECT_FILTER = (
    "Cover-Layout (*_kdp_cover.json);;"
    "Cover-Layout Wrap (*_kdp_wrap_project.json);;"
    "Legacy (cover_project.json);;"
    "Alle Dateien (*.*)"
)
_ELEMENT_SET_FILTER = "Elementset (*_elementset.json);;Alle Dateien (*.*)"
_PROJECT_SAVE_FILTER = "Cover-Layout (*_kdp_cover.json);;Alle Dateien (*.*)"
_ELEMENT_SET_SAVE_FILTER = "Elementset (*_elementset.json);;Alle Dateien (*.*)"


def _book_root(studio: Any) -> Path | None:
    raw = getattr(studio, "current_book", None) if studio else None
    if raw is None and studio is not None:
        facade = getattr(studio, "facade", None)
        raw = getattr(facade, "current_book", None) if facade else None
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def _read_quarto_title_author(book: Path) -> tuple[str, str]:
    yml = book / "_quarto.yml"
    if not yml.is_file():
        return "", ""
    try:
        import yaml

        data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, TypeError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    title = str(data.get("title") or "").strip()
    author = data.get("author") or data.get("authors") or ""
    if isinstance(author, list):
        parts: list[str] = []
        for item in author:
            if isinstance(item, dict):
                parts.append(str(item.get("name") or item.get("family") or "").strip())
            else:
                parts.append(str(item).strip())
        author_s = ", ".join(p for p in parts if p)
    else:
        author_s = str(author).strip()
    book_block = data.get("book") if isinstance(data.get("book"), dict) else {}
    if not title:
        title = str(book_block.get("title") or "").strip()
    if not author_s:
        author_s = str(book_block.get("author") or "").strip()
    return title, author_s


def _pil_to_qpixmap(image) -> QPixmap:
    rgb = image.convert("RGB")
    w, h = rgb.size
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def _draw_overlays(pixmap: QPixmap, geo: WrapGeometry, dpi: float) -> QPixmap:
    from tools.kdp_cover.panel_images import barcode_reserve_mm

    out = QPixmap(pixmap)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    scale = dpi / 25.4

    def _rect(r) -> tuple[float, float, float, float]:
        return r.x * scale, r.y * scale, r.width * scale, r.height * scale

    painter.setPen(QPen(QColor(220, 38, 38, 200), 1, Qt.PenStyle.DashLine))
    painter.drawRect(0, 0, out.width() - 1, out.height() - 1)

    painter.setPen(QPen(QColor(37, 99, 235, 220), 1, Qt.PenStyle.SolidLine))
    for panel in (geo.back_panel, geo.spine_panel, geo.front_panel):
        x, y, w, h = _rect(panel)
        painter.drawRect(int(x), int(y), int(w), int(h))

    painter.setPen(QPen(QColor(22, 163, 74, 220), 1, Qt.PenStyle.DotLine))
    for panel in (geo.back_safe, geo.front_safe):
        x, y, w, h = _rect(panel)
        if w > 2 and h > 2:
            painter.drawRect(int(x), int(y), int(w), int(h))

    painter.setPen(QPen(QColor(100, 116, 139, 180), 1, Qt.PenStyle.DashDotLine))
    sx, sy, sw, sh = _rect(geo.spine_panel)
    cx = int(sx + sw / 2)
    painter.drawLine(cx, int(sy), cx, int(sy + sh))

    # KDP-Barcode-Reserve (unten rechts auf der Rückseite) — Platzhalter.
    barcode = barcode_reserve_mm(geo)
    bx, by, bw, bh = _rect(barcode)
    if bw > 2 and bh > 2:
        painter.fillRect(
            int(bx),
            int(by),
            int(bw),
            int(bh),
            QColor(250, 204, 21, 110),  # amber, semi-transparent
        )
        painter.setPen(QPen(QColor(180, 83, 9, 230), 2, Qt.PenStyle.DashLine))
        painter.drawRect(int(bx), int(by), int(bw), int(bh))
        painter.setPen(QColor(120, 53, 15, 240))
        font = QFont()
        font.setPointSize(max(7, int(round(min(bw, bh) / 8))))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            int(bx),
            int(by),
            int(bw),
            int(bh),
            int(Qt.AlignmentFlag.AlignCenter),
            "KDP-Barcode\n(freihalten)",
        )

    painter.end()
    return out


class _FreeExportConfirmDialog(QDialog):
    """Zweistufige Bestätigung für Frei-Modus-Export mit Hinweisen."""

    def __init__(self, parent: Optional[QWidget], detail: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Frei-Modus: Export bestätigen")
        self.resize(520, 360)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Schritt 1/2: Es gibt Validierungshinweise. Bitte prüfen:\n\n" + detail
            )
        )
        self.ack = QCheckBox(
            "Schritt 2/2: Ich habe die Warnungen/Fehler gelesen und übernehme "
            "die Verantwortung für den KDP-Upload."
        )
        layout.addWidget(self.ack)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        self._yes = buttons.button(QDialogButtonBox.StandardButton.Yes)
        self._yes.setText("Trotzdem exportieren")
        self._yes.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.No).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.ack.toggled.connect(self._yes.setEnabled)


class KdpCoverQtDialog(QDialog):
    def __init__(
        self,
        studio: Any = None,
        parent: Optional[QWidget] = None,
        *,
        front_image: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._studio = studio
        self._book = _book_root(studio)
        self._mode_guard = False
        self._params_guard = True  # bis Init fertig — kein Preview-Sturm
        self._initial_front_image = front_image
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(_PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(_PREVIEW_FIT_DEBOUNCE_MS)
        self._fit_timer.timeout.connect(self._fit_preview_to_viewport)
        self._project_path: Path | None = None
        self._preview_full: QPixmap | None = None
        self._preview_zoom: float = 1.0
        self._preview_fit_size: tuple[int, int] | None = None
        self._wrap_pdf_rel: str = ""
        self._kdp_flag_guard = False
        if self._book:
            self.setWindowTitle(f"KDP Cover-Designer — {self._book.name}")
        else:
            self.setWindowTitle("KDP Cover-Designer")
        self.setObjectName("kdpCoverDialog")
        # Look & Feel: app-weites El-Pitugrafo-Theme (ui_qt.theme) — kein Dialog-QSS.
        # Vergrößerbar inkl. Maximieren (QDialog hat das unter Windows oft nicht).
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(False)
        self.setMinimumSize(1280, 720)
        try:
            _ww, _wh = resolve_window_size(load_settings())
        except OSError:
            _ww, _wh = 1540, 920
        self.resize(_ww, _wh)
        self._size_grip = attach_resize_grip(self)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        HelpBar.create_and_prepend_for_plugin(root, "kdp_cover")

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, stretch=1)

        left_scroll = QScrollArea()
        left_scroll.setObjectName("kdpCoverLeftScroll")
        left_scroll.setWidgetResizable(True)
        # Formular braucht volle Label-Spalte — kein Horizontal-Scroll.
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setFrameShape(left_scroll.Shape.NoFrame)
        left_scroll.setMinimumWidth(560)
        left_scroll.setMaximumWidth(700)
        left_scroll.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        left_scroll.setAutoFillBackground(True)
        left_host = QWidget()
        left_host.setObjectName("kdpCoverLeftHost")
        left_host.setMinimumWidth(540)
        left_host.setAutoFillBackground(True)
        left = QVBoxLayout(left_host)
        left.setContentsMargins(4, 8, 8, 8)
        left.setSpacing(10)
        left_scroll.setWidget(left_host)
        self._left_scroll = left_scroll
        # stretch=0: linke Spalte wächst nicht in die Vorschau hinein.
        body.addWidget(left_scroll, stretch=0)

        self._build_book_banner(left)

        form_box = CollapsibleSection("1. Maße festlegen (KDP)", expanded=True)
        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form_box.body_layout().addLayout(form)

        self.pages_spin = QSpinBox()
        self.pages_spin.setRange(MIN_PAGE_COUNT, MAX_PAGE_COUNT)
        self.pages_spin.setValue(200)
        self.pages_spin.setSuffix(" Seiten")
        self.pages_spin.setToolTip(
            "Seitenzahl der fertigen Innenwerk-PDF — bestimmt die Rückenbreite."
        )
        form.addRow("Seitenzahl:", self.pages_spin)

        self.paper_combo = QComboBox()
        for paper in PAPER_TYPES:
            self.paper_combo.addItem(paper.label, paper.id)
        idx = self.paper_combo.findData(DEFAULT_PAPER_TYPE_ID)
        if idx >= 0:
            self.paper_combo.setCurrentIndex(idx)
        form.addRow("Papierart:", self.paper_combo)

        self.trim_combo = QComboBox()
        preset = studio_paperback_preset()
        trim = preset.get("trim_mm") or {}
        studio_label = (
            f"Studio Paperback ({float(trim.get('width', 135)):g}×"
            f"{float(trim.get('height', 215)):g} mm)"
        )
        self.trim_combo.addItem(studio_label, _STUDIO_PAPERBACK_ID)
        for t in TRIM_SIZES:
            self.trim_combo.addItem(t.label, t.id)
        self.trim_combo.addItem("Benutzerdefiniert…", CUSTOM_TRIM_SIZE_ID)
        form.addRow("Trimmgröße:", self.trim_combo)

        # Ganze Zeile ein-/ausblenden (sonst bleibt das „×“ allein sichtbar).
        self.custom_trim_host = QWidget()
        custom_row = QHBoxLayout(self.custom_trim_host)
        custom_row.setContentsMargins(0, 0, 0, 0)
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
        self.custom_trim_host.setVisible(False)
        form.addRow("Breite × Höhe:", self.custom_trim_host)
        self._size_form = form

        self.size_error_label = QLabel("")
        self.size_error_label.setStyleSheet("color:#b91c1c;")
        self.size_error_label.setWordWrap(True)
        self.size_error_label.setVisible(False)
        form.addRow(self.size_error_label)

        self.size_result_label = QLabel("")
        self.size_result_label.setObjectName("kdpCoverSizeResult")
        self.size_result_label.setStyleSheet(
            "font-family: 'SF Mono','Consolas',monospace; font-size: 12px;"
        )
        self.size_result_label.setWordWrap(True)
        self.size_result_label.setMinimumWidth(0)
        self.size_result_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.size_result_label.setTextInteractionFlags(
            self.size_result_label.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow(self.size_result_label)

        bleed_note = QLabel(format_bleed_note())
        bleed_note.setStyleSheet("color:#5b6573; font-size:11px;")
        bleed_note.setWordWrap(True)
        form.addRow(bleed_note)

        self.btn_copy_size = QPushButton("Maße kopieren")
        self.btn_copy_size.setToolTip(
            "Rücken- und Gesamtmaße in die Zwischenablage "
            "(z. B. für Canva / KDP Cover Creator)."
        )
        self.btn_copy_size.clicked.connect(self._copy_size_result)
        form.addRow(self.btn_copy_size)
        left.addWidget(form_box)

        # --- Allgemein / Vorderseite / Rücken / Rückseite (einklappbar) ---
        general_sec = CollapsibleSection("2. Allgemein", expanded=True)
        general = QFormLayout()
        general.setSpacing(8)
        general_sec.body_layout().addLayout(general)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Sicher (empfohlen)", "safe")
        self.mode_combo.addItem("Frei (Experte)", "free")
        general.addRow("Modus:", self.mode_combo)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("nur PDF-/Projekt-Metadaten, nicht aufs Bild")
        self.title_edit.setToolTip(
            "Wird im Cover-Layout und als PDF-Dokumenttitel gespeichert — "
            "nicht auf das Cover-Bild gezeichnet (Text gehört in die Cover-Grafik)."
        )
        general.addRow("Titel (Meta):", self.title_edit)
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("nur PDF-/Projekt-Metadaten, nicht aufs Bild")
        self.author_edit.setToolTip(
            "Wird im Cover-Layout und als PDF-Autor gespeichert — "
            "nicht auf das Cover-Bild gezeichnet."
        )
        general.addRow("Autor (Meta):", self.author_edit)
        left.addWidget(general_sec)

        front_sec = CollapsibleSection("3. Vorderseite (Cover)", expanded=True)
        design_front = QFormLayout()
        design_front.setSpacing(8)
        front_sec.body_layout().addLayout(design_front)

        self.front_edit = QLineEdit()
        self.front_edit.setPlaceholderText("Vorderseiten-Bild…")
        front_row = QHBoxLayout()
        front_row.addWidget(self.front_edit)
        btn_front_asset = QPushButton("Asset…")
        btn_front_asset.setToolTip(
            "Bild aus dem Asset Manager wählen (Pool oder Buch-img/)."
        )
        btn_front_asset.clicked.connect(lambda: self._pick_image_via_asset("front"))
        front_row.addWidget(btn_front_asset)
        btn_front = QPushButton("…")
        btn_front.setFixedWidth(32)
        btn_front.setToolTip("Datei im Dateisystem wählen")
        btn_front.clicked.connect(self._browse_front)
        front_row.addWidget(btn_front)
        design_front.addRow("Vorderseite:", front_row)
        self.front_zoom_spin = QDoubleSpinBox()
        self.front_zoom_spin.setRange(1.0, 4.0)
        self.front_zoom_spin.setDecimals(2)
        self.front_zoom_spin.setSingleStep(0.05)
        self.front_zoom_spin.setValue(1.0)
        self.front_zoom_spin.setToolTip(
            "Vergrößern über Cover-Fit (≥ 1,0). Danach Ausschnitt mit Offset verschieben."
        )
        design_front.addRow("Front-Zoom:", self.front_zoom_spin)
        self.front_ox_spin = self._mm_spin()
        self.front_oy_spin = self._mm_spin()
        self.front_ox_spin.setToolTip("Ausschnitt horizontal verschieben (mm).")
        self.front_oy_spin.setToolTip("Ausschnitt vertikal verschieben (mm).")
        design_front.addRow(
            "Front-Verschiebung:", self._pair(self.front_ox_spin, self.front_oy_spin)
        )
        left.addWidget(front_sec)

        spine_sec = CollapsibleSection("4. Rücken", expanded=True)
        design_spine = QFormLayout()
        design_spine.setSpacing(8)
        spine_sec.body_layout().addLayout(design_spine)

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
        left.addWidget(spine_sec)
        self._sync_spine_badge_controls()

        back_sec = CollapsibleSection("5. Rückseite", expanded=True)
        design_back = QFormLayout()
        design_back.setSpacing(8)
        back_sec.body_layout().addLayout(design_back)

        back_color_host, self.back_color_edit = self._color_field(
            "#F5F0E8", max_width=100, tooltip="Rückseiten-Hintergrundfarbe"
        )
        design_back.addRow("Back-Farbe:", back_color_host)

        self.back_edit = QLineEdit()
        self.back_edit.setPlaceholderText("optional — Autor:innenfoto o. Ä.")
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
        design_back.addRow("Rückseite:", back_row)
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
        design_back.addRow("Back-Größe:", self.back_scale_spin)
        self.back_frame_check = QCheckBox("Rahmen um Rückseiten-Bild")
        design_back.addRow("", self.back_frame_check)
        self.back_frame_mm_spin = QDoubleSpinBox()
        self.back_frame_mm_spin.setRange(0.5, 20.0)
        self.back_frame_mm_spin.setDecimals(1)
        self.back_frame_mm_spin.setSingleStep(0.5)
        self.back_frame_mm_spin.setSuffix(" mm")
        self.back_frame_mm_spin.setValue(2.0)
        design_back.addRow("Rahmenstärke:", self.back_frame_mm_spin)
        frame_color_host, self.back_frame_color_edit = self._color_field(
            "#000000", max_width=100, tooltip="Rahmenfarbe"
        )
        self.back_frame_color_host = frame_color_host
        design_back.addRow("Rahmenfarbe:", frame_color_host)
        self.back_frame_check.toggled.connect(self._sync_back_frame_controls)
        self._sync_back_frame_controls()
        left.addWidget(back_sec)

        left.addWidget(self._build_compose_front_group())

        # Frei-Modus: nur Rücken-Text verschieben (Titel/Autor sind Meta, nicht gezeichnet)
        self.free_box = CollapsibleSection(
            "6. Frei-Modus: Rücken-Text (mm-Offset)", expanded=False
        )
        free_form = QFormLayout()
        self.free_box.body_layout().addLayout(free_form)
        self.title_ox = self._mm_spin()
        self.title_oy = self._mm_spin()
        self.author_ox = self._mm_spin()
        self.author_oy = self._mm_spin()
        self.spine_oy = self._mm_spin()
        self.title_scale = QDoubleSpinBox()
        self.title_scale.setRange(0.5, 3.0)
        self.title_scale.setSingleStep(0.1)
        self.title_scale.setDecimals(2)
        self.title_scale.setValue(1.0)
        # Unsichtbar halten (Modell-Felder), damit _build_layout/_apply_layout weiterlaufen.
        for w in (self.title_ox, self.title_oy, self.author_ox, self.author_oy, self.title_scale):
            w.hide()
        free_form.addRow("Rücken Y:", self.spine_oy)
        btn_reset_free = QPushButton("Offset zurücksetzen")
        btn_reset_free.clicked.connect(self._reset_free_offsets)
        free_form.addRow("", btn_reset_free)
        left.addWidget(self.free_box)
        self.free_box.setEnabled(False)

        self.show_overlays = QCheckBox(
            "Hilfslinien (Bleed / Trim / Safe / Rückenmitte / Barcode-Zone)"
        )
        self.show_overlays.setChecked(True)
        self.show_overlays.setToolTip(
            "Zeigt u. a. die KDP-Barcode-Reserve unten rechts auf der Rückseite "
            "(gelber Platzhalter — dort nichts Wichtiges platzieren)."
        )
        left.addWidget(self.show_overlays)

        persist_row = QHBoxLayout()
        self.btn_save_project = QPushButton("Cover-Layout speichern…")
        self.btn_save_project.setToolTip(
            "Öffnet Speichern unter <Buch>/export/kdp_cover/ "
            "mit Vorschlag {Buch}_kdp_cover.json — Dateiname frei änderbar "
            "(z. B. …_v2.json)."
        )
        self.btn_save_project.clicked.connect(self._save_project)
        self.btn_load_project = QPushButton("Cover-Layout laden…")
        self.btn_load_project.setToolTip(
            "Nur Cover-Layouts: *_kdp_cover.json / *_kdp_wrap_project.json "
            "(keine Elementsets oder Validierungs-JSON)."
        )
        self.btn_load_project.clicked.connect(self._load_project)
        persist_row.addWidget(self.btn_save_project)
        persist_row.addWidget(self.btn_load_project)
        left.addLayout(persist_row)

        element_row = QHBoxLayout()
        self.btn_save_elementset = QPushButton("Elementset speichern…")
        self.btn_save_elementset.setToolTip(
            "Nur die platzierten Vorderseiten-Elemente (Fade/Band/Titel/Fuß/Ecken-Banner/Badge) "
            "speichern — wiederverwendbar und weiter editierbar in einem anderen Buch.\n"
            "Vorschlagsname: {Buchtitel}_elementset.json unter export/kdp_cover/."
        )
        self.btn_save_elementset.clicked.connect(self._save_elementset)
        self.btn_load_elementset = QPushButton("Elementset laden…")
        self.btn_load_elementset.setToolTip(
            "Nur Elementsets: *_elementset.json "
            "(keine Cover-Layouts; Maße/Bilder bleiben erhalten)."
        )
        self.btn_load_elementset.clicked.connect(self._load_elementset)
        element_row.addWidget(self.btn_save_elementset)
        element_row.addWidget(self.btn_load_elementset)
        left.addLayout(element_row)

        self.project_path_label = QLabel("(kein Cover-Layout geladen)")
        self.project_path_label.setStyleSheet("color:#64748b; font-size:11px;")
        self.project_path_label.setWordWrap(True)
        left.addWidget(self.project_path_label)
        self.elementset_path_label = QLabel("")
        self.elementset_path_label.setStyleSheet("color:#64748b; font-size:11px;")
        self.elementset_path_label.setWordWrap(True)
        left.addWidget(self.elementset_path_label)

        self.status_label = QLabel("● bereit")
        self.status_label.setWordWrap(True)
        left.addWidget(self.status_label)

        self.issues_label = QLabel("")
        self.issues_label.setWordWrap(True)
        self.issues_label.setStyleSheet("font-size: 12px;")
        left.addWidget(self.issues_label)
        left.addStretch(1)

        right = QVBoxLayout()
        body.addLayout(right, stretch=1)

        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(6)
        zoom_hint = QLabel("Vorschau:")
        zoom_hint.setStyleSheet("color:#64748b;")
        zoom_row.addWidget(zoom_hint)
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setFixedWidth(32)
        self.btn_zoom_out.setToolTip("Verkleinern (Strg + Mausrad)")
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        zoom_row.addWidget(self.btn_zoom_out)
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setToolTip("Zoom relativ zur Einpassen-Größe")
        zoom_row.addWidget(self.zoom_label)
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedWidth(32)
        self.btn_zoom_in.setToolTip("Vergrößern (Strg + Mausrad)")
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        zoom_row.addWidget(self.btn_zoom_in)
        self.btn_zoom_fit = QPushButton("Einpassen")
        self.btn_zoom_fit.setToolTip("Auf Viewport einpassen (100 %)")
        self.btn_zoom_fit.clicked.connect(self._zoom_fit)
        zoom_row.addWidget(self.btn_zoom_fit)
        self.preview_print_dpi = QCheckBox("300 DPI")
        self.preview_print_dpi.setChecked(False)
        self.preview_print_dpi.setToolTip(
            "Vorschau in KDP-Druckauflösung rendern (langsamer, schärfer — "
            "z. B. zum Prüfen des Ecken-Banners). Export ist immer ≥ 300 DPI."
        )
        zoom_row.addWidget(self.preview_print_dpi)
        zoom_row.addStretch(1)
        right.addLayout(zoom_row)

        self.preview_label = QLabel("Vorschau erscheint nach Parameterwahl / Bildwahl.")
        self.preview_label.setObjectName("kdpCoverPreview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(400, 320)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_scroll.setWidget(self.preview_label)
        self._preview_scroll.setMinimumWidth(420)
        self._preview_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_scroll.viewport().installEventFilter(self)
        right.addWidget(self._preview_scroll, stretch=1)

        footer = QHBoxLayout()
        # 24px rechts frei für den SizeGrip (sonst liegt er auf PDF/Schließen).
        footer.setContentsMargins(0, 0, 24, 0)
        self.btn_refresh = QPushButton("Vorschau aktualisieren")
        self.btn_refresh.clicked.connect(self._refresh_preview)
        footer.addWidget(self.btn_refresh)
        self.attach_wrap_check = QCheckBox("Wrap-PDF am Buch hinterlegen")
        self.attach_wrap_check.setChecked(bool(self._book))
        self.attach_wrap_check.setEnabled(bool(self._book))
        self.attach_wrap_check.setToolTip(
            "Nach dem Export zusätzlich kanonisch unter "
            "export/kdp_cover/{Buch}_kdp_wrap.pdf speichern und im Cover-Layout merken.\n"
            "Nicht als Quarto-Kapitel / Innenwerk-Buchstruktur — nur KDP-Artefakt."
        )
        footer.addWidget(self.attach_wrap_check)
        footer.addStretch(1)
        self.btn_export = QPushButton("PDF exportieren…")
        self.btn_export.clicked.connect(self._export_pdf)
        footer.addWidget(self.btn_export)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

        if self._book:
            title, author = _read_quarto_title_author(self._book)
            if title:
                self.title_edit.setText(title)
            if author:
                self.author_edit.setText(author)
            img_dir = self._book / "img"
            if img_dir.is_dir():
                candidates = sorted(img_dir.glob("Deckblatt*.png")) + sorted(
                    img_dir.glob("Deckblatt*.jpg")
                )
                if candidates:
                    self.front_edit.setText(str(candidates[0]))

        for w in (
            self.pages_spin,
            self.paper_combo,
            self.trim_combo,
            self.custom_width_spin,
            self.custom_height_spin,
            self.show_overlays,
            self.preview_print_dpi,
            self.title_ox,
            self.title_oy,
            self.author_ox,
            self.author_oy,
            self.spine_oy,
            self.title_scale,
        ):
            if hasattr(w, "valueChanged"):
                w.valueChanged.connect(self._on_params_changed)
            if hasattr(w, "currentIndexChanged"):
                w.currentIndexChanged.connect(self._on_params_changed)
            if hasattr(w, "toggled"):
                w.toggled.connect(self._on_params_changed)

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.front_edit.editingFinished.connect(self._on_params_changed)
        self.back_edit.editingFinished.connect(self._on_params_changed)
        self.front_zoom_spin.valueChanged.connect(self._on_params_changed)
        self.front_ox_spin.valueChanged.connect(self._on_params_changed)
        self.front_oy_spin.valueChanged.connect(self._on_params_changed)
        self.back_scale_spin.valueChanged.connect(self._on_params_changed)
        self.back_frame_check.toggled.connect(self._on_params_changed)
        self.back_frame_mm_spin.valueChanged.connect(self._on_params_changed)
        # back/spine/compose-Farben: editingFinished bereits in _color_field verdrahtet
        self.title_edit.editingFinished.connect(self._on_params_changed)
        self.author_edit.editingFinished.connect(self._on_params_changed)
        self.spine_text_edit.editingFinished.connect(self._on_params_changed)
        self.spine_text_down_edit.editingFinished.connect(self._on_params_changed)
        self.spine_padding_spin.valueChanged.connect(self._on_params_changed)
        self.spine_badge_enabled.toggled.connect(self._on_params_changed)
        self.spine_badge_text.editingFinished.connect(self._on_params_changed)
        self.spine_badge_position.currentIndexChanged.connect(self._on_params_changed)
        self.spine_badge_scale.currentIndexChanged.connect(self._on_params_changed)
        self.title_color_edit.editingFinished.connect(self._on_params_changed)
        self._wire_compose_front_signals()
        self.trim_combo.currentIndexChanged.connect(self._on_trim_changed)

        self._on_trim_changed()
        self._sync_free_controls()
        if self._book:
            auto = resolve_existing_project_path(self._book)
            if auto is not None:
                try:
                    self._apply_layout(load_layout(auto), project_path=auto)
                except (OSError, ValueError, TypeError, KeyError):
                    pass
        self._apply_initial_front_image()
        self._refresh_binding_ui()
        # Einmalige Vorschau nach kompletter Init (Signale waren geblockt).
        self._params_guard = False
        self._on_params_changed()

    def apply_front_image(
        self,
        path: str | Path | None,
        *,
        disable_compose: bool = False,
    ) -> bool:
        """Set front image path, optionally disable layer compose, refresh preview.

        Returns True when the file exists and was applied.
        """
        if path is None or not str(path).strip():
            return False
        resolved = Path(str(path)).expanduser().resolve()
        if not resolved.is_file():
            return False
        self.front_edit.setText(str(resolved))
        if disable_compose and hasattr(self, "compose_enabled"):
            self.compose_enabled.setChecked(False)
        if not self._params_guard:
            self._preview_timer.stop()
            self._refresh_preview()
        return True

    def _apply_initial_front_image(self) -> None:
        """Optional Prefill (z. B. Stylecloud-Übergabe) — überschreibt Deckblatt/Projekt."""
        raw = self._initial_front_image
        if raw is None or not str(raw).strip():
            return
        # Schlagwortwolke = Hintergrund; Projekt-Layer (Titel/Bänder) bleiben darüber.
        ok = self.apply_front_image(raw, disable_compose=False)
        if not ok and hasattr(self, "status_label"):
            self.status_label.setText(
                f"● Übergabe-Bild nicht gefunden: {raw}"
            )
            self.status_label.setStyleSheet("color:#b91c1c; font-weight:600;")

    def _build_book_banner(self, parent_layout: QVBoxLayout) -> None:
        section = CollapsibleSection("Buch & KDP-Kanal", expanded=True)
        banner_layout = section.body_layout()

        if self._book:
            self.book_name_label = QLabel(f"Buch: {self._book.name}")
            self.book_name_label.setToolTip(str(self._book.resolve()))
            self.book_name_label.setStyleSheet("font-weight:600; color:#334b86;")
            self.book_name_label.setWordWrap(True)
        else:
            self.book_name_label = QLabel("Buch: (kein Buch geladen)")
            self.book_name_label.setStyleSheet("color:#8899bb;")
        banner_layout.addWidget(self.book_name_label)

        # El-Pitugrafo-Stil: Text auf der Checkbox + sichtbarer Indikator (App-Theme).
        self.kdp_channel_check = QCheckBox("KDP-Taschenbuch für dieses Buch")
        self.kdp_channel_check.setToolTip(
            "Schreibt bookconfig/distribution.json (Kanal kdp_paperback). "
            "Aktiviert die 1:1-Bindung an export/kdp_cover/{Buch}_kdp_cover.json — "
            "legt die Datei nicht automatisch an."
        )
        self.kdp_channel_check.setEnabled(bool(self._book))
        if self._book:
            self._kdp_flag_guard = True
            self.kdp_channel_check.setChecked(is_kdp_paperback(self._book))
            self._kdp_flag_guard = False
            self.kdp_channel_check.toggled.connect(self._on_kdp_flag_toggled)
        banner_layout.addWidget(self.kdp_channel_check)

        self.binding_status_label = QLabel("")
        self.binding_status_label.setWordWrap(True)
        self.binding_status_label.setStyleSheet("color:#5b6785; font-size:12px;")
        banner_layout.addWidget(self.binding_status_label)

        self.btn_open_cover_dir = QPushButton("Cover-Ordner öffnen…")
        self.btn_open_cover_dir.setToolTip(
            "Öffnet export/kdp_cover/ im Explorer (legt den Ordner bei Bedarf an)."
        )
        self.btn_open_cover_dir.clicked.connect(self._open_cover_export_dir)
        self.btn_open_cover_dir.setEnabled(bool(self._book))
        banner_layout.addWidget(self.btn_open_cover_dir)

        parent_layout.addWidget(section)

    def _refresh_binding_ui(self) -> None:
        if not self._book:
            self.binding_status_label.setText(
                "Ohne Buchprojekt kein kanonisches Cover-Layout."
            )
            self.binding_status_label.setStyleSheet("color:#64748b; font-size:12px;")
            return
        binding = resolve_cover_binding(self._book)
        self.binding_status_label.setText(binding_status_label(binding))
        self.binding_status_label.setToolTip(str(binding.canonical_path))
        if binding.status == "missing":
            self.binding_status_label.setStyleSheet(
                "color:#b45309; font-size:12px; font-weight:600;"
            )
        elif binding.status == "ready":
            self.binding_status_label.setStyleSheet(
                "color:#15803d; font-size:12px;"
            )
        else:
            self.binding_status_label.setStyleSheet("color:#64748b; font-size:12px;")

    def _on_kdp_flag_toggled(self, checked: bool) -> None:
        if self._kdp_flag_guard or not self._book:
            return
        try:
            set_kdp_paperback(self._book, bool(checked))
        except OSError as exc:
            QMessageBox.critical(self, "Kanal-Flag", str(exc))
            self._kdp_flag_guard = True
            self.kdp_channel_check.setChecked(is_kdp_paperback(self._book))
            self._kdp_flag_guard = False
            return
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            state = "an" if checked else "aus"
            log(f"KDP-Taschenbuch-Kanal {state}: {self._book.name}", "info")
        self._refresh_binding_ui()

    def _open_cover_export_dir(self) -> None:
        if not self._book:
            return
        out = self._default_export_dir()
        out.mkdir(parents=True, exist_ok=True)
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(QUrl.fromLocalFile(str(out)))
        except OSError as exc:
            QMessageBox.warning(self, "Ordner öffnen", str(exc))

    @staticmethod
    def _mm_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-80.0, 80.0)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setSuffix(" mm")
        spin.setValue(0.0)
        return spin

    @staticmethod
    def _pair(a: QWidget, b: QWidget) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(a)
        row.addWidget(b)
        return host

    def _color_field(
        self,
        initial: str = "#FFFFFF",
        *,
        max_width: int = 90,
        tooltip: str = "",
    ) -> tuple[QWidget, QLineEdit]:
        """Hex-Feld + Farbvorschau-Button → ``QColorDialog``."""
        edit = QLineEdit(initial)
        edit.setMaximumWidth(max_width)
        edit.setPlaceholderText("#RRGGBB")
        if tooltip:
            edit.setToolTip(tooltip)

        btn = QPushButton()
        btn.setFixedSize(28, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Farbe wählen…")
        btn.setFlat(False)

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
                color = QColor("#FFFFFF")
            return color

        def _sync_swatch() -> None:
            color = _parse()
            # Kontrast-Rahmen: helle Farben brauchen dunkleren Rand.
            border = "#334155" if color.lightness() > 180 else "#94a3b8"
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color.name()}; "
                f"border: 1px solid {border}; border-radius: 3px; }}"
            )

        def _pick() -> None:
            chosen = QColorDialog.getColor(_parse(), self, "Farbe wählen")
            if not chosen.isValid():
                return
            edit.setText(chosen.name().upper())
            _sync_swatch()
            self._on_params_changed()

        btn.clicked.connect(_pick)
        edit.textChanged.connect(lambda *_: _sync_swatch())
        edit.editingFinished.connect(self._on_params_changed)
        _sync_swatch()
        return host, edit

    def _nested_form(self, section: CollapsibleSection) -> QFormLayout:
        form = QFormLayout()
        form.setSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        section.body_layout().addLayout(form)
        return form

    def _build_compose_front_group(self) -> CollapsibleSection:
        """Experimentelle Vorderseiten-Layer (wegwerfbar mit compose_front-Paket)."""
        box = CollapsibleSection("7. Vorderseite gestalten (Layer)", expanded=False)
        box.setToolTip(
            "Optionale Layer über dem Vorderseiten-Foto "
            "(Fade, Band, Titel, Fuß, Ecken-Banner, Badge). "
            "Ausgeschaltet oder ohne Modul: Export wie bisher."
        )
        top = self._nested_form(box)

        self.compose_enabled = QCheckBox("Layer aktiv")
        self.compose_enabled.setChecked(False)
        top.addRow(self.compose_enabled)

        fade_sec = CollapsibleSection("Fade (oben / unten)", expanded=False)
        fade_form = self._nested_form(fade_sec)
        self.compose_fade_enabled = QCheckBox("Fade oben")
        self.compose_fade_enabled.setChecked(True)
        self.compose_fade_enabled.setToolTip(
            "Farbverlauf vom oberen Rand nach unten auslaufend."
        )
        fade_color_host, self.compose_fade_color = self._color_field("#F5F0E8")
        self.compose_fade_height = QDoubleSpinBox()
        self.compose_fade_height.setRange(5.0, 80.0)
        self.compose_fade_height.setValue(32.0)
        self.compose_fade_height.setSuffix(" %H")
        self.compose_fade_opacity = QDoubleSpinBox()
        self.compose_fade_opacity.setRange(0.0, 1.0)
        self.compose_fade_opacity.setSingleStep(0.05)
        self.compose_fade_opacity.setDecimals(2)
        self.compose_fade_opacity.setValue(0.92)
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
            "Farbverlauf vom unteren Rand nach oben auslaufend (analog Fade oben)."
        )
        fade_bottom_color_host, self.compose_fade_bottom_color = self._color_field(
            "#F5F0E8"
        )
        self.compose_fade_bottom_height = QDoubleSpinBox()
        self.compose_fade_bottom_height.setRange(5.0, 80.0)
        self.compose_fade_bottom_height.setValue(28.0)
        self.compose_fade_bottom_height.setSuffix(" %H")
        self.compose_fade_bottom_opacity = QDoubleSpinBox()
        self.compose_fade_bottom_opacity.setRange(0.0, 1.0)
        self.compose_fade_bottom_opacity.setSingleStep(0.05)
        self.compose_fade_bottom_opacity.setDecimals(2)
        self.compose_fade_bottom_opacity.setValue(0.85)
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
        box.body_layout().addWidget(fade_sec)

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
                self._pair(band_text_color_host, self.compose_band_text_size),
            ),
        )
        box.body_layout().addWidget(band_sec)

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
        self.compose_accent.setPlaceholderText("Akzent / Unterzeile")
        accent_color_host, self.compose_accent_color = self._color_field("#9B2C3E")
        self.compose_accent_size = QDoubleSpinBox()
        self.compose_accent_size.setRange(1.0, 12.0)
        self.compose_accent_size.setDecimals(1)
        self.compose_accent_size.setSingleStep(0.5)
        self.compose_accent_size.setValue(5.5)
        self.compose_accent_size.setSuffix(" %H")
        self.compose_accent_size.setToolTip("Schriftgröße Akzent (% der Front-Höhe).")
        self.compose_accent_top = QDoubleSpinBox()
        self.compose_accent_top.setRange(0.0, 100.0)
        self.compose_accent_top.setDecimals(1)
        self.compose_accent_top.setSingleStep(1.0)
        self.compose_accent_top.setValue(18.0)
        self.compose_accent_top.setSuffix(" %Y")
        self.compose_accent_top.setToolTip(
            "Eigene Startposition des Akzents von oben (% der Front-Höhe)."
        )
        self.compose_accent_bold = QCheckBox("Fett")
        self.compose_accent_bold.setToolTip("Akzent-Text fett darstellen")
        self.compose_accent_italic = QCheckBox("Kursiv")
        self.compose_accent_italic.setToolTip("Akzent-Text kursiv darstellen")
        titles_form.addRow(self.compose_titles_enabled)
        titles_form.addRow("Position 1+2:", self.compose_titles_top)
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
            self._pair(self.compose_lines_size, self.compose_lines_bold),
        )
        titles_form.addRow(
            "Akzent:",
            self._pair(self.compose_accent, accent_color_host),
        )
        titles_form.addRow(
            "Akzent Pos/Größe:",
            self._pair(
                self.compose_accent_top,
                self._pair(
                    self.compose_accent_size,
                    self._pair(self.compose_accent_bold, self.compose_accent_italic),
                ),
            ),
        )
        box.body_layout().addWidget(titles_sec)

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
        footer_form.addRow(self.compose_footer_enabled)
        footer_form.addRow("Fußzeile 1:", self.compose_footer_line1)
        footer_form.addRow("Fußzeile 2:", self.compose_footer_line2)
        footer_form.addRow(
            "Farbe / Position:",
            self._pair(footer_color_host, self.compose_footer_bottom),
        )
        box.body_layout().addWidget(footer_sec)

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
        self.compose_corner_pos = QComboBox()
        self.compose_corner_pos.addItem("Oben rechts", "top_right")
        self.compose_corner_pos.addItem("Unten rechts", "bottom_right")
        self.compose_corner_pos.setToolTip("Platzierung der Ecken-Markierung")
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
        corner_form.addRow("Schriftgröße:", self.compose_corner_font)
        corner_form.addRow("", self.compose_corner_icon)
        box.body_layout().addWidget(corner_sec)

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
        box.body_layout().addWidget(badge_sec)

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
            self._pair(text_edit, self._pair(text_color_host, bold_cb)),
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
            self.compose_lines_bold,
        ):
            w.toggled.connect(self._on_params_changed)
        for w in (
            self.compose_fade_height,
            self.compose_fade_opacity,
            self.compose_fade_bottom_height,
            self.compose_fade_bottom_opacity,
            self.compose_band_y,
            self.compose_band_h,
            self.compose_band_text_size,
            self.compose_lines_size,
            self.compose_titles_top,
            self.compose_accent_size,
            self.compose_accent_top,
            self.compose_footer_bottom,
            self.compose_corner_size,
            self.compose_corner_font,
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
        for w in (
            self.compose_band_text,
            self.compose_series,
            self.compose_main,
            self.compose_accent,
            self.compose_footer_line1,
            self.compose_footer_line2,
            self.compose_corner_text,
            self.compose_badge_image,
            self.compose_badge_text,
            self.compose_badge2_image,
            self.compose_badge2_text,
        ):
            w.editingFinished.connect(self._on_params_changed)

    def _browse_compose_badge(self, asset_key: str = "badge") -> None:
        start = str(self._book / "img") if self._book else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Badge-/Overlay-Bild", start, _IMAGE_FILTER
        )
        if not path:
            return
        if asset_key == "badge2":
            self.compose_badge2_image.setText(path)
        else:
            self.compose_badge_image.setText(path)
        self._on_params_changed()

    def _collect_front_compose(self) -> dict[str, Any]:
        from tools.kdp_cover.compose_front.model import FrontComposeSpec

        raw = {
            "enabled": self.compose_enabled.isChecked(),
            "fade": {
                "enabled": self.compose_fade_enabled.isChecked(),
                "color": self.compose_fade_color.text().strip() or "#F5F0E8",
                "height_pct": float(self.compose_fade_height.value()),
                "opacity": float(self.compose_fade_opacity.value()),
            },
            "fade_bottom": {
                "enabled": self.compose_fade_bottom_enabled.isChecked(),
                "color": self.compose_fade_bottom_color.text().strip() or "#F5F0E8",
                "height_pct": float(self.compose_fade_bottom_height.value()),
                "opacity": float(self.compose_fade_bottom_opacity.value()),
            },
            "band": {
                "enabled": self.compose_band_enabled.isChecked(),
                "y_pct": float(self.compose_band_y.value()),
                "height_pct": float(self.compose_band_h.value()),
                "color": self.compose_band_color.text().strip() or "#E8A0B0",
                "opacity": 1.0,
                "text": self.compose_band_text.text().strip(),
                "text_color": self.compose_band_text_color.text().strip() or "#FFFFFF",
                "text_size_pct": float(self.compose_band_text_size.value()),
            },
            "titles": {
                "enabled": self.compose_titles_enabled.isChecked(),
                "lines_size_pct": float(self.compose_lines_size.value()),
                "lines_bold": self.compose_lines_bold.isChecked(),
                "series": {
                    "text": self.compose_series.text().strip(),
                    "color": self.compose_series_color.text().strip() or "#1E3A5F",
                },
                "main": {
                    "text": self.compose_main.text().strip(),
                    "color": self.compose_main_color.text().strip() or "#1E3A5F",
                },
                "accent": {
                    "text": self.compose_accent.text().strip(),
                    "color": self.compose_accent_color.text().strip() or "#9B2C3E",
                    "size_pct": float(self.compose_accent_size.value()),
                    "italic": self.compose_accent_italic.isChecked(),
                    "bold": self.compose_accent_bold.isChecked(),
                },
                "top_pct": float(self.compose_titles_top.value()),
                "accent_top_pct": float(self.compose_accent_top.value()),
            },
            "footer": {
                "enabled": self.compose_footer_enabled.isChecked(),
                "line1": self.compose_footer_line1.text().strip(),
                "line2": self.compose_footer_line2.text().strip(),
                "color": self.compose_footer_color.text().strip() or "#FFFFFF",
                "bottom_pct": float(self.compose_footer_bottom.value()),
            },
            "corner_ribbon": {
                "enabled": self.compose_corner_enabled.isChecked(),
                "text": self.compose_corner_text.text().strip(),
                "color": self.compose_corner_color.text().strip() or "#3DBDB0",
                "text_color": self.compose_corner_text_color.text().strip() or "#FFFFFF",
                "size_pct": float(self.compose_corner_size.value()),
                "font_scale": float(self.compose_corner_font.value()) / 100.0,
                "show_icon": self.compose_corner_icon.isChecked(),
                "corner": str(self.compose_corner_pos.currentData() or "top_right"),
            },
            "badge": {
                "enabled": self.compose_badge_enabled.isChecked(),
                "image": self.compose_badge_image.text().strip(),
                "text": self.compose_badge_text.text().strip(),
                "text_color": self.compose_badge_text_color.text().strip() or "#1E3A5F",
                "bold": self.compose_badge_bold.isChecked(),
                "x_pct": float(self.compose_badge_x.value()),
                "y_pct": float(self.compose_badge_y.value()),
                "scale_pct": float(self.compose_badge_scale.value()),
                "rotation_deg": float(self.compose_badge_rot.value()),
            },
            "badge2": {
                "enabled": self.compose_badge2_enabled.isChecked(),
                "image": self.compose_badge2_image.text().strip(),
                "text": self.compose_badge2_text.text().strip(),
                "text_color": self.compose_badge2_text_color.text().strip() or "#1E3A5F",
                "bold": self.compose_badge2_bold.isChecked(),
                "x_pct": float(self.compose_badge2_x.value()),
                "y_pct": float(self.compose_badge2_y.value()),
                "scale_pct": float(self.compose_badge2_scale.value()),
                "rotation_deg": float(self.compose_badge2_rot.value()),
            },
        }
        return FrontComposeSpec.from_dict(raw).to_dict()

    def _apply_front_compose(self, data: dict[str, Any] | None) -> None:
        from tools.kdp_cover.compose_front.model import FrontComposeSpec

        was_guarded = self._params_guard
        self._params_guard = True
        try:
            spec = FrontComposeSpec.from_dict(data if isinstance(data, dict) else None)
            self.compose_enabled.setChecked(spec.enabled)
            self.compose_fade_enabled.setChecked(spec.fade.enabled)
            self.compose_fade_color.setText(spec.fade.color)
            self.compose_fade_height.setValue(spec.fade.height_pct)
            self.compose_fade_opacity.setValue(spec.fade.opacity)
            self.compose_fade_bottom_enabled.setChecked(spec.fade_bottom.enabled)
            self.compose_fade_bottom_color.setText(spec.fade_bottom.color)
            self.compose_fade_bottom_height.setValue(spec.fade_bottom.height_pct)
            self.compose_fade_bottom_opacity.setValue(spec.fade_bottom.opacity)
            self.compose_band_enabled.setChecked(spec.band.enabled)
            self.compose_band_y.setValue(spec.band.y_pct)
            self.compose_band_h.setValue(spec.band.height_pct)
            self.compose_band_color.setText(spec.band.color)
            self.compose_band_text.setText(spec.band.text)
            self.compose_band_text_color.setText(spec.band.text_color)
            self.compose_band_text_size.setValue(spec.band.text_size_pct)
            self.compose_titles_enabled.setChecked(spec.titles.enabled)
            self.compose_titles_top.setValue(spec.titles.top_pct)
            self.compose_series.setText(spec.titles.series.text)
            self.compose_series_color.setText(spec.titles.series.color)
            self.compose_main.setText(spec.titles.main.text)
            self.compose_main_color.setText(spec.titles.main.color)
            self.compose_lines_size.setValue(spec.titles.lines_size_pct)
            self.compose_lines_bold.setChecked(spec.titles.lines_bold)
            self.compose_accent.setText(spec.titles.accent.text)
            self.compose_accent_color.setText(spec.titles.accent.color)
            self.compose_accent_size.setValue(spec.titles.accent.size_pct)
            self.compose_accent_top.setValue(spec.titles.accent_top_pct)
            self.compose_accent_bold.setChecked(spec.titles.accent.bold)
            self.compose_accent_italic.setChecked(spec.titles.accent.italic)
            self.compose_footer_enabled.setChecked(spec.footer.enabled)
            self.compose_footer_line1.setText(spec.footer.line1)
            self.compose_footer_line2.setText(spec.footer.line2)
            self.compose_footer_color.setText(spec.footer.color)
            self.compose_footer_bottom.setValue(spec.footer.bottom_pct)
            self.compose_corner_enabled.setChecked(spec.corner_ribbon.enabled)
            self.compose_corner_text.setText(spec.corner_ribbon.text)
            self.compose_corner_color.setText(spec.corner_ribbon.color)
            self.compose_corner_text_color.setText(spec.corner_ribbon.text_color)
            self.compose_corner_size.setValue(spec.corner_ribbon.size_pct)
            self.compose_corner_font.setValue(
                float(getattr(spec.corner_ribbon, "font_scale", 1.0) or 1.0) * 100.0
            )
            self.compose_corner_icon.setChecked(spec.corner_ribbon.show_icon)
            cidx = self.compose_corner_pos.findData(spec.corner_ribbon.corner)
            if cidx >= 0:
                self.compose_corner_pos.setCurrentIndex(cidx)
            self.compose_badge_enabled.setChecked(spec.badge.enabled)
            self.compose_badge_image.setText(spec.badge.image)
            self.compose_badge_text.setText(spec.badge.text)
            self.compose_badge_text_color.setText(spec.badge.text_color)
            self.compose_badge_bold.setChecked(spec.badge.bold)
            self.compose_badge_x.setValue(spec.badge.x_pct)
            self.compose_badge_y.setValue(spec.badge.y_pct)
            self.compose_badge_scale.setValue(spec.badge.scale_pct)
            self.compose_badge_rot.setValue(spec.badge.rotation_deg)
            self.compose_badge2_enabled.setChecked(spec.badge2.enabled)
            self.compose_badge2_image.setText(spec.badge2.image)
            self.compose_badge2_text.setText(spec.badge2.text)
            self.compose_badge2_text_color.setText(spec.badge2.text_color)
            self.compose_badge2_bold.setChecked(spec.badge2.bold)
            self.compose_badge2_x.setValue(spec.badge2.x_pct)
            self.compose_badge2_y.setValue(spec.badge2.y_pct)
            self.compose_badge2_scale.setValue(spec.badge2.scale_pct)
            self.compose_badge2_rot.setValue(spec.badge2.rotation_deg)
        finally:
            self._params_guard = was_guarded

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

    def _on_mode_changed(self, *_args: Any) -> None:
        if self._mode_guard:
            return
        new_mode = self.mode_combo.currentData()
        if new_mode == "free":
            reply = QMessageBox.warning(
                self,
                "Frei-Modus",
                "Im Frei-Modus kannst du Texte frei verschieben. "
                "Safe-Zone und KDP-Regeln werden dann nur noch als Hinweis "
                "geprüft — der Export kann trotz Warnungen/Fehler erfolgen "
                "(nach zweistufiger Bestätigung).\n\n"
                "Trotzdem in den Frei-Modus wechseln?",
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

    def _sync_back_frame_controls(self) -> None:
        on = bool(self.back_frame_check.isChecked())
        self.back_frame_mm_spin.setEnabled(on)
        self.back_frame_color_host.setEnabled(on)

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

    def _resolve_base(self) -> Path:
        return self._book if self._book else Path.cwd()

    def _build_layout(self) -> CoverLayout:
        tw, th = self._current_trim_mm()
        mode = str(self.mode_combo.currentData() or "safe")
        layout = CoverLayout(
            page_count=int(self.pages_spin.value()),
            paper_type_id=str(self.paper_combo.currentData()),
            trim_width_mm=tw,
            trim_height_mm=th,
            mode=mode,  # type: ignore[arg-type]
            front_image=self.front_edit.text().strip(),
            back_image=self.back_edit.text().strip(),
            front_image_zoom=float(self.front_zoom_spin.value()),
            front_image_offset_x_mm=float(self.front_ox_spin.value()),
            front_image_offset_y_mm=float(self.front_oy_spin.value()),
            back_image_scale=max(0.05, min(1.0, float(self.back_scale_spin.value()) / 100.0)),
            back_image_frame=bool(self.back_frame_check.isChecked()),
            back_image_frame_mm=float(self.back_frame_mm_spin.value()),
            back_image_frame_color=self.back_frame_color_edit.text().strip() or "#000000",
            back_color=self.back_color_edit.text().strip() or "#FFFFFF",
            spine_color=self.spine_color_edit.text().strip() or "#222222",
            title=self.title_edit.text().strip(),
            author=self.author_edit.text().strip(),
            spine_text=self.spine_text_edit.text().strip(),
            spine_text_down=self.spine_text_down_edit.text().strip(),
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
            wrap_pdf=getattr(self, "_wrap_pdf_rel", "") or "",
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
            # Ungültige Front-/Back-Pfade aus altem Projekt nicht behalten
            # (sonst schwarze/fehlschlagende Vorschau ohne erkennbare Ursache).
            front_raw = (layout.front_image or "").strip()
            if front_raw:
                front_p = Path(front_raw)
                if not front_p.is_absolute() and self._book is not None:
                    front_p = (self._book / front_p).resolve()
                if not front_p.is_file():
                    self.front_edit.clear()
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
            self.back_color_edit.setText(layout.back_color)
            self.spine_color_edit.setText(layout.spine_color)
            self.title_edit.setText(layout.title)
            self.author_edit.setText(layout.author)
            self.spine_text_edit.setText(layout.spine_text)
            self.spine_text_down_edit.setText(
                str(getattr(layout, "spine_text_down", "") or "")
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
            self._wrap_pdf_rel = str(getattr(layout, "wrap_pdf", "") or "")
            self._project_path = project_path
            if project_path:
                self.project_path_label.setText(f"Cover-Layout: {project_path}")
            self._on_trim_changed()
            self._sync_free_controls()
            self._refresh_binding_ui()
        finally:
            self._mode_guard = False
            self._params_guard = was_guarded

    def _browse_front(self) -> None:
        start = str(self._book / "img") if self._book else ""
        path, _ = QFileDialog.getOpenFileName(self, "Vorderseiten-Bild", start, _IMAGE_FILTER)
        if path:
            self.front_edit.setText(path)
            self._on_params_changed()

    def _browse_back(self) -> None:
        start = str(self._book / "img") if self._book else ""
        path, _ = QFileDialog.getOpenFileName(self, "Rückseiten-Bild", start, _IMAGE_FILTER)
        if path:
            self.back_edit.setText(path)
            self._on_params_changed()

    def _pick_image_via_asset(self, target: str) -> None:
        """Bild über Asset-Manager-Picker wählen (Pool oder Buch-img/)."""
        from ui_qt.dialogs.asset_manager_dialog import pick_asset_image_qt

        titles = {
            "front": "Vorderseiten-Bild wählen",
            "back": "Rückseiten-Bild wählen",
            "badge": "Badge-/Overlay-Bild wählen",
            "badge2": "Badge-/Overlay-Bild 2 wählen",
        }
        chosen = pick_asset_image_qt(
            self._studio,
            self,
            title=titles.get(target, "Bild wählen"),
        )
        if chosen is None:
            return
        text = str(chosen)
        if target == "front":
            self.front_edit.setText(text)
        elif target == "back":
            self.back_edit.setText(text)
        elif target == "badge":
            self.compose_badge_image.setText(text)
        elif target == "badge2":
            self.compose_badge2_image.setText(text)
        self._on_params_changed()

    def _suggested_save_path(self) -> tuple[str, str]:
        """Startverzeichnis + Dateiname für Speichern/Laden-Dialoge."""
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
        """Validiert vor Speichern; bei Fehlern Dialog und ``None``."""
        report = validate_layout(layout, resolve_base=self._resolve_base())
        if report.errors:
            detail = "\n".join(f"• {i.message}" for i in report.errors)
            QMessageBox.critical(
                self,
                "Speichern gesperrt — Vorgaben verletzt",
                "Cover-Layout kann nicht gespeichert werden:\n\n"
                f"{detail}\n\n"
                "Bitte Safe-Zone, Barcode-Zone und Bildparameter korrigieren.",
            )
            return None
        return report

    def _save_project(self) -> None:
        """Dialog im Buch-Ordner export/kdp_cover; Dateiname als änderbarer Vorschlag."""
        layout = self._build_layout()
        if self._layout_validation_blocks_persist(layout) is None:
            return
        start_dir, start_name = self._suggested_save_path()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Cover-Layout speichern",
            str(Path(start_dir) / start_name),
            _PROJECT_SAVE_FILTER,
        )
        if not path:
            return
        out = Path(path)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            save_layout(layout, out)
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self._project_path = out
        self.project_path_label.setText(f"Cover-Layout: {out}")
        self._refresh_binding_ui()
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"KDP-Cover-Layout gespeichert: {out}", "success")

    def _load_project(self) -> None:
        start_dir, _start_name = self._suggested_save_path()
        path, _ = QFileDialog.getOpenFileName(
            self, "Cover-Layout laden", start_dir, _PROJECT_FILTER
        )
        if not path:
            return
        try:
            layout = load_layout(Path(path))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Laden fehlgeschlagen", str(exc))
            return
        self._apply_layout(layout, project_path=Path(path))
        self._on_params_changed()

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

    def _set_status(self, report: ValidationReport) -> None:
        if report.errors:
            self.status_label.setText(
                f"● Fehler ({len(report.errors)}) — Export im Sicher-Modus gesperrt"
            )
            self.status_label.setStyleSheet("color:#b91c1c; font-weight:600;")
            self.btn_export.setEnabled(self.mode_combo.currentData() == "free")
        elif report.warnings:
            self.status_label.setText(
                f"● Warnungen ({len(report.warnings)}) — Export möglich"
            )
            self.status_label.setStyleSheet("color:#b45309; font-weight:600;")
            self.btn_export.setEnabled(True)
        else:
            self.status_label.setText("● OK — bereit zum Export")
            self.status_label.setStyleSheet("color:#15803d; font-weight:600;")
            self.btn_export.setEnabled(bool(self.front_edit.text().strip()))

        lines: list[str] = []
        for issue in report.issues:
            mark = "⛔" if issue.severity == "error" else "⚠"
            lines.append(f"{mark} [{issue.code}] {issue.message}")
        self.issues_label.setText("\n".join(lines))

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

    def _on_params_changed(self, *_args: Any) -> None:
        if self._params_guard:
            return
        if not self._update_size_panel():
            self.status_label.setText("● Fehler in den Maßen")
            self.status_label.setStyleSheet("color:#b91c1c; font-weight:600;")
            self.btn_export.setEnabled(False)
            return

        layout = self._build_layout()
        try:
            geo = build_geometry(
                page_count=layout.page_count,
                paper_type_id=layout.paper_type_id,
                trim_width_mm=layout.trim_width_mm,
                trim_height_mm=layout.trim_height_mm,
            )
        except ValueError as exc:
            self.size_error_label.setText(str(exc))
            self.size_error_label.setVisible(True)
            self.status_label.setText("● Fehler")
            self.status_label.setStyleSheet("color:#b91c1c; font-weight:600;")
            self.btn_export.setEnabled(False)
            return

        report = validate_layout(layout, geometry=geo, resolve_base=self._resolve_base())
        self._set_status(report)
        if layout.front_image:
            # Debounce: viele Spinbox-Signale sonst → Dutzende Vollrenders (UI-Freeze).
            self._preview_timer.start()
        else:
            self._preview_timer.stop()
            self._preview_full = None
            self.preview_label.setText("Bitte Vorderseiten-Bild wählen.")
            self.preview_label.setPixmap(QPixmap())

    def _effective_preview_dpi(self) -> float:
        """Bildschirm-Vorschau (120) oder wahlweise Druckauflösung (300)."""
        if getattr(self, "preview_print_dpi", None) is not None and self.preview_print_dpi.isChecked():
            return float(DEFAULT_EXPORT_DPI)
        return float(_PREVIEW_DPI)

    def _refresh_preview(self) -> None:
        layout = self._build_layout()
        if not layout.front_image:
            self._preview_full = None
            self.preview_label.setText("Bitte Vorderseiten-Bild wählen.")
            self.preview_label.setPixmap(QPixmap())
            return
        front_path = Path(layout.front_image.strip())
        if not front_path.is_absolute() and self._book is not None:
            front_path = (self._book / front_path).resolve()
        if not front_path.is_file():
            self._preview_full = None
            self.preview_label.setText(
                f"Vorderseiten-Bild fehlt:\n{front_path}"
            )
            self.preview_label.setPixmap(QPixmap())
            return
        dpi = self._effective_preview_dpi()
        try:
            geo = build_geometry(
                page_count=layout.page_count,
                paper_type_id=layout.paper_type_id,
                trim_width_mm=layout.trim_width_mm,
                trim_height_mm=layout.trim_height_mm,
            )
            image = render_wrap_image(
                layout,
                geometry=geo,
                dpi=dpi,
                resolve_base=self._resolve_base(),
            )
        except (OSError, ValueError) as exc:
            self._preview_full = None
            self.preview_label.setText(f"Vorschau fehlgeschlagen:\n{exc}")
            self.preview_label.setPixmap(QPixmap())
            return

        pix = _pil_to_qpixmap(image)
        if self.show_overlays.isChecked():
            pix = _draw_overlays(pix, geo, dpi)
        self._preview_full = pix
        self._preview_fit_size = None
        self._fit_preview_to_viewport()

    def _persist_window_geometry(self) -> None:
        try:
            save_settings(
                {
                    "window_width": int(self.width()),
                    "window_height": int(self.height()),
                }
            )
        except OSError:
            pass

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._persist_window_geometry()
        super().closeEvent(event)

    def accept(self) -> None:
        self._persist_window_geometry()
        super().accept()

    def reject(self) -> None:
        self._persist_window_geometry()
        super().reject()

    def _fit_preview_to_viewport(self) -> None:
        """Vorschau skalieren: Einpassen × Zoomfaktor."""
        full = self._preview_full
        if full is None or full.isNull():
            return
        viewport = self._preview_scroll.viewport().size()
        avail_w = max(200, viewport.width() - 16)
        avail_h = max(160, viewport.height() - 16)
        zoom = max(_PREVIEW_ZOOM_MIN, min(_PREVIEW_ZOOM_MAX, float(self._preview_zoom)))
        key = (avail_w, avail_h, int(round(zoom * 1000)), int(full.cacheKey()))
        if self._preview_fit_size == key and not self.preview_label.pixmap().isNull():
            return
        if abs(zoom - 1.0) < 1e-9:
            scaled = full.scaled(
                avail_w,
                avail_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            fit = full.scaled(
                avail_w,
                avail_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            scaled = full.scaled(
                max(1, int(round(fit.width() * zoom))),
                max(1, int(round(fit.height() * zoom))),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        self._preview_fit_size = key
        # Bei Zoom > 1 Scrollbalken erlauben, sonst einpassen.
        self._preview_scroll.setWidgetResizable(zoom <= 1.0 + 1e-9)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")
        if zoom > 1.0:
            self.preview_label.setMinimumSize(scaled.size())
            self.preview_label.resize(scaled.size())
        else:
            self.preview_label.setMinimumSize(0, 0)
            self.preview_label.adjustSize()
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        pct = int(round(max(_PREVIEW_ZOOM_MIN, min(_PREVIEW_ZOOM_MAX, self._preview_zoom)) * 100))
        self.zoom_label.setText(f"{pct} %")

    def _set_preview_zoom(self, zoom: float) -> None:
        self._preview_zoom = max(_PREVIEW_ZOOM_MIN, min(_PREVIEW_ZOOM_MAX, float(zoom)))
        self._fit_preview_to_viewport()

    def _zoom_in(self) -> None:
        self._set_preview_zoom(self._preview_zoom * _PREVIEW_ZOOM_STEP)

    def _zoom_out(self) -> None:
        self._set_preview_zoom(self._preview_zoom / _PREVIEW_ZOOM_STEP)

    def _zoom_fit(self) -> None:
        self._set_preview_zoom(1.0)

    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802
        if (
            obj is self._preview_scroll.viewport()
            and event.type() == event.Type.Wheel
            and isinstance(event, QWheelEvent)
        ):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                if delta > 0:
                    self._zoom_in()
                elif delta < 0:
                    self._zoom_out()
                return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Debounce: Beim Öffnen feuern Dutzende resizeEvents — sonst Gezucke.
        self._fit_timer.start()

    def _default_export_dir(self) -> Path:
        """KDP-Artefakte: Layout, Elementset und Wrap-PDF am selben Ort."""
        if self._book:
            return self._book / "export" / "kdp_cover"
        return Path.cwd() / "export" / "kdp_cover"

    def _suggested_wrap_pdf_path(self) -> Path:
        """Vorschlag: ``{Buchname}_kdp_wrap.pdf`` (ohne Zeitstempel — überschreibbar)."""
        if self._book:
            return default_wrap_pdf_path(self._book)
        title = self.title_edit.text().strip()
        from tools.kdp_cover.model import sanitize_book_filename_stem

        stem = sanitize_book_filename_stem(title or "KDP_Wrap")
        return self._default_export_dir() / f"{stem}_kdp_wrap.pdf"

    def _confirm_export(self, layout: CoverLayout, report: ValidationReport) -> bool:
        mode = layout.mode
        hard_codes = {
            "back_image_safe_zone",
            "back_image_barcode",
            "back_image_dpi",
            "back_image_missing",
            "back_image_unreadable",
            "back_image_frame_color",
            "front_image_zoom",
            "front_image_missing",
            "front_image_dpi",
        }
        hard = [i for i in report.errors if i.code in hard_codes]
        if hard:
            detail = "\n".join(f"• {i.message}" for i in hard)
            QMessageBox.critical(
                self,
                "Export gesperrt — Vorgaben verletzt",
                f"{detail}\n\nBitte korrigieren (Safe-Zone / Barcode / Bild).",
            )
            return False

        if mode == "safe" and not report.ok_for_safe_export:
            QMessageBox.warning(
                self,
                "Validierung",
                "Im Sicher-Modus ist der Export bei Fehlern gesperrt.\n"
                "Bitte Fehler beheben oder Modus „Frei“ wählen.",
            )
            return False

        issues = report.warnings + report.errors
        if not issues:
            return True

        detail = "\n".join(f"- [{i.severity}] {i.message}" for i in issues)
        if mode == "free":
            dlg = _FreeExportConfirmDialog(self, detail)
            return dlg.exec() == QDialog.DialogCode.Accepted

        reply = QMessageBox.question(
            self,
            "Warnungen",
            f"Warnungen:\n\n{detail}\n\nTrotzdem exportieren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _export_pdf(self) -> None:
        layout = self._build_layout()
        report = validate_layout(layout, resolve_base=self._resolve_base())
        if not self._confirm_export(layout, report):
            return

        out_dir = self._default_export_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        suggested = self._suggested_wrap_pdf_path()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Wrap-PDF speichern",
            str(suggested),
            "PDF (*.pdf)",
        )
        if not path:
            return
        out_pdf = Path(path)
        validation_json = out_pdf.with_name(out_pdf.stem + "_validation.json")
        project_json = out_pdf.with_name(out_pdf.stem + "_project.json")
        canonical = default_project_path(self._book) if self._book else None
        attached_note = ""
        deploy_source = out_pdf
        try:
            export_wrap_pdf(
                layout,
                out_pdf,
                dpi=float(DEFAULT_EXPORT_DPI),
                resolve_base=self._resolve_base(),
                validation_json=validation_json,
                require_safe=(layout.mode == "safe"),
            )
            if self._book and self.attach_wrap_check.isChecked():
                from tools.kdp_cover.attach_wrap import (
                    attach_wrap_pdf_to_book,
                    wrap_pdf_relpath,
                )

                attached = attach_wrap_pdf_to_book(self._book, out_pdf)
                self._wrap_pdf_rel = wrap_pdf_relpath(self._book, attached)
                layout.wrap_pdf = self._wrap_pdf_rel
                attached_note = f"\nAm Buch hinterlegt: {attached}"
                deploy_source = attached
            save_layout(layout, project_json)
            if canonical is not None:
                save_layout(layout, canonical)
                self._project_path = canonical
                self.project_path_label.setText(f"Cover-Layout: {canonical}")
                self._refresh_binding_ui()
        except (OSError, ValueError, FileNotFoundError) as exc:
            QMessageBox.critical(self, "Export fehlgeschlagen", str(exc))
            return

        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"KDP-Cover exportiert: {out_pdf}", "success")
        self._show_export_success(
            out_pdf=out_pdf,
            validation_name=validation_json.name,
            project_name=project_json.name,
            attached_note=attached_note,
            deploy_source=deploy_source,
        )

    def _configured_deploy_folder(self) -> str:
        import app_config as _app_config
        from ui_qt.book_workspace import repo_root

        try:
            cfg = _app_config.read_config(repo_root() / "app_config.json")
        except (OSError, TypeError, ValueError):
            return ""
        return str(cfg.get("pdf_deploy_folder") or "").strip()

    def _copy_wrap_to_configured_folder(self, source_pdf: Path) -> None:
        """Wie PDF Manager: „Copy to configured folder“ via ``pdf_deploy_folder``."""
        from tools.mapping_manager.deploy import deploy_pdf, resolve_pdf_deploy_folder

        src = Path(source_pdf)
        if not src.is_file():
            QMessageBox.warning(self, "Deploy", f"PDF nicht gefunden:\n{src}")
            return
        dest_dir = resolve_pdf_deploy_folder(self._configured_deploy_folder())
        if dest_dir is None:
            QMessageBox.warning(
                self,
                "Deploy",
                "Kein Deploy-Ziel gefunden.\n\n"
                "Bitte unter Tools → Studio-Konfiguration den Schlüssel "
                "„pdf_deploy_folder“ setzen "
                "(z. B. WEB.DE Online-Speicher\\…\\__Projekte\\IFJN\\PDF).",
            )
            return
        if (dest_dir / src.name).exists():
            if (
                QMessageBox.question(
                    self,
                    "Deploy",
                    f"Datei existiert bereits und wird überschrieben:\n{src.name}\n\n"
                    f"Ziel:\n{dest_dir}",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        try:
            dest = deploy_pdf(src, dest_dir, overwrite=True)
        except (OSError, FileNotFoundError, FileExistsError) as exc:
            QMessageBox.critical(self, "Deploy fehlgeschlagen", str(exc))
            return
        log = getattr(self._studio, "log", None) if self._studio else None
        if callable(log):
            log(f"Wrap-PDF deployed → {dest}", "success")
        QMessageBox.information(
            self,
            "Deploy",
            f"Copy to configured folder:\n{dest}",
        )

    def _show_export_success(
        self,
        *,
        out_pdf: Path,
        validation_name: str,
        project_name: str,
        attached_note: str,
        deploy_source: Path,
    ) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Export")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(
            f"Wrap-PDF geschrieben:\n{out_pdf}\n\n"
            f"Validierung: {validation_name}\n"
            f"Cover-Layout: {project_name}"
            f"{attached_note}"
        )
        box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        deploy_btn = box.addButton(
            "Copy to configured folder",
            QMessageBox.ButtonRole.ActionRole,
        )
        deploy_btn.setToolTip(
            "Wrap-PDF in den konfigurierten Deploy-Ordner kopieren "
            "(Studio-Konfiguration: pdf_deploy_folder) — wie im PDF Manager."
        )
        box.exec()
        if box.clickedButton() is deploy_btn:
            self._copy_wrap_to_configured_folder(deploy_source)


def open_kdp_cover_qt(
    studio: Any = None,
    parent: Optional[QWidget] = None,
    *,
    front_image: str | Path | None = None,
    disable_compose: bool | None = None,
    **_kwargs: Any,
) -> int:
    """Open KDP Cover dialog.

    ``front_image``: Prefill Vorderseite (z. B. Stylecloud-PNG) as background.
    ``disable_compose``: when True, turn off front layer compose. Default False
    so title/band/badge layers stay on top of a Stylecloud handoff image.
    """
    dlg = KdpCoverQtDialog(studio, parent, front_image=front_image)
    if front_image is not None:
        turn_off = False if disable_compose is None else bool(disable_compose)
        dlg.apply_front_image(front_image, disable_compose=turn_off)
        # Nach Show einmal hard refresh (Viewport-Größe erst dann korrekt).
        QTimer.singleShot(0, dlg._refresh_preview)
    return int(dlg.exec())


__all__ = ["KdpCoverQtDialog", "open_kdp_cover_qt", "_FreeExportConfirmDialog"]
