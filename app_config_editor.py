import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from dialog_dirty_utils import DirtyStateController, confirm_discard_changes
from ui_theme import center_on_parent, style_dialog


class AppConfigEditor(tk.Toplevel):
    EXPORT_FORMATS = ("typst", "docx", "html", "pdf")
    FOOTNOTE_MODES = ("footnotes", "endnotes", "pandoc")
    DEFAULTS = {
        "content_root_path": ".",
        "log_font_size": 9,
        "abort_on_first_preflight_error": True,
        "abort_on_first_render_colon_warning": False,
        "enable_footnote_backlinks": False,
        "default_export_format": "typst",
        "default_export_template": "Standard",
        "default_footnote_mode": "endnotes",
        "log_auto_clear_default": False,
        "log_max_lines_default": 500,
        "prep_sources": [],
        "prep_dest_folder": "",
        "indexer_target_folder": "",
    }

    def __init__(self, parent, config_path, on_save=None, templates=None):
        super().__init__(parent)
        self.parent = parent
        self.config_path = Path(config_path)
        self.on_save = on_save
        self._templates = list(templates) if templates else ["Standard"]

        self._base_title = "Studio-Konfiguration"
        self.title(self._base_title)
        self.resizable(True, True)
        self.minsize(760, 420)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._dirty_controller = DirtyStateController(self, self._base_title)
        self.config_data = self._load_config()

        self.content_root_var = tk.StringVar(value=str(self.config_data.get("content_root_path", self.DEFAULTS["content_root_path"])))
        self.resolved_content_root_var = tk.StringVar(value="")
        self.log_font_size_var = tk.StringVar(value=str(self._sanitize_font_size(self.config_data.get("log_font_size", self.DEFAULTS["log_font_size"]))))
        self.abort_on_first_preflight_error_var = tk.BooleanVar(value=bool(self.config_data.get("abort_on_first_preflight_error", self.DEFAULTS["abort_on_first_preflight_error"])))
        self.abort_on_first_render_colon_warning_var = tk.BooleanVar(value=bool(self.config_data.get("abort_on_first_render_colon_warning", self.DEFAULTS["abort_on_first_render_colon_warning"])))
        self.enable_footnote_backlinks_var = tk.BooleanVar(value=bool(self.config_data.get("enable_footnote_backlinks", self.DEFAULTS["enable_footnote_backlinks"])))
        self.default_export_format_var = tk.StringVar(value=self._sanitize_export_format(self.config_data.get("default_export_format", self.DEFAULTS["default_export_format"])))
        self.default_export_template_var = tk.StringVar(value=str(self.config_data.get("default_export_template", self.DEFAULTS["default_export_template"]) or self.DEFAULTS["default_export_template"]))
        self.default_footnote_mode_var = tk.StringVar(value=self._sanitize_footnote_mode(self.config_data.get("default_footnote_mode", self.DEFAULTS["default_footnote_mode"])))
        self.log_auto_clear_default_var = tk.BooleanVar(value=bool(self.config_data.get("log_auto_clear_default", self.DEFAULTS["log_auto_clear_default"])))
        self.log_max_lines_default_var = tk.StringVar(value=str(self._sanitize_log_max_lines(self.config_data.get("log_max_lines_default", self.DEFAULTS["log_max_lines_default"]))))
        self.prep_sources_var = tk.StringVar(value=self._serialize_sources(self.config_data.get("prep_sources", self.DEFAULTS["prep_sources"])))
        self.prep_dest_folder_var = tk.StringVar(value=str(self.config_data.get("prep_dest_folder", self.DEFAULTS["prep_dest_folder"])))
        self.indexer_target_folder_var = tk.StringVar(value=str(self.config_data.get("indexer_target_folder", self.DEFAULTS["indexer_target_folder"])))
        self._initial_values = {
            "content_root_path": self.content_root_var.get(),
            "log_font_size": self.log_font_size_var.get(),
            "abort_on_first_preflight_error": self.abort_on_first_preflight_error_var.get(),
            "abort_on_first_render_colon_warning": self.abort_on_first_render_colon_warning_var.get(),
            "enable_footnote_backlinks": self.enable_footnote_backlinks_var.get(),
            "default_export_format": self.default_export_format_var.get(),
            "default_export_template": self.default_export_template_var.get(),
            "default_footnote_mode": self.default_footnote_mode_var.get(),
            "log_auto_clear_default": self.log_auto_clear_default_var.get(),
            "log_max_lines_default": self.log_max_lines_default_var.get(),
            "prep_sources": self.prep_sources_var.get(),
            "prep_dest_folder": self.prep_dest_folder_var.get(),
            "indexer_target_folder": self.indexer_target_folder_var.get(),
        }

        self.content_root_var.trace_add("write", self._on_field_changed)
        self.log_font_size_var.trace_add("write", self._on_field_changed)
        self.abort_on_first_preflight_error_var.trace_add("write", self._on_field_changed)
        self.abort_on_first_render_colon_warning_var.trace_add("write", self._on_field_changed)
        self.enable_footnote_backlinks_var.trace_add("write", self._on_field_changed)
        self.default_export_format_var.trace_add("write", self._on_field_changed)
        self.default_export_template_var.trace_add("write", self._on_field_changed)
        self.default_footnote_mode_var.trace_add("write", self._on_field_changed)
        self.log_auto_clear_default_var.trace_add("write", self._on_field_changed)
        self.log_max_lines_default_var.trace_add("write", self._on_field_changed)
        self.prep_sources_var.trace_add("write", self._on_field_changed)
        self.prep_dest_folder_var.trace_add("write", self._on_field_changed)
        self.indexer_target_folder_var.trace_add("write", self._on_field_changed)

        center_on_parent(self, parent, 840, 520)
        self._build_ui()
        self._dirty_controller.capture_initial(self._initial_values)

    def _load_config(self):
        if not self.config_path.exists():
            return {}
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def _sanitize_font_size(self, value):
        try:
            font_size = int(value)
        except (TypeError, ValueError):
            font_size = 9
        return max(7, min(24, font_size))

    def _sanitize_export_format(self, value):
        value = str(value).strip().lower()
        return value if value in self.EXPORT_FORMATS else "typst"

    def _sanitize_footnote_mode(self, value):
        value = str(value).strip().lower()
        return value if value in self.FOOTNOTE_MODES else "endnotes"

    def _sanitize_log_max_lines(self, value):
        try:
            amount = int(value)
        except (TypeError, ValueError):
            amount = 500
        return max(50, min(50000, amount))

    def _serialize_sources(self, value):
        if isinstance(value, list):
            parts = [str(item).strip() for item in value if str(item).strip()]
            return "; ".join(parts)
        if isinstance(value, str):
            return value.strip()
        return ""

    def _parse_sources(self, value):
        return [item.strip() for item in str(value or "").split(";") if item.strip()]

    def _build_ui(self):
        style_dialog(self)
        root_frame = tk.Frame(self)
        root_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(root_frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(root_frame, orient="vertical", command=canvas.yview)
        wrapper = ttk.Frame(canvas, padding=(16, 14))

        content_window = canvas.create_window((0, 0), window=wrapper, anchor="nw")

        def _on_wrapper_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(content_window, width=event.width)

        wrapper.bind("<Configure>", _on_wrapper_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                return "break"
            return "break"

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.bind("<Destroy>", lambda _event: canvas.unbind_all("<MouseWheel>"), add="+")

        ttk.Label(wrapper, text="Studio-Konfiguration", font=("Segoe UI Semibold", 11)).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(wrapper, text="Projekt-Root (content_root_path):").grid(row=1, column=0, sticky="w", pady=6)
        root_entry = ttk.Entry(wrapper, textvariable=self.content_root_var, width=58)
        root_entry.grid(row=1, column=1, sticky="we", pady=6)
        ttk.Button(wrapper, text="Ordner...", style="Tool.TButton", command=self._browse_root).grid(row=1, column=2, sticky="e", padx=(8, 0), pady=6)

        ttk.Label(wrapper, text="Aktuell aufgelöst:", font=("Segoe UI", 8, "bold")).grid(row=2, column=0, sticky="nw", pady=(0, 6))
        ttk.Label(
            wrapper,
            textvariable=self.resolved_content_root_var,
            font=("Segoe UI", 8),
            justify="left",
            wraplength=520,
        ).grid(row=2, column=1, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Label(wrapper, text="Log-Fontgröße (7-24):").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.log_font_size_var,
            values=[str(i) for i in range(7, 25)],
            state="readonly",
            width=8,
        ).grid(row=3, column=1, sticky="w", pady=6)

        ttk.Label(wrapper, text="Render: Beim ersten Preflight-Fehler abbrechen:").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Checkbutton(wrapper, variable=self.abort_on_first_preflight_error_var).grid(row=4, column=1, sticky="w", pady=6)

        ttk.Label(wrapper, text="Render: Beim ersten ':::'-Warnhinweis abbrechen:").grid(row=5, column=0, sticky="w", pady=6)
        ttk.Checkbutton(wrapper, variable=self.abort_on_first_render_colon_warning_var).grid(row=5, column=1, sticky="w", pady=6)

        ttk.Label(wrapper, text="Render: Fußnoten-Rücksprunglinks erzeugen:").grid(row=6, column=0, sticky="w", pady=6)
        ttk.Checkbutton(wrapper, variable=self.enable_footnote_backlinks_var).grid(row=6, column=1, sticky="w", pady=6)
        ttk.Label(
            wrapper,
            text="Nur für 'footnotes'-Modus + HTML relevant. Im 'endnotes'-Modus + Typst sind PDF-Links immer aktiv.",
            font=("Segoe UI", 8),
            foreground="#888888",
        ).grid(row=6, column=2, sticky="w", padx=(8, 0), pady=6)

        ttk.Separator(wrapper, orient="horizontal").grid(row=7, column=0, columnspan=3, sticky="we", pady=(6, 8))

        ttk.Label(wrapper, text="Default-Exportformat:").grid(row=8, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.default_export_format_var,
            values=self.EXPORT_FORMATS,
            state="readonly",
            width=10,
        ).grid(row=8, column=1, sticky="w", pady=6)

        ttk.Label(wrapper, text="Default-Template:").grid(row=9, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.default_export_template_var,
            values=self._templates,
            width=32,
        ).grid(row=9, column=1, sticky="w", pady=6)
        ttk.Label(
            wrapper,
            text="\"Standard\", Dateiname aus templates/ oder \"EXT: <name>\" für Quarto-Extensions",
            font=("Segoe UI", 8),
            foreground="#888888",
        ).grid(row=10, column=1, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Label(wrapper, text="Default-Notenmodus:").grid(row=11, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.default_footnote_mode_var,
            values=self.FOOTNOTE_MODES,
            state="readonly",
            width=12,
        ).grid(row=11, column=1, sticky="w", pady=6)

        ttk.Label(wrapper, text="Log Auto-Clear Default:").grid(row=12, column=0, sticky="w", pady=6)
        ttk.Checkbutton(wrapper, variable=self.log_auto_clear_default_var).grid(row=12, column=1, sticky="w", pady=6)

        ttk.Label(wrapper, text="Log-Limit Default:").grid(row=13, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.log_max_lines_default_var,
            values=["200", "500", "1000", "2000", "5000", "10000"],
            state="readonly",
            width=10,
        ).grid(row=13, column=1, sticky="w", pady=6)

        ttk.Separator(wrapper, orient="horizontal").grid(row=14, column=0, columnspan=3, sticky="we", pady=(8, 8))
        ttk.Label(wrapper, text="Tools: Merge-Quellpfade (; getrennt):").grid(row=15, column=0, sticky="w", pady=6)
        ttk.Entry(wrapper, textvariable=self.prep_sources_var, width=58).grid(row=15, column=1, sticky="we", pady=6)
        ttk.Button(wrapper, text="Ordner +", style="Tool.TButton", command=self._add_prep_source_folder).grid(row=15, column=2, sticky="e", padx=(8, 0), pady=6)

        ttk.Label(wrapper, text="Tools: Merge-Zielordner:").grid(row=16, column=0, sticky="w", pady=6)
        ttk.Entry(wrapper, textvariable=self.prep_dest_folder_var, width=58).grid(row=16, column=1, sticky="we", pady=6)
        ttk.Button(wrapper, text="Ordner...", style="Tool.TButton", command=self._browse_prep_dest_folder).grid(row=16, column=2, sticky="e", padx=(8, 0), pady=6)

        ttk.Label(wrapper, text="Tools: Indexer-Zielordner:").grid(row=17, column=0, sticky="w", pady=6)
        ttk.Entry(wrapper, textvariable=self.indexer_target_folder_var, width=58).grid(row=17, column=1, sticky="we", pady=6)
        ttk.Button(wrapper, text="Ordner...", style="Tool.TButton", command=self._browse_indexer_target_folder).grid(row=17, column=2, sticky="e", padx=(8, 0), pady=6)

        hint = (
            "Relative Pfade gelten relativ zum Book-Studio-Codeordner. "
            "Nach dem Speichern wird die Projektliste neu geladen."
        )
        ttk.Label(wrapper, text=hint, font=("Segoe UI", 8)).grid(row=18, column=0, columnspan=3, sticky="w", pady=(6, 10))

        button_row = ttk.Frame(wrapper)
        button_row.grid(row=19, column=0, columnspan=3, sticky="e", pady=(2, 0))
        ttk.Button(button_row, text="Abbrechen", style="Tool.TButton", command=self._cancel).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(button_row, text="Speichern", style="Accent.TButton", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(button_row, text="Auf Standard zurücksetzen", style="Tool.TButton", command=self._reset_defaults).pack(side=tk.RIGHT, padx=(0, 8))

        wrapper.columnconfigure(1, weight=1)
        canvas.yview_moveto(0.0)
        self._update_resolved_content_root_display()

    def _browse_root(self):
        selected = filedialog.askdirectory(parent=self, title="Projekt-Root auswählen")
        if selected:
            self.content_root_var.set(selected)

    def _add_prep_source_folder(self):
        selected = filedialog.askdirectory(parent=self, title="Merge-Quellordner hinzufügen")
        if not selected:
            return
        current = self._parse_sources(self.prep_sources_var.get())
        if selected not in current:
            current.append(selected)
        self.prep_sources_var.set("; ".join(current))

    def _browse_prep_dest_folder(self):
        selected = filedialog.askdirectory(parent=self, title="Merge-Zielordner auswählen")
        if selected:
            self.prep_dest_folder_var.set(selected)

    def _browse_indexer_target_folder(self):
        selected = filedialog.askdirectory(parent=self, title="Indexer-Zielordner auswählen")
        if selected:
            self.indexer_target_folder_var.set(selected)

    def _collect_values(self):
        return {
            "content_root_path": self.content_root_var.get().strip() or ".",
            "log_font_size": self.log_font_size_var.get().strip() or "9",
            "abort_on_first_preflight_error": bool(self.abort_on_first_preflight_error_var.get()),
            "abort_on_first_render_colon_warning": bool(self.abort_on_first_render_colon_warning_var.get()),
            "enable_footnote_backlinks": bool(self.enable_footnote_backlinks_var.get()),
            "default_export_format": self.default_export_format_var.get().strip().lower(),
            "default_export_template": self.default_export_template_var.get().strip() or "Standard",
            "default_footnote_mode": self.default_footnote_mode_var.get().strip().lower(),
            "log_auto_clear_default": bool(self.log_auto_clear_default_var.get()),
            "log_max_lines_default": self.log_max_lines_default_var.get().strip() or "500",
            "prep_sources": self._parse_sources(self.prep_sources_var.get()),
            "prep_dest_folder": self.prep_dest_folder_var.get().strip(),
            "indexer_target_folder": self.indexer_target_folder_var.get().strip(),
        }

    def _on_field_changed(self, *_args):
        self._update_resolved_content_root_display()
        self._dirty_controller.refresh(self._collect_values())

    def _update_resolved_content_root_display(self):
        root_value = self.content_root_var.get().strip() or "."
        root_path = Path(root_value).expanduser()
        if not root_path.is_absolute():
            root_path = self.config_path.parent / root_path
        root_path = root_path.resolve()
        if root_path.exists() and root_path.is_dir():
            self.resolved_content_root_var.set(str(root_path))
        else:
            self.resolved_content_root_var.set(f"{root_path}  (⚠ ungültig)")

    def _reset_defaults(self):
        self.content_root_var.set(self.DEFAULTS["content_root_path"])
        self.log_font_size_var.set(str(self.DEFAULTS["log_font_size"]))
        self.abort_on_first_preflight_error_var.set(self.DEFAULTS["abort_on_first_preflight_error"])
        self.abort_on_first_render_colon_warning_var.set(self.DEFAULTS["abort_on_first_render_colon_warning"])
        self.enable_footnote_backlinks_var.set(self.DEFAULTS["enable_footnote_backlinks"])
        self.default_export_format_var.set(self.DEFAULTS["default_export_format"])
        self.default_export_template_var.set(self.DEFAULTS["default_export_template"])
        self.default_footnote_mode_var.set(self.DEFAULTS["default_footnote_mode"])
        self.log_auto_clear_default_var.set(self.DEFAULTS["log_auto_clear_default"])
        self.log_max_lines_default_var.set(str(self.DEFAULTS["log_max_lines_default"]))
        self.prep_sources_var.set(self._serialize_sources(self.DEFAULTS["prep_sources"]))
        self.prep_dest_folder_var.set(self.DEFAULTS["prep_dest_folder"])
        self.indexer_target_folder_var.set(self.DEFAULTS["indexer_target_folder"])

    def _save(self):
        values = self._collect_values()

        root_value = values["content_root_path"]
        root_path = Path(root_value).expanduser()
        if not root_path.is_absolute():
            root_path = (self.config_path.parent / root_path)
        root_path = root_path.resolve()
        if not root_path.exists() or not root_path.is_dir():
            messagebox.showerror("Ungültiger Root-Pfad", f"Der gewählte content_root_path ist kein existierender Ordner:\n{root_path}")
            return

        try:
            font_size = int(values["log_font_size"])
        except (TypeError, ValueError):
            messagebox.showerror("Ungültige Fontgröße", "Die Log-Fontgröße muss eine Zahl zwischen 7 und 24 sein.")
            return

        if font_size < 7 or font_size > 24:
            messagebox.showerror("Ungültige Fontgröße", "Die Log-Fontgröße muss zwischen 7 und 24 liegen.")
            return

        export_format = self._sanitize_export_format(values["default_export_format"])
        footnote_mode = self._sanitize_footnote_mode(values["default_footnote_mode"])
        log_max_lines_default = self._sanitize_log_max_lines(values["log_max_lines_default"])

        for key, title in (
            ("prep_dest_folder", "Merge-Zielordner"),
            ("indexer_target_folder", "Indexer-Zielordner"),
        ):
            raw_value = str(values.get(key, "")).strip()
            if not raw_value:
                continue
            resolved_path = Path(raw_value).expanduser()
            if not resolved_path.is_absolute():
                resolved_path = self.config_path.parent / resolved_path
            resolved_path = resolved_path.resolve()
            if not resolved_path.exists() or not resolved_path.is_dir():
                messagebox.showerror("Ungültiger Pfad", f"{title} ist kein existierender Ordner:\n{resolved_path}")
                return

        for source in values["prep_sources"]:
            source_path = Path(source).expanduser()
            if not source_path.is_absolute():
                source_path = self.config_path.parent / source_path
            source_path = source_path.resolve()
            if not source_path.exists() or not source_path.is_dir():
                messagebox.showerror("Ungültiger Pfad", f"Merge-Quellordner existiert nicht:\n{source_path}")
                return

        payload = {
            "content_root_path": values["content_root_path"],
            "log_font_size": font_size,
            "abort_on_first_preflight_error": values["abort_on_first_preflight_error"],
            "abort_on_first_render_colon_warning": values["abort_on_first_render_colon_warning"],
            "enable_footnote_backlinks": values["enable_footnote_backlinks"],
            "default_export_format": export_format,
            "default_export_template": values["default_export_template"],
            "default_footnote_mode": footnote_mode,
            "log_auto_clear_default": values["log_auto_clear_default"],
            "log_max_lines_default": log_max_lines_default,
            "prep_sources": values["prep_sources"],
            "prep_dest_folder": values["prep_dest_folder"],
            "indexer_target_folder": values["indexer_target_folder"],
        }
        if callable(self.on_save):
            self.on_save(payload)
        self.destroy()

    def _cancel(self):
        self._dirty_controller.refresh(self._collect_values())
        if self._dirty_controller.is_dirty:
            proceed = confirm_discard_changes(
                self,
                "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen.\n\nDialog wirklich schließen und Änderungen verwerfen?",
            )
            if not proceed:
                return
        self.destroy()
