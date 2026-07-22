"""Deklarative Menue-Definitionen (Phase 4).

`MenuManager` (siehe `menu_manager.py`) liest diese Datenstrukturen
und baut daraus die Menueleiste. Dadurch kann die `build()`-Methode
rein iterativ bleiben, ohne dass die langen add_command-Listen im
`book_studio.py` wachsen.

Format:

    MENU_FILE = [
        MenuCascade(label="Buchstruktur (JSON)", children=[
            MenuItem(label="...", command="import_json"),
            MenuSeparator(),
            ...
        ]),
        MenuSeparator(),
        ...
    ]

Die `command`-Strings sind Namen von Studio-Attributen. Der Manager
loest sie zur Laufzeit ueber `getattr(self.studio, name)` auf.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class MenuItem:
    label: str
    command: str  # Studio-Attributname (Callable)
    accelerator: Optional[str] = None


@dataclass
class MenuSeparator:
    pass


@dataclass
class MenuCascade:
    label: str
    children: List[Union["MenuCascade", MenuItem, MenuSeparator]] = field(default_factory=list)


# --- Buchstruktur (Datei) ----------------------------------------------------

MENU_FILE = [
    MenuCascade(label="Buchstruktur (JSON)", children=[
        MenuItem(label="📂 Buchstruktur aus JSON-Datei laden", command="import_json"),
        MenuItem(label="💾 Buchstruktur als JSON-Datei speichern", command="quick_save_json", accelerator="Ctrl+S"),
        MenuItem(label="📝 Buchstruktur als JSON-Datei speichern als...", command="export_json"),
    ]),
    MenuSeparator(),
    MenuItem(label="💾 In Quarto speichern", command="save_project"),
    MenuSeparator(),
    MenuItem(label="🚪 Beenden", command="close_app"),
]


# --- Export ------------------------------------------------------------------

MENU_EXPORT = [
    MenuItem(label="🖨️ Buch rendern...", command="run_quarto_render", accelerator="F5"),
    MenuItem(label="📝 Buch als Single-Markdown exportieren (.md)", command="export_single_markdown"),
]


# --- Bearbeiten --------------------------------------------------------------

MENU_EDIT = [
    MenuItem(label="↩️ Undo", command="undo", accelerator="Ctrl+Z"),
    MenuItem(label="↪️ Redo", command="redo", accelerator="Ctrl+Y"),
    MenuSeparator(),
    MenuItem(label="➡️ Hinzufügen", command="add_files"),
    MenuItem(label="⬅️ Entfernen", command="remove_files"),
    MenuSeparator(),
    MenuItem(label="⬆️ Hoch", command="move_up"),
    MenuItem(label="⬇️ Runter", command="move_down"),
    MenuItem(label="➡️ Einrücken", command="indent_item"),
    MenuItem(label="⬅️ Ausrücken", command="outdent_item"),
]


# --- Ansicht -----------------------------------------------------------------

MENU_VIEW = [
    MenuItem(label="🔍 Preview öffnen", command="open_preview"),
    MenuItem(label="🔄 Titel neu laden", command="refresh_ui_titles"),
    MenuItem(label="📁 Projekte neu laden", command="reload_projects"),
    MenuSeparator(),
    MenuItem(label="🧹 Status-Filter zurücksetzen", command="reset_status_filter"),
]


# --- Tools -------------------------------------------------------------------

MENU_TOOLS = [
    MenuItem(label="🧹 Sanitizer", command="run_sanitizer_pipeline"),
    MenuItem(label="🧩 Studio-Konfiguration...", command="open_app_config_editor"),
    MenuItem(label="⚙️ Sanitizer-Konfiguration...", command="open_sanitizer_config_editor"),
    MenuItem(label="📘 Quarto.yml konfigurieren...", command="open_quarto_config_editor"),
    MenuItem(label="🔌 Plugin-Konfiguration…", command="open_plugin_config_editor"),
    MenuItem(label="🩺 Buch-Doktor", command="run_doctor"),
    MenuItem(label="✨ Frontmatter ergänzen…", command="heal_frontmatter"),
    MenuItem(label="📦 Backup", command="run_backup"),
    MenuItem(label="⏪ Time Machine", command="open_time_machine"),
    MenuSeparator(),
    MenuCascade(label="Wartung", children=[
        MenuItem(label="⚠️ _quarto.yml hart zurücksetzen (Nuke)", command="reset_quarto_yml"),
    ]),
]


# --- Hilfe -------------------------------------------------------------------

MENU_HELP = [
    MenuItem(label="📘 Handbuch öffnen", command="open_help_manual"),
    MenuItem(label="✏️ Handbuch-Quelle bearbeiten…", command="edit_help_manual_source"),
    MenuItem(label="📄 Handbuch als PDF rendern…", command="render_help_manual_pdf"),
    MenuSeparator(),
    MenuItem(label="ℹ️ Über", command="_show_about_dialog"),
]


# --- Kontextmenues (Tree + Liste) -------------------------------------------

CONTEXT_MENU_AVAIL = [
    MenuItem(label="📂 Im Explorer anzeigen", command="open_avail_in_explorer"),
    MenuItem(label="🖼 Fehlende Bilder anzeigen", command="show_avail_missing_images"),
]


CONTEXT_MENU_TREE = [
    MenuItem(label="📂 Im Explorer anzeigen", command="open_tree_in_explorer"),
    MenuItem(label="🖼 Fehlende Bilder anzeigen", command="show_tree_missing_images"),
]


__all__ = [
    "MenuCascade",
    "MenuItem",
    "MenuSeparator",
    "MENU_FILE",
    "MENU_EXPORT",
    "MENU_EDIT",
    "MENU_VIEW",
    "MENU_TOOLS",
    "MENU_HELP",
    "CONTEXT_MENU_AVAIL",
    "CONTEXT_MENU_TREE",
]
