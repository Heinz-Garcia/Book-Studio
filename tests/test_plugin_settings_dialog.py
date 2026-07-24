"""Tests fuer ui_qt.dialogs.plugin_settings_dialog (generischer Settings-Editor)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_plugin(plugins_dir: Path, name: str, *, config_rel: str, fields: list[dict]) -> None:
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "label": f"Label {name}",
        "entrypoint": "x:y",
        "settings": {"config": config_rel, "fields": fields},
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")


def _qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_dialog_shows_placeholder_without_any_schema(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from ui_qt.dialogs.plugin_settings_dialog import PluginSettingsQtDialog

    app = _qapp()
    (tmp_path / "plugins").mkdir()
    dlg = PluginSettingsQtDialog(None, plugins_dir=tmp_path / "plugins")
    assert dlg._schemas == []
    dlg.close()
    _ = app


def test_dialog_builds_one_page_per_plugin(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[
            {
                "key": "display.max_entries",
                "label": "Maximale Einträge",
                "type": "int",
                "default": 15,
                "min": 1,
                "max": 200,
                "tooltip": "Wie viele Eintraege maximal.",
            },
            {
                "key": "scan.recent_only",
                "label": "Nur zuletzt genutzte",
                "type": "bool",
                "default": True,
            },
        ],
    )
    from ui_qt.dialogs.plugin_settings_dialog import PluginSettingsQtDialog

    app = _qapp()
    dlg = PluginSettingsQtDialog(None, plugins_dir=tmp_path / "plugins")
    assert dlg._list.count() == 1
    assert dlg._list.item(0).text() == "Label demo"

    page = dlg._stack.widget(0)
    assert page.values() == {"display.max_entries": 15, "scan.recent_only": True}
    dlg.close()
    _ = app


def test_dialog_save_writes_edited_values(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[
            {"key": "display.max_entries", "label": "Max.", "type": "int", "default": 15},
            {"key": "scan.recent_only", "label": "Recent", "type": "bool", "default": True},
        ],
    )
    from PySide6.QtWidgets import QMessageBox

    from ui_qt.dialogs.plugin_settings_dialog import PluginSettingsQtDialog

    app = _qapp()
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dlg = PluginSettingsQtDialog(None, plugins_dir=tmp_path / "plugins")
    page = dlg._stack.widget(0)
    page._widgets["display.max_entries"].setValue(3)
    page._widgets["scan.recent_only"].setChecked(False)

    dlg._save_current()

    config_path = tmp_path / "tools" / "demo" / "config.json"
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    assert raw == {"display": {"max_entries": 3}, "scan": {"recent_only": False}}
    dlg.close()
    _ = app


def test_dialog_save_writes_edited_help_text_and_tooltip(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[
            {
                "key": "display.max_entries",
                "label": "Max.",
                "type": "int",
                "default": 15,
                "tooltip": "alter Tooltip",
            }
        ],
    )
    from PySide6.QtWidgets import QMessageBox

    from ui_qt.dialogs.plugin_settings_dialog import PluginSettingsQtDialog

    app = _qapp()
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dlg = PluginSettingsQtDialog(None, plugins_dir=tmp_path / "plugins")
    page = dlg._stack.widget(0)
    page._help_edit.setText("neue Kurzhilfe")
    page._tooltip_edits["display.max_entries"].setText("neuer Tooltip")

    dlg._save_current()

    manifest = json.loads((tmp_path / "plugins" / "demo" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["help_text"] == "neue Kurzhilfe"
    assert manifest["settings"]["fields"][0]["tooltip"] == "neuer Tooltip"
    dlg.close()
    _ = app


def test_help_preview_updates_live_with_edit(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[{"key": "k", "label": "K", "type": "string", "default": ""}],
    )
    from ui_qt.dialogs.plugin_settings_dialog import PluginSettingsQtDialog

    app = _qapp()
    dlg = PluginSettingsQtDialog(None, plugins_dir=tmp_path / "plugins")
    page = dlg._stack.widget(0)
    page._help_edit.setText("Live-Vorschau-Text")
    assert not page._help_preview.isHidden()
    page._help_edit.setText("")
    assert page._help_preview.isHidden()
    dlg.close()
    _ = app


def test_enum_and_string_field_widgets(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[
            {
                "key": "mode",
                "label": "Modus",
                "type": "enum",
                "options": ["a", "b", "c"],
                "default": "b",
            },
            {"key": "label", "label": "Label", "type": "string", "default": "hallo"},
        ],
    )
    from ui_qt.dialogs.plugin_settings_dialog import PluginSettingsQtDialog

    app = _qapp()
    dlg = PluginSettingsQtDialog(None, plugins_dir=tmp_path / "plugins")
    page = dlg._stack.widget(0)
    assert page.values() == {"mode": "b", "label": "hallo"}
    dlg.close()
    _ = app
