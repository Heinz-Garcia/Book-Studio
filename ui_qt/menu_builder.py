"""Baut die QMenuBar aus ``menu_definitions`` + Plugin-Discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar, QWidget

from menu_definitions import (
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
from services.plugin_loader import PluginLoader

DEFAULT_PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
CommandResolver = Callable[[str], Optional[Callable[[], Any]]]


def _accel_to_shortcut(accel: Optional[str]) -> Optional[QKeySequence]:
    if not accel:
        return None
    # Tk "Ctrl+S" → Qt
    return QKeySequence(accel.replace("Ctrl+", "Ctrl+"))


def _bind_action(action: QAction, callback: Callable[[], Any]) -> None:
    """triggered liefert ``checked: bool`` — darf den Command-Callback nicht füttern."""

    def _slot(_checked: bool = False) -> None:
        callback()

    action.triggered.connect(_slot)


def populate_menu(
    menu: QMenu,
    entries: list,
    *,
    resolve: CommandResolver,
) -> None:
    for entry in entries:
        if isinstance(entry, MenuSeparator):
            menu.addSeparator()
        elif isinstance(entry, MenuCascade):
            sub = menu.addMenu(entry.label)
            populate_menu(sub, entry.children, resolve=resolve)
        elif isinstance(entry, MenuItem):
            action = QAction(entry.label, menu)
            if entry.accelerator:
                action.setShortcut(_accel_to_shortcut(entry.accelerator))
            cb = resolve(entry.command)
            if cb is not None:
                _bind_action(action, cb)
            else:
                action.setEnabled(False)
            menu.addAction(action)


def build_menu_bar(
    parent: QWidget,
    *,
    resolve: CommandResolver,
    plugins_dir: Optional[Path] = None,
    recent_builder: Optional[Callable[[QMenu], None]] = None,
) -> QMenuBar:
    """Erzeugt die Menüleiste analog zur Tk-App."""
    bar = QMenuBar(parent)

    # Datei: Recent-Untermenü + Definitionen
    file_menu = bar.addMenu("&Datei")
    recent_menu = file_menu.addMenu("📁 Letzte aktive Projekte")
    if recent_builder is not None:
        # Dynamisch bei jedem Öffnen
        recent_menu.aboutToShow.connect(lambda m=recent_menu: recent_builder(m))
    else:
        recent_menu.addAction("(keine)").setEnabled(False)
    file_menu.addSeparator()
    populate_menu(file_menu, MENU_FILE, resolve=resolve)

    for label, items in (
        ("&Export", MENU_EXPORT),
        ("&Bearbeiten", MENU_EDIT),
        ("&Ansicht", MENU_VIEW),
        ("&Tools", MENU_TOOLS),
    ):
        menu = bar.addMenu(label)
        populate_menu(menu, items, resolve=resolve)

    plugins_menu = bar.addMenu("&Plugins")
    _populate_plugins(plugins_menu, resolve=resolve, plugins_dir=plugins_dir or DEFAULT_PLUGINS_DIR)

    help_menu = bar.addMenu("&Hilfe")
    populate_menu(help_menu, MENU_HELP, resolve=resolve)
    return bar


def _populate_plugins(
    menu: QMenu,
    *,
    resolve: CommandResolver,
    plugins_dir: Path,
) -> None:
    try:
        infos = [
            i
            for i in PluginLoader(plugins_dir).discover()
            if i.menu_section == "Plugins" and i.load_error is None and i.show_in_menu
        ]
    except (OSError, ImportError, TypeError, ValueError):
        infos = []
    if not infos:
        act = menu.addAction("(keine Plugins)")
        act.setEnabled(False)
        return
    for info in infos:
        action = QAction(info.label, menu)
        cb = resolve(f"plugin:{info.name}")
        if cb is not None:
            _bind_action(action, cb)
        else:
            action.setEnabled(False)
        menu.addAction(action)
