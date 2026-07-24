"""Qt-Dialog: generische Plugin-Einstellungen (explizites Manifest-Schema).

Liest ``settings`` aus jedem ``plugins/*/plugin.json`` (siehe
``services.plugin_settings``) und baut je Plugin ein Formular: ein Feld
pro deklariertem Setting, Typ-Widget nach ``type`` + ein "?"-Tooltip-Icon
mit dem Manifest-Text ``tooltip``. Ersetzt den bisherigen Menüpunkt
"Plugin-Konfiguration…", der nur einen Roh-Text-Editor auf eine beliebige
``.toml``-Datei öffnete.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services.plugin_settings import (
    PluginSettingsSchema,
    SettingField,
    discover_plugin_settings,
    load_values,
    save_values,
)
from ui_qt.book_workspace import repo_root

_INT_FALLBACK_RANGE = (-1_000_000, 1_000_000)
_FLOAT_FALLBACK_RANGE = (-1e9, 1e9)


def _info_icon(tooltip: str) -> QToolButton:
    """Kleiner '?'-Button mit Tooltip (leer/deaktiviert ohne Text)."""
    btn = QToolButton()
    btn.setText("?")
    btn.setAutoRaise(True)
    btn.setFixedWidth(20)
    btn.setToolTip(tooltip)
    btn.setEnabled(bool(tooltip.strip()))
    return btn


class _SchemaPage(QWidget):
    """Ein Formular fuer genau ein Plugin-Settings-Schema."""

    def __init__(self, schema: PluginSettingsSchema) -> None:
        super().__init__()
        self.schema = schema
        self._widgets: dict[str, Any] = {}
        values = load_values(schema)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        for f in schema.fields:
            widget = self._build_widget(f, values.get(f.key))
            self._widgets[f.key] = widget
            row = QHBoxLayout()
            row.addWidget(widget, 1)
            row.addWidget(_info_icon(f.tooltip))
            form.addRow(f"{f.label}:", row)
        layout.addLayout(form)
        layout.addStretch(1)

    def _build_widget(self, f: SettingField, current: Any) -> QWidget:
        if f.type == "bool":
            w = QCheckBox()
            w.setChecked(bool(current))
            return w
        if f.type == "int":
            w = QSpinBox()
            lo, hi = _INT_FALLBACK_RANGE
            w.setRange(
                int(f.minimum) if f.minimum is not None else lo,
                int(f.maximum) if f.maximum is not None else hi,
            )
            try:
                w.setValue(int(current))
            except (TypeError, ValueError):
                w.setValue(int(f.default) if isinstance(f.default, (int, float)) else 0)
            return w
        if f.type == "float":
            w = QDoubleSpinBox()
            lo, hi = _FLOAT_FALLBACK_RANGE
            w.setRange(
                f.minimum if f.minimum is not None else lo,
                f.maximum if f.maximum is not None else hi,
            )
            try:
                w.setValue(float(current))
            except (TypeError, ValueError):
                w.setValue(float(f.default) if isinstance(f.default, (int, float)) else 0.0)
            return w
        if f.type == "enum":
            w = QComboBox()
            w.addItems(list(f.options))
            if current is not None and str(current) in f.options:
                w.setCurrentText(str(current))
            return w
        return QLineEdit(str(current) if current is not None else "")

    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in self.schema.fields:
            widget = self._widgets[f.key]
            if f.type == "bool":
                out[f.key] = widget.isChecked()
            elif f.type in ("int", "float"):
                out[f.key] = widget.value()
            elif f.type == "enum":
                out[f.key] = widget.currentText()
            else:
                out[f.key] = widget.text()
        return out


class PluginSettingsQtDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, *, plugins_dir: Optional[Path] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plugin-Konfiguration")
        self.resize(720, 460)

        base = Path(plugins_dir) if plugins_dir is not None else repo_root() / "plugins"
        self._schemas = discover_plugin_settings(base)

        layout = QVBoxLayout(self)

        if not self._schemas:
            layout.addWidget(
                QLabel(
                    "Kein Plugin deklariert einstellbare Felder "
                    '(plugin.json → "settings").'
                )
            )
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)
            return

        body = QHBoxLayout()
        self._list = QListWidget()
        self._list.setMaximumWidth(220)
        self._stack = QStackedWidget()
        for schema in self._schemas:
            self._list.addItem(QListWidgetItem(schema.display_name))
            self._stack.addWidget(_SchemaPage(schema))
        self._list.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._list.setCurrentRow(0)
        body.addWidget(self._list)
        body.addWidget(self._stack, 1)
        layout.addLayout(body)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        buttons.accepted.connect(self._save_current)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save_current(self) -> None:
        page = self._stack.currentWidget()
        if page is None:
            return
        try:
            save_values(page.schema, page.values())
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        QMessageBox.information(
            self, "Gespeichert", f"{page.schema.display_name}: Einstellungen gespeichert."
        )


def open_plugin_settings_qt(parent: Optional[QWidget] = None) -> None:
    PluginSettingsQtDialog(parent).exec()


__all__ = ["PluginSettingsQtDialog", "open_plugin_settings_qt"]
