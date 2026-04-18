import tkinter as tk
from tkinter import messagebox
from ui_theme import apply_menu_theme


class MenuManager:
    def __init__(self, studio):
        self.studio = studio

    def _create_menu(self, parent):
        menu = tk.Menu(parent, tearoff=0)
        apply_menu_theme(menu)
        return menu

    def build(self):
        menu_bar = tk.Menu(self.studio.root)
        apply_menu_theme(menu_bar)

        file_menu = self._create_menu(menu_bar)
        json_menu = self._create_menu(file_menu)
        json_menu.add_command(label="📂 Buchstruktur aus JSON-Datei laden", command=self.studio.import_json)
        json_menu.add_command(label="💾 Buchstruktur als JSON-Datei speichern", command=self.studio.quick_save_json, accelerator="Ctrl+S")
        json_menu.add_command(label="📝 Buchstruktur als JSON-Datei speichern als...", command=self.studio.export_json)
        file_menu.add_cascade(label="Buchstruktur (JSON)", menu=json_menu)
        file_menu.add_separator()
        file_menu.add_command(label="💾 In Quarto speichern", command=self.studio.save_project)
        file_menu.add_separator()
        file_menu.add_command(label="🚪 Beenden", command=self.studio.close_app)
        menu_bar.add_cascade(label="Datei", menu=file_menu)

        export_menu = self._create_menu(menu_bar)
        export_menu.add_command(label="🖨️ Buch rendern...", command=self.studio.exporter.run_quarto_render, accelerator="F5")
        export_menu.add_command(label="📝 Buch als Single-Markdown exportieren (.md)", command=self.studio.exporter.export_single_markdown)
        menu_bar.add_cascade(label="Export", menu=export_menu)

        edit_menu = self._create_menu(menu_bar)
        edit_menu.add_command(label="↩️ Undo", command=self.studio.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="↪️ Redo", command=self.studio.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="➡️ Hinzufügen", command=self.studio.add_files)
        edit_menu.add_command(label="⬅️ Entfernen", command=self.studio.remove_files)
        edit_menu.add_separator()
        edit_menu.add_command(label="⬆️ Hoch", command=self.studio.move_up)
        edit_menu.add_command(label="⬇️ Runter", command=self.studio.move_down)
        edit_menu.add_command(label="➡️ Einrücken", command=self.studio.indent_item)
        edit_menu.add_command(label="⬅️ Ausrücken", command=self.studio.outdent_item)
        menu_bar.add_cascade(label="Bearbeiten", menu=edit_menu)

        view_menu = self._create_menu(menu_bar)
        view_menu.add_command(label="🔍 Preview öffnen", command=self.studio.open_preview)
        view_menu.add_command(label="🔄 Titel neu laden", command=self.studio.refresh_ui_titles)
        view_menu.add_separator()
        view_menu.add_command(
            label="🧹 Status-Filter zurücksetzen",
            command=lambda: (self.studio.status_filter_var.set("Alle"), self.studio.apply_status_filter())
        )
        menu_bar.add_cascade(label="Ansicht", menu=view_menu)

        tools_menu = self._create_menu(menu_bar)
        tools_menu.add_command(label="🧹 Sanitizer", command=self.studio.run_sanitizer_pipeline)
        tools_menu.add_command(label="🧩 Studio-Konfiguration...", command=self.studio.open_app_config_editor)
        tools_menu.add_command(label="⚙️ Sanitizer-Konfiguration...", command=self.studio.open_sanitizer_config_editor)
        tools_menu.add_command(label="📘 Quarto.yml konfigurieren...", command=self.studio.open_quarto_config_editor)
        tools_menu.add_command(label="🩺 Buch-Doktor", command=self.studio.run_doctor)
        tools_menu.add_command(label="📦 Backup", command=self.studio.run_backup)
        tools_menu.add_command(label="⏪ Time Machine", command=self.studio.open_time_machine)

        maintenance_menu = self._create_menu(tools_menu)
        maintenance_menu.add_command(label="⚠️ _quarto.yml hart zurücksetzen (Nuke)", command=self.studio.reset_quarto_yml)
        tools_menu.add_separator()
        tools_menu.add_cascade(label="Wartung", menu=maintenance_menu)
        menu_bar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = self._create_menu(menu_bar)
        help_menu.add_command(label="📘 Handbuch öffnen", command=self.studio.open_help_manual)
        help_menu.add_separator()
        help_menu.add_command(label="ℹ️ Über", command=self._show_about_dialog)
        menu_bar.add_cascade(label="Hilfe", menu=help_menu)

        self.studio.root.config(menu=menu_bar)

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
