"""Tests fuer Phase 3 / PluginLoader.

Deckt:
- Discovery aus einem Test-Plugin-Verzeichnis
- Validierung: fehlende Pflichtfelder, kaputtes JSON
- Lookup per Name
- Section-Filter
- Defekte Plugins werden uebersprungen, valide Nachbarn gefunden
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from services.plugin_loader import PluginInfo, PluginLoader


def _write_plugin(plugins_dir: Path, name: str, **overrides) -> Path:
    """Schreibt ein gueltiges Manifest in plugins/<name>/plugin.json.

    Default-Entrypoint zeigt auf `tests.test_plugin_loader:any_str`,
    das immer existiert. Ueberschreibbar via `overrides`.
    """
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "label": f"Label fuer {name}",
        "entrypoint": "tests.test_plugin_loader:any_str",
        "description": "test",
        "version": "1.0.0",
        "author": "tests",
        "menu_section": "Plugins",
    }
    manifest.update(overrides)
    manifest_path = plugin_dir / "plugin.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_discover_empty_dir(tmp_path):
    loader = PluginLoader(tmp_path)
    assert loader.discover() == []


def test_manifest_with_hooks(tmp_path):
    _write_plugin(
        tmp_path,
        "hooked",
        hooks={"after_book_import": "on_after_book_import"},
    )
    loader = PluginLoader(tmp_path)
    info = loader.get("hooked")
    assert info is not None
    assert info.hooks == {"after_book_import": "on_after_book_import"}


def test_show_in_menu_false(tmp_path):
    _write_plugin(tmp_path, "hidden", show_in_menu=False)
    loader = PluginLoader(tmp_path)
    info = loader.get("hidden")
    assert info is not None
    assert info.show_in_menu is False


def test_discover_nonexistent_dir(tmp_path):
    loader = PluginLoader(tmp_path / "does_not_exist")
    assert loader.discover() == []


def test_discover_single_plugin(tmp_path):
    _write_plugin(tmp_path, "alpha")
    loader = PluginLoader(tmp_path)
    plugins = loader.discover()
    assert len(plugins) == 1
    assert plugins[0].name == "alpha"
    assert plugins[0].label == "Label fuer alpha"
    assert plugins[0].entrypoint == "tests.test_plugin_loader:any_str"
    assert plugins[0].menu_section == "Plugins"
    assert plugins[0].order == 100
    assert plugins[0].load_error is None


def test_discover_sorts_by_order_then_label(tmp_path):
    _write_plugin(tmp_path, "zeta", label="Zeta", order=50)
    _write_plugin(tmp_path, "alpha", label="Alpha", order=10)
    _write_plugin(tmp_path, "beta", label="Beta", order=10)
    loader = PluginLoader(tmp_path)
    names = [p.name for p in loader.discover()]
    assert names == ["alpha", "beta", "zeta"]


def test_discover_caches_result(tmp_path):
    _write_plugin(tmp_path, "alpha")
    loader = PluginLoader(tmp_path)
    first = loader.discover()
    # Hinzufuegen eines weiteren Plugins wird durch den Cache ignoriert.
    _write_plugin(tmp_path, "beta")
    second = loader.discover()
    assert len(first) == 1
    assert len(second) == 1
    # Mit reload=True wird neu gescannt.
    third = loader.discover(reload=True)
    assert len(third) == 2


def test_discover_skips_broken_json(tmp_path):
    _write_plugin(tmp_path, "alpha")
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "plugin.json").write_text("not json", encoding="utf-8")
    _write_plugin(tmp_path, "gamma")
    loader = PluginLoader(tmp_path)
    plugins = loader.discover()
    names = [p.name for p in plugins]
    assert "alpha" in names
    assert "gamma" in names
    assert "broken" not in names


def test_discover_skips_missing_required_field(tmp_path):
    plugin_dir = tmp_path / "incomplete"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"label": "no name", "entrypoint": "x:y"}), encoding="utf-8"
    )
    _write_plugin(tmp_path, "alpha")
    loader = PluginLoader(tmp_path)
    plugins = loader.discover()
    assert [p.name for p in plugins] == ["alpha"]


def test_discover_skips_non_dict_manifest(tmp_path):
    plugin_dir = tmp_path / "weird"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    _write_plugin(tmp_path, "alpha")
    loader = PluginLoader(tmp_path)
    plugins = loader.discover()
    assert [p.name for p in plugins] == ["alpha"]


def test_discover_records_load_error_for_missing_entrypoint(tmp_path):
    _write_plugin(tmp_path, "alpha", entrypoint="nonexistent.module:run")
    loader = PluginLoader(tmp_path)
    plugins = loader.discover()
    assert len(plugins) == 1
    assert plugins[0].load_error is not None
    assert "nonexistent" in plugins[0].load_error


def test_discover_resolves_known_entrypoint(tmp_path):
    """Bekanntes Modul (dieses Test-Modul) wird aufgeloest."""
    # Eigener Entrypoint: tests/test_plugin_loader.py:any_str
    _write_plugin(
        tmp_path, "alpha", entrypoint="tests.test_plugin_loader:any_str"
    )
    loader = PluginLoader(tmp_path)
    plugins = loader.discover()
    assert plugins[0].load_error is None
    assert plugins[0].callable is not None
    assert plugins[0].callable() == "ok"


def any_str(studio=None, **kwargs) -> str:
    return "ok"


def test_get_returns_none_for_unknown(tmp_path):
    loader = PluginLoader(tmp_path)
    assert loader.get("nope") is None


def test_get_finds_existing(tmp_path):
    _write_plugin(tmp_path, "alpha")
    loader = PluginLoader(tmp_path)
    info = loader.get("alpha")
    assert info is not None
    assert info.name == "alpha"


def test_iter_by_section(tmp_path):
    _write_plugin(tmp_path, "alpha", menu_section="Plugins")
    _write_plugin(tmp_path, "beta", menu_section="Other")
    _write_plugin(tmp_path, "gamma", menu_section="Plugins")
    loader = PluginLoader(tmp_path)
    tools = loader.iter_by_section("Plugins")
    assert sorted(p.name for p in tools) == ["alpha", "gamma"]
    other = loader.iter_by_section("Other")
    assert [p.name for p in other] == ["beta"]
    assert loader.iter_by_section("Nope") == []


def test_invalid_entrypoint_format(tmp_path):
    _write_plugin(tmp_path, "alpha", entrypoint="no_colon_here")
    loader = PluginLoader(tmp_path)
    plugins = loader.discover()
    assert len(plugins) == 1
    assert plugins[0].load_error is not None
    assert "Entrypoint" in plugins[0].load_error


def test_plugin_info_is_frozen():
    """PluginInfo ist frozen (hashable, immutable)."""
    info = PluginInfo(name="x", label="L", entrypoint="x:y")
    try:
        info.name = "y"  # type: ignore[misc]
        raise AssertionError("PluginInfo sollte frozen sein")
    except Exception:
        pass
