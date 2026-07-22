"""Tests für services.plugin_runtime."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.plugin_runtime import (
    PluginExecutor,
    ensure_repo_on_path,
    fire_plugin_hooks,
    repo_root_from_file,
)

_HOOK_CALLS: list[str] = []


def _hook_run(studio=None, **kwargs):
    return 0


def _hook_on_after_book_import(studio=None, **kwargs):
    if studio is not None and hasattr(studio, "calls"):
        studio.calls.append("hook_called")


@pytest.fixture(autouse=True)
def _clear_plugins_modules():
    """Verhindert, dass Test-`plugins.*`-Pakete echte Plugins überschatten."""
    stale = [name for name in sys.modules if name == "plugins" or name.startswith("plugins.")]
    for name in stale:
        del sys.modules[name]
    yield
    stale = [name for name in sys.modules if name == "plugins" or name.startswith("plugins.")]
    for name in stale:
        del sys.modules[name]


def test_repo_root_from_file_levels_up(tmp_path: Path):
    plugin_init = tmp_path / "plugins" / "demo" / "__init__.py"
    plugin_init.parent.mkdir(parents=True)
    plugin_init.write_text("", encoding="utf-8")
    assert repo_root_from_file(plugin_init, levels_up=2) == tmp_path


def test_ensure_repo_on_path_inserts_once(tmp_path: Path, monkeypatch):
    plugin_init = tmp_path / "plugins" / "demo" / "__init__.py"
    plugin_init.parent.mkdir(parents=True)
    plugin_init.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "path", [])
    root = ensure_repo_on_path(plugin_init)
    assert str(root) in sys.path
    ensure_repo_on_path(plugin_init)
    assert sys.path.count(str(root)) == 1


def _write_hook_manifest(plugins_dir: Path, name: str) -> None:
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": name,
                "label": name,
                "entrypoint": "tests.test_plugin_runtime:_hook_run",
                "hooks": {"after_book_import": "_hook_on_after_book_import"},
            }
        ),
        encoding="utf-8",
    )


def test_fire_hook_invokes_declared_plugins(tmp_path: Path):
    plugins_dir = tmp_path / "plugins"
    _write_hook_manifest(plugins_dir, "hook_alpha")
    studio = SimpleNamespace(calls=[])
    executor = PluginExecutor(plugins_dir)
    executor.fire_hook("after_book_import", studio)
    assert studio.calls == ["hook_called"]


def test_fire_plugin_hooks_convenience(tmp_path: Path):
    plugins_dir = tmp_path / "plugins"
    _write_hook_manifest(plugins_dir, "hook_beta")
    studio = SimpleNamespace(calls=[])
    fire_plugin_hooks("after_book_import", studio, plugins_dir=plugins_dir)
    assert studio.calls == ["hook_called"]


def test_plugin_executor_run_returns_false_when_missing(tmp_path: Path):
    executor = PluginExecutor(tmp_path / "plugins")
    assert executor.run("missing", studio=None) is False


def test_plugin_executor_run_calls_entrypoint(tmp_path: Path):
    plugin_dir = tmp_path / "plugins" / "runner"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "runner",
                "label": "Runner",
                "entrypoint": "tests.test_plugin_loader:any_str",
            }
        ),
        encoding="utf-8",
    )
    executor = PluginExecutor(tmp_path / "plugins")
    assert executor.run("runner", studio=None) is True


def test_plugin_executor_run_logs_missing_plugin(tmp_path: Path):
    logs: list[tuple[str, str]] = []
    studio = SimpleNamespace(log=lambda msg, level: logs.append((msg, level)))
    executor = PluginExecutor(tmp_path / "plugins")
    assert executor.run("missing", studio) is False
    assert logs
    assert "nicht gefunden" in logs[0][0]
    assert logs[0][1] == "warning"
