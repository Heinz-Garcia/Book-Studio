"""Qt-Dialog: KDP Wrap-Cover-Designer (Phase 2–5).

Geschäftslogik in ``tools.kdp_cover``. Persistenz: Cover-Zwischenstand,
Kanal-Flag in ``bookconfig/distribution.json``, zweistufige Export-Bestätigung.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
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
)
from tools.kdp_cover.constants import (
    SPINE_BADGE_SCALE_STEPS,
    SPINE_EDGE_PADDING_MIN_MM,
)
from tools.kdp_cover.model import (
    load_layout,
    resolve_existing_project_path,
)
from tools.kdp_cover.settings import (
    load_settings,
    resolve_active_tab,
    resolve_body_splitter_sizes,
    resolve_window_size,
)
from tools.kdp_specs import format_bleed_note, studio_paperback_preset
from tools.production_uuid import normalize_uuid
from ui_qt.autonomous_window import (
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)
from ui_qt.widgets.collapsible_section import CollapsibleSection
from ui_qt.widgets.help_bar import HelpBar
from ui_qt.widgets.resize_grip import attach_resize_grip
from ui_qt.dialogs.kdp_cover.form_widgets import FormWidgetsMixin
from ui_qt.dialogs.kdp_cover.binding import BindingMixin
from ui_qt.dialogs.kdp_cover.dimensions import DimensionsMixin
from ui_qt.dialogs.kdp_cover.front import FrontMixin
from ui_qt.dialogs.kdp_cover.spine_back import SpineBackMixin
from ui_qt.dialogs.kdp_cover.layout_io import LayoutIOMixin
from ui_qt.dialogs.kdp_cover.preview import PreviewMixin
from ui_qt.dialogs.kdp_cover.export import ExportMixin
from ui_qt.dialogs.kdp_cover.common import (
    _STUDIO_PAPERBACK_ID,
    _PREVIEW_DEBOUNCE_MS,
    _PREVIEW_FIT_DEBOUNCE_MS,
    _PROJECT_FILTER,
    _ELEMENT_SET_FILTER,
    _PROJECT_SAVE_FILTER,
    _ELEMENT_SET_SAVE_FILTER,
    _STATUS_EXPORT_TOOLTIP,
    _book_root,
    _read_quarto_title_author,
    _draw_overlays,
)
from ui_qt.dialogs.kdp_cover.dialogs import (
    _DeployFolderDialog,
    _ExportSuccessDialog,
    _FreeExportConfirmDialog,
)

_active: list["KdpCoverQtDialog"] = []


class KdpCoverQtDialog(
    FormWidgetsMixin, BindingMixin, DimensionsMixin, FrontMixin, SpineBackMixin, LayoutIOMixin, PreviewMixin, ExportMixin,
    QDialog,
):
    def __init__(
        self,
        studio: Any = None,
        parent: Optional[QWidget] = None,
        *,
        front_image: str | Path | None = None,
    ) -> None:
        super().__init__(None)
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
        self._production_uuid: str = ""
        self._cover_label: str = ""
        self._cover_role: str = "primary"
        self._uuid_origin_label: str = ""
        self._uuid_source_kinds: list[str] = []
        if self._book:
            self.setWindowTitle(f"KDP Cover-Designer — {self._book.name}")
        else:
            self.setWindowTitle("KDP Cover-Designer")
        self.setObjectName("kdpCoverDialog")
        # Look & Feel: app-weites El-Pitugrafo-Theme (ui_qt.theme) — kein Dialog-QSS.
        # Window flags come from prepare_autonomous_window (min/max/close).
        self.setSizeGripEnabled(False)
        self.setMinimumSize(1280, 720)
        try:
            self._session_settings = load_settings()
            _ww, _wh = resolve_window_size(self._session_settings)
            self._restore_maximized = bool(
                self._session_settings.get("window_maximized")
            )
            self._loaded_splitter_sizes = resolve_body_splitter_sizes(
                self._session_settings
            )
        except OSError:
            self._session_settings = {}
            _ww, _wh = 1540, 920
            self._restore_maximized = False
            self._loaded_splitter_sizes = [620, 880]
        self.resize(_ww, _wh)
        self._loaded_size = (_ww, _wh)
        # Bis nach dem ersten Show nichts persistieren — sonst überschreiben
        # Zwischengrößen (sizeHint / Stretch) die gespeicherte Session.
        self._suppress_geometry_persist = True
        self._geometry_restore_scheduled = False
        self._size_grip = attach_resize_grip(self)
        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.setInterval(400)
        self._geometry_save_timer.timeout.connect(self._persist_window_geometry)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        HelpBar.create_and_prepend_for_plugin(root, "kdp_cover")

        self._body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_splitter.setObjectName("kdpCoverBodySplitter")
        self._body_splitter.setChildrenCollapsible(False)
        self._body_splitter.setHandleWidth(8)
        self._body_splitter.setStyleSheet(
            "QSplitter#kdpCoverBodySplitter::handle {"
            "  background: #c8d3ec;"
            "}"
            "QSplitter#kdpCoverBodySplitter::handle:hover {"
            "  background: #5a7dd6;"
            "}"
        )
        root.addWidget(self._body_splitter, stretch=1)

        left_panel = QWidget()
        left_panel.setObjectName("kdpCoverLeftPanel")
        left_panel.setMinimumWidth(360)
        left_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        left_panel.setAutoFillBackground(True)
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(4, 8, 8, 8)
        left.setSpacing(8)
        self._body_splitter.addWidget(left_panel)

        self._build_book_banner(left)

        self._editor_tabs = QTabWidget()
        self._editor_tabs.setObjectName("kdpCoverEditorTabs")
        self._editor_tabs.setDocumentMode(True)
        self._editor_tabs.tabBar().setDrawBase(False)
        self._editor_tabs.setMovable(False)
        self._editor_tabs.setUsesScrollButtons(True)
        self._editor_tabs.setElideMode(Qt.TextElideMode.ElideNone)
        # documentMode + Pane-border-top zeichnet sonst einen Strich quer durch
        # die Tab-Koepfe (nur der aktive Tab deckt ihn mit Weiss ab).
        self._editor_tabs.setStyleSheet(
            """
            QTabWidget#kdpCoverEditorTabs::pane {
                border: 1px solid #c8d3ec;
                border-top: 0px;
                border-radius: 0 0 8px 8px;
                background: #ffffff;
                margin-top: -1px;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar {
                border: none;
                background: transparent;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab {
                background: #eef1f8;
                color: #334b86;
                border: 1px solid #c8d3ec;
                border-bottom-color: #ffffff;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                min-width: 68px;
                padding: 8px 10px;
                margin-right: 2px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab:selected {
                background: #ffffff;
                color: #1c2740;
                border-color: #c8d3ec;
                border-bottom-color: #ffffff;
                margin-bottom: -1px;
                padding-bottom: 9px;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab:!selected {
                margin-top: 2px;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab:hover:!selected {
                background: #e2e8f6;
                color: #1c2740;
            }
            QTabWidget#kdpCoverEditorTabs QTabBar::tab:disabled {
                color: #8899bb;
                background: #f3f5fa;
            }
            """
        )
        left.addWidget(self._editor_tabs, stretch=1)

        # --- Tab: Maße (kurz — ohne ScrollArea, sonst oft nutzlose Scrollbar) ---
        tab_size, size_body = self._make_editor_tab(scrollable=False)
        size_hint = QLabel(
            "Trimmgröße, Papier und Seitenzahl — die Rückenbreite folgt daraus."
        )
        size_hint.setWordWrap(True)
        size_hint.setStyleSheet("color:#5b6573; font-size:12px;")
        size_body.addWidget(size_hint)
        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        size_body.addLayout(form)

        self.pages_spin = QSpinBox()
        self.pages_spin.setRange(MIN_PAGE_COUNT, MAX_PAGE_COUNT)
        self.pages_spin.setValue(200)
        self.pages_spin.setSuffix(" Seiten")
        self.pages_spin.setToolTip(
            "Seitenzahl der fertigen Innenwerk-PDF — bestimmt die Rückenbreite."
        )
        self.pages_estimated_check = QCheckBox("geschätzt")
        self.pages_estimated_check.setToolTip(
            "Seitenzahl ist nur eine Schätzung (Innenwerk noch nicht fertig). "
            "Die Ampel erinnert daran, die Rückenbreite vor dem Upload abzugleichen."
        )
        self.btn_pages_estimate = QPushButton("Schätzen…")
        self.btn_pages_estimate.setToolTip(
            "Ungefähre Seitenzahl und Papierart eingeben (Rückenbreite live)."
        )
        self.btn_pages_estimate.clicked.connect(self._open_page_count_estimate)
        self.btn_pages_from_pdf = QPushButton("Aus Innenwerk-PDF")
        self.btn_pages_from_pdf.setToolTip(
            "Seitenzahl der neuesten gerenderten Buch-PDF übernehmen."
        )
        self.btn_pages_from_pdf.clicked.connect(self._take_interior_page_count)
        pages_row = QHBoxLayout()
        pages_row.setSpacing(6)
        pages_row.addWidget(self.pages_spin)
        pages_row.addWidget(self.pages_estimated_check)
        pages_row.addWidget(self.btn_pages_estimate)
        pages_row.addWidget(self.btn_pages_from_pdf)
        pages_row.addStretch(1)
        form.addRow("Seitenzahl:", pages_row)
        self.pages_source_label = QLabel("")
        self.pages_source_label.setObjectName("kdpPagesSource")
        self.pages_source_label.setWordWrap(True)
        self.pages_source_label.setStyleSheet("color:#5b6573; font-size:11px;")
        form.addRow("", self.pages_source_label)

        from tools.kdp_cover.page_count import paper_description

        self.paper_combo = QComboBox()
        for paper in PAPER_TYPES:
            self.paper_combo.addItem(paper_description(paper.id, paper.label), paper.id)
        idx = self.paper_combo.findData(DEFAULT_PAPER_TYPE_ID)
        if idx >= 0:
            self.paper_combo.setCurrentIndex(idx)
        form.addRow("Papierart:", self.paper_combo)

        self.trim_combo = QComboBox()
        preset = studio_paperback_preset()
        trim = preset.get("trim_mm") or {}
        studio_label = (
            f"Studio Paperback ({float(trim.get('width', 135)):g}×"
            f"{float(trim.get('height', 215)):g} mm) · BoD/DE-Taschenbuch"
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
        self._editor_tabs.addTab(tab_size, "Maße")
        self._editor_tabs.setTabToolTip(
            self._editor_tabs.count() - 1, "1 · Maße festlegen (KDP)"
        )

        # --- Tab: Allgemein ---
        tab_general, general_body = self._make_editor_tab()
        general = QFormLayout()
        general.setSpacing(8)
        general_body.addLayout(general)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Sicher (empfohlen)", "safe")
        self.mode_combo.addItem("Experte", "free")
        self.mode_combo.setToolTip(
            "Sicher: Texte in festen Safe-Slots.\n"
            "Experte: Feinjustage per mm-Offset (Tab „Experte“); "
            "Export trotz Warnungen nur nach Bestätigung."
        )
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
        self._editor_tabs.addTab(tab_general, "Allgemein")
        self._editor_tabs.setTabToolTip(
            self._editor_tabs.count() - 1, "2 · Allgemein (Modus & Metadaten)"
        )

        # --- Tab: Vorderseite ---
        tab_front, front_body = self._make_editor_tab()
        front_hint = QLabel(
            "Bildmodus wählbar: nur Farbe, goldener Schnitt oder vollflächig. "
            "Wortwolke: Stylecloud → Übergabe hierher."
        )
        front_hint.setWordWrap(True)
        front_hint.setStyleSheet("color:#64748b; font-size:12px;")
        front_body.addWidget(front_hint)
        design_front = QFormLayout()
        design_front.setSpacing(8)
        front_body.addLayout(design_front)

        front_color_host, self.front_color_edit = self._color_field(
            "#1e3a5f",
            max_width=100,
            tooltip=(
                "Vorderseiten-Farbe: allein bei „Kein Bild“, "
                "unter dem Bildband bei „goldener Schnitt“, "
                "Unterlage bei Vollbild/Wortwolke."
            ),
        )
        design_front.addRow("Front-Farbe:", front_color_host)

        self.front_mode_none = QRadioButton("Kein Bild (nur Farbe)")
        self.front_mode_top_third = QRadioButton("Bild im goldenen Schnitt")
        self.front_mode_full = QRadioButton("Bild vollflächig")
        self.front_mode_none.setToolTip(
            "Nur Front-Farbe — Bildpfad bleibt erhalten, wird aber nicht gezeichnet."
        )
        self.front_mode_top_third.setToolTip(
            "Bild füllt die oberen ~38,2 % (goldener Schnitt; Zoom/Verschieben "
            "möglich); darunter die Front-Farbe."
        )
        self.front_mode_full.setToolTip(
            "Bild deckt die gesamte Vorderseite ab (Cover-Fit + Zoom/Verschieben)."
        )
        self.front_mode_none.setChecked(True)
        self.front_mode_group = QButtonGroup(self)
        self.front_mode_group.addButton(self.front_mode_none, 0)
        self.front_mode_group.addButton(self.front_mode_top_third, 1)
        self.front_mode_group.addButton(self.front_mode_full, 2)
        front_mode_row = QHBoxLayout()
        front_mode_row.setContentsMargins(0, 0, 0, 0)
        front_mode_row.setSpacing(12)
        front_mode_row.addWidget(self.front_mode_none)
        front_mode_row.addWidget(self.front_mode_top_third)
        front_mode_row.addWidget(self.front_mode_full)
        front_mode_row.addStretch(1)
        front_mode_host = QWidget()
        front_mode_host.setLayout(front_mode_row)
        design_front.addRow("Bildmodus:", front_mode_host)

        self.front_edit = QLineEdit()
        self.front_edit.setPlaceholderText(
            "Optional: Foto oder Stylecloud-Wortwolke…"
        )
        front_row = QHBoxLayout()
        front_row.addWidget(self.front_edit)
        self._btn_front_asset = QPushButton("Asset…")
        self._btn_front_asset.setToolTip(
            "Bild aus dem Asset Manager wählen (Pool oder Buch-img/)."
        )
        self._btn_front_asset.clicked.connect(
            lambda: self._pick_image_via_asset("front")
        )
        front_row.addWidget(self._btn_front_asset)
        self._btn_front_browse = QPushButton("…")
        self._btn_front_browse.setFixedWidth(32)
        self._btn_front_browse.setToolTip("Datei im Dateisystem wählen")
        self._btn_front_browse.clicked.connect(self._browse_front)
        front_row.addWidget(self._btn_front_browse)
        design_front.addRow("Bild / Wortwolke:", front_row)

        self._btn_stylecloud = QPushButton("Wortwolke (Stylecloud)…")
        self._btn_stylecloud.setToolTip(
            "Öffnet Stylecloud. Nach dem Erzeugen: „An KDP Cover übergeben“."
        )
        self._btn_stylecloud.clicked.connect(self._open_stylecloud_for_front)
        design_front.addRow("", self._btn_stylecloud)

        btn_gestalten = QPushButton("Layout öffnen…")
        btn_gestalten.setToolTip(
            "Tab „Vorderseite · Layout“: Titel, Band, Fade, Fußzeile, Banner, Badge "
            "(je Block ein/aus)."
        )
        btn_gestalten.clicked.connect(self._open_gestaltung_tab)
        design_front.addRow("", btn_gestalten)

        self.front_zoom_spin = QDoubleSpinBox()
        self.front_zoom_spin.setRange(1.0, 4.0)
        self.front_zoom_spin.setDecimals(2)
        self.front_zoom_spin.setSingleStep(0.05)
        self.front_zoom_spin.setValue(1.0)
        self.front_zoom_spin.setToolTip(
            "Vergrößern über Cover-Fit (≥ 1,0). Danach Ausschnitt mit Offset "
            "verschieben — gilt für goldenen Schnitt und Vollfläche."
        )
        design_front.addRow("Front-Zoom:", self.front_zoom_spin)
        self.front_ox_spin = self._mm_spin()
        self.front_oy_spin = self._mm_spin()
        self.front_ox_spin.setToolTip(
            "Horizontal (X): Bild nach rechts (+) / links (−) verschieben. "
            "Freie Ränder bleiben Front-Farbe."
        )
        self.front_oy_spin.setToolTip(
            "Vertikal (Y): Bild nach unten (+) / oben (−) verschieben. "
            "Freie Ränder bleiben Front-Farbe."
        )
        design_front.addRow(
            "Front-Verschiebung (X / Y):",
            self._pair(self.front_ox_spin, self.front_oy_spin),
        )
        self._editor_tabs.addTab(tab_front, "Vorderseite · Bild")
        self._front_tab_index = self._editor_tabs.count() - 1
        self._editor_tabs.setTabToolTip(
            self._front_tab_index,
            "3 · Vorderseite · Bild (Farbe, Bildmodus, Bild oder Stylecloud)",
        )

        # --- Tab: Vorderseite · Layout (Layer über Farbe/Bild) ---
        tab_layer, layer_body = self._make_editor_tab()
        layer_body.addWidget(self._build_compose_front_group())
        self._layer_tab_index = self._editor_tabs.addTab(
            tab_layer, "Vorderseite · Layout"
        )
        self._editor_tabs.setTabToolTip(
            self._layer_tab_index,
            "4 · Vorderseite · Layout (Fade, Band, Titel, Fuß, Banner, Badge).",
        )
        self._sync_compose_front_tab_visibility()

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

        # --- Tab: Experte (selten; nur bei Modus Experte aktiv) ---
        tab_free, free_body = self._make_editor_tab()
        free_hint = QLabel(
            "Nur im Modus „Experte“ aktiv. Feinjustage: Rücken-Text per mm-Offset "
            "verschieben. Zurücksetzen: roter Button „Zurück auf Safe-Slots“ "
            "in der Banner-Zeile neben Pipette / UUID ändern…."
        )
        free_hint.setWordWrap(True)
        free_hint.setStyleSheet("color:#5b6573; font-size:12px;")
        free_body.addWidget(free_hint)
        free_form = QFormLayout()
        free_body.addLayout(free_form)
        self.free_box = tab_free
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
        self._free_tab_index = self._editor_tabs.addTab(tab_free, "Experte")
        self._editor_tabs.setTabToolTip(
            self._free_tab_index,
            "7 · Experte: Rücken-Text feinjustieren (mm-Offset)",
        )
        self.free_box.setEnabled(False)

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

        try:
            self._editor_tabs.setCurrentIndex(
                resolve_active_tab(
                    self._session_settings, tab_count=self._editor_tabs.count()
                )
            )
        except (TypeError, ValueError):
            self._editor_tabs.setCurrentIndex(0)
        self._editor_tabs.currentChanged.connect(
            lambda _i: self._geometry_save_timer.start()
        )
        self._editor_tabs.currentChanged.connect(
            lambda _i: self._sync_editor_scrollbars()
        )
        QTimer.singleShot(0, self._sync_editor_scrollbars)

        right_panel = QWidget()
        right_panel.setObjectName("kdpCoverRightPanel")
        right_panel.setMinimumWidth(320)
        right_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(8, 8, 4, 8)
        right.setSpacing(8)
        self._body_splitter.addWidget(right_panel)

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
        self._preview_scroll.setMinimumWidth(280)
        self._preview_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_scroll.viewport().installEventFilter(self)
        right.addWidget(self._preview_scroll, stretch=1)

        self._body_splitter.setStretchFactor(0, 0)
        self._body_splitter.setStretchFactor(1, 1)
        sizes = list(
            getattr(self, "_loaded_splitter_sizes", None) or [620, 880]
        )
        self._body_splitter.setSizes(sizes)
        self._body_splitter.splitterMoved.connect(self._on_body_splitter_moved)

        footer = QHBoxLayout()
        # 24px rechts frei für den SizeGrip (sonst liegt er auf PDF/Schließen).
        footer.setContentsMargins(0, 0, 24, 0)
        from ui_qt.widgets.handbook_info_button import prepend_handbook_info_button

        prepend_handbook_info_button(footer, tool_key="kdp_cover", host=self)
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
        self.btn_export = QPushButton("Aktuellen Stand als PDF exportieren")
        self.btn_export.setToolTip(
            "Wrap-PDF jetzt erzeugen — ohne „Cover fertig“ / ohne Ampel-Commit.\n"
            "Für den nächsten Schritt (Render): Speichern → Ja (Cover wird exportiert)."
        )
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
        self.front_mode_group.idClicked.connect(self._on_front_image_mode_changed)
        self.front_edit.editingFinished.connect(self._on_params_changed)
        self.back_edit.editingFinished.connect(self._on_params_changed)
        self.front_zoom_spin.valueChanged.connect(self._on_params_changed)
        self.front_ox_spin.valueChanged.connect(self._on_params_changed)
        self.front_oy_spin.valueChanged.connect(self._on_params_changed)
        self.back_scale_spin.valueChanged.connect(self._on_params_changed)
        self.back_placement_combo.currentIndexChanged.connect(self._on_params_changed)
        self.back_img_x_spin.valueChanged.connect(self._on_params_changed)
        self.back_img_y_spin.valueChanged.connect(self._on_params_changed)
        self.back_img_width_spin.valueChanged.connect(self._on_params_changed)
        self.back_frame_check.toggled.connect(self._on_params_changed)
        self.back_frame_mm_spin.valueChanged.connect(self._on_params_changed)
        # back/spine/compose-Farben: editingFinished bereits in _color_field verdrahtet
        self.title_edit.editingFinished.connect(self._on_params_changed)
        self.author_edit.editingFinished.connect(self._on_params_changed)
        self.spine_text_edit.editingFinished.connect(self._on_params_changed)
        self.spine_text_down_edit.editingFinished.connect(self._on_params_changed)
        self.spine_font_combo.currentIndexChanged.connect(self._on_params_changed)
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
        self._sync_front_image_mode_controls()
        layout_loaded = False
        if self._book:
            auto = resolve_existing_project_path(self._book)
            if auto is not None:
                try:
                    self._apply_layout(load_layout(auto), project_path=auto)
                    layout_loaded = True
                except (OSError, ValueError, TypeError, KeyError):
                    pass
            # Arbeitsweg: Buch schon gewählt → UUID ohne Picker übernehmen.
            if not normalize_uuid(self._production_uuid):
                self._try_bind_uuid_from_active_book()
        self._init_page_count(layout_loaded=layout_loaded)
        self.pages_spin.valueChanged.connect(self._refresh_page_count_source)
        self.pages_estimated_check.toggled.connect(self._refresh_page_count_source)
        self.pages_estimated_check.toggled.connect(self._on_params_changed)
        self._apply_initial_front_image()
        self._refresh_binding_ui()
        # Einmalige Vorschau nach kompletter Init (Signale waren geblockt).
        self._params_guard = False
        self._on_params_changed()
        prepare_autonomous_window(self, parent)

    # --- Seitenzahl: Innenwerk-PDF oder Schätzung ---------------------------
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
    existing = raise_if_open(_active, lambda _d: True)
    if existing is not None:
        return 0
    dlg = KdpCoverQtDialog(studio, parent, front_image=front_image)
    if front_image is not None:
        turn_off = False if disable_compose is None else bool(disable_compose)
        dlg.apply_front_image(front_image, disable_compose=turn_off)
        # Nach Show einmal hard refresh (Viewport-Größe erst dann korrekt).
        QTimer.singleShot(0, dlg._refresh_preview)
    show_autonomous_window(dlg, _active)
    return 0


__all__ = [
    "KdpCoverQtDialog",
    "open_kdp_cover_qt",
    # Weiter von hier importierbar (Tests, ältere Aufrufer) — Heimat: kdp_cover/
    "_DeployFolderDialog",
    "_ELEMENT_SET_FILTER",
    "_ELEMENT_SET_SAVE_FILTER",
    "_ExportSuccessDialog",
    "_FreeExportConfirmDialog",
    "_PROJECT_FILTER",
    "_PROJECT_SAVE_FILTER",
    "_STUDIO_PAPERBACK_ID",
    "_draw_overlays",
]
