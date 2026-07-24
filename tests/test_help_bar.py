"""Tests fuer ui_qt.widgets.help_bar (Kurzhilfe-Leiste fuer Plugin-Dialoge)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ui_qt.widgets import help_bar


def _write_manifest(plugins_dir: Path, name: str, **fields) -> None:
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"name": name, "label": name, "entrypoint": "x:y", **fields}
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_load_plugin_help_text_reads_field(tmp_path):
    _write_manifest(tmp_path / "plugins", "alpha", help_text=" Kurzhilfe. ")
    text = help_bar.load_plugin_help_text("alpha", root=tmp_path)
    assert text == "Kurzhilfe."


def test_load_plugin_help_text_missing_field_is_empty(tmp_path):
    _write_manifest(tmp_path / "plugins", "alpha")
    assert help_bar.load_plugin_help_text("alpha", root=tmp_path) == ""


def test_load_plugin_help_text_missing_manifest_is_empty(tmp_path):
    assert help_bar.load_plugin_help_text("nope", root=tmp_path) == ""


def test_load_plugin_help_text_broken_json_is_empty(tmp_path):
    plugin_dir = tmp_path / "plugins" / "broken"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text("not json", encoding="utf-8")
    assert help_bar.load_plugin_help_text("broken", root=tmp_path) == ""


def test_create_and_prepend_skips_empty_text(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    layout = QVBoxLayout(parent)
    assert help_bar.HelpBar.create_and_prepend(layout, "  ") is None
    assert layout.count() == 0
    _ = app


def test_create_and_prepend_inserts_bar_at_top(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    layout = QVBoxLayout(parent)
    layout.addWidget(QLabel("erster Inhalt"))

    bar = help_bar.HelpBar.create_and_prepend(layout, "Kurzhilfe-Text")
    assert bar is not None
    assert layout.count() == 2
    assert layout.itemAt(0).widget() is bar
    _ = app


def test_create_and_prepend_for_plugin_reads_manifest(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(help_bar, "repo_root", lambda: tmp_path)
    _write_manifest(tmp_path / "plugins", "alpha", help_text="Aus dem Manifest.")

    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    layout = QVBoxLayout(parent)

    bar = help_bar.HelpBar.create_and_prepend_for_plugin(layout, "alpha")
    assert bar is not None
    assert layout.count() == 1
    _ = app
