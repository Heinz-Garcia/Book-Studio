"""Einklappbare Abschnitte für dichte Formular-Dialoge."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CollapsibleSection(QWidget):
    """Titelzeile mit Pfeil; Inhalt ein-/ausklappbar (ohne Widgets zu disablen)."""

    def __init__(
        self,
        title: str,
        *,
        expanded: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 6)
        root.setSpacing(2)

        self._toggle = QToolButton()
        self._toggle.setObjectName("collapsibleSectionToggle")
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self._toggle.setAutoRaise(True)
        self._toggle.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._toggle.setStyleSheet(
            "QToolButton#collapsibleSectionToggle {"
            "  border: none;"
            "  font-weight: 600;"
            "  text-align: left;"
            "  padding: 4px 2px;"
            "  color: #1e293b;"
            "}"
            "QToolButton#collapsibleSectionToggle:hover {"
            "  color: #0f172a;"
            "}"
        )
        self._toggle.toggled.connect(self._on_toggled)
        root.addWidget(self._toggle)

        self._body_frame = QFrame()
        self._body_frame.setObjectName("collapsibleSectionBody")
        self._body_frame.setFrameShape(QFrame.Shape.NoFrame)
        self._body_frame.setVisible(expanded)
        self._body_layout = QVBoxLayout(self._body_frame)
        self._body_layout.setContentsMargins(10, 2, 2, 4)
        self._body_layout.setSpacing(6)
        root.addWidget(self._body_frame)

    def set_title(self, title: str) -> None:
        self._toggle.setText(title)

    def title(self) -> str:
        return self._toggle.text()

    def body(self) -> QWidget:
        """Container für Formulare / verschachtelte Sektionen."""
        return self._body_frame

    def body_layout(self) -> QVBoxLayout:
        return self._body_layout

    def set_expanded(self, expanded: bool) -> None:
        self._toggle.setChecked(expanded)

    def is_expanded(self) -> bool:
        return self._toggle.isChecked()

    def _on_toggled(self, expanded: bool) -> None:
        self._body_frame.setVisible(expanded)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )


__all__ = ["CollapsibleSection"]
