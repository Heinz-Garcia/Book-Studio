"""Qt-Dialog: generische Plugin-Einstellungen (explizites Manifest-Schema).

Liest ``settings`` aus jedem ``plugins/*/plugin.json`` (siehe
``services.plugin_settings``) und baut je Plugin ein Formular: oben eine
editierbare Kurzhilfe (``help_text``, mit Live-Vorschau als HelpBar-Banner
- derselbe Text, der auch oben im eigentlichen Plugin-Dialog erscheint),
darunter ein Feld pro deklariertem Setting mit Typ-Widget nach ``type``
plus einem editierbaren Tooltip-Textfeld. "Speichern" schreibt sowohl die
Config-Werte (``config.json`` des Plugins) als auch Kurzhilfe/Tooltips
(``plugin.json`` des Plugins) zurueck. Ersetzt den bisherigen Menüpunkt
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
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.plugin_settings import (
    PluginSettingsSchema,
    SettingField,
    discover_plugin_settings,
    load_help_text,
    load_values,
    save_manifest_texts,
    save_values,
)
from ui_qt.book_workspace import repo_root
from ui_qt.widgets.help_bar import HelpBar

_INT_FALLBACK_RANGE = (-1_000_000, 1_000_000)
_FLOAT_FALLBACK_RANGE = (-1e9, 1e9)


def _wrapped_text_edit(text: str, *, height: int) -> QPlainTextEdit:
    """Mehrzeiliges, umbrechendes Textfeld fuer Kurzhilfe/Tooltip-Texte.

    Ein einzeiliges QLineEdit scrollt bei langem Text zum Cursor (Textende)
    und zeigt dann nur das Ende an - unbrauchbar fuer ganze Saetze.
    """
    edit = QPlainTextEdit(text)
    edit.setMaximumHeight(height)
    edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return edit


class _SchemaPage(QWidget):
    """Ein Formular fuer genau ein Plugin-Settings-Schema."""

    def __init__(self, schema: PluginSettingsSchema) -> None:
        super().__init__()
        self.schema = schema
        self._widgets: dict[str, Any] = {}
        self._tooltip_edits: dict[str, QPlainTextEdit] = {}
        values = load_values(schema)
        current_help_text = load_help_text(schema)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("🛈 Kurzhilfe (Banner oben im Plugin-Dialog):"))
        self._help_preview = HelpBar(self, current_help_text)
        layout.addWidget(self._help_preview)
        self._help_edit = _wrapped_text_edit(current_help_text, height=70)
        self._help_edit.textChanged.connect(
            lambda: self._help_preview.set_text(self._help_edit.toPlainText())
        )
        layout.addWidget(self._help_edit)

        for f in schema.fields:
            field_label = QLabel(f"{f.label}:")
            field_label.setStyleSheet("font-weight: 600;")
            layout.addWidget(field_label)

            widget = self._build_widget(f, values.get(f.key))
            self._widgets[f.key] = widget
            layout.addWidget(widget)

            tooltip_edit = _wrapped_text_edit(f.tooltip, height=50)
            tooltip_edit.setPlaceholderText("Tooltip (? -Icon im Plugin-Dialog)")
            self._tooltip_edits[f.key] = tooltip_edit
            layout.addWidget(tooltip_edit)
            layout.addSpacing(8)
        layout.addStretch(1)

    def texts(self) -> tuple[str, dict[str, str]]:
        """(Kurzhilfe-Banner-Text, {Feld-Key: Tooltip-Text})."""
        tooltips = {key: edit.toPlainText() for key, edit in self._tooltip_edits.items()}
        return self._help_edit.toPlainText(), tooltips

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
        self.resize(820, 540)

        base = Path(plugins_dir) if plugins_dir is not None else repo_root() / "plugins"
        self._schemas = discover_plugin_settings(base)

        layout = QVBoxLayout(self)

        if not self._schemas:
            layout.addWidget(
                QLabel(
                    "Kein Plugin hat Kurzhilfe (\"help_text\") oder "
                    'einstellbare Felder ("settings") im Manifest.'
                )
            )
            close_row = QHBoxLayout()
            close_row.addStretch(1)
            close_btn = QPushButton("Schließen")
            close_btn.clicked.connect(self.reject)
            close_row.addWidget(close_btn)
            layout.addLayout(close_row)
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

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self._save_current)
        button_row.addWidget(save_btn)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.reject)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def _save_current(self) -> None:
        page = self._stack.currentWidget()
        if page is None:
            return
        help_text, tooltips = page.texts()
        try:
            save_values(page.schema, page.values())
            save_manifest_texts(page.schema, help_text=help_text, field_tooltips=tooltips)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        QMessageBox.information(
            self, "Gespeichert", f"{page.schema.display_name}: Einstellungen gespeichert."
        )


def open_plugin_settings_qt(parent: Optional[QWidget] = None) -> None:
    PluginSettingsQtDialog(parent).exec()


__all__ = ["PluginSettingsQtDialog", "open_plugin_settings_qt"]
