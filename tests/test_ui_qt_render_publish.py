"""Regression: Render-Shims bleiben installiert; Publish-Hooks existieren."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_install_export_manager_ui_persists(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import export_manager as em
    from ui_qt.dialogs.messagebox_shim import (
        QtMessageBoxShim,
        install_export_manager_ui,
        uninstall_export_manager_ui,
    )

    app = QApplication.instance() or QApplication([])
    install_export_manager_ui(None)
    assert isinstance(em.messagebox, QtMessageBoxShim)
    # Context-Manager darf Shims NICHT entfernen
    from ui_qt.dialogs.messagebox_shim import patch_export_manager_ui

    with patch_export_manager_ui(None):
        assert isinstance(em.messagebox, QtMessageBoxShim)
    assert isinstance(em.messagebox, QtMessageBoxShim)
    uninstall_export_manager_ui()
    _ = app


def test_qt_bridge_has_publish_hooks():
    pytest.importorskip("PySide6")
    from ui_qt.studio_bridge import QtStudioBridge

    for name in (
        "_fire_plugin_hooks_after_render",
        "_fire_plugin_hooks_after_book_import",
        "_fire_plugin_hooks_after_doctor_check",
    ):
        assert callable(getattr(QtStudioBridge, name, None)), name


def test_mapping_manager_prefers_active_snapshot(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import json

    from PySide6.QtWidgets import QApplication

    book = tmp_path / "Band"
    cfg = book / "bookconfig"
    cfg.mkdir(parents=True)
    payload = {
        "active_snapshot_id": "snap-b",
        "snapshots": [
            {"id": "snap-a", "origin": "local", "created_at": "2026-01-01T00:00:00", "renders": []},
            {"id": "snap-b", "origin": "local", "created_at": "2026-02-01T00:00:00", "renders": []},
        ],
    }
    (cfg / "publish_map.json").write_text(json.dumps(payload), encoding="utf-8")

    class Studio:
        current_book = book

        def log(self, *a, **k):
            pass

    from ui_qt.dialogs.mapping_manager_dialog import MappingManagerQtDialog

    app = QApplication.instance() or QApplication([])
    dlg = MappingManagerQtDialog(None, Studio())
    assert dlg.snapshot_combo.currentData() == "snap-b"
    assert "★" in dlg.snapshot_combo.currentText()
    dlg.close()
    _ = app
