"""Live-Validierung, Vorschau, Zoom, Fenstergeometrie und Qt-Ereignisse.

Mixin von ``KdpCoverQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from tools.kdp_cover.constants import (
    DEFAULT_EXPORT_DPI,
)
from tools.kdp_cover.export_pdf import render_wrap_image
from tools.kdp_cover.geometry import build_geometry
from tools.kdp_cover.settings import (
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    resolve_active_tab,
    save_settings,
)
from tools.kdp_cover.validate import ValidationReport, validate_layout
from ui_qt.dialogs.kdp_cover.common import (
    _PREVIEW_DPI,
    _PREVIEW_ZOOM_MAX,
    _PREVIEW_ZOOM_MIN,
    _PREVIEW_ZOOM_STEP,
    _STATUS_EXPORT_TOOLTIP,
    _draw_overlays,
    _pil_to_qpixmap,
    _qlabel_color_ss,
)


class PreviewMixin:
    """Live-Validierung, Vorschau, Zoom, Fenstergeometrie und Qt-Ereignisse."""

    def _set_status(self, report: ValidationReport) -> None:
        if report.errors:
            self.status_label.setText(
                f"● Fehler ({len(report.errors)}) — Export im Sicher-Modus gesperrt"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#b91c1c", weight="600"))
            self.btn_export.setEnabled(self.mode_combo.currentData() == "free")
        elif report.warnings:
            self.status_label.setText(
                f"● Warnungen ({len(report.warnings)}) — Export möglich"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#b45309", weight="600"))
            self.btn_export.setEnabled(True)
        else:
            self.status_label.setText(
                "● OK — bereit zum Export (Validierung ohne Befunde)"
            )
            self.status_label.setStyleSheet(_qlabel_color_ss("#15803d", weight="600"))
            self.btn_export.setEnabled(True)
        self.status_label.setToolTip(_STATUS_EXPORT_TOOLTIP)

        lines: list[str] = []
        for issue in report.issues:
            mark = "⛔" if issue.severity == "error" else "⚠"
            lines.append(f"{mark} [{issue.code}] {issue.message}")
        self.issues_label.setText("\n".join(lines))

    def _on_params_changed(self, *_args: Any) -> None:
        if self._params_guard:
            return
        if not self._update_size_panel():
            self.status_label.setText("● Fehler in den Maßen")
            self.status_label.setStyleSheet(_qlabel_color_ss("#b91c1c", weight="600"))
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
            self.status_label.setStyleSheet(_qlabel_color_ss("#b91c1c", weight="600"))
            self.btn_export.setEnabled(False)
            return

        report = validate_layout(layout, geometry=geo, resolve_base=self._resolve_base())
        self._set_status(report)
        self._refresh_zone_maps(layout, geo)
        # Farbe allein reicht für Vorschau; Bild optional.
        self._preview_timer.start()

    def _effective_preview_dpi(self) -> float:
        """Bildschirm-Vorschau (120) oder wahlweise Druckauflösung (300)."""
        if getattr(self, "preview_print_dpi", None) is not None and self.preview_print_dpi.isChecked():
            return float(DEFAULT_EXPORT_DPI)
        return float(_PREVIEW_DPI)

    def _refresh_preview(self) -> None:
        layout = self._build_layout()
        front_raw = (layout.front_image or "").strip()
        if front_raw:
            front_path = Path(front_raw)
            if not front_path.is_absolute() and self._book is not None:
                front_path = (self._book / front_path).resolve()
            if not front_path.is_file():
                self._preview_full = None
                self.preview_label.setText(
                    f"Vorderseiten-Bild fehlt:\n{front_path}\n"
                    "(Front-Farbe reicht zum Speichern — Bildpfad korrigieren oder leeren.)"
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

    def _on_body_splitter_moved(self, *_args: Any) -> None:
        if getattr(self, "_suppress_geometry_persist", False):
            return
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.start()

    def _apply_restored_layout(self) -> None:
        """Fenstergröße + Trenner nach dem ersten Show erneut setzen.

        QSplitter kennt seine Breite erst nach Show; setSizes in ``__init__``
        wird sonst vom Layout/Stretch überschrieben.
        """
        self._suppress_geometry_persist = True
        try:
            loaded = getattr(self, "_loaded_size", None)
            if (
                isinstance(loaded, tuple)
                and len(loaded) == 2
                and not getattr(self, "_restore_maximized", False)
                and not self.isMaximized()
            ):
                self.resize(int(loaded[0]), int(loaded[1]))
            sizes = getattr(self, "_loaded_splitter_sizes", None)
            splitter = getattr(self, "_body_splitter", None)
            if splitter is not None and isinstance(sizes, list) and len(sizes) >= 2:
                splitter.setSizes([int(sizes[0]), int(sizes[1])])
        finally:
            # Ein Tick später freigeben — Show/resize-Kaskade noch abwarten.
            QTimer.singleShot(0, self._enable_geometry_persist)

    def _enable_geometry_persist(self) -> None:
        self._suppress_geometry_persist = False

    def _persist_window_geometry(self) -> None:
        if getattr(self, "_suppress_geometry_persist", False):
            return
        if not self.isVisible():
            return
        try:
            maximized = bool(self.isMaximized())
            if maximized:
                geo = self.normalGeometry()
                width = int(geo.width())
                height = int(geo.height())
            else:
                width = int(self.width())
                height = int(self.height())
            if width < MIN_WINDOW_WIDTH or height < MIN_WINDOW_HEIGHT:
                return
            active_tab = 0
            tabs = getattr(self, "_editor_tabs", None)
            if tabs is not None:
                active_tab = int(tabs.currentIndex())
            splitter_sizes: list[int] = []
            splitter = getattr(self, "_body_splitter", None)
            if splitter is not None:
                splitter_sizes = [int(v) for v in splitter.sizes()]
            if len(splitter_sizes) >= 2:
                self._loaded_splitter_sizes = [
                    int(splitter_sizes[0]),
                    int(splitter_sizes[1]),
                ]
            self._loaded_size = (width, height)
            save_settings(
                {
                    "window_width": width,
                    "window_height": height,
                    "window_maximized": maximized,
                    "active_tab": active_tab,
                    "body_splitter_sizes": splitter_sizes,
                }
            )
        except OSError:
            pass

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if getattr(self, "_restore_maximized", False):
            self._restore_maximized = False
            self.showMaximized()
        if not getattr(self, "_geometry_restore_scheduled", False):
            self._geometry_restore_scheduled = True
            QTimer.singleShot(0, self._apply_restored_layout)
        QTimer.singleShot(0, self._sync_editor_scrollbars)
        if getattr(self, "_page_count_prompt_pending", False):
            self._page_count_prompt_pending = False
            QTimer.singleShot(0, self._open_page_count_estimate)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._suppress_geometry_persist = False
        self._persist_window_geometry()
        super().closeEvent(event)

    def accept(self) -> None:
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._suppress_geometry_persist = False
        self._persist_window_geometry()
        super().accept()

    def reject(self) -> None:
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.stop()
        self._suppress_geometry_persist = False
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
        preview = getattr(self, "_preview_scroll", None)
        if (
            preview is not None
            and obj is preview.viewport()
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
        et = event.type()
        if et in (
            QEvent.Type.Resize,
            QEvent.Type.LayoutRequest,
            QEvent.Type.Show,
        ):
            scrolls = getattr(self, "_editor_scroll_areas", None) or []
            for scroll in scrolls:
                try:
                    if obj is scroll.viewport() or obj is scroll.widget():
                        self._sync_editor_scrollbars()
                        break
                except RuntimeError:
                    continue
        return super().eventFilter(obj, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Debounce: Beim Öffnen feuern Dutzende resizeEvents — sonst Gezucke.
        self._fit_timer.start()
        self._sync_editor_scrollbars()
        if getattr(self, "_suppress_geometry_persist", False):
            return
        timer = getattr(self, "_geometry_save_timer", None)
        if timer is not None:
            timer.start()

    def _restore_active_tab(self) -> None:
        """Zuletzt aktiven Tab wiederherstellen, Tab-Wechsel verdrahten."""
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

    def _build_preview_panel(self) -> None:
        """Rechte Spalte: Zoom-Leiste und Vorschau."""
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

    def _wire_param_signals(self) -> None:
        """Formularänderungen → Live-Validierung und Vorschau."""
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
