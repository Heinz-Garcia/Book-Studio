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
    MenuCascade,
    MenuItem,
    MenuSeparator,
)


class MenuManager:
    def __init__(self, studio):
        self.studio = studio

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
        return getattr(self.studio, name)

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
            ("Datei", MENU_FILE),
            ("Export", MENU_EXPORT),
            ("Bearbeiten", MENU_EDIT),
            ("Ansicht", MENU_VIEW),
            ("Tools", MENU_TOOLS),
            ("Hilfe", MENU_HELP),
        ]:
            sub = self._create_menu(menu_bar)
            self._populate(sub, items)
            menu_bar.add_cascade(label=label, menu=sub)

        self.studio.root.config(menu=menu_bar)

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
