"""Formular-Bausteine: Tab-Gerüst, Spin-/Farb-/Font-Felder, Pipette, Asset-Auswahl.

Mixin von ``KdpCoverQtDialog`` — setzt dessen Attribute voraus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui_qt.widgets.collapsible_section import CollapsibleSection


class FormWidgetsMixin:
    """Formular-Bausteine: Tab-Gerüst, Spin-/Farb-/Font-Felder, Pipette, Asset-Auswahl."""

    def _make_editor_tab(self, *, scrollable: bool = True) -> tuple[QWidget, QVBoxLayout]:
        """Tab-Seite; ``scrollable=False`` für kurze Tabs (z. B. Maße).

        Bei Scroll: Scrollbar standardmäßig aus, nur bei echtem Overflow ein.
        """
        if not scrollable:
            page = QWidget()
            body = QVBoxLayout(page)
            body.setContentsMargins(12, 10, 12, 10)
            body.setSpacing(8)
            body.setAlignment(Qt.AlignmentFlag.AlignTop)
            return page, body

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Erst aus — AsNeeded zeigt unter Windows oft schon bei 1 px Overflow.
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        scroll.setAutoFillBackground(True)
        host = QWidget()
        host.setAutoFillBackground(True)
        host.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        body = QVBoxLayout(host)
        body.setContentsMargins(12, 10, 12, 10)
        body.setSpacing(8)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(host)
        outer.addWidget(scroll)
        if not hasattr(self, "_editor_scroll_areas"):
            self._editor_scroll_areas: list[QScrollArea] = []
        self._editor_scroll_areas.append(scroll)
        scroll.viewport().installEventFilter(self)
        host.installEventFilter(self)
        return page, body

    def _sync_editor_scrollbars(self) -> None:
        """Scrollbar nur, wenn Inhalt die Viewport-Höhe überschreitet."""
        for scroll in getattr(self, "_editor_scroll_areas", []):
            host = scroll.widget()
            if host is None:
                continue
            lay = host.layout()
            hint_h = lay.sizeHint().height() if lay is not None else host.sizeHint().height()
            view_h = scroll.viewport().height()
            need = hint_h > view_h + 2
            want = (
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
                if need
                else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            if scroll.verticalScrollBarPolicy() != want:
                scroll.setVerticalScrollBarPolicy(want)

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

    def _font_family_combo(self) -> QComboBox:
        """Sans / Black / Serif / Mono."""
        combo = QComboBox()
        combo.addItem("Sans", "sans")
        combo.addItem("Black", "black")
        combo.addItem("Serif", "serif")
        combo.addItem("Mono", "mono")
        combo.setCurrentIndex(0)
        combo.setToolTip(
            "Fonttyp: Sans, Black (Arial Black / extra fett), Serif, Mono"
        )
        combo.setMaximumWidth(88)
        return combo

    @staticmethod
    def _set_font_combo(combo: QComboBox, value: str | None) -> None:
        idx = combo.findData(str(value or "sans"))
        combo.setCurrentIndex(idx if idx >= 0 else 0)

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
            # Pipette is WindowStaysOnTop: without suspending, the modal
            # QColorDialog opens behind it and the UI appears frozen.
            from ui_qt.dialogs.color_pipette_dialog import suspend_stay_on_top

            with suspend_stay_on_top():
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

    def _scroll_editor_to_widget(self, widget: QWidget) -> None:
        """Scroll the active editor tab so ``widget`` is visible."""
        if widget is None:
            return
        parent: QWidget | None = widget
        while parent is not None:
            if isinstance(parent, QScrollArea):
                parent.ensureWidgetVisible(widget, 24, 24)
                return
            parent = parent.parentWidget()

    def _open_color_pipette(self) -> None:
        """Always-on-top: Farbe aus Referenzbild → Hex in Zwischenablage."""
        from ui_qt.dialogs.color_pipette_dialog import open_color_pipette

        initial: str | None = None
        front = self.front_edit.text().strip() if hasattr(self, "front_edit") else ""
        if front:
            p = Path(front)
            if not p.is_absolute() and self._book is not None:
                p = (self._book / p).resolve()
            if p.is_file():
                initial = str(p)
        start_dir: str | None = None
        if self._book is not None:
            res_dir = Path(self._book) / "res"
            if res_dir.is_dir():
                start_dir = str(res_dir)
            else:
                start_dir = str(Path(self._book))
        open_color_pipette(
            parent=self, initial_image=initial, start_dir=start_dir
        )

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
            self._ensure_front_image_mode_for_path()
        elif target == "back":
            self.back_edit.setText(text)
        elif target == "badge":
            self.compose_badge_image.setText(text)
        elif target == "badge2":
            self.compose_badge2_image.setText(text)
        self._on_params_changed()
