"""Arbeitsweg-Leiste — horizontales Stepper-Control (G–J).

Knoten + Verbindungslinie + Substep-Pills. Domänenlogik bleibt in
``services.work_path``; hier nur Darstellung und Klick-Targets.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services.constants import StatusFg
from services.work_path import (
    ChecklistItem,
    StageId,
    StageKind,
    StageSnapshot,
    WorkPathState,
    guided_bar_enablement,
)

_KIND_COLORS = {
    StageKind.OK: StatusFg.SUCCESS,
    StageKind.OPEN: StatusFg.WARNING,
    # Blockiert = klickbar → „Warum Rot?“ — deshalb hellrot, nicht grau.
    StageKind.BLOCKED: StatusFg.DANGER_SOFT,
    StageKind.EMPTY: StatusFg.NEUTRAL,
}

_LINE_DONE = StatusFg.SUCCESS
_LINE_TODO = "#c8d3ec"
_NODE_SIZE = 26

_ACTION_SHORT = {
    "delivery_intake": "Lieferung übernehmen (Inbox)",
    "book_projects": "Bücher wählen (Buchprojekte verwalten)",
    "open_quarto_config_editor": "Struktur prüfen (_quarto.yml)",
    "open_rahmen_editor": "Rahmen prüfen (Rahmenseiten)",
    "open_kapitel_editor": "Kapitel prüfen (Kapitelstruktur)",
    "skeleton_populate": "Übernehmen (Skeleton)",
    "gg_content_swap": "Inhalt aktualisieren (GG-Inhaltstausch)",
    "accept_kapitel_as_is": "Inhalt belassen (Buchstruktur)",
    "markup_inventory": "Formate zuordnen (Textauszeichnungs-Inventar)",
    "kdp_cover": "Cover gestalten (KDP Cover-Designer)",
    "render": "PDF erzeugen (Export)",
    "publisher_compliance": "Freigabe prüfen (Druck-Freigabe)",
    "mapping_manager": "Ablegen (PDF-Manager)",
}

_CONTROL_OK_IDS = frozenset(
    {
        "lieferung",
        "book",
        "rahmen",
        "kapitel",
        "formate",
        # Erledigt, aber Artefakte erneut ansehen / Dialog öffnen
        "render",
        "freigabe",
        "archiv",
    }
)
#: Auch ohne KDP erreichbar — Cover-Designer / Kanal umschalten.
_ALWAYS_CLICKABLE_IDS = frozenset({"cover"})


class StageNodeButton(QWidget):
    """Runder Stage-Knoten (Buchstabe) + Label darunter."""

    clicked = Signal()

    def __init__(
        self,
        stage: StageSnapshot,
        *,
        enabled: bool,
        guide_reason: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("workPathStageNode")
        self._enabled = bool(enabled)
        color = _KIND_COLORS.get(stage.kind, StatusFg.NEUTRAL)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._node = QPushButton(stage.id.value)
        self._node.setObjectName("workPathStageNodeCircle")
        self._node.setFixedSize(_NODE_SIZE, _NODE_SIZE)
        self._node.setCursor(
            Qt.CursorShape.PointingHandCursor
            if enabled
            else Qt.CursorShape.ArrowCursor
        )
        self._node.setEnabled(enabled)
        if stage.kind == StageKind.OK:
            bg, fg, border = color, "#ffffff", color
        elif stage.kind == StageKind.OPEN and enabled:
            bg, fg, border = "#ffffff", color, color
        elif stage.kind == StageKind.OPEN:
            bg, fg, border = "#fffbeb", color, color
        else:
            bg, fg, border = "#f1f5f9", "#94a3b8", "#cbd5e1"
        ring = "2px" if enabled else "1px"
        self._node.setStyleSheet(
            f"QPushButton#workPathStageNodeCircle {{"
            f"  background: {bg}; color: {fg}; border: {ring} solid {border};"
            f"  border-radius: {_NODE_SIZE // 2}px; font-weight: 700;"
            f"  font-size: 11px; padding: 0;"
            f"}}"
            f"QPushButton#workPathStageNodeCircle:hover {{"
            f"  background: {'#eef2ff' if enabled and stage.kind != StageKind.OK else bg};"
            f"}}"
            f"QPushButton#workPathStageNodeCircle:disabled {{"
            f"  background: {bg}; color: {fg}; border: 1px solid {border};"
            f"}}"
        )
        if enabled:
            self._node.clicked.connect(self.clicked.emit)
        layout.addWidget(self._node, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._label = QLabel(stage.label)
        self._label.setObjectName("workPathStageNodeLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        label_color = color if stage.kind != StageKind.BLOCKED else "#94a3b8"
        if stage.kind == StageKind.OK:
            label_color = StatusFg.SUCCESS
        self._label.setStyleSheet(
            f"QLabel#workPathStageNodeLabel {{"
            f"  color: {label_color}; font-size: 11px; font-weight: 600;"
            f"}}"
        )
        layout.addWidget(self._label)

        tip_parts = [stage.tip, stage.detail, guide_reason]
        tip = "\n".join(p for p in tip_parts if p).strip()
        self.setToolTip(tip)
        self._node.setToolTip(tip)
        self._label.setToolTip(tip)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def isEnabled(self) -> bool:  # noqa: N802 — Qt-Parität für Tests
        return self._enabled and super().isEnabled()

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self._enabled = bool(enabled)
        super().setEnabled(enabled)
        self._node.setEnabled(enabled)


def _connector_line(*, done: bool) -> QFrame:
    line = QFrame()
    line.setObjectName("workPathConnector")
    line.setFrameShape(QFrame.Shape.NoFrame)
    line.setFixedHeight(2)
    line.setMinimumWidth(16)
    line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    color = _LINE_DONE if done else _LINE_TODO
    line.setStyleSheet(
        f"QFrame#workPathConnector {{ background: {color}; border: none; "
        f"border-radius: 1px; max-height: 2px; }}"
    )
    return line


class WorkPathBar(QWidget):
    """Orientierung + genau ein geführter Stufen-/Chip-Klick."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        on_next: Optional[Callable[[], None]] = None,
        on_pipeline: Optional[Callable[[], None]] = None,
        on_refresh: Optional[Callable[[], None]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_collapsed_changed: Optional[Callable[[bool], None]] = None,
        collapsed: bool = False,
    ) -> None:
        super().__init__(parent)
        self._on_next = on_next
        self._on_pipeline = on_pipeline
        self._on_refresh = on_refresh
        self._on_stage = on_stage
        self._on_collapsed_changed = on_collapsed_changed
        self._collapsed = bool(collapsed)
        self.setObjectName("workPathBar")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 2, 0, 2)
        root.setSpacing(2)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)

        self._toggle = QToolButton()
        self._toggle.setAutoRaise(True)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setText("Arbeitsweg")
        self._toggle.setToolTip(
            "Stufen und Einzelschritte ein-/ausklappen. "
            "Nur der nächste Schritt ist klickbar; "
            "Teilkette: Menü Ansicht → Arbeitsweg. "
            "Weitere Werkzeuge: Menü Werkzeuge / Tools."
        )
        self._toggle.clicked.connect(self._toggle_collapsed)
        head.addWidget(self._toggle)

        self._summary = QLabel("")
        self._summary.setObjectName("workPathSummary")
        self._summary.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._summary.setMinimumWidth(120)
        head.addWidget(self._summary, stretch=1)

        self._primary_cta = QPushButton("Weiter")
        self._primary_cta.setObjectName("workPathPrimaryCta")
        self._primary_cta.setCursor(Qt.CursorShape.PointingHandCursor)
        self._primary_cta.setToolTip(
            "Die eine nächste Handlung auf dem Arbeitsweg."
        )
        self._primary_cta.clicked.connect(self._emit_next)
        head.addWidget(self._primary_cta)
        # Alias für ältere Tests / Aufrufer
        self._collapsed_next_btn = self._primary_cta

        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setFixedWidth(36)
        self._refresh_btn.setToolTip(
            "Aktualisieren — Ampeln aus dem Buchstand neu lesen "
            "(kein Werkzeug-Start)."
        )
        self._refresh_btn.clicked.connect(self._emit_refresh)
        head.addWidget(self._refresh_btn)
        root.addLayout(head)

        self._details = QWidget()
        self._details.setObjectName("workPathDetails")
        details = QHBoxLayout(self._details)
        details.setContentsMargins(22, 4, 0, 4)
        details.setSpacing(0)
        details.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._columns_box = details
        self._stage_buttons: list[StageNodeButton] = []
        self._checklist_buttons: list[QPushButton] = []
        root.addWidget(self._details)

        self._state: Optional[WorkPathState] = None
        self._apply_collapsed_chrome()

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        flag = bool(collapsed)
        if flag == self._collapsed:
            self._apply_collapsed_chrome()
            return
        self._collapsed = flag
        self._apply_collapsed_chrome()
        if self._on_collapsed_changed is not None:
            self._on_collapsed_changed(self._collapsed)

    def apply_state(self, state: WorkPathState) -> None:
        self._state = state
        guide = guided_bar_enablement(state)

        while self._columns_box.count():
            item = self._columns_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._stage_buttons.clear()
        self._checklist_buttons.clear()

        by_stage: dict[StageId, list[ChecklistItem]] = {
            StageId.F: [],
            StageId.G: [],
            StageId.H: [],
            StageId.I: [],
            StageId.J: [],
        }
        for chip in state.checklist:
            by_stage.setdefault(chip.stage_id, []).append(chip)

        next_id = state.next_action_id
        columns: list[QFrame] = []
        chip_rows: list[Optional[QWidget]] = []
        chip_counts: list[int] = []
        prev_kind: Optional[StageKind] = None

        for index, stage in enumerate(state.stages):
            if index:
                connector_host = QWidget()
                connector_host.setFixedWidth(20)
                ch = QVBoxLayout(connector_host)
                ch.setContentsMargins(2, 0, 2, 0)
                ch.setSpacing(0)
                # Linie auf Höhe der Knotenmitte (~halbe Node + Label-Offset)
                ch.addSpacing(_NODE_SIZE // 2 - 1)
                line = _connector_line(done=prev_kind == StageKind.OK)
                ch.addWidget(line)
                ch.addStretch(1)
                self._columns_box.addWidget(
                    connector_host, alignment=Qt.AlignmentFlag.AlignTop
                )

            col = QFrame()
            col.setObjectName("workPathStageColumn")
            col.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
            )
            col_layout = QVBoxLayout(col)
            col_layout.setContentsMargins(10, 4, 10, 4)
            col_layout.setSpacing(6)
            col_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

            enabled, reason = guide.stages.get(stage.id, (False, ""))
            stage_chip_actions = {c.action for c in by_stage.get(stage.id, [])}
            stage_enabled = enabled or (
                bool(next_id) and next_id in stage_chip_actions
            )
            stage_for_click = stage
            if stage_enabled and next_id and stage.action != next_id:
                stage_for_click = StageSnapshot(
                    id=stage.id,
                    label=stage.label,
                    kind=stage.kind,
                    action=next_id,
                    tip=stage.tip,
                    detail=stage.detail,
                )
            node = StageNodeButton(
                stage_for_click,
                enabled=stage_enabled,
                guide_reason=reason
                if enabled
                else (
                    f"Als Nächstes: {_ACTION_SHORT.get(next_id or '', next_id)}."
                    if stage_enabled
                    else reason
                ),
            )
            if stage_enabled:
                action = stage_for_click.action

                def _on_stage(_checked: bool = False, act: str = action) -> None:
                    if self._on_stage is not None:
                        self._on_stage(act)

                node.clicked.connect(_on_stage)
            self._stage_buttons.append(node)
            col_layout.addWidget(node, alignment=Qt.AlignmentFlag.AlignHCenter)

            chips = by_stage.get(stage.id, [])
            chip_counts.append(len(chips))
            chip_row_host: Optional[QWidget] = None
            if chips:
                chip_row_host = QWidget()
                chip_row_host.setObjectName("workPathSubChipRow")
                chip_row_host.setSizePolicy(
                    QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
                )
                chip_row = QHBoxLayout(chip_row_host)
                chip_row.setContentsMargins(0, 0, 0, 0)
                chip_row.setSpacing(4)
                for c_index, chip in enumerate(chips):
                    if c_index:
                        sep = QLabel("·")
                        sep.setObjectName("workPathSubSep")
                        sep.setStyleSheet(
                            "QLabel#workPathSubSep { color: #c8d3ec; font-size: 12px; }"
                        )
                        chip_row.addWidget(sep)
                    c_enabled = (
                        chip.kind == StageKind.OPEN
                        or chip.kind == StageKind.BLOCKED
                        or (bool(next_id) and chip.action == next_id)
                    )
                    if chip.id in _CONTROL_OK_IDS and chip.kind == StageKind.OK:
                        c_enabled = True
                    if chip.id in _ALWAYS_CLICKABLE_IDS and chip.kind in (
                        StageKind.EMPTY,
                        StageKind.OK,
                    ):
                        c_enabled = True
                    c_btn = self._make_checklist_button(
                        chip, enabled=c_enabled, next_id=next_id
                    )
                    self._checklist_buttons.append(c_btn)
                    chip_row.addWidget(c_btn)
                col_layout.addWidget(
                    chip_row_host, alignment=Qt.AlignmentFlag.AlignHCenter
                )
            chip_rows.append(chip_row_host)
            columns.append(col)
            self._columns_box.addWidget(col, stretch=0)
            prev_kind = stage.kind

        self._equalize_stage_widths(columns, chip_rows, chip_counts)
        self._columns_box.addStretch(1)

        self._summary.setText(state.summary)
        self._summary.setToolTip(state.summary)

        short = _ACTION_SHORT.get(state.next_action_id or "", "nächste Stufe")
        self._primary_cta.setEnabled(guide.next_enabled)
        self._primary_cta.setToolTip(guide.next_reason)
        self._primary_cta.setText(
            f"Weiter: {short}" if guide.next_enabled else "Weiter"
        )

        self._apply_collapsed_chrome()

    def _equalize_stage_widths(
        self,
        columns: list[QFrame],
        chip_rows: list[Optional[QWidget]],
        chip_counts: list[int],
    ) -> None:
        """Alle Stage-Spalten gleich breit = Substage-Summe der vollsten Stufe."""
        if not columns or not self._stage_buttons:
            return
        max_count = max(chip_counts) if chip_counts else 0
        content_w = 0
        for count, row in zip(chip_counts, chip_rows):
            if count != max_count or row is None:
                continue
            layout = row.layout()
            measured = 0
            if layout is not None:
                spacing = int(layout.spacing())
                n = layout.count()
                for i in range(n):
                    item = layout.itemAt(i)
                    child = item.widget() if item is not None else None
                    if child is not None:
                        measured += int(child.sizeHint().width())
                    if i + 1 < n:
                        measured += spacing
            content_w = max(content_w, measured, int(row.sizeHint().width()))
        if content_w <= 0:
            content_w = max(
                (int(btn.sizeHint().width()) for btn in self._stage_buttons),
                default=0,
            )
        if content_w <= 0:
            return
        for btn in self._stage_buttons:
            btn.setFixedWidth(content_w)
        for col in columns:
            margins = col.layout().contentsMargins() if col.layout() else None
            pad = (margins.left() + margins.right()) if margins else 20
            col.setFixedWidth(content_w + pad + 2)

    def _apply_collapsed_chrome(self) -> None:
        expanded = not self._collapsed
        self._details.setVisible(expanded)
        # Weiter / Aktualisieren gehören zum Panelinhalt — platzsparend einklappbar.
        self._primary_cta.setVisible(expanded)
        self._refresh_btn.setVisible(expanded)
        arrow = "▶" if self._collapsed else "▼"
        self._toggle.setText(f"{arrow} Arbeitsweg")

    def _toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def _make_checklist_button(
        self,
        item: ChecklistItem,
        *,
        enabled: bool,
        next_id: Optional[str],
    ) -> QPushButton:
        color = _KIND_COLORS.get(item.kind, StatusFg.NEUTRAL)
        btn = QPushButton(item.label)
        btn.setObjectName("workPathSubChip")
        btn.setProperty("chipKind", item.kind.value)
        btn.setProperty("chipActive", "true" if enabled else "false")
        btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        tip_parts = [
            f"Stufe {item.stage_id.value}",
            item.detail,
        ]
        if enabled and item.id == "lieferung" and item.kind == StageKind.OK:
            tip_parts.append(
                "Erneut Lieferung wählen (auch älteren Lauf, mit Nachfrage)."
            )
        elif enabled and item.id == "book" and item.kind == StageKind.OK:
            tip_parts.append("_quarto.yml zur Kontrolle öffnen.")
        elif enabled and item.id == "rahmen" and item.kind == StageKind.OK:
            tip_parts.append("Pflichtseiten prüfen und bearbeiten.")
        elif enabled and item.id == "kapitel" and item.kind == StageKind.OK:
            tip_parts.append("Buchstruktur und Kapitelinhalt prüfen.")
        elif enabled and item.id == "formate" and item.kind == StageKind.OK:
            tip_parts.append("Textauszeichnungs-Inventar erneut öffnen.")
        elif enabled and item.id == "render" and item.kind == StageKind.OK:
            tip_parts.append(
                "PDF vorhanden — Klick: Neu rendern oder PDF öffnen."
            )
        elif enabled and item.id == "freigabe" and item.kind == StageKind.OK:
            tip_parts.append("Freigabe-Prüfung erneut öffnen.")
        elif enabled and item.id == "archiv" and item.kind == StageKind.OK:
            tip_parts.append("Publish-Archiv / PDF Manager öffnen.")
        elif enabled and item.id == "cover" and item.kind == StageKind.EMPTY:
            tip_parts.append(
                "KDP aus — Cover optional. Hier klicken: Designer öffnen "
                "oder KDP-Taschenbuch aktivieren."
            )
        elif enabled and item.kind == StageKind.OPEN:
            tip_parts.append("Lücke — hier klicken (Warum Rot → Beheben).")
        elif enabled and item.kind == StageKind.BLOCKED:
            tip_parts.append("Noch blockiert — Klick erklärt Warum Rot.")
        elif enabled:
            tip_parts.append("Als Nächstes — hier klicken.")
        elif item.kind == StageKind.OK:
            tip_parts.append("Erledigt. Erneut: Menü Werkzeuge / Tools.")
        elif item.kind == StageKind.EMPTY:
            tip_parts.append(
                "KDP-Taschenbuch ist aus — Cover ist optional, nicht erledigt."
                if item.id == "cover"
                else "Nicht nötig / nicht anwendbar."
            )
        elif item.kind == StageKind.BLOCKED:
            tip_parts.append("Noch nicht dran — zuerst die hervorgehobene Stufe.")
        elif next_id:
            tip_parts.append("Später im Arbeitsweg.")
        btn.setToolTip("\n".join(p for p in tip_parts if p).strip())

        if enabled:
            btn.setStyleSheet(
                f"QPushButton#workPathSubChip {{"
                f"  color: {color}; background: #ffffff;"
                f"  border: none; border-bottom: 2px solid {color};"
                f"  border-radius: 0; padding: 2px 8px;"
                f"  font-size: 11px; font-weight: 600;"
                f"}}"
                f"QPushButton#workPathSubChip:hover {{ background: #eef2ff; }}"
            )
            btn.setEnabled(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action = item.action

            def _click(_checked: bool = False, act: str = action) -> None:
                if self._on_stage is not None:
                    self._on_stage(act)

            btn.clicked.connect(_click)
        elif item.kind == StageKind.OK:
            btn.setStyleSheet(
                f"QPushButton#workPathSubChip {{"
                f"  color: {StatusFg.SUCCESS}; background: transparent;"
                f"  border: none; padding: 2px 8px;"
                f"  font-size: 11px; font-weight: 500;"
                f"}}"
                f"QPushButton#workPathSubChip:disabled {{ color: {StatusFg.SUCCESS}; }}"
            )
            btn.setEnabled(False)
            btn.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            muted = "#94a3b8"
            btn.setStyleSheet(
                f"QPushButton#workPathSubChip {{"
                f"  color: {muted}; background: transparent;"
                f"  border: none; padding: 2px 8px;"
                f"  font-size: 11px;"
                f"}}"
                f"QPushButton#workPathSubChip:disabled {{ color: {muted}; }}"
            )
            btn.setEnabled(False)
            btn.setCursor(Qt.CursorShape.ArrowCursor)
        return btn

    def _emit_next(self) -> None:
        if self._on_next is not None:
            self._on_next()

    def _emit_refresh(self) -> None:
        if self._on_refresh is not None:
            self._on_refresh()
