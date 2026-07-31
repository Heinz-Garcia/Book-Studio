"""Tests für den deklarativen Studio-Config-Dialog (Feldliste)."""

from __future__ import annotations

import app_config
from ui_qt.dialogs.app_config_dialog import FIELDS, _path_list_to_text


def test_gui_fields_are_subset_of_app_config_defaults():
    unknown = [f.key for f in FIELDS if f.key not in app_config.DEFAULTS]
    assert unknown == [], f"GUI-Felder fehlen in DEFAULTS: {unknown}"


def test_important_path_keys_are_in_gui():
    keys = {f.key for f in FIELDS}
    for required in (
        "content_root_path",
        "pdf_deploy_folder",
        "prep_dest_folder",
        "indexer_target_folder",
        "asset_pool_path",
    ):
        assert required in keys


def test_path_list_to_text_joins_lists():
    assert _path_list_to_text(["a", "b"]) == "a, b"
    assert _path_list_to_text(".") == "."
    assert _path_list_to_text([]) == ""
