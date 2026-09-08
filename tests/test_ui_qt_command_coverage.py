"""Tests: Qt CommandHost-Vollständigkeit (keine Menü-Stubs)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Union

import pytest

from menu_definitions import (
    CONTEXT_MENU_AVAIL,
    CONTEXT_MENU_TREE,
    MENU_EDIT,
    MENU_EXPORT,
    MENU_FILE,
    MENU_HELP,
    MENU_TOOLS,
    MENU_VIEW,
    MenuCascade,
    MenuItem,
    MenuSeparator,
)


def _collect_commands(items: Iterable[Union[MenuCascade, MenuItem, MenuSeparator]]) -> set[str]:
    commands: set[str] = set()
    for item in items:
        if isinstance(item, MenuSeparator):
            continue
        if isinstance(item, MenuItem):
            commands.add(item.command)
        elif isinstance(item, MenuCascade):
            commands |= _collect_commands(item.children)
    return commands


def test_command_host_covers_all_menu_commands():
    pytest.importorskip("PySide6")
    from ui_qt.command_host import CommandHost

    required = set()
    for section in (
        MENU_FILE,
        MENU_EXPORT,
        MENU_EDIT,
        MENU_VIEW,
        MENU_TOOLS,
        MENU_HELP,
        CONTEXT_MENU_AVAIL,
        CONTEXT_MENU_TREE,
    ):
        required |= _collect_commands(section)

    missing = [name for name in sorted(required) if not callable(getattr(CommandHost, name, None))]
    assert missing == [], f"CommandHost fehlt Methoden: {missing}"


def test_time_machine_lists_struct_backups(tmp_path: Path):
    pytest.importorskip("PySide6")
    from ui_qt.structure_snapshot import format_backup_label, list_structure_backups

    book = tmp_path / "Band"
    backups = book / ".backups"
    backups.mkdir(parents=True)
    (backups / "struct_20260723_153000.json").write_text("[]", encoding="utf-8")
    (backups / "backup_ignore.zip").write_bytes(b"x")
    found = list_structure_backups(book)
    assert len(found) == 1
    label = format_backup_label(found[0])
    assert "ohne Namen" in label or "0 Kapitel" in label
    assert "15:30" in label


def test_file_indexer_plugin_is_thin_qt_adapter(monkeypatch):
    """Das Plugin fuehrt kein Subprozess-Tool mehr aus, sondern oeffnet den Dialog.

    Aus "Dateien indexieren" ist der CSV-Export der Kapitelliste geworden
    (siehe .doc/kapitelliste-csv-export-plan.md). Der Ordnername blieb, weil er
    die Plugin-Identitaet ist -- der Inhalt nicht.
    """
    pytest.importorskip("PySide6")
    from plugins import file_indexer
    from ui_qt.dialogs import chapter_list_dialog

    assert file_indexer.is_available()

    gerufen = {}

    def _fake(studio=None, parent=None, **kwargs):
        gerufen["studio"] = studio
        return 0

    monkeypatch.setattr(chapter_list_dialog, "open_chapter_list_qt", _fake)

    class Studio:
        root = None

        def log(self, *a, **k):
            pass

    studio = Studio()
    assert file_indexer.run(studio=studio) == 0
    assert gerufen["studio"] is studio
