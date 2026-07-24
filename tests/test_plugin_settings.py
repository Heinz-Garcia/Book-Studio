"""Tests fuer services.plugin_settings (generischer Plugin-Settings-Editor)."""

from __future__ import annotations

import json
from pathlib import Path

from services.plugin_settings import discover_plugin_settings, load_values, save_values


def _write_plugin(
    plugins_dir: Path,
    name: str,
    *,
    config_rel: str,
    fields: list[dict],
) -> None:
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "label": name,
        "entrypoint": "x:y",
        "settings": {"config": config_rel, "fields": fields},
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_discover_finds_settings_schema(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[
            {"key": "display.max_entries", "label": "Max.", "type": "int", "default": 15},
        ],
    )
    schemas = discover_plugin_settings(tmp_path / "plugins")
    assert len(schemas) == 1
    assert schemas[0].plugin_name == "demo"
    assert schemas[0].config_path == tmp_path / "tools" / "demo" / "config.json"
    assert schemas[0].fields[0].key == "display.max_entries"
    assert schemas[0].fields[0].type == "int"


def test_discover_skips_plugin_without_settings(tmp_path: Path):
    plugin_dir = tmp_path / "plugins" / "plain"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "plain", "label": "plain", "entrypoint": "x:y"}),
        encoding="utf-8",
    )
    assert discover_plugin_settings(tmp_path / "plugins") == []


def test_discover_skips_settings_without_fields_or_config(tmp_path: Path):
    plugin_dir = tmp_path / "plugins" / "broken"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "broken",
                "label": "broken",
                "entrypoint": "x:y",
                "settings": {"config": "", "fields": []},
            }
        ),
        encoding="utf-8",
    )
    assert discover_plugin_settings(tmp_path / "plugins") == []


def test_discover_defaults_unknown_type_to_string(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[{"key": "k", "label": "K", "type": "not_a_real_type"}],
    )
    schemas = discover_plugin_settings(tmp_path / "plugins")
    assert schemas[0].fields[0].type == "string"


def test_load_values_falls_back_to_default_when_file_missing(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[{"key": "display.max_entries", "label": "Max.", "type": "int", "default": 15}],
    )
    schema = discover_plugin_settings(tmp_path / "plugins")[0]
    values = load_values(schema)
    assert values == {"display.max_entries": 15}


def test_load_values_reads_current_value_from_config_file(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[{"key": "display.max_entries", "label": "Max.", "type": "int", "default": 15}],
    )
    schema = discover_plugin_settings(tmp_path / "plugins")[0]
    schema.config_path.parent.mkdir(parents=True, exist_ok=True)
    schema.config_path.write_text(json.dumps({"display": {"max_entries": 42}}), encoding="utf-8")

    values = load_values(schema)
    assert values == {"display.max_entries": 42}


def test_save_values_writes_nested_json(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[
            {"key": "display.max_entries", "label": "Max.", "type": "int", "default": 15},
            {"key": "scan.recent_only", "label": "Recent", "type": "bool", "default": True},
        ],
    )
    schema = discover_plugin_settings(tmp_path / "plugins")[0]
    save_values(schema, {"display.max_entries": 7, "scan.recent_only": False})

    raw = json.loads(schema.config_path.read_text(encoding="utf-8"))
    assert raw == {"display": {"max_entries": 7}, "scan": {"recent_only": False}}

    again = load_values(schema)
    assert again == {"display.max_entries": 7, "scan.recent_only": False}


def test_save_values_preserves_unrelated_existing_keys(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[{"key": "display.max_entries", "label": "Max.", "type": "int", "default": 15}],
    )
    schema = discover_plugin_settings(tmp_path / "plugins")[0]
    schema.config_path.parent.mkdir(parents=True, exist_ok=True)
    schema.config_path.write_text(
        json.dumps({"display": {"max_entries": 1, "unrelated": "keep-me"}, "other_section": True}),
        encoding="utf-8",
    )

    save_values(schema, {"display.max_entries": 9})

    raw = json.loads(schema.config_path.read_text(encoding="utf-8"))
    assert raw["display"]["max_entries"] == 9
    assert raw["display"]["unrelated"] == "keep-me"
    assert raw["other_section"] is True


def test_discover_returns_empty_for_missing_dir(tmp_path: Path):
    assert discover_plugin_settings(tmp_path / "does_not_exist") == []
