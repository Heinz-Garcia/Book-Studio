"""Tests fuer services.plugin_settings (generischer Plugin-Settings-Editor)."""

from __future__ import annotations

import json
from pathlib import Path

from services.plugin_settings import (
    discover_plugin_settings,
    load_help_text,
    load_values,
    save_manifest_texts,
    save_values,
)


def _write_plugin(
    plugins_dir: Path,
    name: str,
    *,
    config_rel: str,
    fields: list[dict],
    help_text: str = "",
) -> None:
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "label": name,
        "entrypoint": "x:y",
        "settings": {"config": config_rel, "fields": fields},
    }
    if help_text:
        manifest["help_text"] = help_text
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


def test_load_help_text_reads_manifest_field(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[{"key": "k", "label": "K", "type": "string", "default": ""}],
        help_text=" Kurzhilfe fuer demo. ",
    )
    schema = discover_plugin_settings(tmp_path / "plugins")[0]
    assert load_help_text(schema) == "Kurzhilfe fuer demo."


def test_load_help_text_empty_when_not_set(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[{"key": "k", "label": "K", "type": "string", "default": ""}],
    )
    schema = discover_plugin_settings(tmp_path / "plugins")[0]
    assert load_help_text(schema) == ""


def test_save_manifest_texts_writes_help_text_and_tooltips(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[
            {"key": "display.max_entries", "label": "Max.", "type": "int", "default": 15, "tooltip": "alt"},
        ],
        help_text="alter Text",
    )
    schema = discover_plugin_settings(tmp_path / "plugins")[0]

    save_manifest_texts(
        schema,
        help_text="neuer Kurzhilfe-Text",
        field_tooltips={"display.max_entries": "neuer Tooltip"},
    )

    assert load_help_text(schema) == "neuer Kurzhilfe-Text"
    reloaded = discover_plugin_settings(tmp_path / "plugins")[0]
    assert reloaded.fields[0].tooltip == "neuer Tooltip"


def test_save_manifest_texts_preserves_other_manifest_fields(tmp_path: Path):
    _write_plugin(
        tmp_path / "plugins",
        "demo",
        config_rel="tools/demo/config.json",
        fields=[{"key": "k", "label": "K", "type": "string", "default": "", "tooltip": "x"}],
    )
    schema = discover_plugin_settings(tmp_path / "plugins")[0]

    save_manifest_texts(schema, help_text="hallo")

    raw = json.loads(schema.manifest_path.read_text(encoding="utf-8"))
    assert raw["name"] == "demo"
    assert raw["entrypoint"] == "x:y"
    assert raw["settings"]["fields"][0]["type"] == "string"


def test_save_manifest_texts_noop_without_manifest(tmp_path: Path):
    from services.plugin_settings import PluginSettingsSchema

    schema = PluginSettingsSchema(
        plugin_name="ghost",
        display_name="Ghost",
        config_path=tmp_path / "tools" / "ghost" / "config.json",
        manifest_path=tmp_path / "plugins" / "ghost" / "plugin.json",
        fields=(),
    )
    save_manifest_texts(schema, help_text="wird nie geschrieben")
    assert not schema.manifest_path.exists()
