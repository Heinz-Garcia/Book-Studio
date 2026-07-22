"""Tests fuer `MenuManager._resolve_command`.

B-Fix (Code-Review 2026-07-03): Ein Tippfehler im Command-Namen einer
Menue-Definition liess `getattr(self.studio, name)` (ohne Default) mit
`AttributeError` crashen und damit die gesamte Menueleiste (Programmstart)
abstuerzen. `_resolve_command` liefert jetzt fuer unbekannte Namen einen
Platzhalter-Befehl, der beim Klick eine Warnung zeigt, statt beim Aufbau
zu crashen.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from menu_manager import MenuManager


def _make_studio():
    return SimpleNamespace(
        exporter=SimpleNamespace(
            run_quarto_render=lambda: "rendered",
            export_single_markdown=lambda: "exported",
        ),
        status_filter_var=SimpleNamespace(set=lambda v: None),
        apply_status_filter=lambda: None,
        existing_method=lambda: "ok",
    )


def test_resolve_command_returns_known_studio_method():
    studio = _make_studio()
    mgr = MenuManager(studio)
    cmd = mgr._resolve_command("existing_method")
    assert cmd() == "ok"


def test_resolve_command_special_names_resolved_directly():
    studio = _make_studio()
    mgr = MenuManager(studio)
    assert mgr._resolve_command("run_quarto_render") == studio.exporter.run_quarto_render
    assert mgr._resolve_command("export_single_markdown") == studio.exporter.export_single_markdown


def test_resolve_command_unknown_name_does_not_raise():
    """Frueher: AttributeError beim Menue-Aufbau. Jetzt: Platzhalter-Callable."""
    studio = _make_studio()
    mgr = MenuManager(studio)
    cmd = mgr._resolve_command("this_method_does_not_exist")
    assert callable(cmd)


def test_resolve_command_unknown_name_shows_warning_on_invocation():
    studio = _make_studio()
    mgr = MenuManager(studio)
    cmd = mgr._resolve_command("typo_method")
    with patch("menu_manager.messagebox.showwarning") as mock_warn:
        cmd()
    mock_warn.assert_called_once()
    args, _ = mock_warn.call_args
    assert "typo_method" in args[1]


# --- "Letzte aktive Projekte": dynamisches Untermenue -----------------------


class _FakeMenu:
    """Minimaler Tk-Menu-Stand-in: zeichnet nur Aufrufe auf, kein echtes Tk."""

    def __init__(self):
        self.calls = []

    def delete(self, start, end):
        self.calls.append(("delete", start, end))

    def add_command(self, **kwargs):
        self.calls.append(("add_command", kwargs))


def test_refresh_recent_projects_menu_shows_placeholder_when_empty():
    studio = SimpleNamespace(get_recent_books=lambda: [])
    mgr = MenuManager(studio)
    menu = _FakeMenu()

    mgr._refresh_recent_projects_menu(menu)

    assert ("delete", 0, "end") in menu.calls
    add_calls = [c for c in menu.calls if c[0] == "add_command"]
    assert len(add_calls) == 1
    assert add_calls[0][1]["state"] == "disabled"


def test_make_plugin_runner_uses_plugin_executor(tmp_path):
    import json

    plugin_dir = tmp_path / "demo"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "label": "Demo",
                "entrypoint": "tests.test_plugin_loader:any_str",
            }
        ),
        encoding="utf-8",
    )
    calls: list[str] = []
    studio = SimpleNamespace(log=lambda msg, level: calls.append(level))
    mgr = MenuManager(studio, plugins_dir=tmp_path)
    with patch("services.plugin_runtime.PluginExecutor") as mock_executor_cls:
        mock_executor_cls.return_value.run.return_value = True
        mgr._make_plugin_runner("demo")()
    mock_executor_cls.assert_called_once_with(tmp_path)
    mock_executor_cls.return_value.run.assert_called_once_with("demo", studio)


def test_refresh_recent_projects_menu_lists_entries_and_wires_open_recent_book():
    opened = []
    studio = SimpleNamespace(
        get_recent_books=lambda: [
            {"key": "Band_A", "label": "Band_A", "path": "irrelevant", "current": True},
            {"key": "Band_B", "label": "Band_B", "path": "irrelevant", "current": False},
        ],
        open_recent_book=lambda key: opened.append(key),
    )
    mgr = MenuManager(studio)
    menu = _FakeMenu()

    mgr._refresh_recent_projects_menu(menu)

    add_calls = [c for c in menu.calls if c[0] == "add_command"]
    assert add_calls[0][1]["label"] == "● Band_A (aktuell)"
    assert add_calls[0][1]["state"] == "disabled"
    assert add_calls[1][1]["label"] == "Band_B"

    # Nur nicht-aktuelle Eintraege sind klickbar.
    add_calls[1][1]["command"]()
    assert opened == ["Band_B"]

def test_refresh_recent_projects_menu_handles_missing_get_recent_books():
    """Falls das Studio (noch) kein get_recent_books hat, kein Crash."""
    studio = SimpleNamespace()
    mgr = MenuManager(studio)
    menu = _FakeMenu()

    mgr._refresh_recent_projects_menu(menu)

    add_calls = [c for c in menu.calls if c[0] == "add_command"]
    assert len(add_calls) == 1
    assert add_calls[0][1]["state"] == "disabled"


def test_collect_plugin_items_from_manifests(tmp_path):
    import json

    plugin_dir = tmp_path / "demo"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "label": "Demo-Plugin",
                "entrypoint": "tests.test_plugin_loader:any_str",
                "menu_section": "Plugins",
                "order": 5,
            }
        ),
        encoding="utf-8",
    )
    mgr = MenuManager(SimpleNamespace(), plugins_dir=tmp_path)
    items = mgr._collect_plugin_items()
    assert len(items) == 1
    assert items[0].label == "Demo-Plugin"
    assert items[0].command == "plugin:demo"


def test_populate_plugins_menu_empty_placeholder():
    mgr = MenuManager(SimpleNamespace())
    menu = _FakeMenu()
    mgr._populate_plugins_menu(menu, [])
    add_calls = [c for c in menu.calls if c[0] == "add_command"]
    assert add_calls[0][1]["state"] == "disabled"
