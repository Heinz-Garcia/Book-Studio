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
