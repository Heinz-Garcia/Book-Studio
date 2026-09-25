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
    QDialog,
    QLayout,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tools.kdp_cover.model import (
    load_layout,
    resolve_existing_project_path,
)
from tools.kdp_cover.settings import (
    load_settings,
    resolve_body_splitter_sizes,
    resolve_window_size,
)
from tools.production_uuid import normalize_uuid
from ui_qt.autonomous_window import (
    prepare_autonomous_window,
    raise_if_open,
    show_autonomous_window,
)
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
    _book_root,
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
        self._init_state(studio, front_image)
        root, left = self._build_shell()
        self._build_tab_size()
        self._build_tab_general()
        self._build_tab_front()
        self._build_tab_front_layout()
        self._build_tab_zones()
        self._build_tab_spine()
        self._build_tab_back()
        self._build_tab_expert()
        self._build_sticky_actions(left)
        self._restore_active_tab()
        self._build_preview_panel()
        self._build_footer(root)
        self._prefill_from_book()
        self._wire_param_signals()
        self._finish_init(parent)

    def _init_state(self, studio: Any, front_image: str | Path | None) -> None:
        """Zustand, Timer und Fenstergröße aus der Sitzung."""
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

    def _build_shell(self) -> tuple[QVBoxLayout, QVBoxLayout]:
        """Grundgerüst: Hilfeleiste, Splitter, linke Spalte mit Banner und Tabs."""
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
        return root, left

    def _finish_init(self, parent: Optional[QWidget]) -> None:
        """Autoload, Seitenzahl, UUID-Bindung, erste Vorschau."""
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
