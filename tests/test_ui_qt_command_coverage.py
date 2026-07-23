"""Tests: Qt CommandHost-Vollständigkeit (keine Menü-Stubs)."""

from __future__ import annotations

import json
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

    missing = [
        name
        for name in sorted(required)
        if not callable(getattr(CommandHost, name, None))
    ]
    assert missing == [], f"CommandHost fehlt Methoden: {missing}"


def test_time_machine_lists_struct_backups(tmp_path: Path):
    pytest.importorskip("PySide6")
    from ui_qt.dialogs.time_machine_dialog import format_backup_label, list_structure_backups

    book = tmp_path / "Band"
    backups = book / ".backups"
    backups.mkdir(parents=True)
    (backups / "struct_20260723_153000.json").write_text("[]", encoding="utf-8")
    (backups / "backup_ignore.zip").write_bytes(b"x")
    found = list_structure_backups(book)
    assert len(found) == 1
    assert "15:30:00" in format_backup_label(found[0])


def test_file_indexer_plugin_runs_tool(tmp_path: Path):
    from plugins import file_indexer

    target = tmp_path / "md"
    target.mkdir()
    (target / "a.md").write_text('---\ntitle: "A"\n---\n', encoding="utf-8")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(
        json.dumps({"indexer_target_folder": str(target)}),
        encoding="utf-8",
    )

    class LogStudio:
        def __init__(self):
            self.lines = []

        def log(self, msg, level="info"):
            self.lines.append((level, msg))

    studio = LogStudio()
    code = file_indexer.run(studio=studio, config=cfg)
    assert code == 0
    assert (target / "buch_struktur_final.csv").is_file()


def test_file_indexer_falls_back_to_book_content(tmp_path: Path):
    from plugins import file_indexer

    book = tmp_path / "Band"
    content = book / "content"
    content.mkdir(parents=True)
    (content / "x.md").write_text("---\ntitle: X\n---\n", encoding="utf-8")
    cfg = tmp_path / "empty.json"
    cfg.write_text("{}", encoding="utf-8")

    class Studio:
        current_book = book

        def log(self, *a, **k):
            pass

    code = file_indexer.run(studio=Studio(), config=cfg)
    assert code == 0
    assert (content / "buch_struktur_final.csv").is_file()
