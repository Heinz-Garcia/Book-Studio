"""MenuManager - baut die Menueleiste aus deklarativen Definitionen.

Phase 4: Die Menue-Items sind in `menu_definitions.py` als
Datenstrukturen definiert. Diese Datei enthaelt nur noch die
Wandlung Daten -> Tk-Menu-Widgets.

Verweise:
- .doc/gui_architektur.md (Modulgrenzen)
- menu_definitions.py (Datenstrukturen)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Optional

from ui_theme import apply_menu_theme

from menu_definitions import (
    CONTEXT_MENU_AVAIL,
    CONTEXT_MENU_TREE,
    MENU_EDIT,
    MENU_EXPORT,
    MENU_FILE,
    MENU_HELP,
    MENU_TOOLS,
    MENU_VIEW,
    PLUGIN_MENU_FALLBACK,
    MenuCascade,
    MenuItem,
    MenuSeparator,
)

# Default-Pfad fuer das Plugins-Verzeichnis. Liegt eine Ebene
# oberhalb von `book_studio.py` (also Projekt-Root).
DEFAULT_PLUGINS_DIR = Path(__file__).resolve().parent / "plugins"


class MenuManager:
    def __init__(self, studio, plugins_dir: Optional[Path] = None):
        self.studio = studio
        self._plugins_dir = plugins_dir or DEFAULT_PLUGINS_DIR

    def _create_menu(self, parent):
        menu = tk.Menu(parent, tearoff=0)
        apply_menu_theme(menu)
        return menu

    def _resolve_command(self, name: str):
        """Loest einen Command-Namen zu einer Callable auf.

        Spezialnamen:
        - '_show_about_dialog': interne About-Box
        - 'run_quarto_render', 'export_single_markdown': delegieren an Exporter
        - 'reset_status_filter': setzt Filter + appliziert
        - 'plugin:<name>': Plugin-Entrypoint-Aufruf (Phase 3)
        """
        if name == "_show_about_dialog":
            return self._show_about_dialog
        if name == "run_quarto_render":
            return self.studio.exporter.run_quarto_render
        if name == "export_single_markdown":
            return self.studio.exporter.export_single_markdown
        if name == "reset_status_filter":
            return lambda: (
                self.studio.status_filter_var.set("Alle"),
                self.studio.apply_status_filter(),
            )
        if name.startswith("plugin:"):
            return self._make_plugin_runner(name[len("plugin:"):])
        if not hasattr(self.studio, name):
            # B-Fix (Code-Review 2026-07-03): ein Tippfehler in einem
            # Menue-Definitionsnamen liess `getattr(...)` ohne Default
            # vorher mit `AttributeError` beim Menue-Aufbau crashen (nicht,
            # wie urspruenglich vermutet, still `command=None` liefern).
            # Statt die komplette Menueleiste (und damit den Programmstart)
            # abstuerzen zu lassen, wird ein sprechender Platzhalter
            # zurueckgegeben, der beim Klick eine Warnung zeigt.
            return self._make_missing_command_warning(name)
        return getattr(self.studio, name)

    def _make_missing_command_warning(self, missing_name: str):
        def _missing_command():
            messagebox.showwarning(
                "Menü-Befehl nicht gefunden",
                f"Der Menü-Befehl '{missing_name}' ist nicht implementiert "
                "(vermutlich ein Tippfehler in der Menü-Definition).",
            )

        return _missing_command

    def _make_plugin_runner(self, plugin_name: str):
        """Erzeugt einen Runner fuer ein Plugin.

        Delegiert an `services.plugin_loader.PluginLoader.discover()`.
        Wenn das Plugin nicht gefunden wird, wird ein No-Op-Runner
        geliefert, der eine Warnung loggt (kein Crash).
        """
        from services.plugin_loader import PluginLoader

        def _runner():
            loader = PluginLoader(self._plugins_dir)
            info = loader.get(plugin_name)
            if info is None:
                if hasattr(self.studio, "log"):
                    self.studio.log(
                        f"⚠️ Plugin nicht gefunden: {plugin_name}",
                        "warning",
                    )
                return
            if info.load_error:
                if hasattr(self.studio, "log"):
                    self.studio.log(
                        f"⚠️ Plugin {plugin_name} nicht ladbar: {info.load_error}",
                        "warning",
                    )
                return
            try:
                info.callable(self.studio)
            except Exception as exc:  # pragma: no cover - defensive
                if hasattr(self.studio, "log"):
                    self.studio.log(
                        f"❌ Plugin {plugin_name} abgestuerzt: {exc}",
                        "error",
                    )

        return _runner

    def _populate(self, menu_widget, items):
        for entry in items:
            if isinstance(entry, MenuSeparator):
                menu_widget.add_separator()
            elif isinstance(entry, MenuCascade):
                sub = self._create_menu(menu_widget)
                self._populate(sub, entry.children)
                menu_widget.add_cascade(label=entry.label, menu=sub)
            elif isinstance(entry, MenuItem):
                cmd = self._resolve_command(entry.command)
                if entry.accelerator:
                    menu_widget.add_command(
                        label=entry.label, command=cmd, accelerator=entry.accelerator
                    )
                else:
                    menu_widget.add_command(label=entry.label, command=cmd)
            else:
                raise TypeError(f"Unbekannter Menue-Eintrag: {type(entry).__name__}")

    def build(self):
        menu_bar = tk.Menu(self.studio.root)
        apply_menu_theme(menu_bar)

        for label, items in [
            ("Export", MENU_EXPORT),
            ("Bearbeiten", MENU_EDIT),
            ("Ansicht", MENU_VIEW),
            ("Tools", self._build_tools_items()),
            ("Hilfe", MENU_HELP),
        ]:
            sub = self._create_menu(menu_bar)
            self._populate(sub, items)
            menu_bar.add_cascade(label=label, menu=sub)

        # "Datei" wird gesondert gebaut: enthaelt das dynamische
        # "Letzte aktive Projekte"-Untermenue (siehe _build_file_menu).
        menu_bar.insert_cascade(0, label="Datei", menu=self._build_file_menu(menu_bar))

        self.studio.root.config(menu=menu_bar)

    def _build_file_menu(self, parent):
        """Baut das 'Datei'-Menue inkl. dynamischem 'Letzte aktive
        Projekte'-Untermenue (per `postcommand` bei jedem Oeffnen neu
        befuellt, da sich die Liste waehrend der Sitzung aendert)."""
        menu = self._create_menu(parent)
        recent_menu = self._create_menu(menu)
        recent_menu.configure(postcommand=lambda: self._refresh_recent_projects_menu(recent_menu))
        menu.add_cascade(label="📁 Letzte aktive Projekte", menu=recent_menu)
        menu.add_separator()
        self._populate(menu, MENU_FILE)
        return menu

    def _refresh_recent_projects_menu(self, menu_widget):
        menu_widget.delete(0, "end")
        entries = self.studio.get_recent_books() if hasattr(self.studio, "get_recent_books") else []
        if not entries:
            menu_widget.add_command(label="(keine)", state="disabled")
            return
        for entry in entries:
            menu_widget.add_command(
                label=entry["label"],
                command=lambda k=entry["key"]: self.studio.open_recent_book(k),
            )

    def _build_tools_items(self) -> list:
        """Erzeugt die Tools-Menue-Items inkl. dynamischer Plugin-Eintraege.

        Phase 3: Wenn der PluginLoader Plugins mit `menu_section=Tools`
        findet, werden sie hinter den Standard-Tools als Cascade
        'Plugins' einsortiert. Sonst faellt das Menue auf den
        `PLUGIN_MENU_FALLBACK` zurueck.
        """
        items = list(MENU_TOOLS)
        plugin_items = self._collect_plugin_items()
        if plugin_items:
            items.append(MenuSeparator())
            items.append(MenuCascade(label="Plugins", children=plugin_items))
        return items

    def _collect_plugin_items(self) -> list:
        """Liest die `plugins/`-Verzeichnis-Manifeste und liefert
        `MenuItem`-Eintraege fuer `menu_section=Tools`.
        """
        try:
            from services.plugin_loader import PluginLoader
        except ImportError:
            return list(PLUGIN_MENU_FALLBACK)
        loader = PluginLoader(self._plugins_dir)
        infos = loader.discover()
        tool_infos = [i for i in infos if i.menu_section == "Tools" and i.load_error is None]
        if not tool_infos:
            return list(PLUGIN_MENU_FALLBACK)
        return [
            MenuItem(label=info.label, command=f"plugin:{info.name}")
            for info in tool_infos
        ]

    # --- Kontextmenues -------------------------------------------------------

    def build_avail_context_menu(self, parent):
        menu = self._create_menu(parent)
        self._populate(menu, CONTEXT_MENU_AVAIL)
        return menu

    def build_tree_context_menu(self, parent):
        menu = self._create_menu(parent)
        self._populate(menu, CONTEXT_MENU_TREE)
        return menu

    def _show_about_dialog(self):
        app_title = getattr(self.studio, "app_name", "Quarto Book Studio")
        messagebox.showinfo(
            "Über Quarto Book Studio",
            f"{app_title}\n\n"
            "Kürzel:\n"
            "- Ctrl+S: Speichern\n"
            "- Ctrl+Z / Ctrl+Y: Undo / Redo\n"
            "- F5: Rendern"
        )
