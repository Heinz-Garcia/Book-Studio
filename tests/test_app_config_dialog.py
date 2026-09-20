"""Tests für den deklarativen Studio-Config-Dialog (Feldliste)."""

from __future__ import annotations

from pathlib import Path

import app_config
import pytest

from ui_qt.dialogs.app_config_dialog import FIELDS, _path_list_to_text


def test_gui_fields_are_subset_of_app_config_defaults():
    unknown = [f.key for f in FIELDS if f.key not in app_config.DEFAULTS]
    assert unknown == [], f"GUI-Felder fehlen in DEFAULTS: {unknown}"


def test_important_path_keys_are_in_gui():
    keys = {f.key for f in FIELDS}
    for required in (
        "content_root_path",
        "pdf_deploy_folder",
        "exiftool_path",
        "prep_dest_folder",
        "indexer_target_folder",
        "asset_pool_path",
    ):
        assert required in keys


def test_exiftool_path_is_file_field():
    """ExifTool muss als Datei wählbar sein (nicht nur Ordner)."""
    field = next(f for f in FIELDS if f.key == "exiftool_path")
    assert field.kind == "file"
    assert "exiftool" in field.file_filter.casefold()


def test_path_list_to_text_joins_lists():
    assert _path_list_to_text(["a", "b"]) == "a, b"
    assert _path_list_to_text(".") == "."
    assert _path_list_to_text([]) == ""


def test_dialog_uses_tabs_and_short_browse_buttons(tmp_path: Path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget

    from ui_qt.dialogs.app_config_dialog import AppConfigDialog, _PathRow

    app = QApplication.instance() or QApplication([])
    cfg = tmp_path / "app_config.json"
    cfg.write_text("{}", encoding="utf-8")
    dlg = AppConfigDialog(None, cfg)

    tabs = dlg.findChild(QTabWidget)
    assert tabs is not None
    titles = [tabs.tabText(i) for i in range(tabs.count())]
    assert titles == ["Pfade", "Export", "Log & Editor", "Skeleton", "Arbeitsweg"]

    browse_labels = {
        btn.text()
        for row in dlg.findChildren(_PathRow)
        for btn in row.findChildren(QPushButton)
    }
    assert browse_labels == {"..."}
    dlg.close()
    app.processEvents()
