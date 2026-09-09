"""Baut die QMenuBar aus ``menu_definitions`` + Plugin-Discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap
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

# Magenta-Badge wie bei GrammarGraph (autonome ``tools/``-Einträge): markiert
# Menüpunkte, die aus ``plugins/<name>/`` kommen — nicht Kern-Menüdefinitionen.
_PLUGIN_ICON_PX = 14
_PLUGIN_BADGE_CHAR = "⬢"
_PLUGIN_BADGE_COLOR = "#c026d3"
_PLUGIN_BADGE_COLOR_DISABLED = "#e879f9"
_PLUGIN_STATUS_HINT = "Autonomes Plugin (plugins/)"


def _paint_plugin_badge(px: int, color: str) -> QPixmap:
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    font = QFont()
    font.setPointSizeF(max(7.0, px * 0.72))
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(
        pixmap.rect(),
        int(Qt.AlignmentFlag.AlignCenter),
        _PLUGIN_BADGE_CHAR,
    )
    painter.end()
    return pixmap


def plugin_menu_icon(*, size: int = _PLUGIN_ICON_PX) -> QIcon:
    """Kleines Magenta-Badge für Einträge aus ``plugins/``."""
    px = max(10, int(size))
    icon = QIcon()
    normal = _paint_plugin_badge(px, _PLUGIN_BADGE_COLOR)
    disabled = _paint_plugin_badge(px, _PLUGIN_BADGE_COLOR_DISABLED)
    for mode in (
        QIcon.Mode.Normal,
        QIcon.Mode.Active,
        QIcon.Mode.Selected,
    ):
        icon.addPixmap(normal, mode, QIcon.State.Off)
        icon.addPixmap(normal, mode, QIcon.State.On)
    icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.Off)
    icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.On)
    return icon


def format_plugin_status_tip(base: str) -> str:
    text = (base or "").strip()
    if not text:
        return _PLUGIN_STATUS_HINT
    if _PLUGIN_STATUS_HINT in text:
        return text
    return f"{text}  ·  {_PLUGIN_STATUS_HINT}"


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


#: Gruppen des Plugin-Menues, in dieser Reihenfolge und je durch einen
#: Trennstrich abgesetzt. Die Folge bildet den Arbeitsweg ab: Buch aufsetzen,
#: Inhalt hineinholen, gestalten, Umschlag, freigeben, nachweisen, Werkzeuge.
#:
#: Diese Liste ist der einzige Ort, an dem die Menuegliederung steht -- die
#: ``order``-Zahlen der Manifeste ordnen nur, was hier nicht genannt ist.
#: Innerhalb einer Gruppe gilt die hier notierte Reihenfolge, nicht die Zahl:
#: „Bücher verwalten“ gehoert vor „Skeleton übernehmen“, weil man in dieser
#: Reihenfolge arbeitet.
#:
#: Ein neues Plugin, das hier fehlt, landet sichtbar in der letzten Gruppe --
#: es verschwindet nicht, gehoert aber mit einer Zeile an seinen Platz.
_PLUGIN_GROUPS: tuple[tuple[str, ...], ...] = (
    # Buch und Gerüst
    ("book_projects", "skeleton_populate", "skeleton_editor"),
    # Inhalt hineinholen und pflegen
    ("gg_content_swap", "asset_manager"),
    # Layout, Textauszeichnung und Satz
    ("doclayout_editor", "doclayout_wizard", "markup_inventory", "satz_werkzeuge"),
    # Umschlag
    ("cover_size", "kdp_cover", "stylecloud", "breathcloud"),
    # Vor der Veröffentlichung prüfen
    ("publish_readiness", "publisher_compliance"),
    # Ergebnis und Nachweis
    (
        "generated_books",
        "mapping_manager",
        "publish_record",
        "provenance",
        "uuid_manager",
    ),
    # Notizen
    ("memo_pad", "book_note"),
    # Kapitelliste (eigenes Thema)
    ("file_indexer",),
)


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

    by_name = {i.name: i for i in infos}
    gruppen = [
        [by_name[name] for name in gruppe if name in by_name]
        for gruppe in _PLUGIN_GROUPS
    ]
    einsortiert = {info.name for gruppe in gruppen for info in gruppe}
    rest = [i for i in infos if i.name not in einsortiert]
    rest.sort(key=lambda p: (p.order, p.label.casefold(), p.name.casefold()))
    if rest:
        gruppen.append(rest)

    def _add(info) -> None:
        action = QAction(info.label, menu)
        action.setIcon(plugin_menu_icon())
        tip = format_plugin_status_tip(getattr(info, "description", "") or info.label)
        action.setToolTip(tip)
        action.setStatusTip(tip)
        cb = resolve(f"plugin:{info.name}")
        if cb is not None:
            _bind_action(action, cb)
        else:
            action.setEnabled(False)
        menu.addAction(action)

    # Trennstrich nur zwischen gefuellten Gruppen -- eine leere Gruppe darf
    # keinen doppelten Strich hinterlassen.
    schon_etwas = False
    for gruppe in gruppen:
        if not gruppe:
            continue
        if schon_etwas:
            menu.addSeparator()
        for info in gruppe:
            _add(info)
        schon_etwas = True
