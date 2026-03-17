# PROJEKT-KONTEXT: BOOK STUDIO
Generiert am: 17.03.2026 16:55:25

## 🗂️ GEPACKTE DATEIEN (Inhaltsverzeichnis)
Folgende Dateien wurden in diesem Kontext gebündelt:

- `.vscode/settings.json`
- `app_config_editor.py`
- `Band_Dummy/_quarto.yml`
- `Band_Stoffwechselgesundheit/_extensions/elipousson/typstdoc/_extension.yml`
- `Band_Stoffwechselgesundheit/_extensions/quarto-ext/letter/_extension.yml`
- `Band_Stoffwechselgesundheit/_quarto.yml`
- `Band_Template/_quarto.yml`
- `book_doctor.py`
- `book_studio.py`
- `dialog_dirty_utils.py`
- `examples/unmanned_request.json`
- `examples/unmanned_request_ext_typstdoc.json`
- `examples/unmanned_request_prepare_only.json`
- `export_dialog.py`
- `export_manager.py`
- `footnote_harvester.py`
- `log_manager.py`
- `markdown_asset_scanner.py`
- `md_editor.py`
- `menu_manager.py`
- `pre_processor.py`
- `preview_inspector.py`
- `quarto_config_editor.py`
- `quarto_render_safe.py`
- `render_current_book.py`
- `Sanitizer.py`
- `sanitizer_config_editor.py`
- `search_filter.py`
- `session_manager.py`
- `smoke_tests.py`
- `studio_config.json`
- `template_manager.py`
- `templates/quarto_reset_minimal.yml`
- `test.py`
- `tests/test_book_doctor_regression.py`
- `tests/test_export_manager_regression.py`
- `tests/test_footnote_harvester_regression.py`
- `tests/test_pre_processor_regression.py`
- `tests/test_yaml_engine_regression.py`
- `tools/Book_Preper_Scripter.py`
- `tools/Files_Indexer.py`
- `ui_actions_manager.py`
- `ui_theme.py`
- `unmanned_trigger.py`
- `yaml_engine.py`

---



======================================================================
📁 FILE: .vscode/settings.json
======================================================================

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
  "python.analysis.typeCheckingMode": "off",
  "editor.formatOnSave": false,
  "python.analysis.diagnosticSeverityOverrides": {
    "reportUnusedImport": "information",
    "reportMissingModuleSource": "none"
  },
  "flake8.args": [
    "--ignore=E,W,F"
  ],
  "files.exclude": {
    "**/.git": true,
    "**/.svn": true,
    "**/.hg": true,
    "**/.DS_Store": true,
    "**/Thumbs.db": true,
    "**/CVS": true,
    "**/__pycache__": true,
    "**/.venv": true,
    "Band_Template": true,
    "Band_Dummy": true
  },
  "markdownlint.config": {
    "MD033": false,
    "MD025": false
  },
  "hide-files.files": [
    "Band_Template",
    "Band_Dummy"
  ],
  "chat.tools.terminal.autoApprove": {
    "c:/Users/Daniel/Documents/Python/IFJN/Book-Studio/.venv/Scripts/python.exe": true,
    "/^quarto render \"Band_Stoffwechselgesundheit\" --to typstdoc-typst$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "Tee-Object": true,
    "ForEach-Object": true,
    ".\\.venv\\Scripts\\python.exe": true,
    "/^python smoke_tests\\.py 2>&1 \\| head -100$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "/^python smoke_tests\\.py 2>&1 \\| Select-Object -First 150$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "/^python smoke_tests\\.py 2>&1 \\| Select-Object -First 200$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "/^python -c \"from sanitizer_config_editor import SanitizerConfigEditor, parse_toml_with_comments; print\\('✓ Import successful'\\)\"$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "/^cd \"c:\\\\Users\\\\Daniel\\\\Documents\\\\Python\\\\IFJN\\\\Book-Studio\" ; python << 'EOF'\nfrom pathlib import Path\nfrom sanitizer_config_editor import parse_toml_with_comments\n\n# Test parsing with the actual TOML file\nconfig_path = Path\\(\"sanitizer_config\\.toml\"\\)\nparsed = parse_toml_with_comments\\(config_path\\)\n\nprint\\(\"=== Parsed TOML Structure ===\"\\)\nfor section_name, section_dict in parsed\\.items\\(\\):\n    print\\(f\"\\\\n\\[\\{section_name\\}\\]\"\\)\n    for key, spec in section_dict\\.items\\(\\):\n        if key == \"__meta__\":\n            print\\(f\"  __meta__: \\{spec\\}\"\\)\n        else:\n            print\\(f\"  \\{key\\}: value=\\{spec\\.get\\('value'\\)\\}, type=\\{spec\\.get\\('type'\\)\\}, doc=\\{spec\\.get\\('doc'\\)\\[:50\\]\\}\\.\\.\\.\"\\)\nEOF\n$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "/^python test_parser\\.py$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "/^python test_editor_refactored\\.py$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "/^python test_toml_preservation\\.py$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "/^python test_integration\\.py$/": {
      "approve": true,
      "matchCommandLine": true
    },
    "/^python test_parser\\.py 2>&1 \\| grep -A 10 \"\\\\\\[tags\\\\\\]\"$/": {
      "approve": true,
      "matchCommandLine": true
    }
  }
}
```


======================================================================
📁 FILE: app_config_editor.py
======================================================================

```py
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

```


======================================================================
📁 FILE: Band_Dummy/_quarto.yml
======================================================================

```yaml
project:
  output-dir: export/_book
  type: book
book:
  title: NurWidmung
  author: Wolfram Daniel Heinz Garcia
  date: last-modified
  chapters:
  - index.md
  - content/Grundlagen.md
  - content/Klappentext_hinten.md
  - content/Text_2.md
  - content/Prozessbeschreibung.md
  - content/widmung.md
  - content/Sicherheit.md
  - content/Klappentext_innen.md
  - content/Text_1.md
  - content/Prozessbeschreibung_content.md
format:
  typst:
    keep-typ: true
    toc: true
    toc-depth: 3
    number-sections: true
    section-numbering: 1.1.1
    papersize: a4
  html:
    theme: cosmo
    toc: true

```


======================================================================
📁 FILE: Band_Stoffwechselgesundheit/_extensions/elipousson/typstdoc/_extension.yml
======================================================================

```yaml
title: typstdoc
author: Eli Pousson
version: 1.0.0
quarto-required: ">=1.5.0"
contributes:
  formats:
    common:
      knitr:
          opts_chunk:
            echo: false
    typst:
      template: template.typ
      template-partials:
        - typst-template.typ
        - typst-show.typ


```


======================================================================
📁 FILE: Band_Stoffwechselgesundheit/_extensions/quarto-ext/letter/_extension.yml
======================================================================

```yaml
title: Typst Letter
author: J.J. Allaire
version: "0.2.0"
quarto-required: ">=1.9.18"
contributes:
  formats:
    typst:
      template-partials:
        - typst-template.typ
        - typst-show.typ


```


======================================================================
📁 FILE: Band_Stoffwechselgesundheit/_quarto.yml
======================================================================

```yaml
project:
  type: book
  output-dir: export/_book_Required_Test
author: Wolfram Daniel Heinz Garcia
subtitle: ''
description: ''
keywords: []
publisher: ''
imprint: ''
isbn-print: ''
isbn-ebook: ''
edition: '1'
rights-holder: ''
rights-license: all-rights-reserved
frontmatter-profile: standard
book:
  title: Band_Stoffwechselgesundheit
  chapters:
  - index.md
  - content/required/Titel.md
  - content/required/Klappentext_vorne.md
  - content/required/Impressum.md
  - content/required/Widmung.md
  - content/required/IVZ.md
  - content/required/GP_Einleitung.md
  - content/required/These.md
  - content/20260214133723.md
  - content/20260215131749.md
  - content/20260214111614.md
  - content/20260221115703.md
  - content/required/Danksagung.md
  - content/required/UeberAutor.md
  - content/required/Klappentext_hinten.md
  - content/required/Rueckseite.md
format:
  typst:
    keep-typ: true
    toc: false
    toc-depth: 3
    number-sections: true
    section-numbering: 1.1.1
    papersize: a4
  html:
    theme: cosmo
    toc: true
  typstdoc-typst:
    toc: true
    toc-depth: 3
    number-sections: true
    section-numbering: 1.1.1
    mainfont: Segoe UI
    monofont: Consolas
    heading-family: Segoe UI
    link-family: Segoe UI
lang: de

```


======================================================================
📁 FILE: Band_Template/_quarto.yml
======================================================================

```yaml
project:
  type: book
  output-dir: export/_book

book:
  title: "Band_Stoffwechselgesundheit"
  chapters:
    - index.md

format:
  typst:
    keep-typ: true
    toc: true
    toc-depth: 3
    number-sections: true
    section-numbering: 1.1.1
    papersize: a4
  html:
    theme: cosmo
    toc: true

```


======================================================================
📁 FILE: book_doctor.py
======================================================================

```py
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import re
import zipfile
from datetime import datetime
import json
import yaml
from tkinter import ttk
from ui_theme import COLORS, FONTS, center_on_parent, style_dialog

# =========================================================================
# 1. DER BUCH-DOKTOR (DIAGNOSE & SICHERHEIT)
# =========================================================================
class BookDoctor:
    def __init__(self, current_book, title_registry):
        """Initialisiert den Doktor mit dem aktuellen Projekt und den Metadaten."""
        self.current_book = Path(current_book) if current_book else None
        self.title_registry = title_registry

    def analyze_health(self, used_paths, unused_count, include_index=True):
        """Liefert strukturierte Befunde inkl. betroffener Pfade für die GUI."""
        if not self.current_book:
            return {
                "is_healthy": False,
                "errors": ["Kein Projekt aktiv."],
                "warnings": [],
                "issues_by_path": {},
                "issue_details_by_path": {},
                "issue_first_line_by_path": {},
                "report": "Kein Projekt aktiv.",
                "error_count": 1,
                "warning_count": 0,
            }

        err = []
        warn = []
        issues_by_path = {}
        issue_details_by_path = {}
        issue_first_line_by_path = {}

        def record_issue(path, message, line_number=None):
            err.append(message)
            if path:
                issues_by_path.setdefault(path, []).append(message)
                issue_details_by_path.setdefault(path, []).append(
                    {"message": message, "line_number": line_number}
                )
                if line_number and path not in issue_first_line_by_path:
                    issue_first_line_by_path[path] = line_number

        def body_start_line(content, match):
            return content[: match.start(2)].count("\n") + 1

        def sanitize_markdown_preview(text):
            text = re.sub(
                r':{3,4}\s*\\?\[BOX:\s*(.*?)\\?\](.*?):{3,4}',
                r'::: {.callout-note title="\1"}\n\2\n:::',
                text,
                flags=re.DOTALL,
            )
            text = re.sub(r'^::::\s*$', r':::', text, flags=re.MULTILINE)
            text = re.sub(r'\[@([a-zA-Z0-9_-]+)\]', r'[^\1]', text)
            text = re.sub(r'(^|\s)@([a-zA-Z0-9_-]+):', r'\1\n[^\2]:', text)
            text = re.sub(r'(^|\s|\()@([a-zA-Z0-9_-]+)', r'\1[^\2]', text)
            return text

        def find_fenced_div_issues(body, base_line_number):
            issues = []
            stack = []
            marker_pattern = re.compile(r'^\s*(:{3,})(\s*.*)$')
            code_fence_pattern = re.compile(r'^\s*(```+|~~~+)')
            in_code_block = False

            for offset, raw_line in enumerate(body.splitlines()):
                line = raw_line.rstrip("\r")
                line_number = base_line_number + offset

                if code_fence_pattern.match(line):
                    in_code_block = not in_code_block
                    continue

                if in_code_block:
                    continue

                marker_match = marker_pattern.match(line)
                if marker_match:
                    colon_count = len(marker_match.group(1))
                    tail = marker_match.group(2).strip()

                    if tail:
                        stack.append((colon_count, line_number))
                    else:
                        if stack:
                            top_colon_count, _top_line = stack[-1]
                            if colon_count >= top_colon_count:
                                stack.pop()
                            else:
                                issues.append((
                                    line_number,
                                    "❌ FENCED-DIV FEHLER: Schließender :::-Marker passt nicht zur Öffnung.",
                                ))
                        else:
                            issues.append((
                                line_number,
                                "❌ FENCED-DIV FEHLER: Schließender :::-Marker ohne passende Öffnung.",
                            ))
                    continue

                if ":::" in line and not line.lstrip().startswith("```"):
                    issues.append((
                        line_number,
                        "❌ FENCED-DIV WARNZEICHEN: ':::' im Fließtext gefunden (möglicherweise defekter Div-Block).",
                    ))

            for _colon_count, open_line in stack:
                issues.append((
                    open_line,
                    "❌ FENCED-DIV FEHLER: Öffnender :::-Marker ohne passenden Abschluss.",
                ))

            return issues

        paths_to_check = list(used_paths)
        if include_index and "index.md" not in paths_to_check:
            paths_to_check.insert(0, "index.md")

        if include_index and not (self.current_book / "index.md").exists():
            record_issue("index.md", "❌ Root: 'index.md' fehlt komplett!")

        for p_str in paths_to_check:
            full_p = self.current_book / p_str

            doc_title = self.title_registry.get(p_str, "Unbekannter Titel")
            clean_title = doc_title.replace("[FEHLT] ", "")
            display_name = f"'{clean_title}' ({Path(p_str).name})"

            if not full_p.exists():
                record_issue(p_str, f"❌ Geister-Datei: {display_name} existiert nicht.")
                continue

            if doc_title.startswith("[FEHLT]") and p_str != "index.md":
                record_issue(p_str, f"❌ Frontmatter-Fehler: {display_name} hat gar keinen YAML Titel.", line_number=1)

            try:
                with open(full_p, 'r', encoding='utf-8') as f:
                    content = f.read()

                match = re.match(r'^\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]+(.*)', content, re.DOTALL)
                if match:
                    frontmatter = match.group(1)
                    body = match.group(2)

                    try:
                        parsed_yaml = yaml.safe_load(frontmatter)

                        if not parsed_yaml:
                            record_issue(p_str, f"❌ LEERES FRONTMATTER in {display_name}: Der YAML-Block ist leer.", line_number=1)
                        else:
                            if 'title' not in parsed_yaml:
                                record_issue(p_str, f"❌ FEHLENDES FELD in {display_name}: Das Pflichtfeld 'title' fehlt im Frontmatter.", line_number=1)
                            if 'description' not in parsed_yaml:
                                record_issue(p_str, f"❌ FEHLENDES FELD in {display_name}: Das Pflichtfeld 'description' fehlt im Frontmatter.", line_number=1)

                    except yaml.YAMLError as exc:
                        line_number = None
                        problem_mark = getattr(exc, "problem_mark", None)
                        if problem_mark is not None:
                            line_number = int(problem_mark.line) + 2
                        record_issue(p_str, f"❌ YAML-CRASH in {display_name}: Quarto wird hier abbrechen! Grund: {exc}", line_number=line_number)

                    if '\t' in frontmatter:
                        tab_line = None
                        for idx, line in enumerate(frontmatter.splitlines(), start=2):
                            if '\t' in line:
                                tab_line = idx
                                break
                        record_issue(p_str, f"❌ VERBOTENES ZEICHEN in {display_name}: YAML enthält Tabulatoren! Bitte durch Leerzeichen ersetzen.", line_number=tab_line)

                    body_line_number = body_start_line(content, match)
                    seen_fenced_issue_keys = set()
                    for offset, line in enumerate(body.split('\n')):
                        if line.strip() == '---':
                            record_issue(
                                p_str,
                                f"❌ VERSTECKTER TRENNSTRICH in {display_name}: Quarto stürzt bei '---' im Text ab. (Bitte *** nutzen)",
                                line_number=body_line_number + offset,
                            )

                    for line_number, fence_message in find_fenced_div_issues(body, body_line_number):
                        issue_key = (line_number, fence_message)
                        if issue_key in seen_fenced_issue_keys:
                            continue
                        seen_fenced_issue_keys.add(issue_key)
                        record_issue(
                            p_str,
                            f"{fence_message} in {display_name}",
                            line_number=line_number,
                        )

                    sanitized_body = sanitize_markdown_preview(body)
                    if sanitized_body != body:
                        for line_number, fence_message in find_fenced_div_issues(sanitized_body, body_line_number):
                            issue_key = (line_number, fence_message)
                            if issue_key in seen_fenced_issue_keys:
                                continue
                            seen_fenced_issue_keys.add(issue_key)
                            record_issue(
                                p_str,
                                f"{fence_message} in {display_name} (nach Pre-Processing)",
                                line_number=line_number,
                            )
                else:
                    record_issue(p_str, f"❌ FRONTMATTER DEFEKT in {display_name}: Die '---' Blöcke umschließen den Bereich nicht sauber.", line_number=1)

            except OSError as e:
                record_issue(p_str, f"❌ Datei-Lesefehler bei {display_name}: {e}")

        if unused_count > 0:
            warn.append(f"⚠️ Hinweis: {unused_count} Markdown-Dateien liegen aktuell ungenutzt im Datei-Pool.")

        report = "\n\n".join(err)
        if warn:
            if err:
                report += "\n\n---\n\n"
            report += "\n".join(warn)

        if not report:
            report = "Das Buchprojekt ist in perfektem Zustand. ✅"

        return {
            "is_healthy": len(err) == 0,
            "errors": err,
            "warnings": warn,
            "issues_by_path": issues_by_path,
            "issue_details_by_path": issue_details_by_path,
            "issue_first_line_by_path": issue_first_line_by_path,
            "report": report,
            "error_count": len(err),
            "warning_count": len(warn),
        }

    def check_health(self, used_paths, unused_count):
        """Führt alle strengen Buch-Prüfungen durch."""
        analysis = self.analyze_health(used_paths, unused_count)
        return analysis["is_healthy"], analysis["report"]

    def run_doctor_manual(self, used_paths, unused_count):
        """Manuelle Ausführung liefert strukturierte Befunde für die Haupt-GUI."""
        return self.analyze_health(used_paths, unused_count)


# =========================================================================
# 2. DER BACKUP MANAGER & TIME MACHINE (JSON EDITION)
# =========================================================================
class BackupManager:
    def __init__(self, root, current_book):
        self.root = root
        self.current_book = Path(current_book) if current_book else None
        self.backup_dir = self.current_book / ".backups" if self.current_book else None

    def create_full_backup(self):
        """Erstellt eine komplette ZIP-Datei des Projekts."""
        if not self.current_book:
            return None
        self.backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = self.backup_dir / f"backup_{timestamp}.zip"
        
        with zipfile.ZipFile(file_name, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Sichere auch den bookconfig Ordner mit!
            for f in self.current_book.rglob("*"):
                if f.is_file() and not any(folder in f.parts for folder in ['_book', '.backups', 'export', 'processed']):
                    zf.write(f, f.relative_to(self.current_book))
                    
        return file_name.name

    def create_structure_backup(self, tree_data): # NEU: Nimmt jetzt die Daten direkt an!
        """Sichert die JSON-GUI-Struktur direkt aus dem Arbeitsspeicher für die Time Machine."""
        if not self.current_book:
            return None
        self.backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        f_name = self.backup_dir / f"struct_{timestamp}.json"
        
        # Wir schreiben die Daten direkt aus dem RAM in die Backup-Datei!
        with open(f_name, 'w', encoding='utf-8') as f:
            json.dump(tree_data, f, ensure_ascii=False, indent=4)
            
        return f_name.name

    def show_restore_manager(self, preview_callback, apply_callback, cancel_callback):
        """Öffnet das modale Fenster für die Time Machine (Live-Preview aus JSON)."""
        if not self.current_book:
            return
        
        if not self.backup_dir.exists():
            messagebox.showinfo("Time Machine", "Keine Backups gefunden.")
            return
            
        # NEU: Wir suchen nach den neuen .json Backups!
        backups = sorted(list(self.backup_dir.glob("struct_*.json")), reverse=True)
        if not backups:
            messagebox.showinfo("Time Machine", "Keine Struktur-Backups gefunden.\n\nSpeichere das Buch einmal, um den ersten Snapshot anzulegen!")
            return
            
        win = tk.Toplevel(self.root)
        win.title("⏪ Time Machine: Live-Preview")
        center_on_parent(win, self.root, 560, 430)
        
        win.transient(self.root)
        win.grab_set()
        style_dialog(win)
        
        tk.Label(win, text="Klicke auf ein Backup, um es im Hintergrund live anzusehen:", bg=COLORS["app_bg"], fg=COLORS["heading"], font=FONTS["ui_semibold"]).pack(pady=12)
        
        listbox = tk.Listbox(
            win,
            font=("Consolas", 10),
            selectbackground=COLORS["accent"],
            bg=COLORS["surface"],
            fg=COLORS["text"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            relief="flat",
        )
        listbox.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        for b in backups:
            # Wir formatieren den Namen hübsch (struct_20260307_120000.json -> 2026-03-07 12:00:00)
            try:
                raw_time = b.stem.replace("struct_", "")
                dt = datetime.strptime(raw_time, '%Y%m%d_%H%M%S')
                nice_name = dt.strftime('%d.%m.%Y - %H:%M:%S Uhr')
                listbox.insert(tk.END, f"{nice_name} ({b.name})")
            except ValueError:
                listbox.insert(tk.END, b.name)
        
        # --- Events ---
        def on_select_preview(_event):
            sel = listbox.curselection()
            if not sel:
                return
            
            # Wir holen uns den echten Dateinamen (steht in den Klammern)
            item_text = listbox.get(sel[0])
            real_filename = item_text.split("(")[-1].replace(")", "")
            
            target_json = self.backup_dir / real_filename
            
            # Lese die JSON und schicke sie an die GUI
            if target_json.exists():
                with open(target_json, 'r', encoding='utf-8') as f:
                    tree_data = json.load(f)
                preview_callback(tree_data) # NEU: Wir übergeben direkt das fertige Dictionary!
        
        def on_apply():
            apply_callback()
            messagebox.showinfo("Erfolg", "Struktur wurde dauerhaft wiederhergestellt!")
            win.destroy()

        def on_cancel():
            cancel_callback()
            win.destroy()
            
        listbox.bind("<<ListboxSelect>>", on_select_preview)
        win.protocol("WM_DELETE_WINDOW", on_cancel)
        
        # --- Buttons ---
        btn_frame = ttk.Frame(win, padding=(0, 12))
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="✅ DIESE STRUKTUR ÜBERNEHMEN", style="Accent.TButton", command=on_apply).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Abbrechen", style="Tool.TButton", command=on_cancel).pack(side=tk.LEFT)
```


======================================================================
📁 FILE: book_studio.py
======================================================================

```py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import subprocess
import threading
import json
import re
import platform
import importlib
import logging
import sys
from export_manager import ExportManager
from log_manager import LogManager
from session_manager import SessionManager

# --- UNSERE NEUEN, SAUBEREN MODULE ---
from md_editor import MarkdownEditor
from yaml_engine import QuartoYamlEngine
from book_doctor import BookDoctor, BackupManager
from menu_manager import MenuManager
from markdown_asset_scanner import find_missing_image_refs
from ui_actions_manager import UiActionsManager
from app_config_editor import AppConfigEditor
from sanitizer_config_editor import SanitizerConfigEditor
from quarto_config_editor import QuartoConfigEditor
from search_filter import matches_tree_node, normalize_search_term, should_include_available_item
from ui_theme import COLORS, ThemedTooltip, apply_menu_theme, apply_ttk_theme, center_on_parent, configure_root, style_dialog

try:
    sv_ttk = importlib.import_module("sv_ttk")
except ModuleNotFoundError:
    sv_ttk = None

logger = logging.getLogger(__name__)

# =============================================================================
# QUARTO BOOK STUDIO
# =============================================================================

class BookStudio:
    def __init__(self, root):
        self.root = root
        self.base_path = Path(__file__).parent
        
        # Name + Version vollständig aus version.txt
        self.app_name = "Quarto Book Studio"   # Fallback
        version_file = self.base_path / "version.txt"
        if version_file.exists():
            try:
                raw = version_file.read_text(encoding="utf-8").strip()
                if raw:
                    self.app_name = raw
            except OSError as error:
                self._report_nonfatal_error("version.txt konnte nicht gelesen werden", error)

        self.root.title(f"📚 {self.app_name}")
        # ----------------------------------------------
        configure_root(self.root)

        # Letzte Fensterposition/-größe wiederherstellen
        self._config_path = Path(__file__).parent / "studio_config.json"
        saved_geo = self._load_window_geometry()
        self.root.geometry(saved_geo)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.base_path = Path(__file__).parent
        self.projects_root_path = self._get_projects_root_path()
        self.books = self._discover_projects()
        self.current_book = None
        
        self.yaml_engine = None
        self.doctor = None
        self.backup_mgr = None
        self.title_registry = {}
        self.status_registry = {}
        self.file_state_registry = {}
        self.doctor_issue_registry = {}
        self.doctor_issue_line_registry = {}
        self._content_search_cache = {}
        self.available_templates = ["Standard"]
        self.last_export_options = self._get_default_export_options()
        self.log_filter_labels = ["Alle", "Info", "Erfolg", "Warnung", "Fehler", "Header", "Meta"]
        self.log_filter_map = {
            "Alle": None,
            "Info": {"info"},
            "Erfolg": {"success"},
            "Warnung": {"warning"},
            "Fehler": {"error"},
            "Header": {"header"},
            "Meta": {"dim"},
        }
        self.log_filter_var = tk.StringVar(value="Alle")
        log_auto_clear_default, log_max_lines_default = self._get_log_preference_defaults()
        self.log_auto_clear_var = tk.BooleanVar(value=log_auto_clear_default)
        self.log_max_lines_var = tk.StringVar(value=log_max_lines_default)
        self.log_records = []
        self.is_restoring_session = False
        self.log_manager = LogManager(self)
        self.session_manager = SessionManager(self)
        self.restored_session_state = self.session_manager.load()

        # UI-Attribute, die von UiActionsManager gesetzt werden
        self.status = None
        self.fmt_box = None
        self.template_var = None
        self.template_box = None
        self.footnote_box = None
        self.btn_render = None
        self.log_output = None
        self.log_menu = None
        self.middle_panel = None
        self.main_vertical_pane = None
        self.log_panel = None
        self._default_log_panel_height = 170
        self._middle_sash_gap = None
        self._pane_sash_positions = None
        self._syncing_middle_pane = False
        
        self.current_profile_name = None 
        
        self.drag_data = {'item': None}
        self.undo_stack = []
        self.redo_stack = []
        self.exporter = ExportManager(self) # NEU: Unser ausgelagerter Export-Manager
        self.menu_manager = MenuManager(self)
        self.ui_actions_manager = UiActionsManager(self)
        
        self._set_style()
        self.setup_ui()
        
        if self.books:
            self._restore_session_state()

        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-Z>", self.redo)
        self.root.bind("<Control-s>", lambda e: self.save_project())
        self.root.bind("<F5>", lambda e: self.exporter.run_quarto_render())
        self.root.bind("<F4>", self.focus_next_doctor_issue)
        self.root.bind("<Shift-F4>", self.focus_previous_doctor_issue)

    # =========================================================================
    # FENSTERPOSITION SPEICHERN / LADEN
    # =========================================================================
    def _load_window_geometry(self) -> str:
        try:
            cfg = self._read_config()
            geo = cfg.get("window_geometry", "")
            if geo and "x" in geo:
                return geo
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._report_nonfatal_error("Fenstergeometrie konnte nicht geladen werden", error)
        return "1300x900"

    def _save_window_geometry(self):
        try:
            self.root.update_idletasks()
            cfg = self._read_config()
            cfg["window_geometry"] = self.root.geometry()
            self._write_config(cfg)
        except (OSError, TypeError, ValueError) as error:
            self._report_nonfatal_error("Fenstergeometrie konnte nicht gespeichert werden", error)

    def _read_config(self):
        if not self._config_path.exists():
            return {}
        with open(self._config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    def _write_config(self, cfg):
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

    def _report_nonfatal_error(self, context, error):
        message = f"⚠️ {context}: {error}"
        if hasattr(self, "log_manager") and self.log_output:
            self.log(message, "warning")
            return
        logger.warning(message)

    def _get_projects_root_path(self) -> Path:
        default_root = self.base_path
        try:
            cfg = self._read_config()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._report_nonfatal_error("Projekt-Root konnte nicht aus Config geladen werden", error)
            return default_root

        raw_value = cfg.get("content_root_path", ".")
        if not isinstance(raw_value, str) or not raw_value.strip():
            return default_root

        configured_path = Path(raw_value.strip()).expanduser()
        root_path = configured_path if configured_path.is_absolute() else (self.base_path / configured_path)
        root_path = root_path.resolve()
        if not root_path.exists() or not root_path.is_dir():
            self._report_nonfatal_error(
                "Konfigurierter content_root_path ist ungültig, verwende Code-Ordner",
                root_path,
            )
            return default_root
        return root_path

    def get_log_font_size(self) -> int:
        default_size = 9
        min_size = 7
        max_size = 24
        try:
            cfg = self._read_config()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._report_nonfatal_error("Log-Fontgröße konnte nicht aus Config geladen werden", error)
            return default_size

        value = cfg.get("log_font_size", default_size)
        try:
            font_size = int(value)
        except (TypeError, ValueError):
            return default_size
        return max(min_size, min(max_size, font_size))

    def _get_default_export_options(self):
        defaults = {
            "format": "typst",
            "template": "Standard",
            "footnote_mode": "endnotes",
        }
        try:
            cfg = self._read_config()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._report_nonfatal_error("Export-Defaults konnten nicht aus Config geladen werden", error)
            return defaults

        fmt = str(cfg.get("default_export_format", defaults["format"])).strip().lower()
        if fmt not in {"typst", "docx", "html", "pdf"}:
            fmt = defaults["format"]

        template = str(cfg.get("default_export_template", defaults["template"]))
        template = template.strip() if template.strip() else defaults["template"]

        footnote_mode = str(cfg.get("default_footnote_mode", defaults["footnote_mode"])).strip().lower()
        if footnote_mode not in {"footnotes", "endnotes", "pandoc"}:
            footnote_mode = defaults["footnote_mode"]

        return {
            "format": fmt,
            "template": template,
            "footnote_mode": footnote_mode,
        }

    def _get_log_preference_defaults(self):
        default_auto_clear = False
        default_max_lines = "500"
        try:
            cfg = self._read_config()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._report_nonfatal_error("Log-Defaults konnten nicht aus Config geladen werden", error)
            return default_auto_clear, default_max_lines

        auto_clear = bool(cfg.get("log_auto_clear_default", default_auto_clear))
        try:
            max_lines = int(cfg.get("log_max_lines_default", int(default_max_lines)))
        except (TypeError, ValueError):
            max_lines = int(default_max_lines)
        max_lines = max(50, min(50000, max_lines))
        return auto_clear, str(max_lines)

    def _default_editor_end_commands(self):
        return [
            {
                "id": "pdf_pagebreak_end",
                "label": "PDF-Seitenumbruch am Dateiende",
                "append_text": "```{=typst}\n#pagebreak()\n```\n",
                "detect_pattern": r'```\{=typst\}\s*#pagebreak(?:\([^\)]*\))?\s*```\s*\Z',
                "marks_state": "pdf_pagebreak_end",
            },
            {
                "id": "pdf_pagebreak_end_weak",
                "label": "Schwacher PDF-Seitenumbruch am Dateiende",
                "append_text": "```{=typst}\n#pagebreak(weak: true)\n```\n",
                "detect_pattern": r'```\{=typst\}\s*#pagebreak\(weak:\s*true\)\s*```\s*\Z',
                "marks_state": "pdf_pagebreak_end",
            },
        ]

    def _get_editor_end_commands(self):
        defaults = self._default_editor_end_commands()
        try:
            cfg = self._read_config()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._report_nonfatal_error("Editor-End-Commands konnten nicht aus Config geladen werden", error)
            return defaults

        commands = cfg.get("editor_end_commands")
        if not isinstance(commands, list):
            return defaults

        normalized = []
        for entry in commands:
            if not isinstance(entry, dict):
                continue
            label = entry.get("label")
            append_text = entry.get("append_text")
            if not isinstance(label, str) or not label.strip():
                continue
            if not isinstance(append_text, str) or not append_text.strip():
                continue
            normalized.append(
                {
                    "id": str(entry.get("id") or label).strip(),
                    "label": label.strip(),
                    "append_text": append_text,
                    "detect_pattern": entry.get("detect_pattern") if isinstance(entry.get("detect_pattern"), str) else None,
                    "marks_state": entry.get("marks_state") if isinstance(entry.get("marks_state"), str) else None,
                }
            )

        return normalized or defaults

    # --- Session (delegated to SessionManager) ---

    def _load_session_state(self):
        return self.session_manager.load()

    def _book_session_key(self, book_path):
        return self.session_manager.book_key(book_path)

    def _save_session_state(self):
        self.session_manager.save()

    def read_config(self) -> dict:
        return self._read_config()

    def write_config(self, cfg: dict):
        self._write_config(cfg)

    def load_profile_from_file(self, filepath, show_message=True, track_undo=True):
        return self._load_profile_from_file(filepath, show_message, track_undo)

    def _find_tree_node_by_path(self, path, parent=""):
        return self.session_manager.find_tree_node(path, parent)

    def _find_avail_node_by_path(self, path):
        return self.session_manager.find_avail_node(path)

    def _restore_ui_session_state(self, ui_state):
        self.session_manager.restore_ui(ui_state)

    def _restore_session_state(self):
        self.session_manager.restore()

    def close_app(self):
        self._save_session_state()
        self._save_window_geometry()
        self.root.destroy()

    def persist_app_state(self):
        self._save_session_state()

    # --- Manager host API ---

    def schedule_ui(self, callback, delay=0):
        if callable(callback):
            return self.root.after(delay, callback)
        return None

    def update_status(self, text, fg):
        if self.status is not None:
            self.status.config(text=text, fg=fg)

    def copy_text_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def get_current_book(self):
        return self.current_book

    def get_current_profile_name(self):
        return self.current_profile_name

    def get_title_for_path(self, path):
        return self.title_registry.get(path, Path(path).name)

    def get_available_templates(self):
        return list(self.available_templates)

    def get_last_export_options(self):
        return dict(self.last_export_options)

    def set_last_export_options(self, options):
        self.last_export_options = dict(options)

    def get_yaml_engine(self):
        return self.yaml_engine

    def register_status_widget(self, widget):
        self.status = widget
        return widget

    def register_log_output_widget(self, widget):
        self.log_output = widget
        return widget

    def register_log_menu_widget(self, widget):
        self.log_menu = widget
        return widget

    def get_log_filter_var(self):
        return self.log_filter_var

    def get_log_filter_labels(self):
        return list(self.log_filter_labels)

    def get_log_max_lines_var(self):
        return self.log_max_lines_var

    def get_log_auto_clear_var(self):
        return self.log_auto_clear_var

    # --- Log terminal (delegated to LogManager) ---

    def refresh_log_view(self):
        self.log_manager.refresh_view()

    def on_log_preferences_changed(self):
        self.log_manager.on_preferences_changed()

    def clear_log(self):
        self.log_manager.clear()

    def copy_log_to_clipboard(self, copy_all=False):
        self.log_manager.copy_to_clipboard(copy_all)

    def open_sanitizer_config_editor(self):
        config_path = self.base_path / "sanitizer_config.toml"
        SanitizerConfigEditor(self.root, config_path, on_save=self._on_sanitizer_config_saved)

    def open_app_config_editor(self):
        templates = list(getattr(self, "available_templates", None) or ["Standard"])
        AppConfigEditor(self.root, self._config_path, on_save=self._on_app_config_saved, templates=templates)

    def _on_app_config_saved(self, updates):
        cfg = self._read_config()
        cfg.update(updates)
        self._write_config(cfg)

        self.projects_root_path = self._get_projects_root_path()
        self._reload_books_from_current_root()
        self._apply_log_font_size()
        self._apply_log_preferences_from_config()
        self._apply_export_defaults_from_config()

        self.log("⚙️ Studio-Konfiguration gespeichert.", "success")
        self.status.config(text="Studio-Konfiguration gespeichert", fg="#27ae60")

    def _apply_log_font_size(self):
        if not self.log_output:
            return
        font_size = self.get_log_font_size()
        try:
            self.log_output.configure(font=("Consolas", font_size))
        except tk.TclError:
            pass

    def _apply_log_preferences_from_config(self):
        auto_clear, max_lines = self._get_log_preference_defaults()
        self.log_auto_clear_var.set(auto_clear)
        self.log_max_lines_var.set(max_lines)
        self.on_log_preferences_changed()

    def _apply_export_defaults_from_config(self):
        self.last_export_options = self._get_default_export_options()
        self.persist_app_state()

    def _clear_current_project_view(self):
        self.current_book = None
        self.yaml_engine = None
        self.doctor = None
        self.backup_mgr = None
        self.title_registry = {}
        self.status_registry = {}
        self.file_state_registry = {}
        self.doctor_issue_registry = {}
        self.doctor_issue_line_registry = {}
        self.current_profile_name = None
        self.profile_lbl.config(text="Profil: [Standard]")
        self._content_search_cache.clear()

        self.list_avail.delete(*self.list_avail.get_children())
        for item in self.tree_book.get_children():
            self.tree_book.delete(item)

    def _reload_books_from_current_root(self):
        previous_book = self.current_book
        previous_name = previous_book.name if previous_book else None

        self.books = self._discover_projects()
        self.book_combo.config(values=[b.name for b in self.books])

        if not self.books:
            self.book_combo.set("")
            self._clear_current_project_view()
            self.status.config(text="Keine Projekte unter content_root_path gefunden", fg="#f59e0b")
            return

        target_index = 0
        if previous_book and previous_book in self.books:
            target_index = self.books.index(previous_book)
        elif previous_name:
            for idx, book in enumerate(self.books):
                if book.name == previous_name:
                    target_index = idx
                    break

        self.book_combo.current(target_index)
        self.load_book(None)

    def _on_sanitizer_config_saved(self, _config):
        self.log("⚙️ Sanitizer-Konfiguration gespeichert.", "success")
        self.status.config(text="Sanitizer-Konfiguration gespeichert", fg="#27ae60")

    def open_quarto_config_editor(self):
        if not self.current_book:
            messagebox.showwarning("Kein Projekt", "Bitte zuerst ein Projekt auswählen.")
            return
        yaml_path = self.current_book / "_quarto.yml"
        QuartoConfigEditor(self.root, yaml_path, on_save=self._on_quarto_config_saved)

    def _on_quarto_config_saved(self, _config):
        self.log("⚙️ Quarto-Konfiguration gespeichert.", "success")
        self.status.config(text="Quarto-Konfiguration gespeichert", fg="#27ae60")
        self.load_book(None)

    # =========================================================================
    # LOG-TERMINAL
    # =========================================================================
    def log(self, msg: str, level: str = "info"):
        """Schreibt eine Zeile ins integrierte Log-Terminal.
        level: 'info' | 'success' | 'error' | 'warning' | 'header' | 'dim'
        """
        self.log_manager.log(msg, level)

    def _sanitize_log_line_for_navigation(self, line_text: str) -> str:
        if not isinstance(line_text, str):
            return ""
        cleaned = re.sub(r"\x1b\[[0-9;]*m", "", line_text)
        cleaned = re.sub(r"^\[\d{2}:\d{2}:\d{2}\]\s*", "", cleaned)
        return cleaned.strip()

    def _extract_doctor_path_from_log_line(self, line_text: str):
        sanitized = self._sanitize_log_line_for_navigation(line_text)
        match = re.search(r"\[([^\]]+\.md)\]", sanitized)
        if not match:
            return None
        return match.group(1).strip()

    def _extract_issue_line_from_log_line(self, line_text: str):
        sanitized = self._sanitize_log_line_for_navigation(line_text)
        match = re.search(r"\bL(\d+)\b", sanitized)
        if not match:
            return None
        return int(match.group(1))

    def _extract_log_target_from_line(self, line_text: str):
        rel_path = self._extract_doctor_path_from_log_line(line_text)
        if not rel_path:
            return None, None
        target_line = self._extract_issue_line_from_log_line(line_text)
        if target_line is None:
            target_line = self.doctor_issue_line_registry.get(rel_path)
        return rel_path, target_line

    def _find_nearest_doctor_path_in_log(self, log_line_number: int):
        if not self.log_output:
            return None
        if log_line_number <= 0:
            return None

        for current_line in range(log_line_number, 0, -1):
            line_text = self.log_output.get(f"{current_line}.0", f"{current_line}.end")
            path = self._extract_doctor_path_from_log_line(line_text)
            if path:
                return path
        return None

    def on_log_double_click(self, event):
        if not self.current_book or not self.log_output:
            return None

        try:
            index = self.log_output.index(f"@{event.x},{event.y}")
            line_number = int(str(index).split(".")[0])
        except (tk.TclError, ValueError):
            return None

        clicked_line_text = self.log_output.get(f"{line_number}.0", f"{line_number}.end")
        rel_path, target_line = self._extract_log_target_from_line(clicked_line_text)
        if not rel_path:
            rel_path = self._find_nearest_doctor_path_in_log(line_number)
            target_line = self.doctor_issue_line_registry.get(rel_path) if rel_path else None
        if not rel_path:
            return None

        return self.open_log_target(rel_path, target_line)

    def on_log_click(self, event):
        if not self.current_book or not self.log_output:
            return None

        try:
            index = self.log_output.index(f"@{event.x},{event.y}")
            line_number = int(str(index).split(".")[0])
        except (tk.TclError, ValueError):
            return None

        clicked_line_text = self.log_output.get(f"{line_number}.0", f"{line_number}.end")
        rel_path, target_line = self._extract_log_target_from_line(clicked_line_text)
        if not rel_path:
            return None

        return self.open_log_target(rel_path, target_line)

    def open_log_target(self, rel_path, target_line=None):
        if not self.current_book or not rel_path:
            return "break"

        target_file = self.current_book / rel_path
        if not target_file.exists():
            self.log(f"⚠️ Ziel-Datei aus Log nicht gefunden: {rel_path}", "warning")
            return "break"

        node = self._find_tree_node_by_path(rel_path)
        if node:
            self.tree_book.selection_set(node)
            self.tree_book.focus(node)
            self.tree_book.see(node)

        MarkdownEditor(
            self.root,
            target_file,
            self.on_markdown_saved,
            self._get_editor_end_commands(),
            initial_line=target_line,
        )
        if self.status:
            line_hint = f" (Zeile {target_line})" if isinstance(target_line, int) and target_line > 0 else ""
            self.status.config(text=f"Log-Navigation: {Path(rel_path).name}{line_hint}", fg="#27ae60")
        return "break"

    def _discover_projects(self):
        found = []
        for p in self.projects_root_path.rglob("_quarto.yml"):
            if not any(x in p.parts for x in ['.venv', '_book', '.backups', '.git', 'bookconfig', 'export', 'processed']):
                found.append(p.parent)
        return found

    def _build_file_state_registry(self):
        registry = {}
        if not self.current_book:
            self.file_state_registry = registry
            return

        pagebreak_patterns = []
        for command in self._get_editor_end_commands():
            if command.get("marks_state") != "pdf_pagebreak_end":
                continue
            pattern = command.get("detect_pattern")
            if not pattern:
                continue
            try:
                pagebreak_patterns.append(re.compile(pattern, re.DOTALL | re.MULTILINE))
            except re.error:
                continue

        if not pagebreak_patterns:
            pagebreak_patterns.append(
                re.compile(r'```\{=typst\}\s*#pagebreak(?:\([^\)]*\))?\s*```\s*\Z', re.DOTALL)
            )

        for path in self.title_registry.keys():
            state = {
                "orphan_footnotes": False,
                "pdf_pagebreak_end": False,
                "missing_images": False,
                "missing_images_count": 0,
                "missing_image_targets": (),
                "missing_image_refs": (),
            }

            if not str(path).lower().endswith(".md"):
                registry[path] = state
                continue

            abs_path = self.current_book / path
            if not abs_path.exists() or not abs_path.is_file():
                registry[path] = state
                continue

            try:
                text = abs_path.read_text(encoding="utf-8")
            except OSError:
                registry[path] = state
                continue

            markers = set(re.findall(r'\[\^([^\]]+)\](?!:)', text))
            definitions = set(re.findall(r'^\s*(?:\[cite_start\]\s*)?\[\^([^\]]+)\]:', text, re.MULTILINE))
            state["orphan_footnotes"] = bool(markers - definitions)
            state["pdf_pagebreak_end"] = any(pattern.search(text) for pattern in pagebreak_patterns)
            missing_image_refs = find_missing_image_refs(text, abs_path, self.current_book)
            missing_images = [target for _, target in missing_image_refs]
            state["missing_images"] = bool(missing_image_refs)
            state["missing_images_count"] = len(missing_image_refs)
            state["missing_image_targets"] = tuple(sorted(set(missing_images)))
            state["missing_image_refs"] = tuple(missing_image_refs)

            registry[path] = state

        self.file_state_registry = registry

    def _path_matches_file_state_filter(self, path):
        filter_value = self.file_state_filter_var.get() if hasattr(self, "file_state_filter_var") else "Alle"
        if filter_value == "Alle":
            return True

        state = self.file_state_registry.get(path, {})
        has_orphan = bool(state.get("orphan_footnotes"))
        has_pagebreak = bool(state.get("pdf_pagebreak_end"))
        has_missing_images = bool(state.get("missing_images"))

        if filter_value == "Verwaiste Fußnoten":
            return has_orphan
        if filter_value == "PDF-Seitenumbruch am Dateiende":
            return has_pagebreak
        if filter_value == "Fehlende Bilder":
            return has_missing_images
        return True

    def _state_tags_for_path(self, path):
        state = self.file_state_registry.get(path, {})
        has_orphan = bool(state.get("orphan_footnotes"))
        has_pagebreak = bool(state.get("pdf_pagebreak_end"))
        if has_orphan and has_pagebreak:
            return ("state_both",)
        if has_orphan:
            return ("state_orphan",)
        if has_pagebreak:
            return ("state_pagebreak",)
        return ()

    def _tree_tags_for_path(self, path, is_visible=True):
        if not is_visible:
            return ("dimmed",)
        return ("normal",) + self._state_tags_for_path(path)

    def _status_code_for_path(self, path):
        state = self.file_state_registry.get(path, {})
        has_orphan = bool(state.get("orphan_footnotes"))
        has_pagebreak = bool(state.get("pdf_pagebreak_end"))
        has_missing_images = bool(state.get("missing_images"))
        has_doctor_issue = path in self.doctor_issue_registry

        status_codes = []
        if has_orphan:
            status_codes.append("●")
        if has_pagebreak:
            status_codes.append("↵")
        if has_missing_images:
            status_codes.append("🖼")
        if has_doctor_issue:
            status_codes.append("☠")
        return "".join(status_codes)

    def _is_technical_content_node(self, path):
        normalized = str(path or "").replace("\\", "/").strip()
        return normalized in {"content", "content/"}

    def _decorate_title_for_path(self, title, path):
        if not path:
            return title

        state = self.file_state_registry.get(path, {})
        suffixes = []
        if state.get("orphan_footnotes"):
            suffixes.append("●")
        if state.get("pdf_pagebreak_end"):
            suffixes.append("↵")
        if state.get("missing_images"):
            suffixes.append("🖼")
        if path in self.doctor_issue_registry:
            suffixes.append("☠")

        if not suffixes:
            return title
        return f"{title} {' '.join(suffixes)}"

    def _refresh_tree_titles_from_current_state(self):
        if not hasattr(self, "tree_book") or not self.tree_book:
            return

        def update_tree(node):
            values = self.tree_book.item(node, "values")
            if values:
                path = values[0]
                raw_title = self._raw_title_from_values(values, self.tree_book.item(node, "text"))
                display_title = self._decorate_title_for_path(raw_title, path)
                status_code = self._status_code_for_path(path)
                self.tree_book.item(node, text=display_title, values=(path, raw_title, status_code))

            for child in self.tree_book.get_children(node):
                update_tree(child)

        for root_item in self.tree_book.get_children():
            update_tree(root_item)

        if hasattr(self, "_apply_tree_filters"):
            self._apply_tree_filters()

    def _log_doctor_analysis(self, analysis, context_label):
        error_count = analysis.get("error_count", 0)
        warning_count = analysis.get("warning_count", 0)
        issue_details_by_path = analysis.get("issue_details_by_path", {})
        warnings = analysis.get("warnings", [])

        self.log(f"{'=' * 50}", "dim")
        if error_count:
            self.log(f"🩺 {context_label}: {error_count} kritische Befunde, {warning_count} Hinweise", "header")
        elif warning_count:
            self.log(f"🩺 {context_label}: keine kritischen Befunde, aber {warning_count} Hinweise", "header")
        else:
            self.log(f"🩺 {context_label}: keine Befunde", "success")

        for path, issues in issue_details_by_path.items():
            base_title = self.title_registry.get(path, Path(path).name)
            self.log(f"☠ {base_title} [{path}]", "error")
            for issue in issues:
                line_number = issue.get("line_number")
                prefix = f"L{line_number}: " if isinstance(line_number, int) and line_number > 0 else ""
                self.log(f"   {prefix}{issue.get('message', '')}", "error")

        if error_count and issue_details_by_path:
            self.log("💡 Navigation: F4 = nächster Fund, Shift+F4 = vorheriger Fund, Enter = Problemstelle öffnen", "dim")

        for warning in warnings:
            self.log(warning, "warning")

    def _select_first_doctor_issue(self):
        if not self.doctor_issue_registry:
            return

        for path in self._get_all_used_paths():
            if path not in self.doctor_issue_registry:
                continue
            node = self._find_tree_node_by_path(path)
            if not node:
                continue
            self.tree_book.selection_set(node)
            self.tree_book.focus(node)
            self.tree_book.see(node)
            return

    def _doctor_issue_paths_in_tree_order(self):
        if not self.doctor_issue_registry:
            return []
        return [path for path in self._get_all_used_paths() if path in self.doctor_issue_registry]

    def _focus_doctor_issue(self, step):
        issue_paths = self._doctor_issue_paths_in_tree_order()
        if not issue_paths:
            if self.status:
                self.status.config(text="Keine Buch-Doktor-Befunde vorhanden", fg="#64748b")
            return "break"

        selected = self.tree_book.selection()
        current_path = None
        if selected:
            vals = self.tree_book.item(selected[0], "values")
            if vals:
                current_path = vals[0]

        if current_path in issue_paths:
            current_index = issue_paths.index(current_path)
            target_path = issue_paths[(current_index + step) % len(issue_paths)]
        else:
            target_path = issue_paths[0] if step >= 0 else issue_paths[-1]

        node = self._find_tree_node_by_path(target_path)
        if node:
            self.tree_book.selection_set(node)
            self.tree_book.focus(node)
            self.tree_book.see(node)
            issue_count = len(self.doctor_issue_registry.get(target_path, []))
            self.status.config(
                text=f"Buch-Doktor-Fund: {Path(target_path).name} ({issue_count} Problem{'e' if issue_count != 1 else ''})",
                fg="#b91c1c",
            )
        return "break"

    def focus_next_doctor_issue(self, _event=None):
        return self._focus_doctor_issue(1)

    def focus_previous_doctor_issue(self, _event=None):
        return self._focus_doctor_issue(-1)

    def _run_doctor_check(self, context_label, emit_success_log=False):
        if not self.current_book or not self.doctor:
            return False, None

        analysis = self.doctor.analyze_health(
            self._get_all_used_paths(),
            len(self.list_avail.get_children("")),
        )
        self.doctor_issue_registry = analysis.get("issues_by_path", {})
        self.doctor_issue_line_registry = analysis.get("issue_first_line_by_path", {})
        self._refresh_tree_titles_from_current_state()
        self._select_first_doctor_issue()

        has_findings = bool(analysis.get("error_count") or analysis.get("warning_count"))
        if has_findings or emit_success_log:
            self._log_doctor_analysis(analysis, context_label)

        if analysis["is_healthy"]:
            self.status.config(text=f"{context_label}: keine kritischen Befunde", fg="#27ae60")
        else:
            self.status.config(
                text=f"{context_label}: {analysis['error_count']} kritische Befunde - siehe Log",
                fg="#e74c3c",
            )

        return analysis["is_healthy"], analysis

    def run_doctor_preflight(self, context_label, emit_success_log=False):
        return self._run_doctor_check(context_label, emit_success_log=emit_success_log)

    def _raw_title_from_values(self, values, fallback_text):
        if values and len(values) > 1 and values[1]:
            return values[1]
        return fallback_text

    def _set_style(self):
        s = ttk.Style()
        apply_ttk_theme(s, sv_ttk)

    # =========================================================================
    # GUI AUFBAU
    # =========================================================================
    def setup_ui(self):
        self.menu_manager.build()

        tb = tk.Frame(self.root, bg=COLORS["panel_dark"], pady=12)
        tb.pack(fill=tk.X)
        tk.Label(tb, text="AKTIVES PROJEKT:", fg="#f8fafc", bg=COLORS["panel_dark"], font=("Segoe UI Semibold", 10)).pack(side=tk.LEFT, padx=(20, 10))
        
        self.book_combo = ttk.Combobox(tb, values=[b.name for b in self.books], state="readonly", width=50, font=("Segoe UI", 10))
        self.book_combo.pack(side=tk.LEFT)
        self.book_combo.bind("<<ComboboxSelected>>", self.load_book)
        
        self.profile_lbl = tk.Label(tb, text="Profil: [Standard]", fg="#fbbf24", bg=COLORS["panel_dark"], font=("Consolas", 10, "bold"))
        self.profile_lbl.pack(side=tk.RIGHT, padx=20)

        self.main_vertical_pane = tk.PanedWindow(
            self.root,
            orient=tk.VERTICAL,
            bg=COLORS["border"],
            sashwidth=8,
            sashrelief=tk.FLAT,
        )
        self.main_vertical_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.pane = tk.PanedWindow(self.main_vertical_pane, orient=tk.HORIZONTAL, bg=COLORS["border"], sashwidth=8, sashrelief=tk.FLAT)
        self.main_vertical_pane.add(self.pane, minsize=320, stretch="always")
        
        # --- LINKS ---
        l_frame = tk.Frame(self.pane, bg="white")
        self.pane.add(l_frame, width=450, minsize=700, stretch="always")
        self.lbl_avail_count = tk.Label(l_frame, text="NICHT ZUGEORDNETE KAPITEL (0)", bg=COLORS["surface_muted"], fg=COLORS["heading"], font=("Segoe UI Semibold", 9), pady=7)
        self.lbl_avail_count.pack(fill=tk.X)        
        search_f = tk.Frame(l_frame, bg=COLORS["surface_alt"], pady=6)
        search_f.pack(fill=tk.X)
        search_label = tk.Label(search_f, text=" 🔍 Suche (Titel/Pfad/Volltext): ", bg=COLORS["surface_alt"], fg="#475569", font=("Segoe UI", 9))
        search_label.pack(side=tk.LEFT)
        ThemedTooltip(
            search_label,
            "Titel/Pfad: sucht in Titel und Dateipfad.\n"
            "Volltext: durchsucht zusätzlich den Inhalt der Markdown-Dateien.",
        )
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.on_title_search_change()) # Tcl 9 / Python 3.14 Fix
        ttk.Entry(search_f, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.search_scope_var = tk.StringVar(value="Links")
        self.search_scope_box = ttk.Combobox(
            search_f,
            textvariable=self.search_scope_var,
            values=["Links", "Rechts", "Beide"],
            state="readonly",
            width=8,
        )
        self.search_scope_box.pack(side=tk.LEFT, padx=(0, 5))
        self.search_scope_box.bind("<<ComboboxSelected>>", self.on_title_search_change)

        self.search_mode_var = tk.StringVar(value="Titel/Pfad")
        self.search_mode_box = ttk.Combobox(
            search_f,
            textvariable=self.search_mode_var,
            values=["Titel/Pfad", "Volltext"],
            state="readonly",
            width=12,
        )
        self.search_mode_box.pack(side=tk.LEFT, padx=(0, 5))
        self.search_mode_box.bind("<<ComboboxSelected>>", self.on_title_search_change)
        ThemedTooltip(
            self.search_mode_box,
            "Titel/Pfad: sucht in Titel und Dateipfad.\n"
            "Volltext: durchsucht zusätzlich den Inhalt der Markdown-Dateien.",
        )

        tk.Label(search_f, text=" Status: ", bg=COLORS["surface_alt"], fg="#475569", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.file_state_filter_var = tk.StringVar(value="Alle")
        self.file_state_filter_box = ttk.Combobox(
            search_f,
            textvariable=self.file_state_filter_var,
            values=["Alle", "Verwaiste Fußnoten", "PDF-Seitenumbruch am Dateiende", "Fehlende Bilder"],
            state="readonly",
            width=30,
        )
        self.file_state_filter_box.pack(side=tk.LEFT, padx=(0, 5))
        self.file_state_filter_box.bind("<<ComboboxSelected>>", self.on_file_state_filter_change)

        ttk.Button(search_f, text="Leeren", style="Tool.TButton", command=self.clear_title_search).pack(side=tk.LEFT, padx=(0, 5))

        self.list_avail = ttk.Treeview(l_frame, selectmode="extended", show="tree")
        self.list_avail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list_avail.tag_configure('state_orphan', foreground='#ff6a00')
        self.list_avail.tag_configure('state_pagebreak', foreground='#004dff')
        self.list_avail.tag_configure('state_both', foreground='#b000ff')
        sl = tk.Scrollbar(l_frame, command=self.list_avail.yview)
        sl.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_avail.config(yscrollcommand=sl.set)
        
        self.list_avail.bind("<Double-1>", self.on_double_click)
        self.list_avail.bind("<Return>", self.on_activate_selected)
        self.list_avail.bind("<KP_Enter>", self.on_activate_selected)
        
        # --- KONTEXTMENÜ LINKS ---
        self.avail_menu = tk.Menu(self.root, tearoff=0)
        apply_menu_theme(self.avail_menu)
        self.avail_menu.add_command(label="📂 Im Explorer anzeigen", command=self.open_avail_in_explorer)
        self.avail_menu.add_command(label="🖼 Fehlende Bilder anzeigen", command=self.show_avail_missing_images)
        self.list_avail.bind("<Button-3>", self.show_avail_menu)
        
        # --- MITTE ---
        self.middle_panel = self.ui_actions_manager.build_middle_panel(self.pane)
        self.pane.paneconfigure(self.middle_panel, width=196, minsize=196, stretch="never")

        # --- RECHTS ---
        r_frame = tk.Frame(self.pane, bg="white")
        self.pane.add(r_frame, width=600, minsize=320, stretch="always")
        
        # NEU: Ein kleiner Header-Frame für die rechte Seite
        r_header = tk.Frame(r_frame, bg=COLORS["surface_muted"], pady=6)
        r_header.pack(fill=tk.X)
        tk.Label(r_header, text="BUCH-STRUKTUR", bg=COLORS["surface_muted"], fg=COLORS["heading"], font=("Segoe UI Semibold", 9)).pack(side=tk.LEFT, padx=6)
        
        tk.Label(r_header, text=" | Status-Filter: ", bg=COLORS["surface_muted"], fg="#475569", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.status_filter_var = tk.StringVar(value="Alle")
        self.status_combo = ttk.Combobox(r_header, textvariable=self.status_filter_var, state="readonly", width=15)
        self.status_combo.pack(side=tk.LEFT, padx=5)
        self.status_combo.bind("<<ComboboxSelected>>", self.apply_status_filter)

        ttk.Button(r_header, text="Reload Tree", style="Tool.TButton", command=self.reload_tree).pack(side=tk.LEFT, padx=(8, 4))
        
        self.tree_book = ttk.Treeview(r_frame, selectmode="extended", columns=("path", "raw_title", "status"), show="tree headings", displaycolumns=())
        self.tree_book.heading("#0", text="Kapitel")
        self.tree_book.column("#0", stretch=True, width=480)
        self.tree_book.column("path", width=0, minwidth=0, stretch=False)
        self.tree_book.column("raw_title", width=0, minwidth=0, stretch=False)
        self.tree_book.column("status", width=0, minwidth=0, stretch=False)
        self.tree_book.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # NEU: Farben (Tags) für den Filter definieren
        self.tree_book.tag_configure('dimmed', foreground='#bdc3c7')
        self.tree_book.tag_configure('normal', foreground='black')
        self.tree_book.tag_configure('state_orphan', foreground='#ff6a00')
        self.tree_book.tag_configure('state_pagebreak', foreground='#004dff')
        self.tree_book.tag_configure('state_both', foreground='#b000ff')
        
        sr = tk.Scrollbar(r_frame, command=self.tree_book.yview)
        sr.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_book.config(yscrollcommand=sr.set)
        
        self.tree_book.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree_book.bind("<B1-Motion>", self.on_drag_motion)
        self.tree_book.bind("<ButtonRelease-1>", self.on_drop)
        self.tree_book.bind("<Double-1>", self.on_double_click)
        self.tree_book.bind("<Return>", self.on_activate_selected)
        self.tree_book.bind("<KP_Enter>", self.on_activate_selected)
        
        # --- KONTEXTMENÜ RECHTS ---
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        apply_menu_theme(self.tree_menu)
        self.tree_menu.add_command(label="📂 Im Explorer anzeigen", command=self.open_tree_in_explorer)
        self.tree_menu.add_command(label="🖼 Fehlende Bilder anzeigen", command=self.show_tree_missing_images)
        self.tree_book.bind("<Button-3>", self.show_tree_menu)
        
        # --- FOOTER --- (zuerst packen → landet ganz unten)
        self.ui_actions_manager.build_footer(self.root)

        # --- LOG-TERMINAL (resizable über vertikalen Split) ---
        self.log_panel = self.ui_actions_manager.build_log_panel(self.main_vertical_pane)
        self.main_vertical_pane.add(self.log_panel, minsize=110, height=self._default_log_panel_height, stretch="never")
        self.root.after(0, self._init_vertical_log_pane)
        self.root.after(0, self._init_fixed_middle_pane_behavior)

    def _set_vertical_log_pane_height(self, log_height=None):
        if not self.main_vertical_pane:
            return
        try:
            total_height = self.main_vertical_pane.winfo_height()
            if total_height <= 0:
                return
            if log_height is None:
                log_height = self._default_log_panel_height
            sash_y = max(320, total_height - log_height)
            self.main_vertical_pane.sash_place(0, 1, sash_y)
        except tk.TclError:
            pass

    def _init_vertical_log_pane(self):
        self._set_vertical_log_pane_height()
        self.main_vertical_pane.bind("<Double-Button-1>", self._on_vertical_pane_double_click, add="+")

    def _on_vertical_pane_double_click(self, event):
        if not self.main_vertical_pane or len(self.main_vertical_pane.panes()) < 2:
            return None
        try:
            _sash_x, sash_y = self.main_vertical_pane.sash_coord(0)
        except tk.TclError:
            return None

        if abs(event.y - sash_y) > 10:
            return None

        self._set_vertical_log_pane_height()
        if self.status:
            self.status.config(text="Log-Höhe auf Standard zurückgesetzt", fg="#64748b")
        return "break"

    def _get_sash_positions(self):
        if len(self.pane.panes()) < 3:
            return None
        return self.pane.sash_coord(0)[0], self.pane.sash_coord(1)[0]

    def _remember_sash_positions(self):
        self._pane_sash_positions = self._get_sash_positions()

    def _init_fixed_middle_pane_behavior(self):
        positions = self._get_sash_positions()
        if not positions:
            return
        self._middle_sash_gap = positions[1] - positions[0]
        self._pane_sash_positions = positions
        self.pane.bind("<ButtonRelease-1>", self._on_pane_sash_drag, add="+")
        self.pane.bind("<B1-Motion>", self._on_pane_sash_drag, add="+")
        self.pane.bind("<Configure>", self._on_pane_configure, add="+")

    def _on_pane_configure(self, _event=None):
        if self._middle_sash_gap is None or self._syncing_middle_pane:
            return
        self.root.after_idle(self._sync_middle_pane_width)

    def _on_pane_sash_drag(self, _event=None):
        if self._middle_sash_gap is None or self._syncing_middle_pane:
            return
        self.root.after_idle(self._sync_middle_pane_width)

    def _sync_middle_pane_width(self):
        if self._syncing_middle_pane or self._middle_sash_gap is None:
            return

        positions = self._get_sash_positions()
        if not positions:
            return

        if self._pane_sash_positions is None:
            self._pane_sash_positions = positions
            return

        prev_left, prev_right = self._pane_sash_positions
        left_x, right_x = positions
        current_gap = right_x - left_x
        if current_gap == self._middle_sash_gap:
            self._pane_sash_positions = positions
            return

        delta_left = abs(left_x - prev_left)
        delta_right = abs(right_x - prev_right)

        self._syncing_middle_pane = True
        try:
            if delta_left >= delta_right:
                self.pane.sash_place(1, left_x + self._middle_sash_gap, self.pane.sash_coord(1)[1])
            else:
                self.pane.sash_place(0, right_x - self._middle_sash_gap, self.pane.sash_coord(0)[1])
        finally:
            self._syncing_middle_pane = False

        self._pane_sash_positions = self._get_sash_positions()

    def apply_status_filter(self, _event=None):
        self._apply_tree_filters()

    def on_file_state_filter_change(self, _event=None):
        self._update_avail_list()
        self._apply_tree_filters()
        if not self.is_restoring_session:
            self.persist_app_state()

    def on_title_search_change(self, _event=None):
        self._update_avail_list()
        self._apply_tree_filters()
        if not self.is_restoring_session:
            self.persist_app_state()

    def clear_title_search(self):
        self.search_var.set("")
        if hasattr(self, "search_scope_var"):
            self.search_scope_var.set("Links")
        self.on_title_search_change()

    def _is_fulltext_search_enabled(self):
        if not hasattr(self, "search_mode_var"):
            return False
        return self.search_mode_var.get() == "Volltext"

    def _get_content_for_search(self, path):
        if not self.current_book or not path:
            return ""

        cached = self._content_search_cache.get(path)
        if cached is not None:
            return cached

        abs_path = self.current_book / path
        if not abs_path.exists() or not abs_path.is_file():
            self._content_search_cache[path] = ""
            return ""

        try:
            text = abs_path.read_text(encoding="utf-8")
        except OSError:
            text = ""

        lowered = text.lower()
        self._content_search_cache[path] = lowered
        return lowered

    def _apply_tree_filters(self):
        if not self.current_book:
            return

        target_status = self.status_filter_var.get() if hasattr(self, "status_filter_var") else "Alle"
        search_scope = self.search_scope_var.get() if hasattr(self, "search_scope_var") else "Links"
        search_term = normalize_search_term(self.search_var.get()) if hasattr(self, "search_var") else ""
        is_fulltext = self._is_fulltext_search_enabled()

        search_on_right = search_scope in {"Rechts", "Beide"}
        active_search_term = search_term if search_on_right else ""

        first_match = [None]

        def walk_tree(node):
            vals = self.tree_book.item(node, "values")
            node_text = self.tree_book.item(node, "text").lower()
            children = self.tree_book.get_children(node)

            child_visible = False
            for child in children:
                if walk_tree(child):
                    child_visible = True

            status_ok = True
            state_ok = True
            path_text = ""
            raw_title = ""
            content_text = ""
            if vals:
                path_text = str(vals[0]).lower()
                raw_title = self._raw_title_from_values(vals, self.tree_book.item(node, "text")).lower()
                if is_fulltext:
                    content_text = self._get_content_for_search(vals[0])
                status = self.status_registry.get(vals[0], "ohne Eintrag")
                status_ok = target_status == "Alle" or status == target_status
                state_ok = self._path_matches_file_state_filter(vals[0])

            has_search_term = bool(active_search_term)
            self_match = matches_tree_node(
                search_term=active_search_term,
                node_text=node_text,
                path_text=path_text,
                raw_title=raw_title,
                content_text=content_text,
                is_fulltext=is_fulltext,
            )
            search_ok = (not has_search_term) or self_match or child_visible

            visible_self = status_ok and state_ok and search_ok
            is_visible = visible_self or child_visible
            node_path = vals[0] if vals else ""
            self.tree_book.item(node, tags=self._tree_tags_for_path(node_path, is_visible=is_visible))

            if has_search_term and search_ok and children:
                self.tree_book.item(node, open=True)

            if has_search_term and self_match and status_ok and first_match[0] is None:
                first_match[0] = node

            return is_visible

        for root_node in self.tree_book.get_children():
            walk_tree(root_node)

        if first_match[0] is not None:
            self.tree_book.selection_set(first_match[0])
            self.tree_book.see(first_match[0])

    # =========================================================================
    # LADEN & JSON IMPORT/EXPORT
    # =========================================================================
    def load_book(self, _event):
        if not self.book_combo.get():
            return
        self.current_book = self.books[self.book_combo.current()]
        self._content_search_cache.clear()
        
        self.current_profile_name = None
        self.profile_lbl.config(text="Profil: [Standard]")
        
        self.status.config(text="Lese Metadaten aus Dateien...", fg="#f1c40f")
        self.root.update()
        
        self.yaml_engine = QuartoYamlEngine(self.current_book)
        self.title_registry = self.yaml_engine.build_title_registry()
        self._build_file_state_registry()
        
        # NEU: Check ob engine den Status holen kann
        if hasattr(self.yaml_engine, 'build_status_registry'):
            self.status_registry = self.yaml_engine.build_status_registry() 
            # Dropdown mit allen verfügbaren Status füllen
            unique_statuses = set(self.status_registry.values())
            combo_vals = ["Alle"] + sorted(list(unique_statuses))
            self.status_combo.config(values=combo_vals)
            self.status_filter_var.set("Alle")
        else:
            self.status_registry = {}

        self.doctor_issue_registry = {}
            
        self.doctor = BookDoctor(self.current_book, self.title_registry)
        self.backup_mgr = BackupManager(self.root, self.current_book)
        
        self.undo_stack.clear()
        self.redo_stack.clear()
        for i in self.tree_book.get_children():
            self.tree_book.delete(i)
        
        struct = self.yaml_engine.parse_chapters()
        self._build_tree_recursive("", struct)
        self._update_avail_list()
        self._apply_tree_filters()
        
        self.status.config(text=f"Projekt geladen: {self.current_book.name}", fg="#2ecc71")
        self.log(f"📚 Projekt geladen: {self.current_book.name}", "success")
        # NEU: Templates über das neue Modul entdecken
        from template_manager import TemplateManager
        tpls = TemplateManager.discover_templates(self.current_book)
        self.available_templates = tpls if tpls else ["Standard"]
        if not self.is_restoring_session:
            self._save_session_state()

    def refresh_ui_titles(self):
        """Aktualisiert nur die Titel in der GUI, ohne die Struktur zu zerstören."""
        if not self.current_book:
            return
        self._content_search_cache.clear()
        
        # 1. Registries aus den Dateien neu einlesen (für Titel und Status)
        self.title_registry = self.yaml_engine.build_title_registry()
        self._build_file_state_registry()
        
        # Falls die Status-Registry existiert (für den neuen Filter) laden wir sie auch
        if hasattr(self.yaml_engine, 'build_status_registry'):
            self.status_registry = self.yaml_engine.build_status_registry()
            
            # Dropdown updaten, falls ein GANZ NEUER Status eingetippt wurde
            if hasattr(self, 'status_combo'):
                unique_statuses = set(self.status_registry.values())
                combo_vals = ["Alle"] + sorted(list(unique_statuses))
                self.status_combo.config(values=combo_vals)
        
        # 2. Den rechten Baum updaten
        def update_tree(node):
            vals = self.tree_book.item(node, "values")
            if vals:
                path = vals[0]
                # Den frisch geänderten Titel aus der Registry holen
                new_title = self.title_registry.get(path, f"[NEU] {Path(path).stem}")
                display_title = self._decorate_title_for_path(new_title, path)
                status_code = self._status_code_for_path(path)
                self.tree_book.item(node, text=display_title, values=(path, new_title, status_code), tags=self._tree_tags_for_path(path))
                
            # Rekursiv durch alle Kinder (Unterkapitel) gehen
            for child in self.tree_book.get_children(node):
                update_tree(child)
                
        # Start: Den Baum von der Wurzel an durchlaufen
        for root_item in self.tree_book.get_children():
            update_tree(root_item)
            
        # 3. Die linke Liste updaten (falls dort eine Datei bearbeitet wurde)
        self._update_avail_list()
        
        # 4. Den Status-Filter direkt wieder anwenden (Highlighting aktualisieren)
        if hasattr(self, '_apply_tree_filters'):
            self._apply_tree_filters()

    def on_markdown_saved(self, saved_file_path=None):
        self.refresh_ui_titles()

        if not saved_file_path or not self.current_book or not self.doctor:
            return

        try:
            file_path = Path(saved_file_path).resolve()
        except (TypeError, ValueError, OSError):
            return

        try:
            rel_path = file_path.relative_to(self.current_book).as_posix()
        except ValueError:
            return

        if not rel_path.lower().endswith(".md"):
            return

        had_issue_before = rel_path in self.doctor_issue_registry
        analysis = self.doctor.analyze_health([rel_path], 0, include_index=False)

        issues = analysis.get("issues_by_path", {}).get(rel_path, [])
        if issues:
            self.doctor_issue_registry[rel_path] = issues
            first_line = analysis.get("issue_first_line_by_path", {}).get(rel_path)
            if isinstance(first_line, int) and first_line > 0:
                self.doctor_issue_line_registry[rel_path] = first_line
            else:
                self.doctor_issue_line_registry.pop(rel_path, None)

            issue_details = analysis.get("issue_details_by_path", {}).get(rel_path, [])
            file_label = self.title_registry.get(rel_path, Path(rel_path).name)
            self.log(f"🩺 Datei-Check: {file_label} [{rel_path}]", "warning")
            for issue in issue_details:
                line_number = issue.get("line_number")
                prefix = f"L{line_number}: " if isinstance(line_number, int) and line_number > 0 else ""
                self.log(f"   {prefix}{issue.get('message', '')}", "warning")
        else:
            self.doctor_issue_registry.pop(rel_path, None)
            self.doctor_issue_line_registry.pop(rel_path, None)
            if had_issue_before:
                self.log(f"✅ Datei-Check bestanden: {rel_path} (Totenkopf entfernt)", "success")

        self._refresh_tree_titles_from_current_state()
        self._update_avail_list()

    def reload_tree(self):
        if not self.current_book:
            return
        self.refresh_ui_titles()
        order_updated = self._reapply_required_order_in_tree()
        if hasattr(self, '_apply_tree_filters'):
            self._apply_tree_filters()
        if order_updated:
            self.status.config(text="Baum neu geladen (ORDER aktualisiert)", fg="#27ae60")
            self.log("🔄 Baum neu geladen (Titel/Status/Dateimarker + ORDER aktualisiert).", "success")
        else:
            self.status.config(text="Baum neu geladen", fg="#27ae60")
            self.log("🔄 Baum neu geladen (Titel/Status/Dateimarker aktualisiert).", "success")
        if not self.is_restoring_session:
            self.persist_app_state()

    def _reapply_required_order_in_tree(self):
        if not self.current_book or not hasattr(self, "yaml_engine") or not self.yaml_engine:
            return False

        if not self.tree_book.get_children(""):
            return False

        index_node = None
        front_nodes = []
        end_nodes = []

        original_pos = 0

        def collect_nodes(parent_id=""):
            nonlocal index_node, original_pos
            for node in self.tree_book.get_children(parent_id):
                values = self.tree_book.item(node, "values")
                path = values[0] if values else ""
                if parent_id == "" and path == "index.md":
                    index_node = node

                sort_key, group = self.yaml_engine.get_required_order(path) if path else (None, None)
                if sort_key is not None:
                    if group == "front":
                        front_nodes.append((sort_key, original_pos, node))
                    elif group == "end":
                        end_nodes.append((sort_key, original_pos, node))

                original_pos += 1
                collect_nodes(node)

        collect_nodes("")

        if not front_nodes and not end_nodes:
            return False

        changed = False

        if front_nodes:
            front_nodes.sort(key=lambda entry: (entry[0], entry[1]))
            insert_at = self.tree_book.index(index_node) + 1 if index_node else 0
            for _sort_key, _original_pos, node in front_nodes:
                current_parent = self.tree_book.parent(node)
                current_index = self.tree_book.index(node)
                if current_parent != "" or current_index != insert_at:
                    self.tree_book.move(node, "", insert_at)
                    changed = True
                insert_at += 1

        if end_nodes:
            end_nodes.sort(key=lambda entry: (-entry[0], entry[1]))
            for _sort_key, _original_pos, node in end_nodes:
                current_parent = self.tree_book.parent(node)
                if current_parent != "":
                    self.tree_book.move(node, "", "end")
                    changed = True
                    continue

                siblings = list(self.tree_book.get_children(""))
                if not siblings or siblings[-1] != node:
                    self.tree_book.move(node, "", "end")
                    changed = True

        return changed

    def quick_save_json(self):
        """Überschreibt das aktuelle Profil ohne Dialog. Fallback auf 'Save As', wenn kein Profil existiert."""
        if not self.current_book:
            return
        
        # Wenn wir noch im [Standard] Profil sind, erzwingen wir den "Speichern als"-Dialog
        if not self.current_profile_name:
            self.export_json()
            return
            
        # Ansonsten überschreiben wir die Datei still und heimlich
        filepath = self.current_book / "bookconfig" / f"{self.current_profile_name}.json"
        tree_data = self._get_tree_data_for_engine()
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, indent=4, ensure_ascii=False)
            
            # Kleines visuelles Feedback in der Statusleiste statt störendem Popup
            self.status.config(text=f"Profil '{self.current_profile_name}' gespeichert!", fg="#27ae60")
            self._save_session_state()
        except (OSError, TypeError, ValueError) as e:
            messagebox.showerror("Fehler", f"Konnte Profil nicht überschreiben:\n{e}")
    
    def export_json(self):
        if not self.current_book:
            return
        config_dir = self.current_book / "bookconfig"
        config_dir.mkdir(exist_ok=True)
        
        filepath = filedialog.asksaveasfilename(
            initialdir=config_dir,
            defaultextension=".json",
            filetypes=[("JSON Dateien", "*.json")],
            title="Struktur speichern (JSON)"
        )
        if not filepath:
            return
        
        self.current_profile_name = Path(filepath).stem
        self.profile_lbl.config(text=f"Profil: [{self.current_profile_name}]")
        
        tree_data = self._get_tree_data_for_engine()
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, indent=4, ensure_ascii=False)
            self._save_session_state()
            messagebox.showinfo("Erfolg", f"Struktur gespeichert unter:\n{Path(filepath).name}\n\nBeim Rendern wird Quarto die Ausgabedatei '{self.current_profile_name}' nennen!")
        except (OSError, TypeError, ValueError) as e:
            messagebox.showerror("Fehler", f"Konnte JSON nicht speichern:\n{e}")

    def import_json(self):
        if not self.current_book:
            return
        config_dir = self.current_book / "bookconfig"
        config_dir.mkdir(exist_ok=True)
        
        filepath = filedialog.askopenfilename(
            initialdir=config_dir,
            filetypes=[("JSON Dateien", "*.json")],
            title="Struktur laden (JSON)"
        )
        if not filepath:
            return
        self._load_profile_from_file(filepath)

    def _load_profile_from_file(self, filepath, show_message=True, track_undo=True):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree_data = json.load(f)

            pre_state = self._get_current_state() if track_undo else None
            for i in self.tree_book.get_children():
                self.tree_book.delete(i)

            self._build_tree_from_json("", tree_data)
            self._update_avail_list()
            if track_undo and pre_state is not None:
                self._push_undo(pre_state)

            self.current_profile_name = Path(filepath).stem
            self.profile_lbl.config(text=f"Profil: [{self.current_profile_name}]")
            if not self.is_restoring_session:
                self.log(f"📄 Profil geladen: {self.current_profile_name}", "success")
            self._save_session_state()

            if show_message:
                messagebox.showinfo("Erfolg", f"Profil '{self.current_profile_name}' geladen!\n\nKlicke auf 'IN QUARTO SPEICHERN' oder direkt auf 'RENDERN'.")
            return True
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
            if show_message:
                messagebox.showerror("Fehler", f"Konnte JSON nicht laden:\n{e}")
            else:
                self.log(f"⚠️  Konnte gespeichertes Profil nicht laden: {e}", "warning")
            return False

    def _build_tree_from_json(self, parent_id, data):
        for item in data:
            path = item.get("path", "")
            if path == "index.md":
                continue
            if self._is_technical_content_node(path):
                if item.get("children"):
                    self._build_tree_from_json(parent_id, item["children"])
                continue
            title = item.get("title", self.title_registry.get(path, f"[NEU] {Path(path).stem}"))
            display_title = self._decorate_title_for_path(title, path)
            status_code = self._status_code_for_path(path)
            node = self.tree_book.insert(parent_id, "end", text=display_title, values=(path, title, status_code), open=True, tags=self._tree_tags_for_path(path))
            if item.get("children"):
                self._build_tree_from_json(node, item["children"])

    # =========================================================================
    # BAUM-HILFSFUNKTIONEN
    # =========================================================================
    def _build_tree_recursive(self, parent_id, data):
        for item in data:
            path = item["path"]
            if path == "index.md":
                continue
            if self._is_technical_content_node(path):
                if item.get("children"):
                    self._build_tree_recursive(parent_id, item["children"])
                continue
            title = self.title_registry.get(path, f"[NEU] {Path(path).stem}")
            display_title = self._decorate_title_for_path(title, path)
            status_code = self._status_code_for_path(path)
            node = self.tree_book.insert(parent_id, "end", text=display_title, values=(path, title, status_code), open=True, tags=self._tree_tags_for_path(path))
            if item.get("children"):
                self._build_tree_recursive(node, item["children"])

    def _update_avail_list(self):
        used_paths = self._get_all_used_paths()
        used_paths.append("index.md")
        self.list_avail.delete(*self.list_avail.get_children())
        search_term = normalize_search_term(self.search_var.get())
        search_scope = self.search_scope_var.get() if hasattr(self, "search_scope_var") else "Links"
        apply_left_search = search_scope in {"Links", "Beide"}
        is_fulltext = self._is_fulltext_search_enabled()
        
        count = 0  # NEU: Zähler starten
        
        for path, title in sorted(self.title_registry.items(), key=lambda x: x[1]):
            if path in used_paths:
                continue
            if not self._path_matches_file_state_filter(path):
                continue
            content_text = self._get_content_for_search(path) if is_fulltext and search_term else ""
            should_include = should_include_available_item(
                search_term=search_term,
                apply_left_search=apply_left_search,
                is_fulltext=is_fulltext,
                title=title,
                path=path,
                content_text=content_text,
            )

            if should_include:
                tags = self._state_tags_for_path(path)
                display_title = self._decorate_title_for_path(title, path)
                self.list_avail.insert("", "end", text=display_title, values=(path,), tags=tags)
                count += 1  # NEU: Zähler hochzählen
                
        # NEU: Das Label oben updaten!
        if hasattr(self, 'lbl_avail_count'):
            self.lbl_avail_count.config(text=f"NICHT ZUGEORDNETE KAPITEL ({count}) - DOPPELKLICK = EDIT")
    
    def _get_all_used_paths(self):
        res = []
        def walk(node):
            vals = self.tree_book.item(node, "values")
            if vals:
                res.append(vals[0])
            for c in self.tree_book.get_children(node):
                walk(c)
        walk("")
        return res

    def _get_tree_data_for_engine(self, node=""):
        data = []
        for child in self.tree_book.get_children(node):
            values = self.tree_book.item(child, "values")
            path = values[0] if values else ""
            if self._is_technical_content_node(path):
                data.extend(self._get_tree_data_for_engine(child))
                continue
            raw_title = self._raw_title_from_values(values, self.tree_book.item(child, "text"))
            item = {
                "title": raw_title,
                "path": path,
                "children": self._get_tree_data_for_engine(child)
            }
            data.append(item)
        return data

    def get_tree_data_for_engine(self, node=""):
        return self._get_tree_data_for_engine(node)

    # =========================================================================
    # SPEICHERN, DOKTOR, EDITOR (INKL. GEISTER-DATEI-ERKENNUNG)
    # =========================================================================
    def save_project(self, show_msg=True, run_doctor_check=True):
        if not self.current_book:
            return False

        if run_doctor_check:
            is_healthy, analysis = self._run_doctor_check("Buch-Doktor Vorabcheck", emit_success_log=False)
            if not is_healthy:
                if analysis is not None:
                    self.log("⛔ Speichern/Rendern gestoppt. Bitte behebe die markierten Dateien in der Buch-Struktur.", "error")
                return False
            
        try:
            # 1. ZUERST den aktuellen Baum aus der GUI auslesen!
            tree_data = self._get_tree_data_for_engine()
            
            # 2. DANN den Baum direkt an den Backup-Manager übergeben
            b_name = self.backup_mgr.create_structure_backup(tree_data)
            
            # 3. UND ZULETZT die Quarto Engine speichern lassen
            self.yaml_engine.save_chapters(tree_data, profile_name=self.current_profile_name)
            
            msg = f"Struktur in _quarto.yml gesichert.\n🛡️ Backup: {b_name}"
            if self.current_profile_name:
                msg += f"\n\n📄 Output: {self.current_profile_name}"
                
            if show_msg:
                messagebox.showinfo("Speichern", msg)
            self.status.config(text="Zuletzt gespeichert: Gerade eben", fg="#27ae60")
            self.log("💾 Struktur in _quarto.yml gespeichert.", "success")
            return True
            
        except (OSError, ValueError, TypeError, RuntimeError) as e:
            messagebox.showerror("YAML Fehler", f"Konnte _quarto.yml nicht speichern:\n\n{str(e)}")
            return False
        

    def reset_quarto_yml(self):
        if not self.current_book:
            return
        
        msg = ("🚨 HARD RESET 🚨\n\n"
               "Möchtest du die _quarto.yml WIRKLICH auf eine saubere, leere Basis zurücksetzen?\n\n"
               "Alle fehlerhaften/fremden Dateieinträge (Geister-Dateien) werden restlos aus der Konfiguration gelöscht!\n"
               "Das Projekt startet strukturell bei Null (nur index.md).\n\n"
               "Deine echten Markdown-Dateien auf der Festplatte bleiben natürlich erhalten!")
               
        if messagebox.askyesno("🔥 _quarto.yml plattmachen", msg):
            yaml_path = self.current_book / "_quarto.yml"
            gui_path = self.current_book / "bookconfig" / ".gui_state.json"

            # 1. Ein sauberes, frisches Quarto-Skelett aus Template/Config generieren
            try:
                cfg = self._read_config()
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                cfg = {}

            template_rel_path = cfg.get("reset_quarto_template_path", "templates/quarto_reset_minimal.yml")
            if isinstance(template_rel_path, str) and template_rel_path.strip():
                template_path = Path(template_rel_path.strip())
            else:
                template_path = Path("templates/quarto_reset_minimal.yml")

            if not template_path.is_absolute():
                template_path = self.base_path / template_path

            default_template = (
                "project:\n"
                "  type: book\n"
                "  output-dir: export/_book\n\n"
                "book:\n"
                "  title: \"{{BOOK_TITLE}}\"\n"
                "  chapters:\n"
                "    - index.md\n\n"
                "format:\n"
                "  typst:\n"
                "    keep-typ: true\n"
                "    toc: true\n"
                "    toc-depth: 3\n"
                "    number-sections: true\n"
                "    section-numbering: 1.1.1\n"
                "    papersize: a4\n"
                "  html:\n"
                "    theme: cosmo\n"
                "    toc: true\n"
            )

            try:
                template_text = template_path.read_text(encoding="utf-8")
            except OSError:
                template_text = default_template

            minimal_yaml = template_text.replace("{{BOOK_TITLE}}", self.current_book.name)
            
            try:
                # 2. Die alte YAML erbarmungslos überschreiben
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    f.write(minimal_yaml)
                    
                # 3. Den GUI-State löschen (damit der Müll nicht zurückkommt!)
                if gui_path.exists():
                    gui_path.unlink()
                    
                messagebox.showinfo("Erfolg", "Tabula Rasa!\n\nDie _quarto.yml ist jetzt wieder blitzsauber.")
                
                # 4. Das Buch zwingen, sich im Book Studio komplett neu zu laden
                self.load_book(None)
                
            except OSError as e:
                messagebox.showerror("Fehler", f"Konnte YAML nicht resetten:\n{e}")
    
    def run_doctor(self):
        if not self.current_book:
            return
        self._run_doctor_check("Buch-Doktor", emit_success_log=True)

    def open_help_manual(self):
        try:
            cfg = self._read_config()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._report_nonfatal_error("Handbuch-Konfiguration konnte nicht gelesen werden", error)
            cfg = {}

        manual_setting = cfg.get("help_manual_path", "")
        if not isinstance(manual_setting, str) or not manual_setting.strip():
            messagebox.showwarning(
                "Handbuch nicht konfiguriert",
                "Bitte setze in studio_config.json den Eintrag 'help_manual_path'\n"
                "auf eine Markdown-Datei (relativ zum Projekt oder absolut).",
            )
            return

        manual_path = Path(manual_setting.strip())
        if not manual_path.is_absolute():
            manual_path = self.base_path / manual_path

        manual_path = manual_path.resolve()
        if not manual_path.exists() or not manual_path.is_file():
            messagebox.showerror(
                "Handbuch nicht gefunden",
                f"Die konfigurierte Handbuch-Datei existiert nicht:\n{manual_path}",
            )
            return

        if manual_path.suffix.lower() != ".md":
            messagebox.showwarning(
                "Ungültiges Handbuch-Format",
                f"Die konfigurierte Datei ist keine Markdown-Datei:\n{manual_path}",
            )
            return

        MarkdownEditor(self.root, manual_path, self.on_markdown_saved, self._get_editor_end_commands())

    def _open_item_from_widget(self, widget, item):
        if not item:
            return None

        vals = widget.item(item, "values")
        if not vals:
            return None
        f_path = self.current_book / vals[0]
        
        if f_path.exists():
            initial_line = None
            if widget == self.tree_book:
                initial_line = self.doctor_issue_line_registry.get(vals[0])
            MarkdownEditor(
                self.root,
                f_path,
                self.on_markdown_saved,
                self._get_editor_end_commands(),
                initial_line=initial_line,
            )
            return True
        else:
            dead_path = vals[0]
            msg = (f"Die Datei wurde auf der Festplatte nicht gefunden:\n{dead_path}\n\n"
                   "Sie wurde wahrscheinlich umbenannt oder gelöscht.\n\n"
                   "Möchtest du diesen toten Eintrag jetzt aus der Liste entfernen?")
                   
            if messagebox.askyesno("Geister-Datei 👻", msg):
                pre = self._get_current_state()
                
                if widget == self.tree_book:
                    for child in self._get_all_tree_children(item):
                        txt, c_vals = self.tree_book.item(child, "text"), self.tree_book.item(child, "values")
                        if c_vals:
                            self.list_avail.insert("", "end", text=txt, values=(c_vals[0],))
                        
                widget.delete(item)
                self._push_undo(pre)
                return True
        return None

    def on_double_click(self, event):
        item = event.widget.identify_row(event.y)
        self._open_item_from_widget(event.widget, item)

    def on_activate_selected(self, event):
        widget = event.widget
        selection = widget.selection()
        if not selection:
            focus_item = widget.focus()
            if focus_item:
                selection = (focus_item,)
        if not selection:
            return None
        result = self._open_item_from_widget(widget, selection[0])
        if result:
            return "break"
        return None

    # =========================================================================
    # KONTEXTMENÜ-FUNKTIONEN (Im Explorer öffnen)
    # =========================================================================
    def show_avail_menu(self, event):
        item = self.list_avail.identify_row(event.y)
        if item:
            self.list_avail.selection_set(item)
            self.avail_menu.post(event.x_root, event.y_root)

    def open_avail_in_explorer(self):
        sel = self.list_avail.selection()
        if not sel:
            return
        self._open_in_explorer(self.list_avail.item(sel[0], "values"))

    def show_avail_missing_images(self):
        sel = self.list_avail.selection()
        if not sel:
            return
        self._show_missing_images_for_values(self.list_avail.item(sel[0], "values"))

    def show_tree_menu(self, event):
        item = self.tree_book.identify_row(event.y)
        if item:
            self.tree_book.selection_set(item)
            self.tree_menu.post(event.x_root, event.y_root)

    def open_tree_in_explorer(self):
        sel = self.tree_book.selection()
        if not sel:
            return
        self._open_in_explorer(self.tree_book.item(sel[0], "values"))

    def show_tree_missing_images(self):
        sel = self.tree_book.selection()
        if not sel:
            return
        self._show_missing_images_for_values(self.tree_book.item(sel[0], "values"))

    def _show_missing_images_for_values(self, vals):
        if not vals:
            return

        file_path = vals[0]
        state = self.file_state_registry.get(file_path, {})
        missing_refs = list(state.get("missing_image_refs") or ())

        if not str(file_path).lower().endswith(".md"):
            messagebox.showinfo("Fehlende Bilder", "Die Auswahl ist keine Markdown-Datei.")
            return

        if not missing_refs:
            messagebox.showinfo("Fehlende Bilder", "Keine fehlenden Bildreferenzen gefunden.")
            return

        self._open_missing_images_dialog(file_path, missing_refs)

    def _open_missing_images_dialog(self, file_path, missing_refs):
        win = tk.Toplevel(self.root)
        style_dialog(win, "Fehlende Bilder")
        win.transient(self.root)
        win.grab_set()
        center_on_parent(win, self.root, 760, 460)

        header = tk.Frame(win, bg=COLORS["surface_muted"], padx=12, pady=10)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=f"Datei: {file_path}",
            bg=COLORS["surface_muted"],
            fg=COLORS["heading"],
            font=("Segoe UI Semibold", 10),
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            header,
            text=f"Nicht gefundene Bildreferenzen: {len(missing_refs)}",
            bg=COLORS["surface_muted"],
            fg=COLORS["danger_text"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            header,
            text="Doppelklick oder Enter auf einer Zeile öffnet den Editor an der passenden Stelle.",
            bg=COLORS["surface_muted"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        body = tk.Frame(win, bg=COLORS["surface"], padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(
            body,
            wrap="none",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=("Consolas", 10),
            relief="solid",
            bd=1,
        )
        yscroll = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        xscroll = ttk.Scrollbar(body, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        content = "\n".join(f"L{line_number}: {target}" for line_number, target in missing_refs)
        text.insert("1.0", content)
        text.configure(state="disabled")
        text.focus_set()

        def open_clicked_reference(event=None):
            try:
                line_index = text.index(f"@{event.x},{event.y} linestart") if event else text.index("insert linestart")
                line_text = text.get(line_index, f"{line_index} lineend").strip()
            except tk.TclError:
                return

            match = re.match(r"^L(\d+):", line_text)
            if not match:
                return

            line_number = int(match.group(1))
            abs_path = self.current_book / file_path
            if not abs_path.exists():
                messagebox.showwarning("Datei fehlt", "Die ausgewählte Datei existiert nicht mehr.")
                return

            win.destroy()
            MarkdownEditor(
                self.root,
                abs_path,
                self.on_markdown_saved,
                self._get_editor_end_commands(),
                initial_line=line_number,
            )

            if event is not None:
                return "break"

        text.bind("<Double-1>", open_clicked_reference)
        text.bind("<Return>", open_clicked_reference)
        win.bind("<Return>", open_clicked_reference)

        footer = tk.Frame(win, bg=COLORS["app_bg"], padx=12, pady=10)
        footer.pack(fill=tk.X)

        def copy_to_clipboard():
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                self.root.update()
                if self.status:
                    self.status.config(text="Fehlende Bildpfade in Zwischenablage kopiert", fg=COLORS["success"])
            except tk.TclError as error:
                self._report_nonfatal_error("Zwischenablage konnte nicht beschrieben werden", error)

        ttk.Button(footer, text="In Zwischenablage kopieren", style="Tool.TButton", command=copy_to_clipboard).pack(side=tk.LEFT)
        ttk.Button(footer, text="An markierter Zeile öffnen", style="Tool.TButton", command=open_clicked_reference).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Schließen", style="Tool.TButton", command=win.destroy).pack(side=tk.RIGHT)

    def _open_in_explorer(self, vals):
        if not vals:
            return
        f_path = self.current_book / vals[0]
        if not f_path.exists():
            messagebox.showwarning("Geister-Datei", "Die Datei existiert nicht mehr auf der Festplatte.")
            return
            
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{f_path.resolve()}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", str(f_path.resolve())])
            else:
                subprocess.Popen(["xdg-open", str(f_path.parent.resolve())])
        except (OSError, subprocess.SubprocessError) as e:
            messagebox.showerror("Fehler", f"Explorer konnte nicht geöffnet werden:\n{e}")

    # =========================================================================
    # TIME MACHINE & PREVIEW
    # =========================================================================
    def run_backup(self):
        if self.current_book:
            res = self.backup_mgr.create_full_backup()
            messagebox.showinfo("Backup 📦", f"Sicherungs-ZIP erstellt:\n{res}")

    
    def open_time_machine(self):
        if not self.current_book:
            return
        original_state = self._get_current_state()
        
        # Das Callback empfängt jetzt direkt die tree_data (JSON-Liste) aus dem Backup
        def preview_callback(tree_data):
            # 1. Den alten Baum im GUI löschen
            for i in self.tree_book.get_children(): 
                self.tree_book.delete(i)
                
            # 2. Den neuen Baum direkt aus den JSON-Daten bauen!
            self._build_tree_from_json("", tree_data)
            self._update_avail_list()
            
        def apply_callback():
            self.save_project()
            
        def cancel_callback():
            self._restore_state(original_state)
            
        self.backup_mgr.show_restore_manager(preview_callback, apply_callback, cancel_callback)

    def open_preview(self):
        if not self.current_book:
            return
        from preview_inspector import PreviewInspector
        tree_data = self._get_tree_data_for_engine()
        PreviewInspector(self.root, tree_data, self.yaml_engine)

    # =========================================================================
    # GUI AKTIONEN & DRAG AND DROP
    # =========================================================================
    def add_files(self):
        pre = self._get_current_state()
        files_healed = False

        def get_order_meta(rel_path):
            if not hasattr(self, "yaml_engine") or not self.yaml_engine:
                return None, None
            try:
                return self.yaml_engine.get_required_order(rel_path)
            except (AttributeError, OSError, ValueError, TypeError):
                return None, None

        def insert_required_by_order(rel_path, title, sort_key, group):
            root_children = list(self.tree_book.get_children(""))

            if group == "front":
                insert_at = 0
                for idx, node in enumerate(root_children):
                    vals = self.tree_book.item(node, "values")
                    node_path = vals[0] if vals else ""
                    if node_path == "index.md":
                        insert_at = idx + 1
                        break

                idx = insert_at
                while idx < len(root_children):
                    vals = self.tree_book.item(root_children[idx], "values")
                    node_path = vals[0] if vals else ""
                    other_key, other_group = get_order_meta(node_path)
                    if other_group != "front":
                        break
                    if other_key is not None and other_key <= sort_key:
                        idx += 1
                        continue
                    break

                self.tree_book.insert("", idx, text=title, values=(rel_path,))
                return

            if group == "end":
                first_end_idx = None
                for idx, node in enumerate(root_children):
                    vals = self.tree_book.item(node, "values")
                    node_path = vals[0] if vals else ""
                    _other_key, other_group = get_order_meta(node_path)
                    if other_group == "end":
                        first_end_idx = idx
                        break

                if first_end_idx is None:
                    self.tree_book.insert("", "end", text=title, values=(rel_path,))
                    return

                idx = first_end_idx
                while idx < len(root_children):
                    vals = self.tree_book.item(root_children[idx], "values")
                    node_path = vals[0] if vals else ""
                    other_key, other_group = get_order_meta(node_path)
                    if other_group != "end":
                        idx += 1
                        continue
                    if other_key is not None and other_key > sort_key:
                        idx += 1
                        continue
                    break

                self.tree_book.insert("", idx, text=title, values=(rel_path,))
                return

            self.tree_book.insert("", "end", text=title, values=(rel_path,))
        
        # --- NEU: DEN "CURSOR" ERMITTELN ---
        target_parent = ""
        target_index = "end"
        
        # Prüfen, ob im rechten Buch-Baum aktuell ein Element markiert ist
        selected_in_book = self.tree_book.selection()
        if selected_in_book:
            # Wir nehmen das (erste) markierte Element als Cursor
            cursor_node = selected_in_book[0]
            target_parent = self.tree_book.parent(cursor_node)
            # Wir wollen die neuen Dateien DIREKT UNTER dem Cursor einfügen
            target_index = self.tree_book.index(cursor_node) + 1
        # -----------------------------------
        
        for i in self.list_avail.selection():
            rel_path = self.list_avail.item(i, "values")[0]
            full_path = self.current_book / rel_path
            
            # Auto-Healing
            fallback_title = self.list_avail.item(i, "text").replace("[FEHLT] ", "")
            if self.yaml_engine.ensure_required_frontmatter(full_path, fallback_title):
                files_healed = True

            order_key, order_group = get_order_meta(rel_path)
            
            # required + order => feste Position (Cursor wird ignoriert)
            if order_group in {"front", "end"} and order_key is not None:
                insert_required_by_order(rel_path, fallback_title, order_key, order_group)
            # --- NEU: AN DER CURSOR-POSITION EINFÜGEN ---
            elif target_index == "end":
                # Standard-Verhalten (Ans Ende hängen)
                self.tree_book.insert("", "end", text=fallback_title, values=(rel_path,))
            else:
                # Am Cursor einfügen
                self.tree_book.insert(target_parent, target_index, text=fallback_title, values=(rel_path,))
                # Den Index um 1 erhöhen, damit die nächste Datei aus der Liste
                # sauber unter die gerade eingefügte Datei rutscht!
                target_index += 1
                
            self.list_avail.delete(i)
            
        self._push_undo(pre)
        
        if files_healed:
            self.refresh_ui_titles()
            self.status.config(text="✨ Auto-Healing: Fehlende YAML-Felder wurden ergänzt!", fg="#d35400") # Ein schickes Orange

    def remove_files(self):
        pre = self._get_current_state()
        for i in self.tree_book.selection():
            if not self.tree_book.exists(i):
                continue
            for child in [i] + self._get_all_tree_children(i):
                txt, vals = self.tree_book.item(child, "text"), self.tree_book.item(child, "values")
                if self.search_var.get().lower() in txt.lower():
                    self.list_avail.insert("", "end", text=txt, values=vals)
            self.tree_book.delete(i)
        self._push_undo(pre)

    def reset_structure(self):
        if not self.current_book:
            return
        
        msg = ("Möchtest du wirklich die komplette Buch-Struktur leeren?\n\n"
               "Alle Kapitel werden zurück in die linke Liste geschoben und die _quarto.yml wird zurückgesetzt.\n"
               "Deine Dateien auf der Festplatte bleiben natürlich erhalten!\n\n"
               "(Du kannst dies danach noch mit Strg+Z widerrufen.)")
               
        if messagebox.askyesno("🚨 Struktur zurücksetzen", msg):
            pre = self._get_current_state()
            
            # 1. Rechten Baum komplett leeren
            for i in self.tree_book.get_children():
                self.tree_book.delete(i)
                
            # 2. Linke Liste neu berechnen und befüllen
            self._update_avail_list()
            
            # 3. Undo-State speichern
            self._push_undo(pre)
            
            # 4. Direkt speichern, um die _quarto.yml und .gui_state.json zu überschreiben
            self.save_project(show_msg=True)
    
    def _get_all_tree_children(self, item):
        res = list(self.tree_book.get_children(item))
        for child in res:
            res.extend(self._get_all_tree_children(child))
        return res

    def move_up(self):
        pre = self._get_current_state()
        for i in self.tree_book.selection():
            idx = self.tree_book.index(i)
            if idx > 0:
                self.tree_book.move(i, self.tree_book.parent(i), idx-1)
        self._push_undo(pre)

    def move_down(self):
        pre = self._get_current_state()
        for i in reversed(self.tree_book.selection()):
            self.tree_book.move(i, self.tree_book.parent(i), self.tree_book.index(i)+1)
        self._push_undo(pre)

    def indent_item(self):
        pre = self._get_current_state()
        for i in self.tree_book.selection():
            p, idx = self.tree_book.parent(i), self.tree_book.index(i)
            if idx > 0:
                t = self.tree_book.get_children(p)[idx-1]
                self.tree_book.move(i, t, "end")
                self.tree_book.item(t, open=True)
        self._push_undo(pre)

    def outdent_item(self):
        pre = self._get_current_state()
        for i in reversed(self.tree_book.selection()):
            p = self.tree_book.parent(i)
            if p:
                self.tree_book.move(i, self.tree_book.parent(p), self.tree_book.index(p)+1)
        self._push_undo(pre)

    def on_drag_start(self, event):
        self.drag_data['item'] = self.tree_book.identify_row(event.y)

    def on_drag_motion(self, _event):
        if self.drag_data['item']:
            self.tree_book.config(cursor="fleur")
    
    def on_drop(self, e):
        self.tree_book.config(cursor="")
        drag, target = self.drag_data['item'], self.tree_book.identify_row(e.y)
        self.drag_data['item'] = None
        if not drag or not target or drag == target:
            return
        
        p = self.tree_book.parent(target)
        while p:
            if p == drag:
                return
            p = self.tree_book.parent(p)

        bbox = self.tree_book.bbox(target)
        if bbox:
            pre = self._get_current_state()
            idx = self.tree_book.index(target) + (1 if e.y > bbox[1] + (bbox[3]/2) else 0)
            self.tree_book.move(drag, self.tree_book.parent(target), idx)
            self.tree_book.selection_set(drag)
            self._push_undo(pre)

    def _mark_unsaved(self):
        """Ändert die Statusmeldung, sobald eine Änderung erkannt wurde."""
        current_text = self.status.cget("text")
        # Nur wenn vorher "gespeichert" da stand, springen wir um
        if "gespeichert" in current_text.lower():
            self.status.config(text="Status: Ungespeicherte Änderungen*", fg="#f39c12") # Orange
            
    # =========================================================================
    # UNDO / REDO (SNAPSHOT ENGINE)
    # =========================================================================
    def _get_current_state(self):
        def get_state(n, tree):
            return [{"text": tree.item(c, "text"), "values": tree.item(c, "values"), "open": tree.item(c, "open"), "children": get_state(c, tree)} for c in tree.get_children(n)]
        return {"book": get_state("", self.tree_book), "avail": get_state("", self.list_avail)}

    def _restore_state(self, state):
        for i in self.tree_book.get_children():
            self.tree_book.delete(i)
        for i in self.list_avail.get_children():
            self.list_avail.delete(i)
        def rebuild(p, data, tree):
            for d in data:
                rebuild(tree.insert(p, "end", text=d["text"], values=d["values"], open=d["open"]), d["children"], tree)
        rebuild("", state["book"], self.tree_book)
        rebuild("", state["avail"], self.list_avail)

    def undo(self, _event=None):
        if self.undo_stack:
            self.redo_stack.append(self._get_current_state())
            self._restore_state(self.undo_stack.pop())
            self._mark_unsaved()  # <-- NEU

    def redo(self, _event=None):
        if self.redo_stack:
            self.undo_stack.append(self._get_current_state())
            self._restore_state(self.redo_stack.pop())
            self._mark_unsaved()  # <-- NEU

    def _push_undo(self, pre):
        if pre != self._get_current_state():
            self.undo_stack.append(pre)
            self.redo_stack.clear()
            self._mark_unsaved()  # <-- NEU

    # =========================================================================
    # SANITIZER PIPELINE (Inklusive Pre-Backup)
    # =========================================================================
    def run_sanitizer_pipeline(self):
        if not self.current_book:
            return
        
        content_dir = self.current_book / "content"
        if not content_dir.exists():
            messagebox.showerror("Fehler", "Kein 'content'-Ordner gefunden. Es gibt nichts zu bereinigen.")
            return

        # 1. Konfiguration laden (für konfigurierbaren Backup-Pfad)
        config_path = self.base_path / "studio_config.json"
        
        # Standard-Pfad: Eine Ebene über dem aktuellen Buch-Projekt
        backup_base_dir = self.current_book.parent / f"_Sanitizer_Backups_{self.current_book.name}"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    custom_path = cfg.get("sanitizer_backup_path")
                    if custom_path:
                        backup_base_dir = Path(custom_path)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
                self.log(f"⚠️  Konnte studio_config.json für Sanitizer-Backup nicht lesen: {e}", "warning")

        # 2. Zeitstempel-Ordnernamen generieren (Format: DDMMYY_HHMM)
        from datetime import datetime
        import shutil
        timestamp = datetime.now().strftime("%d%m%y_%H%M")
        backup_dir = backup_base_dir / f"sanitizer_backup_{timestamp}"

        # 3. Sicherheitsabfrage
        msg = (f"Möchtest du den Sanitizer-Waschgang jetzt starten?\n\n"
               f"🛡️ SCHRITT 1:\n"
               f"Der aktuelle 'content'-Ordner wird gesichert nach:\n"
               f"{backup_dir}\n\n"
               f"🧹 SCHRITT 2:\n"
               f"Der Sanitizer repariert Frontmatter und konvertiert Tags. "
               f"Dabei werden die Originaldateien im Projekt überschrieben.")

        if not messagebox.askyesno("🧹 Sanitizer Pipeline starten", msg):
            return

        # 4. Backup physisch durchführen
        try:
            # Stellt sicher, dass das Basis-Verzeichnis existiert
            backup_base_dir.mkdir(parents=True, exist_ok=True) 
            shutil.copytree(content_dir, backup_dir)
        except (OSError, shutil.Error) as e:
            messagebox.showerror("Backup Fehler", f"Konnte das Pre-Backup nicht erstellen. Abbruch!\n\n{e}")
            return

        # 5. Status melden und Thread starten
        self.log("=" * 50, "dim")
        self.log("🧹 SANITIZER PIPELINE GESTARTET", "header")
        self.log("=" * 50, "dim")

        # 6. Thread starten, damit die GUI nicht einfriert
        def sanitizer_thread():
            self.root.after(0, lambda: self.log(f"✅ PRE-BACKUP: {backup_dir}", "success"))
            self.root.after(0, lambda: self.log("🚀 Starte Sanitizer...", "header"))
            
            # Sanitizer.py aufrufen und Output abfangen
            cmd = [sys.executable, "Sanitizer.py", str(self.current_book)]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=self.base_path)
            
            for line in p.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.root.after(0, lambda ln=stripped: self.log(ln, "info"))
                
            p.wait()
            
            if p.returncode == 0:
                self.root.after(0, lambda: self.log("✅ SANITIZER-LAUF ABGESCHLOSSEN!", "success"))
                # GANZ WICHTIG: Die UI aktualisieren, falls der Sanitizer defektes Frontmatter repariert hat!
                self.root.after(0, self.refresh_ui_titles)
            else:
                self.root.after(0, lambda: self.log(f"❌ FEHLER: Crash (Code {p.returncode})", "error"))

        threading.Thread(target=sanitizer_thread, daemon=True).start()

if __name__ == "__main__":
    app_root = tk.Tk()
    app = BookStudio(app_root)
    app_root.mainloop()
```


======================================================================
📁 FILE: dialog_dirty_utils.py
======================================================================

```py
import copy
from tkinter import TclError, messagebox


def apply_dirty_title(window, base_title, is_dirty):
    if is_dirty:
        window.title(f"{base_title} *")
    else:
        window.title(base_title)


def confirm_discard_changes(parent, title, message):
    return messagebox.askyesno(title, message, parent=parent)


class DirtyStateController:
    def __init__(self, window, base_title):
        self.window = window
        self.base_title = base_title
        self._initial_state = None
        self._is_dirty = False
        self._watch_after_id = None
        self._watch_provider = None

    @property
    def is_dirty(self):
        return self._is_dirty

    def capture_initial(self, initial_state):
        self._initial_state = copy.deepcopy(initial_state)
        self.refresh(initial_state)

    def refresh(self, current_state):
        if self._initial_state is None:
            return
        self._is_dirty = current_state != self._initial_state
        apply_dirty_title(self.window, self.base_title, self._is_dirty)

    def confirm_discard(self, title, message, parent=None):
        return confirm_discard_changes(parent or self.window, title, message)

    def start_polling(self, state_provider, interval_ms=350):
        self._watch_provider = state_provider
        self._poll(interval_ms)

    def _poll(self, interval_ms):
        if self._watch_provider is not None:
            self.refresh(self._watch_provider())
            self._watch_after_id = self.window.after(interval_ms, lambda: self._poll(interval_ms))

    def stop_polling(self):
        if self._watch_after_id:
            try:
                self.window.after_cancel(self._watch_after_id)
            except TclError:
                pass
        self._watch_after_id = None
        self._watch_provider = None

```


======================================================================
📁 FILE: examples/unmanned_request.json
======================================================================

```json
{
  "format": "typst",
  "template": "Standard",
  "footnote_mode": "endnotes",
  "profile_name": "Pandemie_Diabetes_All_files_Gemini_sorted_v.3"
}

```


======================================================================
📁 FILE: examples/unmanned_request_ext_typstdoc.json
======================================================================

```json
{
  "format": "typst",
  "template": "EXT: typstdoc",
  "footnote_mode": "endnotes",
  "profile_name": "Pandemie_Diabetes_All_files_Gemini_sorted_v.3"
}

```


======================================================================
📁 FILE: examples/unmanned_request_prepare_only.json
======================================================================

```json
{
  "format": "typst",
  "template": "Standard",
  "footnote_mode": "endnotes",
  "profile_name": "Pandemie_Diabetes_All_files_Gemini_sorted_v.3"
}

```


======================================================================
📁 FILE: export_dialog.py
======================================================================

```py
import tkinter as tk
from tkinter import ttk

from dialog_dirty_utils import DirtyStateController, confirm_discard_changes
from ui_theme import center_on_parent, style_dialog


class ExportDialog(tk.Toplevel):
    def __init__(self, parent, templates, initial=None):
        super().__init__(parent)
        self._base_title = "Export-Optionen"
        self.title(self._base_title)
        self._dirty_controller = DirtyStateController(self, self._base_title)
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        w, h = 460, 250
        center_on_parent(self, parent, w, h)

        self.result = None
        self.templates = templates or ["Standard"]
        self.initial = initial or {}

        initial_format = self.initial.get("format", "typst")
        initial_template = self.initial.get("template", self.templates[0])
        initial_footnote_mode = self.initial.get("footnote_mode", "endnotes")

        if initial_template not in self.templates:
            initial_template = self.templates[0]

        self.format_var = tk.StringVar(value=initial_format)
        self.template_var = tk.StringVar(value=initial_template)
        self.footnote_var = tk.StringVar(value=initial_footnote_mode)
        self._initial_values = {
            "format": initial_format,
            "template": initial_template,
            "footnote_mode": initial_footnote_mode,
        }

        self.format_var.trace_add("write", self._on_field_changed)
        self.template_var.trace_add("write", self._on_field_changed)
        self.footnote_var.trace_add("write", self._on_field_changed)

        self._build_ui()
        self._dirty_controller.capture_initial(self._initial_values)

    def _build_ui(self):
        style_dialog(self)
        wrapper = ttk.Frame(self, padding=(16, 14))
        wrapper.pack(fill=tk.BOTH, expand=True)

        ttk.Label(wrapper, text="Export-Optionen", font=("Segoe UI Semibold", 11)).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(wrapper, text="Format:").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.format_var,
            values=["typst", "docx", "html", "pdf"],
            state="readonly",
            width=22,
        ).grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(wrapper, text="Template:").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.template_var,
            values=self.templates,
            state="readonly",
            width=22,
        ).grid(row=2, column=1, sticky="w", pady=6)

        ttk.Label(wrapper, text="Noten:").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.footnote_var,
            values=["footnotes", "endnotes", "pandoc"],
            state="readonly",
            width=22,
        ).grid(row=3, column=1, sticky="w", pady=6)

        button_row = ttk.Frame(wrapper)
        button_row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(18, 0))

        ttk.Button(button_row, text="Abbrechen", style="Tool.TButton", command=self._cancel).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(button_row, text="Export starten", style="Accent.TButton", command=self._confirm).pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _confirm(self):
        self.result = {
            "format": self.format_var.get(),
            "template": self.template_var.get(),
            "footnote_mode": self.footnote_var.get(),
        }
        self.destroy()

    def _collect_values(self):
        return {
            "format": self.format_var.get(),
            "template": self.template_var.get(),
            "footnote_mode": self.footnote_var.get(),
        }

    def _on_field_changed(self, *_args):
        self._refresh_dirty_state()

    def _refresh_dirty_state(self):
        self._dirty_controller.refresh(self._collect_values())

    def _cancel(self):
        self._refresh_dirty_state()
        if self._dirty_controller.is_dirty:
            proceed = confirm_discard_changes(
                self,
                "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen.\n\nDialog wirklich schließen und Änderungen verwerfen?",
            )
            if not proceed:
                return
        self.result = None
        self.destroy()

    @staticmethod
    def ask(parent, templates, initial=None):
        dialog = ExportDialog(parent, templates, initial=initial)
        parent.wait_window(dialog)
        return dialog.result

```


======================================================================
📁 FILE: export_manager.py
======================================================================

```py
import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import threading
import re
import os
import sys
import platform
import json
from datetime import datetime
from pathlib import Path

from pre_processor import PreProcessor
from export_dialog import ExportDialog

class ExportManager:
    def __init__(self, studio):
        self.studio = studio
        self._processed_label_occurrences = {}
        self._processed_colon_occurrences = []
        self._logged_missing_labels = set()
        self._logged_colon_warning_hint = False
        self._active_render_log_handle = None
        self._active_render_log_path = None

    def _log(self, message, level="info"):
        self.studio.log(message, level)

    def _current_book(self):
        getter = getattr(self.studio, "get_current_book", None)
        if callable(getter):
            return getter()
        return getattr(self.studio, "current_book", None)

    def _current_profile_name(self):
        getter = getattr(self.studio, "get_current_profile_name", None)
        if callable(getter):
            return getter()
        return getattr(self.studio, "current_profile_name", None)

    def _title_for_path(self, source_path):
        getter = getattr(self.studio, "get_title_for_path", None)
        if callable(getter):
            return getter(source_path)
        title_registry = getattr(self.studio, "title_registry", {}) or {}
        return title_registry.get(source_path, Path(source_path).name)

    def _root(self):
        return getattr(self.studio, "root", None)

    def _after(self, delay, callback):
        scheduler = getattr(self.studio, "schedule_ui", None)
        if callable(scheduler):
            return scheduler(callback, delay=delay)
        root = self._root()
        if root is not None and hasattr(root, "after"):
            return root.after(delay, callback)
        return callback()

    def _set_status(self, text, fg):
        updater = getattr(self.studio, "update_status", None)
        if callable(updater):
            updater(text, fg)
            return
        status = getattr(self.studio, "status", None)
        if status is not None and hasattr(status, "config"):
            status.config(text=text, fg=fg)

    def _copy_to_clipboard(self, text):
        copier = getattr(self.studio, "copy_text_to_clipboard", None)
        if callable(copier):
            copier(text)
            return
        root = self._root()
        if root is None:
            return
        root.clipboard_clear()
        root.clipboard_append(text)

    def _available_templates(self):
        getter = getattr(self.studio, "get_available_templates", None)
        if callable(getter):
            return getter() or ["Standard"]
        return getattr(self.studio, "available_templates", None) or ["Standard"]

    def _last_export_options(self):
        getter = getattr(self.studio, "get_last_export_options", None)
        if callable(getter):
            return getter() or {}
        return getattr(self.studio, "last_export_options", {})

    def _set_last_export_options(self, selected):
        setter = getattr(self.studio, "set_last_export_options", None)
        if callable(setter):
            setter(selected)
            return
        self.studio.last_export_options = dict(selected)

    def _persist_app_state(self):
        persist = getattr(self.studio, "persist_app_state", None)
        if callable(persist):
            persist()

    def _get_tree_data_for_engine(self):
        getter = getattr(self.studio, "get_tree_data_for_engine", None)
        return getter() if callable(getter) else []

    def _run_doctor_preflight(self, context_label, emit_success_log=False):
        runner = getattr(self.studio, "run_doctor_preflight", None)
        if callable(runner):
            return runner(context_label, emit_success_log=emit_success_log)
        return False, None

    def _save_project(self, show_msg=False, run_doctor_check=False):
        saver = getattr(self.studio, "save_project", None)
        if callable(saver):
            return saver(show_msg=show_msg, run_doctor_check=run_doctor_check)
        return False

    def _read_config(self):
        reader = getattr(self.studio, "read_config", None)
        if callable(reader):
            return reader() or {}
        return {}

    def _yaml_engine(self):
        getter = getattr(self.studio, "get_yaml_engine", None)
        if callable(getter):
            return getter()
        return getattr(self.studio, "yaml_engine", None)

    def _write_active_render_log(self, message: str):
        handle = self._active_render_log_handle
        if handle is None:
            return
        try:
            handle.write(f"{message}\n")
            handle.flush()
        except OSError:
            return

    def _start_render_log(self, target_fmt, selected_tpl, footnote_mode, enable_footnote_backlinks):
        current_book = self._current_book()
        if not current_book:
            return

        book_root = Path(current_book)
        log_dir = book_root / "export" / "render_logs"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_fmt = re.sub(r"[^A-Za-z0-9._-]", "_", str(target_fmt or "unknown"))
        log_path = log_dir / f"render_{timestamp}_{safe_fmt}.log"

        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._active_render_log_handle = log_path.open("w", encoding="utf-8")
            self._active_render_log_path = log_path
        except OSError as error:
            self._active_render_log_handle = None
            self._active_render_log_path = None
            self._log(f"⚠️ Render-Log konnte nicht angelegt werden: {error}", "warning")
            return

        profile_name = self._current_profile_name()
        self._write_active_render_log("=== Quarto Book Studio Render Log ===")
        self._write_active_render_log(f"started_at={datetime.now().isoformat(timespec='seconds')}")
        self._write_active_render_log(f"book={book_root}")
        self._write_active_render_log(f"format={target_fmt}")
        self._write_active_render_log(f"template={selected_tpl}")
        self._write_active_render_log(f"footnote_mode={footnote_mode}")
        self._write_active_render_log(f"footnote_backlinks={bool(enable_footnote_backlinks)}")
        self._write_active_render_log(f"profile={profile_name if profile_name else 'default'}")
        self._write_active_render_log("--- render output ---")
        self._log(f"🧾 Render-Log: {log_path}", "dim")

    def _finalize_render_log(self, status, primary_returncode=None, fallback_returncode=None):
        handle = self._active_render_log_handle
        path = self._active_render_log_path
        if handle is not None:
            self._write_active_render_log("--- summary ---")
            self._write_active_render_log(f"finished_at={datetime.now().isoformat(timespec='seconds')}")
            self._write_active_render_log(f"status={status}")
            if primary_returncode is not None:
                self._write_active_render_log(f"primary_returncode={primary_returncode}")
            if fallback_returncode is not None:
                self._write_active_render_log(f"fallback_returncode={fallback_returncode}")
            try:
                handle.close()
            except OSError:
                pass

        self._active_render_log_handle = None
        self._active_render_log_path = None

        if path is not None:
            self._log(f"🧾 Render-Log gespeichert: {path}", "dim")

    def _iter_tree_paths(self, tree_data):
        for item in tree_data:
            path = item.get("path")
            if isinstance(path, str):
                yield path
            children = item.get("children") or []
            if children:
                yield from self._iter_tree_paths(children)

    def collect_processed_fenced_div_hits(self, processed_tree):
        findings = []
        current_book = self._current_book()
        if not current_book:
            return findings

        book_root = Path(current_book)
        for rel_path in self._iter_tree_paths(processed_tree):
            if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
                continue

            processed_file = book_root / rel_path
            if not processed_file.exists() or not processed_file.is_file():
                continue

            try:
                lines = processed_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            issues = self._detect_fenced_div_issues(lines)
            for line_number, issue_kind in issues:
                source_rel_path = rel_path[len("processed/") :] if rel_path.startswith("processed/") else rel_path
                findings.append(
                    {
                        "source_path": source_rel_path,
                        "processed_path": rel_path,
                        "line_number": line_number,
                        "issue_kind": issue_kind,
                    }
                )
        return findings

    def _detect_fenced_div_issues(self, lines):
        issues = []
        stack = []
        marker_pattern = re.compile(r'^\s*(:{3,})(\s*.*)$')
        code_fence_pattern = re.compile(r'^\s*(```+|~~~+)')
        in_code_block = False

        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip("\r")

            if code_fence_pattern.match(line):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            marker_match = marker_pattern.match(line)
            if marker_match:
                colon_count = len(marker_match.group(1))
                tail = marker_match.group(2).strip()
                if tail:
                    stack.append((colon_count, line_number))
                else:
                    if stack:
                        top_colon_count, _top_line = stack[-1]
                        if colon_count >= top_colon_count:
                            stack.pop()
                        else:
                            issues.append((line_number, "mismatched-close"))
                    else:
                        issues.append((line_number, "orphan-close"))
                continue

            if ":::" in line:
                issues.append((line_number, "inline"))

        for _colon_count, open_line in stack:
            issues.append((open_line, "unclosed-open"))

        return issues

    def log_processed_fenced_div_hits(self, processed_tree):
        findings = self.collect_processed_fenced_div_hits(processed_tree)
        if not findings:
            return False

        abort_first = self.should_abort_on_first_preflight_error()
        self._log("⚠️ Render-Vorabcheck (Buch-Doktor): ':::' in processed-Dateien gefunden.", "warning")

        if abort_first:
            first = findings[0]
            source_path = first["source_path"]
            title = self._title_for_path(source_path)
            line_number = first["line_number"]
            self._log(
                f"☠ {title} [{source_path}] L{line_number}: defekter ':::'-Block ({first['issue_kind']}, Quelle {first['processed_path']})",
                "error",
            )
            if len(findings) > 1:
                self._log(
                    f"⛔ Abbruch beim ersten Fehler. Weitere {len(findings)-1} Befunde erst nach Korrektur sichtbar.",
                    "warning",
                )
        else:
            max_lines = 60
            hidden_count = max(0, len(findings) - max_lines)
            for finding in findings[:max_lines]:
                source_path = finding["source_path"]
                title = self._title_for_path(source_path)
                line_number = finding["line_number"]
                self._log(
                    f"☠ {title} [{source_path}] L{line_number}: defekter ':::'-Block ({finding['issue_kind']}, Quelle {finding['processed_path']})",
                    "error",
                )
            if hidden_count:
                self._log(
                    f"… {hidden_count} weitere ':::'-Befunde ausgeblendet (Log-Limit).",
                    "warning",
                )

        self._log("💡 Tipp: Klick auf [Pfad] Lx im Log öffnet direkt Datei+Zeile.", "dim")
        return abort_first

    def should_abort_on_first_preflight_error(self):
        default_value = True
        try:
            cfg = self._read_config()
        except (OSError, TypeError, ValueError):
            return default_value
        return bool(cfg.get("abort_on_first_preflight_error", default_value))

    def should_abort_on_first_render_colon_warning(self):
        default_value = False
        try:
            cfg = self._read_config()
        except (OSError, TypeError, ValueError):
            return default_value
        return bool(cfg.get("abort_on_first_render_colon_warning", default_value))

    def should_enable_footnote_backlinks(self):
        default_value = True
        try:
            cfg = self._read_config()
        except (OSError, TypeError, ValueError):
            return default_value
        return bool(cfg.get("enable_footnote_backlinks", default_value))

    def is_raw_colon_warning_line(self, line: str):
        if not isinstance(line, str):
            return False
        sanitized_line = re.sub(r"\x1b\[[0-9;]*m", "", line)
        return "The following string was found in the document:" in sanitized_line and ":::" in sanitized_line

    def has_structural_colon_occurrences(self):
        for entry in self._processed_colon_occurrences:
            if isinstance(entry, dict) and bool(entry.get("is_structural")):
                return True
        return False

    def build_processed_label_occurrences(self, processed_tree):
        occurrences = {}
        current_book = self._current_book()
        if not current_book:
            return occurrences

        label_pattern = re.compile(r'@([A-Za-z0-9_-]+)(?:\[[^\]]*\])?')
        book_root = Path(current_book)

        for rel_path in self._iter_tree_paths(processed_tree):
            if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
                continue

            processed_file = book_root / rel_path
            if not processed_file.exists() or not processed_file.is_file():
                continue

            try:
                lines = processed_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            source_rel_path = rel_path[len("processed/") :] if rel_path.startswith("processed/") else rel_path
            for line_number, raw_line in enumerate(lines, start=1):
                for match in label_pattern.finditer(raw_line):
                    label = match.group(1)
                    occurrences.setdefault(label, []).append((source_rel_path, line_number))

        return occurrences

    def build_processed_colon_occurrences(self, processed_tree):
        structural_occurrences = []
        raw_occurrences = []
        current_book = self._current_book()
        if not current_book:
            return structural_occurrences

        book_root = Path(current_book)
        for rel_path in self._iter_tree_paths(processed_tree):
            if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
                continue

            processed_file = book_root / rel_path
            if not processed_file.exists() or not processed_file.is_file():
                continue

            try:
                lines = processed_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            source_rel_path = rel_path[len("processed/") :] if rel_path.startswith("processed/") else rel_path
            structural_issues = self._detect_fenced_div_issues(lines)
            for line_number, issue_kind in structural_issues:
                structural_occurrences.append(
                    {
                        "source_path": source_rel_path,
                        "line_number": line_number,
                        "issue_kind": issue_kind,
                        "is_structural": True,
                    }
                )

            for line_number, line in enumerate(lines, start=1):
                if ":::" not in line:
                    continue
                raw_occurrences.append(
                    {
                        "source_path": source_rel_path,
                        "line_number": line_number,
                        "issue_kind": "raw-match",
                        "is_structural": False,
                    }
                )

        return structural_occurrences if structural_occurrences else raw_occurrences

    def _log_colon_warning_hint(self):
        if self._logged_colon_warning_hint:
            return
        self._logged_colon_warning_hint = True

        entries = self._processed_colon_occurrences
        if not entries:
            self._log("📌 ':::'-Warnung: keine passende Stelle im processed-Baum gefunden.", "warning")
            return

        def _entry_dict(entry):
            if isinstance(entry, dict):
                return entry
            if isinstance(entry, (tuple, list)) and len(entry) >= 2:
                return {
                    "source_path": entry[0],
                    "line_number": entry[1],
                    "issue_kind": "raw-match",
                    "is_structural": False,
                }
            return None

        normalized_entries = []
        for entry in entries:
            entry_dict = _entry_dict(entry)
            if entry_dict is None:
                continue
            normalized_entries.append(entry_dict)

        if not normalized_entries:
            self._log("📌 ':::'-Warnung: keine passende Stelle im processed-Baum gefunden.", "warning")
            return

        has_structural_hits = any(bool(item.get("is_structural")) for item in normalized_entries)

        if has_structural_hits:
            self._log("📌 Früher Treffer für ':::': strukturell auffällige Stelle(n):", "warning")
        else:
            self._log(
                "📌 Früher Treffer für ':::': keine strukturellen Defekte erkannt – nur mögliche Auslöser.",
                "warning",
            )
        shown = []
        seen = set()
        max_hits = 20
        for item in normalized_entries:
            source_path = item.get("source_path")
            line_number = item.get("line_number")
            issue_kind = item.get("issue_kind")
            is_structural = bool(item.get("is_structural"))
            if not isinstance(source_path, str) or not isinstance(line_number, int):
                continue
            key = (source_path, line_number)
            if key in seen:
                continue
            seen.add(key)
            shown.append((source_path, line_number, issue_kind, is_structural))
            if len(shown) >= max_hits:
                break

        for source_path, line_number, issue_kind, is_structural in shown:
            title = self._title_for_path(source_path)
            if is_structural:
                self._log(
                    f"   ☠ {title} [{source_path}] L{line_number}: defekter ':::'-Block ({issue_kind})",
                    "error",
                )
            else:
                self._log(f"   🔎 {title} [{source_path}] L{line_number}", "warning")

        if len(normalized_entries) > len(shown):
            self._log(
                f"… {len(normalized_entries) - len(shown)} weitere mögliche Treffer ausgeblendet (Log-Limit).",
                "warning",
            )

        primary_path, primary_line, _primary_kind, _primary_structural = shown[0]
        self._log(f"👉 KLICK: [{primary_path}] L{primary_line}", "header")
        if len(shown) > 1:
            alt_path, alt_line, _alt_kind, _alt_structural = shown[1]
            self._log(f"👉 Alternative: [{alt_path}] L{alt_line}", "header")

    def _log_missing_label_hint(self, label):
        if label in self._logged_missing_labels:
            return
        self._logged_missing_labels.add(label)

        entries = self._processed_label_occurrences.get(label, [])
        if not entries:
            self._log(f"📌 Fehlendes Label <{label}>: keine Quelle im processed-Baum gefunden.", "error")
            return

        shown = []
        seen = set()
        for source_path, line_number in entries:
            key = (source_path, line_number)
            if key in seen:
                continue
            seen.add(key)
            shown.append((source_path, line_number))
            if len(shown) >= 6:
                break

        self._log(f"📌 Fehlendes Label <{label}> – mögliche Quellen:", "error")
        for source_path, line_number in shown:
            title = self._title_for_path(source_path)
            self._log(f"   ☠ {title} [{source_path}] L{line_number}", "error")

        primary_path, primary_line = shown[0]
        self._log(f"👉 KLICK: [{primary_path}] L{primary_line}", "header")
        if len(shown) > 1:
            alt_path, alt_line = shown[1]
            self._log(f"👉 Alternative: [{alt_path}] L{alt_line}", "header")

    def candidate_registry_paths_for_error_file(self, abs_file_path: Path):
        candidates = []
        current_book = self._current_book()
        if not current_book:
            return candidates

        try:
            rel = abs_file_path.resolve().relative_to(Path(current_book).resolve()).as_posix()
        except (OSError, RuntimeError, TypeError, ValueError):
            return candidates

        candidates.append(rel)
        if rel.startswith("processed/"):
            candidates.append(rel[len("processed/"):])
        return candidates

    def resolve_error_file_title(self, abs_file_path: Path):
        title_registry = getattr(self.studio, "title_registry", {}) or {}
        for candidate in self.candidate_registry_paths_for_error_file(abs_file_path):
            title = title_registry.get(candidate)
            if title:
                return str(title), candidate

        yaml_engine = self._yaml_engine()
        if yaml_engine and abs_file_path.exists() and abs_file_path.suffix.lower() == ".md":
            try:
                extracted = yaml_engine.extract_title_from_md(abs_file_path)
            except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
                extracted = None
            if extracted:
                return str(extracted), abs_file_path.name

        return abs_file_path.stem, abs_file_path.name

    def _log_render_line(self, stripped_line: str):
        self._log(stripped_line, "info")
        self._write_active_render_log(stripped_line)

        sanitized_line = re.sub(r"\x1b\[[0-9;]*m", "", stripped_line)

        if (
            "The following string was found in the document:" in sanitized_line
            and ":::" in sanitized_line
        ):
            self._log_colon_warning_hint()

        label_match = re.search(
            r'label\s+`?<([^>]+)>`?\s+does\s+not\s+exist\s+in\s+the\s+document',
            sanitized_line,
            re.IGNORECASE,
        )
        if label_match:
            self._log_missing_label_hint(label_match.group(1).strip())

        match = re.search(r"ERROR:\s+In file\s+(.+)$", sanitized_line)
        if not match:
            return

        file_str = match.group(1).strip().strip('"\'')
        if not file_str:
            return

        abs_file_path = Path(file_str)
        title, shown_path = self.resolve_error_file_title(abs_file_path)
        self._log(f"📌 Betroffener Titel: {title} [{shown_path}]", "error")

    # =========================================================================
    # 1. SCRIVENER EXPORT (SINGLE MARKDOWN)
    # =========================================================================
    def export_single_markdown(self):
        current_book = self._current_book()
        if not current_book:
            return
        
        export_dir = current_book / "export"
        export_dir.mkdir(exist_ok=True)
        
        default_name = f"{current_book.name}_Scrivener.md"
        filepath = filedialog.asksaveasfilename(
            initialdir=export_dir,
            initialfile=default_name,
            defaultextension=".md",
            filetypes=[("Markdown", "*.md")],
            title="Export als Single-Markdown für Scrivener"
        )
        if not filepath:
            return
        
        tree_data = self._get_tree_data_for_engine()
        
        try:
            with open(filepath, 'w', encoding='utf-8') as out_f:
                out_f.write(f"# {current_book.name}\n\n")
                self._write_tree_to_file(tree_data, out_f, 0)
                
            messagebox.showinfo("Erfolg", "Markdown erfolgreich exportiert!\n\nDu kannst diese Datei nun in Scrivener über 'Importieren und aufteilen' einlesen.")
            self._open_folder_and_select(filepath)
                
        except (OSError, TypeError, ValueError) as e:
            messagebox.showerror("Fehler", f"Konnte Markdown nicht exportieren:\n{e}")

    def _write_tree_to_file(self, data, out_file, level_offset):
        for item in data:
            path_str = item["path"]
            
            if path_str.startswith("PART:"):
                title = path_str.replace("PART:", "")
                hashes = "#" * (1 + level_offset)
                out_file.write(f"{hashes} {title}\n\n")
                if item.get("children"):
                    self._write_tree_to_file(item["children"], out_file, level_offset + 1)
            else:
                src = self._current_book() / path_str
                if src.exists():
                    with open(src, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
                    body = content[match.end():] if match else content
                    
                    if level_offset > 0:
                        def shift_heading(m):
                            h, t = m.group(1), m.group(2)
                            return f"{'#' * (len(h) + level_offset)}{t}"
                        body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                        
                    out_file.write(body.strip() + "\n\n\n")
                
                if item.get("children"):
                    self._write_tree_to_file(item["children"], out_file, level_offset + 1)

    # =========================================================================
    # 2. QUARTO RENDER PIPELINE
    # =========================================================================
    def run_quarto_render(self):
        if not self._current_book():
            return

        is_healthy, analysis = self._run_doctor_preflight("Render-Vorabcheck", emit_success_log=False)
        if not is_healthy:
            if analysis is not None:
                self._log("⛔ Rendern abgebrochen. Bitte behebe die markierten Dateien in der Buch-Struktur.", "error")
            self._set_status("Render abgebrochen (Buch-Doktor-Befund)", "#e74c3c")
            return

        templates = self._available_templates()
        selected = ExportDialog.ask(
            self._root(),
            templates,
            initial=self._last_export_options(),
        )
        if not selected:
            self._set_status("Export abgebrochen", "#95a5a6")
            return

        self._set_last_export_options(selected)
        self._persist_app_state()
        
        if not self._save_project(show_msg=False, run_doctor_check=False):
            self._set_status("Render abgebrochen (Speicherfehler)", "#e74c3c")
            return
            
        base_fmt = selected["format"]
        footnote_mode = selected["footnote_mode"]
        selected_tpl = selected["template"]
        enable_footnote_backlinks = self.should_enable_footnote_backlinks()
        
        # --- DIE NEUE EXTENSION-WEICHE ---
        # --- DIE NEUE EXTENSION-WEICHE ---
        target_fmt = base_fmt
        extra_opts = None
        
        if selected_tpl.startswith("EXT: "):
            # Es ist eine Quarto Extension (z.B. typstdoc)
            ext_name = selected_tpl.replace("EXT: ", "").strip()
            target_fmt = f"{ext_name}-{base_fmt}" 
            
            # NEU: Wir injizieren die wichtigsten Buch-Features (TOC, Nummerierung) 
            # direkt in das Extension-Format!
            extra_opts = {
                target_fmt: {
                    "toc": True,
                    "toc-depth": 3,
                    "number-sections": True,
                    "section-numbering": "1.1.1" #
                }
            }
            
        elif selected_tpl != "Standard":
            # Es ist eine dumme lokale Datei in templates/
            extra_opts = {base_fmt: {"template": f"templates/{selected_tpl}"}}
        # ----------------------------------
        
        self._set_status(f"Rendere {target_fmt} (Pre-Processing)...", "#3498db")
        
        processor = PreProcessor(
            self._current_book(),
            footnote_mode=footnote_mode,
            enable_footnote_backlinks=enable_footnote_backlinks,
            output_format=target_fmt,
        )
        original_tree = self._get_tree_data_for_engine()
        processed_tree = processor.prepare_render_environment(original_tree)
        self._processed_label_occurrences = self.build_processed_label_occurrences(processed_tree)
        self._processed_colon_occurrences = self.build_processed_colon_occurrences(processed_tree)
        self._logged_missing_labels = set()
        self._logged_colon_warning_hint = False
        has_processed_errors = self.log_processed_fenced_div_hits(processed_tree)
        if has_processed_errors:
            self._set_status("Render abgebrochen (erster Preflight-Fehler)", "#e74c3c")
            return

        # Verwaiste Fußnoten-Marker ins Log schreiben
        if processor.harvester.orphan_warnings:
            self._log("⚠️  Verwaiste Fußnoten-Marker (keine Definition gefunden):", "warning")
            for file_key, label in processor.harvester.orphan_warnings:
                rel = Path(file_key).name
                self._log(f"   [{label}] in {rel}", "warning")
        
        self._log(f"{'='*50}", "dim")
        self._log(f"🖨️  EXPORT PIPELINE: {target_fmt.upper()}", "header")
        self._log(f"{'='*50}", "dim")
        self._start_render_log(target_fmt, selected_tpl, footnote_mode, enable_footnote_backlinks)

        def render_thread():
            self._after(
                0,
                lambda: self._log(
                    "🛡️ Render startet über sichere temporäre Kopie (processed + ORDER-kompatibel).",
                    "dim",
                ),
            )
            return_code, aborted_on_colon_warning = self._run_safe_render(
                target_fmt,
                footnote_mode,
                enable_footnote_backlinks,
                profile_name=self._current_profile_name(),
                extra_format_options=extra_opts,
            )

            if aborted_on_colon_warning:
                self._finalize_render_log("aborted_on_first_colon_warning", primary_returncode=return_code)
                return

            if return_code == 0:
                self._finalize_render_log("success", primary_returncode=return_code)
                self._handle_render_success(target_fmt)
            else:
                self._finalize_render_log("failed", primary_returncode=return_code)
                self._after(0, lambda: self._log(f"❌ FEHLER: Code {return_code}", "error"))
                self._after(0, lambda: self._set_status("Render fehlgeschlagen", "#e74c3c"))

        threading.Thread(target=render_thread, daemon=True).start()

    def _run_safe_render(self, target_fmt, footnote_mode, enable_footnote_backlinks, profile_name=None, extra_format_options=None):
        safe_script = Path(__file__).resolve().parent / "quarto_render_safe.py"
        if not safe_script.exists():
            self._after(0, lambda: self._log("❌ Fallback-Skript nicht gefunden: quarto_render_safe.py", "error"))
            return 2, False

        cmd = [
            sys.executable,
            str(safe_script),
            str(self._current_book()),
            "--to",
            target_fmt,
            "--footnote-mode",
            footnote_mode,
            "--footnote-backlinks" if enable_footnote_backlinks else "--no-footnote-backlinks",
        ]
        if profile_name:
            cmd.extend(["--profile-name", str(profile_name)])
        if extra_format_options:
            cmd.extend([
                "--extra-format-options-json",
                json.dumps(extra_format_options, ensure_ascii=False, separators=(",", ":")),
            ])
        self._write_active_render_log(f"safe_command={' '.join(str(part) for part in cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        aborted_on_colon_warning = False
        if proc.stdout is not None:
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    self._after(0, lambda ln=stripped: self._log_render_line(ln))
                    if (
                        self.is_raw_colon_warning_line(stripped)
                        and self.should_abort_on_first_render_colon_warning()
                        and self.has_structural_colon_occurrences()
                    ):
                        aborted_on_colon_warning = True
                        try:
                            proc.terminate()
                        except OSError:
                            pass
                        self._after(
                            0,
                            lambda: self._log(
                                "⛔ Render abgebrochen (Config): erster ':::'-Warnhinweis erkannt. Folgefehler werden bewusst unterdrückt.",
                                "error",
                            ),
                        )
                        self._after(
                            0,
                            lambda: self._set_status("Render abgebrochen (erster :::-Warnhinweis)", "#e74c3c"),
                        )
                        break
        proc.wait()
        return proc.returncode, aborted_on_colon_warning

    # =========================================================================
    # HILFSFUNKTIONEN (Auto-Open & UI)
    # =========================================================================
    def _handle_render_success(self, fmt):
        try:
            profile = self._current_profile_name()
            safe_profile = re.sub(r'[^a-zA-Z0-9_\-]', '_', profile) if profile else None
            out_dir_name = f"_book_{safe_profile}" if safe_profile else "_book"
            out_dir = self._current_book() / "export" / out_dir_name

            ext = ".pdf" if "pdf" in fmt.lower() or "typst" in fmt.lower() else f".{fmt}"
            found = list(out_dir.glob(f"*{ext}"))

            if found:
                abs_path = str(found[0].resolve())
                self._copy_to_clipboard(abs_path)

                self._after(0, lambda: self._log(f"✅ ERFOLG: {fmt.upper()} generiert!", "success"))
                self._after(0, lambda: self._log(f"📋 Pfad in Zwischenablage: {abs_path}", "success"))
                self._after(0, lambda: self._set_status("Render erfolgreich", "#2ecc71"))

                if platform.system() == 'Windows':
                    os.startfile(abs_path)
                elif platform.system() == 'Darwin':
                    subprocess.call(('open', abs_path))
                else:
                    subprocess.call(('xdg-open', abs_path))
            else:
                self._after(0, lambda: self._log(f"✅ ERFOLG: {fmt.upper()} im export/ Ordner generiert.", "success"))
                self._after(0, lambda: self._set_status("Render erfolgreich", "#2ecc71"))
        except (tk.TclError, OSError, subprocess.SubprocessError) as post_err:
            self._after(0, lambda err=post_err: self._log(f"⚠️  Post-Render-Fehler: {err}", "warning"))

    def _open_folder_and_select(self, filepath):
        f_path = Path(filepath).resolve()
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{f_path}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", str(f_path)])
        else:
            subprocess.Popen(["xdg-open", str(f_path.parent)])
```


======================================================================
📁 FILE: footnote_harvester.py
======================================================================

```py
import re

class FootnoteHarvester:
    def __init__(self, mode="endnotes", title="Anmerkungen", use_typst_links=False):
        """
        mode="endnotes": Ersetzt Fußnoten durch hochgestellte Zahlen und baut ein Endnoten-Kapitel.
          use_typst_links=True: erzeugt Typst-native #link/<#label>-Anker (klickbare PDF-Links).
        mode="pandoc": Sammelt die Noten, belässt aber die Quarto-Syntax [^1] für klassische Fußnoten.
        mode="footnotes" wird nicht hier verarbeitet; in diesem Modus lässt der PreProcessor den Fußnoten-Text unverändert.
        """
        self.mode = mode
        self.title = title
        self.use_typst_links = use_typst_links

        self.global_counter = 1
        self.harvested = [] # Speichert Tuples: (neue_id, text) für das finale Endnoten-Kapitel

        # --- Das 2-Pass-System (Globale Lexika) ---
        self.definitions = {} # Globales Lexikon: (file_key, label) -> Inhalt
        self.file_mapping = {} # (file_key, label) -> fortlaufende Nummer
        self.orphan_warnings = [] # Verwaiste Marker ohne Definition: (file_key, label)
        self._ref_anchors = {} # new_id -> [back-link-anchor, ...] für Typst-Rücksprünge
        # -------------------------------------------

    def _parse_definition_start(self, line):
        """Erkennt den Start einer Fußnoten-Definition mit optional leichter Einrückung."""
        return re.match(r'^\s{0,3}\[\^([^\]]+)\]:\s?(.*)$', line)

    def extract_definitions(self, text, file_key=""):
        """PASS 1: Findet alle Fußnoten-Definitionen, speichert sie datei-scoped und entfernt sie aus dem Text.
        
        file_key: eindeutiger Bezeichner der Quelldatei (z.B. Pfad als String).
        So können [^1] in Datei A und [^1] in Datei B als verschiedene Fußnoten behandelt werden.
        """
        lines = text.splitlines(keepends=True)
        clean_parts = []
        active_label = None
        active_content_parts = []

        def flush_active_definition():
            nonlocal active_label, active_content_parts
            if active_label is None:
                return
            note_content = "".join(active_content_parts).strip()
            self.definitions[(file_key, active_label)] = note_content
            active_label = None
            active_content_parts = []

        for line in lines:
            start_match = self._parse_definition_start(line)
            if start_match:
                flush_active_definition()
                active_label = start_match.group(1)
                first_content = start_match.group(2)
                active_content_parts.append(first_content)
                if line.endswith("\n"):
                    active_content_parts.append("\n")
                continue

            if active_label is not None:
                # Pandoc-kompatibel: Fortsetzungszeilen sind eingerückt oder leer.
                if line.strip() == "" or line.startswith((" ", "\t")):
                    active_content_parts.append(line)
                    continue

                flush_active_definition()

            clean_parts.append(line)

        flush_active_definition()
        clean_text = "".join(clean_parts)
        return clean_text.strip()

    def replace_markers(self, text, file_key=""):
        """PASS 2: Nutzt das globale Lexikon, um alle Verweise durch saubere fortlaufende Zahlen zu ersetzen.
        
        file_key: muss derselbe Wert sein wie beim zugehörigen extract_definitions-Aufruf,
        damit Marker korrekt ihrer datei-scoped Definition zugeordnet werden.
        """
        def inline_repl(m):
            old_id = m.group(1)
            scoped_key = (file_key, old_id)
            
            # Prüfen, ob wir die Quelle im datei-scoped Lexikon gefunden haben
            if scoped_key in self.definitions:
                
                # Wenn diese Quelle noch keine globale Nummer hat, bekommt sie jetzt die nächste
                if scoped_key not in self.file_mapping:
                    self.file_mapping[scoped_key] = self.global_counter
                    self.harvested.append((self.global_counter, self.definitions[scoped_key]))
                    self.global_counter += 1
                
                new_id = self.file_mapping[scoped_key]
                
                # Konfigurierbares Ausgabeformat anwenden
                if self.mode == "endnotes":
                    if self.use_typst_links:
                        ref_count = len(self._ref_anchors.get(new_id, [])) + 1
                        ref_anchor = f"fnref-{new_id}-{ref_count}"
                        self._ref_anchors.setdefault(new_id, []).append(ref_anchor)
                        return (
                            f"`#label(\"{ref_anchor}\")`{{=typst}}"
                            f"`#super[#link(<fn-{new_id}>)[{new_id}]]`{{=typst}}"
                        )
                    return f"^[{new_id}]^"
                else:
                    return f"[^{new_id}]"
                    
            # Falls die Quelle nicht im Lexikon existiert, Marker unberührt lassen
            # Marker ohne Definition: als verwaist merken und unberührt lassen
            if (file_key, old_id) not in self.orphan_warnings:
                self.orphan_warnings.append((file_key, old_id))
            return m.group(0)

        # Sucht nach [^Label] im Text und jagt es durch die Ersetzungs-Funktion
        clean_text = re.sub(r'\[\^([^\]]+)\]', inline_repl, text)
        return clean_text.strip()

    def generate_endnotes_file(self, export_path):
        """Generiert die fertige Endnoten.md Datei am Ende des Buchs."""
        if not self.harvested:
            return False
            
        with open(export_path, 'w', encoding='utf-8') as f:
            # YAML Frontmatter für das Kapitel
            f.write(f"---\ntitle: \"{self.title}\"\n---\n\n")
            
            for note_id, text in self.harvested:
                if self.mode == "endnotes":
                    if self.use_typst_links:
                        anchors = self._ref_anchors.get(note_id, [])
                        if len(anchors) == 1:
                            backlink_str = f" `#link(<{anchors[0]}>)[↩]`{{=typst}}"
                        elif len(anchors) > 1:
                            parts = [f"`#link(<{a}>)[↩{i+1}]`{{=typst}}" for i, a in enumerate(anchors)]
                            backlink_str = " " + " ".join(parts)
                        else:
                            backlink_str = ""
                        f.write(f"`#label(\"fn-{note_id}\")`{{=typst}}**[{note_id}]** {text}{backlink_str}\n\n")
                    else:
                        f.write(f"**[{note_id}]** {text}\n\n")
                else:
                    f.write(f"[^{note_id}]: {text}\n\n")
                    
        return True
```


======================================================================
📁 FILE: log_manager.py
======================================================================

```py
import tkinter as tk
import re
from ui_theme import COLORS


class LogManager:
    """Manages the log terminal: records, filtering, display, and clipboard."""

    def __init__(self, studio):
        self.studio = studio

    # =========================================================================
    # WRITE
    # =========================================================================
    def log(self, msg: str, level: str = "info"):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"
        self.studio.log_records.append((line, level))
        self._prune_records()
        self.refresh_view()

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================
    def _get_max_lines(self) -> int:
        try:
            max_lines = int(self.studio.log_max_lines_var.get())
        except (TypeError, ValueError):
            max_lines = 500
        return max(50, max_lines)

    def _get_visible_records(self) -> list:
        filter_label = self.studio.log_filter_var.get()
        allowed = self.studio.log_filter_map.get(filter_label)
        if allowed is None:
            return list(self.studio.log_records)
        return [r for r in self.studio.log_records if r[1] in allowed]

    def _prune_records(self):
        if self.studio.log_auto_clear_var.get():
            keep = self._get_max_lines()
            if len(self.studio.log_records) > keep:
                self.studio.log_records = self.studio.log_records[-keep:]

    # =========================================================================
    # VIEW
    # =========================================================================
    def refresh_view(self):
        log_output = self.studio.log_output
        if not log_output:
            return
        visible = self._get_visible_records()
        try:
            log_output.config(state="normal")
            log_output.delete("1.0", tk.END)
            link_index = 0
            for line, level in visible:
                line_start = log_output.index(tk.END)
                log_output.insert(tk.END, line, level)
                self._apply_clickable_links(log_output, line, line_start, link_index)
                link_index += 1
            log_output.see(tk.END)
            log_output.config(state="disabled")
        except tk.TclError:
            pass

    def _apply_clickable_links(self, log_output, line: str, line_start: str, link_index: int):
        if not hasattr(self.studio, "open_log_target"):
            return

        link_pattern = re.compile(r'\[([^\]\n]+\.(?:md|markdown))\](?:\s+L(\d+))?', re.IGNORECASE)
        for match_idx, match in enumerate(link_pattern.finditer(line)):
            rel_path = match.group(1)
            line_number = int(match.group(2)) if match.group(2) else None
            start = f"{line_start}+{match.start()}c"
            end = f"{line_start}+{match.end()}c"
            tag = f"log_link_{link_index}_{match_idx}"
            log_output.tag_add(tag, start, end)
            log_output.tag_configure(
                tag,
                foreground="#60a5fa",
                underline=True,
                font=("Consolas", 10, "bold"),
                background="#0f172a",
            )
            log_output.tag_raise(tag)
            log_output.tag_bind(tag, "<Enter>", lambda _e: log_output.configure(cursor="hand2"))
            log_output.tag_bind(tag, "<Leave>", lambda _e: log_output.configure(cursor="xterm"))
            log_output.tag_bind(
                tag,
                "<Button-1>",
                lambda _e, path=rel_path, ln=line_number: self.studio.open_log_target(path, ln),
            )
            log_output.tag_bind(
                tag,
                "<Double-1>",
                lambda _e, path=rel_path, ln=line_number: self.studio.open_log_target(path, ln),
            )

    def on_preferences_changed(self):
        self._prune_records()
        self.refresh_view()
        if not self.studio.is_restoring_session:
            self.studio.persist_app_state()

    def clear(self):
        self.studio.log_records.clear()
        self.refresh_view()
        if not self.studio.is_restoring_session:
            self.studio.persist_app_state()

    # =========================================================================
    # CLIPBOARD
    # =========================================================================
    def copy_to_clipboard(self, copy_all: bool = False):
        log_output = self.studio.log_output
        if not log_output:
            return
        try:
            if copy_all:
                content = log_output.get("1.0", tk.END).strip()
            else:
                try:
                    content = log_output.selection_get().strip()
                except tk.TclError:
                    content = log_output.get("1.0", tk.END).strip()
            if not content:
                return
            self.studio.root.clipboard_clear()
            self.studio.root.clipboard_append(content)
            self.studio.root.update()
            if self.studio.status:
                self.studio.status.config(text="Log in Zwischenablage kopiert", fg=COLORS["success"])
        except tk.TclError:
            pass

```


======================================================================
📁 FILE: markdown_asset_scanner.py
======================================================================

```py
import bisect
import re
from pathlib import Path


_INLINE_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_REF_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\[([^\]]*)\]")
_REF_DEF_PATTERN = re.compile(r"^\s*\[([^\]]+)\]:\s*(.+?)\s*$", re.MULTILINE)
_URL_SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _extract_target(raw_target):
    target = str(raw_target or "").strip()
    if not target:
        return ""

    if target.startswith("<") and ">" in target:
        target = target[1:target.find(">")].strip()
    else:
        target = target.split(None, 1)[0].strip()

    if "#" in target:
        target = target.split("#", 1)[0]
    if "?" in target:
        target = target.split("?", 1)[0]

    return target.strip()


def _is_local_asset_target(target):
    if not target:
        return False
    lower = target.lower()
    if lower.startswith(("http://", "https://", "data:", "mailto:")):
        return False
    if _URL_SCHEME_PATTERN.match(target):
        return False
    return True


def _build_line_starts(text):
    starts = [0]
    for idx, char in enumerate(text):
        if char == "\n":
            starts.append(idx + 1)
    return starts


def _line_for_index(index, line_starts):
    return bisect.bisect_right(line_starts, index)


def collect_image_targets(markdown_text):
    text = str(markdown_text or "")
    reference_map = {}

    for ref_name, raw_target in _REF_DEF_PATTERN.findall(text):
        normalized_name = ref_name.strip().lower()
        reference_map[normalized_name] = _extract_target(raw_target)

    targets = []

    for raw_target in _INLINE_IMAGE_PATTERN.findall(text):
        target = _extract_target(raw_target)
        if target:
            targets.append(target)

    for raw_ref in _REF_IMAGE_PATTERN.findall(text):
        ref_name = raw_ref.strip().lower()
        if not ref_name:
            continue
        target = reference_map.get(ref_name, "")
        if target:
            targets.append(target)

    return targets


def collect_image_refs(markdown_text):
    text = str(markdown_text or "")
    line_starts = _build_line_starts(text)
    reference_map = {}

    for ref_name, raw_target in _REF_DEF_PATTERN.findall(text):
        normalized_name = ref_name.strip().lower()
        reference_map[normalized_name] = _extract_target(raw_target)

    refs = []

    for match in _INLINE_IMAGE_PATTERN.finditer(text):
        target = _extract_target(match.group(1))
        if target:
            refs.append((target, _line_for_index(match.start(), line_starts)))

    for match in _REF_IMAGE_PATTERN.finditer(text):
        alt_text = match.group(1).strip().lower()
        raw_ref = match.group(2).strip().lower()
        ref_name = raw_ref if raw_ref else alt_text
        if not ref_name:
            continue
        target = reference_map.get(ref_name, "")
        if target:
            refs.append((target, _line_for_index(match.start(), line_starts)))

    return refs


def find_missing_image_refs(markdown_text, markdown_file_path, book_root_path):
    markdown_path = Path(markdown_file_path)
    book_root = Path(book_root_path)
    missing_refs = []

    for target, line_number in collect_image_refs(markdown_text):
        if not _is_local_asset_target(target):
            continue

        normalized_target = target.replace("\\", "/")
        candidates = []

        if normalized_target.startswith("/"):
            candidates.append(book_root / normalized_target.lstrip("/"))
        else:
            candidates.append(markdown_path.parent / normalized_target)
            candidates.append(book_root / normalized_target)

        exists = any(candidate.exists() and candidate.is_file() for candidate in candidates)
        if not exists:
            missing_refs.append((line_number, target))

    unique_refs = sorted(set(missing_refs), key=lambda item: (item[0], item[1].lower()))
    return unique_refs


def find_missing_images(markdown_text, markdown_file_path, book_root_path):
    missing_refs = find_missing_image_refs(markdown_text, markdown_file_path, book_root_path)
    return sorted({target for _, target in missing_refs})

```


======================================================================
📁 FILE: md_editor.py
======================================================================

```py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import re
from ui_theme import COLORS, FONTS, apply_menu_theme, center_on_parent, style_code_text, style_dialog

class MarkdownEditor(tk.Toplevel):
    def __init__(self, parent, file_path, on_save_callback=None, end_commands=None, initial_line=None):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.on_save_callback = on_save_callback
        self.end_commands = end_commands or []
        self.initial_line = int(initial_line) if isinstance(initial_line, int) and initial_line > 0 else None
        self._last_saved_content = ""
        self.view_mode_var = tk.StringVar(value="code")
        self._preview_dirty = True
        
        self.title(f"📝 Markdown Editor: {self.file_path.name}")
        center_on_parent(self, parent, 850, 650)
        
        # Macht das Fenster "modal" (blockiert das Hauptfenster, bis der Editor geschlossen wird)
        self.transient(parent)
        self.grab_set()
        
        self.setup_ui()
        self.load_file()
        if self.initial_line:
            self.focus_line(self.initial_line)

    def _normalize_editor_content(self, content):
        if content.endswith("\n"):
            return content[:-1]
        return content

    def _has_unsaved_changes(self):
        current_content = self._normalize_editor_content(self.text_area.get("1.0", tk.END))
        return current_content != getattr(self, "_last_saved_content", "")

    def cancel_or_close(self):
        if self._has_unsaved_changes():
            should_discard = messagebox.askyesno(
                "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen.\n\nWirklich verwerfen und schließen?",
                parent=self,
            )
            if not should_discard:
                return
        self.destroy()

    def _source_badge_info(self):
        normalized_parts = {str(part).lower() for part in self.file_path.parts}
        if "processed" in normalized_parts:
            return "Quelle: processed (abgeleitet)", "#dc2626"
        return "Quelle: Originaldatei", "#16a34a"

    def _set_view_mode(self, mode):
        selected_mode = mode if mode in {"code", "preview"} else self.view_mode_var.get()
        if selected_mode not in {"code", "preview"}:
            selected_mode = "code"

        if selected_mode == "preview":
            self.code_frame.pack_forget()
            self.preview_frame.pack(fill=tk.BOTH, expand=True)
            self._render_preview(force=False)
            self.set_editor_status("Vorschau aktiv (read-only)", "#0369a1")
        else:
            self.preview_frame.pack_forget()
            self.code_frame.pack(fill=tk.BOTH, expand=True)
            self.text_area.focus_set()
            self.set_editor_status("Codeansicht aktiv", "#475569")

    def _strip_inline_markdown(self, text):
        result = str(text or "")
        result = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"🖼 \1 (\2)", result)
        result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", result)
        result = re.sub(r"`([^`]+)`", r"\1", result)
        result = re.sub(r"\*\*([^*]+)\*\*", r"\1", result)
        result = re.sub(r"__([^_]+)__", r"\1", result)
        result = re.sub(r"\*([^*]+)\*", r"\1", result)
        result = re.sub(r"_([^_]+)_", r"\1", result)
        return result

    def _render_preview(self, force=False):
        if not force and not self._preview_dirty:
            return
        if not hasattr(self, "preview_text"):
            return

        content = self._normalize_editor_content(self.text_area.get("1.0", tk.END))
        lines = content.splitlines()

        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)

        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                self.preview_text.insert(tk.END, "\n")
                continue

            if in_code_block:
                self.preview_text.insert(tk.END, f"{line}\n", "code")
                continue

            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = self._strip_inline_markdown(heading_match.group(2)).strip()
                self.preview_text.insert(tk.END, f"{heading_text}\n", f"h{level}")
                continue

            quote_match = re.match(r"^\s*>\s?(.*)$", line)
            if quote_match:
                quote_text = self._strip_inline_markdown(quote_match.group(1)).strip()
                self.preview_text.insert(tk.END, f"▌ {quote_text}\n", "quote")
                continue

            bullet_match = re.match(r"^\s*[-*+]\s+(.*)$", line)
            if bullet_match:
                bullet_text = self._strip_inline_markdown(bullet_match.group(1)).strip()
                self.preview_text.insert(tk.END, f"• {bullet_text}\n", "bullet")
                continue

            number_match = re.match(r"^\s*\d+[\.)]\s+(.*)$", line)
            if number_match:
                number_text = self._strip_inline_markdown(number_match.group(1)).strip()
                self.preview_text.insert(tk.END, f"◦ {number_text}\n", "bullet")
                continue

            plain = self._strip_inline_markdown(line)
            self.preview_text.insert(tk.END, f"{plain}\n", "paragraph")

        self.preview_text.config(state="disabled")
        self._preview_dirty = False

    def _on_text_modified(self, _event=None):
        if not self.text_area.edit_modified():
            return
        self.text_area.edit_modified(False)
        self._preview_dirty = True
        if self.view_mode_var.get() == "preview":
            self._render_preview(force=False)
        
    def setup_ui(self):
        style_dialog(self)
        # Toolbar
        toolbar = tk.Frame(self, bg=COLORS["panel_dark"], pady=8, padx=10)
        toolbar.pack(fill=tk.X)
        
        ttk.Button(toolbar, text="💾 Speichern & Schließen (Strg+S)", style="Accent.TButton", command=self.save_and_close).pack(side=tk.LEFT)
                  
        # --- FIXED: SPEICHERN ALS BUTTON hängt jetzt an der 'toolbar' ---
        ttk.Button(toolbar, text="📝 Speichern als...", style="Tool.TButton", command=self.save_as_file).pack(side=tk.LEFT, padx=5)

        view_toggle = tk.Frame(toolbar, bg=COLORS["panel_dark"])
        view_toggle.pack(side=tk.LEFT, padx=(8, 4))
        ttk.Radiobutton(view_toggle, text="Code", value="code", variable=self.view_mode_var, command=lambda: self._set_view_mode("code")).pack(side=tk.LEFT)
        ttk.Radiobutton(view_toggle, text="Vorschau", value="preview", variable=self.view_mode_var, command=lambda: self._set_view_mode("preview")).pack(side=tk.LEFT, padx=(6, 0))

        if self.end_commands:
            insert_btn = tk.Menubutton(
                toolbar,
                text="End-Befehl einfügen",
                bg=COLORS["panel_dark"],
                fg="#e2e8f0",
                activebackground=COLORS["panel_dark"],
                activeforeground="#ffffff",
                relief=tk.FLAT,
                padx=10,
                pady=4,
            )
            insert_btn.pack(side=tk.LEFT, padx=(5, 0))
            insert_menu = tk.Menu(insert_btn, tearoff=0)
            apply_menu_theme(insert_menu)
            for command in self.end_commands:
                insert_menu.add_command(
                    label=command.get("label", "Befehl"),
                    command=lambda cmd=command: self.insert_end_command(cmd),
                )
            insert_btn.configure(menu=insert_menu)
                  
        ttk.Button(toolbar, text="Abbrechen (Esc)", style="Tool.TButton", command=self.cancel_or_close).pack(side=tk.LEFT, padx=10)

        source_text, source_color = self._source_badge_info()
        self.source_label = tk.Label(
            toolbar,
            text=source_text,
            bg=COLORS["panel_dark"],
            fg=source_color,
            font=("Segoe UI", 9, "bold"),
            padx=8,
        )
        self.source_label.pack(side=tk.RIGHT)
        
        # Status Label für Pfad (als self-Variable, damit wir es updaten können)
        self.path_label = tk.Label(toolbar, text=self.file_path.as_posix(), bg=COLORS["panel_dark"], fg="#cbd5e1", font=FONTS["mono"])
        self.path_label.pack(side=tk.RIGHT, padx=(8, 0))

        self.editor_status = tk.Label(self, text="", anchor="w", bg=COLORS["surface_muted"], fg="#475569", font=("Segoe UI", 8), padx=10, pady=4)
        self.editor_status.pack(fill=tk.X)
        
        # Editorbereich mit umschaltbarer Code-/Vorschauansicht
        self.editor_container = tk.Frame(self, bg=COLORS["app_bg"])
        self.editor_container.pack(fill=tk.BOTH, expand=True)

        self.code_frame = tk.Frame(self.editor_container, bg=COLORS["app_bg"])
        self.preview_frame = tk.Frame(self.editor_container, bg=COLORS["app_bg"])

        # Codeansicht (editierbar) + Scrollbar
        self.text_area = tk.Text(self.code_frame, wrap="word", undo=True)
        style_code_text(self.text_area)
        self.text_scroll_y = ttk.Scrollbar(self.code_frame, orient="vertical", command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=self.text_scroll_y.set)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Vorschauansicht (read-only) + Scrollbar
        self.preview_text = tk.Text(self.preview_frame, wrap="word", state="disabled")
        self.preview_text.configure(
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONTS["ui"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            padx=16,
            pady=12,
        )
        self.preview_scroll_y = ttk.Scrollbar(self.preview_frame, orient="vertical", command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=self.preview_scroll_y.set)
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preview_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.preview_text.tag_configure("paragraph", spacing1=2, spacing3=6)
        self.preview_text.tag_configure("bullet", lmargin1=16, lmargin2=28, spacing1=2, spacing3=3)
        self.preview_text.tag_configure("quote", foreground=COLORS["text_muted"], lmargin1=18, lmargin2=18, spacing1=2, spacing3=6)
        self.preview_text.tag_configure("code", font=("Consolas", 10), background=COLORS["surface_muted"], lmargin1=12, lmargin2=12, spacing1=2, spacing3=4)
        self.preview_text.tag_configure("h1", font=("Segoe UI Semibold", 18), spacing1=10, spacing3=8)
        self.preview_text.tag_configure("h2", font=("Segoe UI Semibold", 16), spacing1=8, spacing3=7)
        self.preview_text.tag_configure("h3", font=("Segoe UI Semibold", 14), spacing1=8, spacing3=6)
        self.preview_text.tag_configure("h4", font=("Segoe UI Semibold", 12), spacing1=7, spacing3=5)
        self.preview_text.tag_configure("h5", font=("Segoe UI Semibold", 11), spacing1=6, spacing3=4)
        self.preview_text.tag_configure("h6", font=("Segoe UI Semibold", 10), spacing1=6, spacing3=4)

        self.code_frame.pack(fill=tk.BOTH, expand=True)
        
        # Keybindings
        self.bind("<Control-s>", lambda e: self.save_and_close())
        self.bind("<Escape>", lambda e: self.cancel_or_close())
        self.protocol("WM_DELETE_WINDOW", self.cancel_or_close)
        self.text_area.bind("<<Modified>>", self._on_text_modified)

    def set_editor_status(self, text, color="#475569"):
        self.editor_status.config(text=text, fg=color)

    def save_current_file(self, close_after_save=False):
        try:
            content = self.text_area.get("1.0", tk.END)
            content = self._normalize_editor_content(content)

            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self._last_saved_content = content
            self._preview_dirty = True
            if self.view_mode_var.get() == "preview":
                self._render_preview(force=False)

            if self.on_save_callback:
                try:
                    self.on_save_callback(self.file_path)
                except TypeError:
                    self.on_save_callback()

            if close_after_save:
                self.destroy()
            return True
        except (OSError, UnicodeError) as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht gespeichert werden:\n{e}")
            return False

    def insert_end_command(self, command):
        append_text = command.get("append_text", "")
        if not append_text.strip():
            self.set_editor_status("Kein gültiger End-Befehl konfiguriert.", COLORS["danger"] if "danger" in COLORS else "#dc2626")
            return

        content = self.text_area.get("1.0", tk.END)
        detect_pattern = command.get("detect_pattern")
        if detect_pattern:
            try:
                if re.search(detect_pattern, content, re.DOTALL | re.MULTILINE):
                    self.set_editor_status(f"'{command.get('label', 'Befehl')}' ist am Dateiende bereits vorhanden.", "#d97706")
                    return
            except re.error:
                pass

        base = content.rstrip("\n")
        addition = append_text.strip("\n")
        if base:
            new_content = f"{base}\n\n{addition}\n"
        else:
            new_content = f"{addition}\n"

        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", new_content)
        self.text_area.see(tk.END)
        self.set_editor_status(
            f"'{command.get('label', 'Befehl')}' eingefügt (noch nicht gespeichert).",
            "#0369a1",
        )

    def load_file(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_area.insert("1.0", content)
            # Nach dem Einfügen aus dem Widget lesen, damit das Tk-interne
            # trailing-\n schon berücksichtigt ist und kein Falsch-Positiv entsteht.
            self._last_saved_content = self._normalize_editor_content(self.text_area.get("1.0", tk.END))
            self._preview_dirty = True
            self._render_preview(force=True)
            self.text_area.edit_modified(False)
        except (OSError, UnicodeError) as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht geladen werden:\n{e}")
            self.destroy()

    def focus_line(self, line_number):
        if not isinstance(line_number, int) or line_number <= 0:
            return
        try:
            if self.view_mode_var.get() != "code":
                self.view_mode_var.set("code")
                self._set_view_mode("code")
            line_index = f"{line_number}.0"
            line_end = f"{line_number}.end"
            self.text_area.mark_set("insert", line_index)
            self.text_area.tag_remove("sel", "1.0", tk.END)
            self.text_area.tag_add("sel", line_index, line_end)
            self.text_area.see(line_index)
            self.text_area.focus_set()
            self.set_editor_status(f"Gesprungen zu Zeile {line_number}", "#0369a1")
        except tk.TclError:
            pass

    def save_and_close(self):
        self.save_current_file(close_after_save=True)
            
    # --- FIXED: Saubere Einrückung für die Funktion ---
    def save_as_file(self):
        # Öffnet den Dialog exakt im Ordner der aktuell geöffneten Datei
        new_path = filedialog.asksaveasfilename(
            initialdir=self.file_path.parent,
            title="Neue Markdown-Datei erstellen",
            defaultextension=".md",
            filetypes=[("Markdown Dateien", "*.md"), ("Alle Dateien", "*.*")]
        )
        
        if new_path:
            try:
                # 1. Text in die NEUE Datei schreiben
                with open(new_path, 'w', encoding='utf-8') as f:
                    f.write(self.text_area.get("1.0", tk.END).strip() + "\n")
                
                # 2. Den Editor auf die neue Datei "umbiegen"
                self.file_path = Path(new_path)
                self.title(f"📝 Markdown Editor: {self.file_path.name}")
                self.path_label.config(text=self.file_path.as_posix()) # Pfad oben rechts updaten!
                self._last_saved_content = self._normalize_editor_content(self.text_area.get("1.0", tk.END))
                self._preview_dirty = True
                if self.view_mode_var.get() == "preview":
                    self._render_preview(force=False)
                source_text, source_color = self._source_badge_info()
                self.source_label.config(text=source_text, fg=source_color)
                
                # 3. Das Wichtigste: Das Hauptfenster zwingen, die Liste neu zu laden!
                if self.on_save_callback:
                    try:
                        self.on_save_callback(self.file_path)
                    except TypeError:
                        self.on_save_callback()
                    
                messagebox.showinfo("Erfolg", f"Datei erfolgreich gespeichert unter:\n{self.file_path.name}")
                
            except (OSError, UnicodeError, tk.TclError) as e:
                messagebox.showerror("Fehler", f"Konnte neue Datei nicht speichern:\n{e}")
```


======================================================================
📁 FILE: menu_manager.py
======================================================================

```py
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

```


======================================================================
📁 FILE: pre_processor.py
======================================================================

```py
import re
import shutil
from pathlib import Path
import hashlib
import yaml
from footnote_harvester import FootnoteHarvester

class PreProcessor:
    def __init__(self, book_path, footnote_mode="endnotes", enable_footnote_backlinks=True, output_format="typst"):
        self.book_path = Path(book_path)
        self.processed_dir = self.book_path / "processed"
        self.footnote_mode = footnote_mode
        self.enable_footnote_backlinks = bool(enable_footnote_backlinks)
        self.output_format = str(output_format) if output_format else "typst"
        _use_typst_links = (
            footnote_mode == "endnotes"
            and "typst" in self.output_format.lower()
        )
        self.harvester = FootnoteHarvester(
            mode=footnote_mode,
            title="Anmerkungen",
            use_typst_links=_use_typst_links,
        )

    def _uses_harvester(self):
        return self.footnote_mode in {"endnotes", "pandoc"}

    def _namespace_local_footnotes(self, text, source_path):
        if self.footnote_mode != "footnotes":
            return text

        path_text = str(source_path).replace("\\", "/")
        prefix = re.sub(r"[^A-Za-z0-9_]+", "_", Path(path_text).stem).strip("_") or "note"
        digest = hashlib.sha1(path_text.encode("utf-8")).hexdigest()[:8]
        namespace = f"{prefix}_{digest}"

        def replace_definition(match):
            label = match.group(1)
            return f"[^{namespace}_{label}]:"

        def replace_marker(match):
            label = match.group(1)
            return f"[^{namespace}_{label}]"

        text = re.sub(r'\[\^([^\]]+)\]:', replace_definition, text)
        text = re.sub(r'\[\^([^\]]+)\](?!:)', replace_marker, text)
        return text

    def _footnote_anchor_id(self, label, index):
        safe_label = re.sub(r"[^A-Za-z0-9_-]+", "-", str(label)).strip("-") or "note"
        return f"fnref-{safe_label}-{index}"

    def _inject_footnote_backlinks(self, text):
        if self.footnote_mode != "footnotes" or not self.enable_footnote_backlinks:
            return text

        ref_counts = {}
        ref_targets = {}

        def replace_marker(match):
            label = match.group(1)
            next_index = ref_counts.get(label, 0) + 1
            ref_counts[label] = next_index
            anchor_id = self._footnote_anchor_id(label, next_index)
            ref_targets.setdefault(label, []).append(anchor_id)
            return f"[]{{#{anchor_id}}}[^{label}]"

        text = re.sub(r'\[\^([^\]]+)\](?!:)', replace_marker, text)

        definition_pattern = re.compile(
            r'^\[\^([^\]]+)\]:\s*(.*?)(?=^\[\^[^\]]+\]:|\Z)',
            re.DOTALL | re.MULTILINE,
        )

        def replace_definition(match):
            label = match.group(1)
            body = match.group(2).rstrip()
            targets = ref_targets.get(label, [])
            if not targets:
                return match.group(0)
            if len(targets) == 1:
                backlink_text = f" [↩](#{targets[0]})"
            else:
                backlink_parts = [f"[↩{i + 1}](#{target})" for i, target in enumerate(targets)]
                backlink_text = " " + " ".join(backlink_parts)
            return f"[^{label}]: {body}{backlink_text}\n"

        text = definition_pattern.sub(replace_definition, text)
        return text

    def _extract_parts(self, content):
        """Trennt Frontmatter extrem robust vom Text ab, selbst bei Windows-BOMs."""
        match = re.match(r'^\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*', content, re.DOTALL)
        if match:
            return match.group(0), content[match.end():]
        return "", content

    def _sanitize_frontmatter_for_render(self, frontmatter):
        """Entfernt nicht-numerisches `order` im processed-Klon (Quarto verlangt Number)."""
        if not frontmatter:
            return frontmatter

        match = re.match(
            r'^(\uFEFF?)---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*$',
            frontmatter,
            re.DOTALL,
        )
        if not match:
            return frontmatter

        bom = match.group(1)
        frontmatter_body = match.group(2)
        newline = "\r\n" if "\r\n" in frontmatter else "\n"

        try:
            parsed = yaml.safe_load(frontmatter_body) or {}
        except yaml.YAMLError:
            return frontmatter

        order_val = parsed.get("order")
        if order_val is None:
            return frontmatter

        is_numeric_order = False
        if isinstance(order_val, (int, float)):
            is_numeric_order = True
        elif isinstance(order_val, str) and re.fullmatch(r"\d+", order_val.strip()):
            is_numeric_order = True

        if is_numeric_order:
            return frontmatter

        parsed.pop("order", None)
        dumped = yaml.safe_dump(
            parsed,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).rstrip("\r\n")

        return f"{bom}---{newline}{dumped}{newline}---{newline}"

    def _prune_unused_footnote_definitions(self, text):
        """Entfernt ungenutzte Fußnoten-Definitionen im footnotes-Modus aus dem processed-Text."""
        if self.footnote_mode != "footnotes":
            return text

        definition_pattern = re.compile(
            r'^\[\^([^\]]+)\]:\s*(.*?)(?=^\[\^[^\]]+\]:|\Z)',
            re.DOTALL | re.MULTILINE,
        )
        matches = list(definition_pattern.finditer(text))
        if not matches:
            return text

        used_labels = set(re.findall(r'\[\^([^\]]+)\](?!:)', text))

        parts = []
        cursor = 0
        for match in matches:
            start, end = match.span()
            parts.append(text[cursor:start])
            label = match.group(1)
            if label in used_labels:
                parts.append(match.group(0))
            cursor = end
        parts.append(text[cursor:])

        return ''.join(parts).strip()

    # =========================================================================
    # NEU: DER WASCHGANG FÜR KAPUTTE MARKDOWN-SYNTAX
    # =========================================================================
    def _sanitize_markdown(self, text):
        """Repariert alte Boxen und übersetzt @-Zitationen absolut verlustfrei in echte Fußnoten."""
        
        # 1. Boxen reparieren: :::: \[BOX: Titel\] Inhalt ::: -> Quarto Callout
        text = re.sub(
            r':{3,4}\s*\\?\[BOX:\s*(.*?)\\?\](.*?):{3,4}', 
            r'::: {.callout-note title="\1"}\n\2\n:::', 
            text, 
            flags=re.DOTALL
        )
        
        # 1b. Übrig gebliebene eklige 4er-Doppelpunkte auf saubere 3er kürzen
        text = re.sub(r'^::::\s*$', r':::', text, flags=re.MULTILINE)
        
        # 2. @-ZITATIONEN ROBUST IN FUSSNOTEN UMWANDELN
        # Ziel: Auch Varianten wie [@Key, S. 331] oder [vgl. @Key1; @Key2] sicher abfangen.

        # A) Definitionszeilen mit Klammernotation normalisieren:
        #    [@Key, S. 331]: Text  ->  [^Key]: Text
        text = re.sub(
            r'^([ \t]*)\[@([a-zA-Z0-9_-]+)(?:[^\]]*)\]:',
            r'\1[^\2]:',
            text,
            flags=re.MULTILINE,
        )

        # B) Definitionszeilen ohne Klammern normalisieren:
        #    @Key: Text -> [^Key]: Text
        text = re.sub(
            r'^([ \t]*)@([a-zA-Z0-9_-]+):',
            r'\1[^\2]:',
            text,
            flags=re.MULTILINE,
        )

        # C) Klammer-Zitationsgruppen in Marker umwandeln:
        #    [@Key, S. 331] -> [^Key]
        #    [vgl. @A; @B]  -> [^A][^B]
        def _replace_citation_group(match):
            group_content = match.group(1)
            labels = re.findall(r'@([a-zA-Z0-9_-]+)', group_content)
            if not labels:
                return match.group(0)
            unique_labels = []
            seen = set()
            for label in labels:
                if label in seen:
                    continue
                seen.add(label)
                unique_labels.append(label)
            return ''.join(f'[^{label}]' for label in unique_labels)

        text = re.sub(r'\[([^\]\n]*@[^\]\n]*)\]', _replace_citation_group, text)

        # D) Bare @Label-Verweise im Fließtext umwandeln (ohne E-Mail/Teilwörter zu beschädigen)
        #    Beispiel: "... (siehe @Key)" -> "... (siehe [^Key])"
        text = re.sub(r'(?<![\w\[\^])@([a-zA-Z0-9_-]+)', r'[^\1]', text)
        
        return text
    # =========================================================================

    def _gather_all_definitions(self, nodes):
        """
        PASS 1: Liest alle Dateien heimlich vorab ein, bereinigt sie (Waschgang) 
        und füllt das globale Lexikon im FootnoteHarvester.
        """
        if not self._uses_harvester():
            return
        for node in nodes:
            if not node["path"].startswith("PART:"):
                path = self.book_path / node["path"]
                if path.exists() and path.is_file():
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    _, body = self._extract_parts(content)
                    body = self._sanitize_markdown(body)
                    body = self._namespace_local_footnotes(body, path)
                    
                    # Füllt das Lexikon (datei-scoped), ohne den Text schon zu verändern
                    self.harvester.extract_definitions(body, file_key=str(path))
                    
            if node.get("children"):
                self._gather_all_definitions(node["children"])

    def prepare_render_environment(self, tree_data):
        if self.processed_dir.exists():
            shutil.rmtree(self.processed_dir)
        self.processed_dir.mkdir(parents=True)

        # --- DER MAGISCHE PANDOC FIX ---
        index_path = self.book_path / "index.md"
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                idx_content = f.read()
            if not idx_content.endswith('\n\n'):
                with open(index_path, 'a', encoding='utf-8') as f:
                    f.write('\n\n')
        # -------------------------------

        # === PASS 1: ALLE QUELLEN SAMMELN (Globales Lexikon füllen) ===
        self._gather_all_definitions(tree_data)

        # === PASS 2: DATEIEN SCHREIBEN UND VERWEISE SETZEN ===
        processed_tree = []

        for root_node in tree_data:
            if root_node.get("children"):
                self._process_part_file(root_node)
                
                new_part = {
                    "title": root_node["title"],
                    "path": f"processed/{root_node['path']}",
                    "children": [] 
                }
                
                for chapter_node in root_node["children"]:
                    chapter_dest = self._process_host_file(chapter_node)
                    
                    new_chapter = {
                        "title": chapter_node["title"],
                        "path": f"processed/{chapter_node['path']}",
                        "children": [] 
                    }
                    new_part["children"].append(new_chapter)
                    
                    if chapter_node.get("children"):
                        self._amalgamate_children(chapter_node["children"], chapter_dest, offset=1)
                        
                processed_tree.append(new_part)
            else:
                self._process_host_file(root_node)
                
                new_chapter = {
                    "title": root_node["title"],
                    "path": f"processed/{root_node['path']}",
                    "children": []
                }
                processed_tree.append(new_chapter)

        # Ganz am Ende die gesammelten Endnoten generieren
        if self._uses_harvester() and self.harvester.harvested:
            endnotes_filename = "Endnoten.md"
            endnotes_dest = self.processed_dir / endnotes_filename
            self.harvester.generate_endnotes_file(endnotes_dest)
            
            processed_tree.append({
                "title": self.harvester.title,
                "path": f"processed/{endnotes_filename}",
                "children": []
            })

        return processed_tree

    def _process_part_file(self, node):
        src = self.book_path / node["path"]
        dest = self.processed_dir / node["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            return dest
        
        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()
            
        frontmatter, body = self._extract_parts(content)
        frontmatter = self._sanitize_frontmatter_for_render(frontmatter)
        
        # 1. Text waschen
        body = self._sanitize_markdown(body)
        body = self._namespace_local_footnotes(body, src)
        body = self._inject_footnote_backlinks(body)
        
        # 2. H1 bereinigen
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        
        # 3. Lexikon anwenden (Definitionen entfernen, Marker ersetzen) — datei-scoped
        if self._uses_harvester():
            body = self.harvester.extract_definitions(body, file_key=str(src))
            body = self.harvester.replace_markers(body, file_key=str(src))
        else:
            body = self._prune_unused_footnote_definitions(body)
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body.rstrip() + "\n\n")
            
        return dest

    def _process_host_file(self, node):
        src = self.book_path / node["path"]
        dest = self.processed_dir / node["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            return dest
        
        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()
            
        frontmatter, body = self._extract_parts(content)
        frontmatter = self._sanitize_frontmatter_for_render(frontmatter)
        
        # 1. Text waschen
        body = self._sanitize_markdown(body)
        body = self._namespace_local_footnotes(body, src)
        body = self._inject_footnote_backlinks(body)
        
        # 2. H1 bereinigen
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        
        # 3. Lexikon anwenden — datei-scoped
        if self._uses_harvester():
            body = self.harvester.extract_definitions(body, file_key=str(src))
            body = self.harvester.replace_markers(body, file_key=str(src))
        else:
            body = self._prune_unused_footnote_definitions(body)
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body.rstrip() + "\n\n")
            
        return dest

    def _amalgamate_children(self, children, host_dest, offset):
        for child in children:
            src = self.book_path / child["path"]
            if src.exists():
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                _, body = self._extract_parts(content)
                
                # 1. Text waschen
                body = self._sanitize_markdown(body)
                body = self._namespace_local_footnotes(body, src)
                body = self._inject_footnote_backlinks(body)
                
                # 2. Lexikon anwenden — datei-scoped
                if self._uses_harvester():
                    body = self.harvester.extract_definitions(body, file_key=str(src))
                    body = self.harvester.replace_markers(body, file_key=str(src))
                else:
                    body = self._prune_unused_footnote_definitions(body)
                
                # 3. Überschriften einrücken
                def shift_heading(m):
                    return f"{'#' * (len(m.group(1)) + offset)}{m.group(2)}"
                
                body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                
                with open(host_dest, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n\n{body.strip()}\n\n")
            
            if child.get("children"):
                self._amalgamate_children(child["children"], host_dest, offset + 1)
```


======================================================================
📁 FILE: preview_inspector.py
======================================================================

```py
import tkinter as tk
from tkinter import ttk
from ui_theme import COLORS, FONTS, center_on_parent, style_code_text, style_dialog

class PreviewInspector(tk.Toplevel):
    def __init__(self, parent, tree_data, yaml_engine):
        super().__init__(parent)
        self.title("🔍 Struktur-Preview & Offset-Matrix")
        center_on_parent(self, parent, 900, 700)
        
        # Modal machen (blockiert Hauptfenster, bis es geschlossen wird)
        self.transient(parent)
        self.grab_set()
        
        self.tree_data = tree_data
        self.yaml_engine = yaml_engine
        
        self.setup_ui()
        self.generate_report()
        
    def setup_ui(self):
        style_dialog(self)
        # Header
        header = tk.Frame(self, bg=COLORS["panel_dark"], pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text="ARCHITEKTUR-INSPEKTOR (NUR LESEN)", fg="white", bg=COLORS["panel_dark"], font=FONTS["title_large"]).pack()
        
        # Textfeld für den Report
        self.txt = tk.Text(self, wrap="word")
        style_code_text(self.txt)
        self.txt.pack(fill=tk.BOTH, expand=True)
        
        # Footer
        footer = ttk.Frame(self, padding=(0, 10))
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(footer, text="Schließen", style="Tool.TButton", command=self.destroy).pack()
        
    def generate_report(self):
        report = []
        
        # TEIL 1: YAML OUTPUT
        report.append("="*70)
        report.append("1. QUARTO YAML OUTPUT (Die flache Liste für _quarto.yml)")
        report.append("="*70)
        report.append("So wird der 'chapters:' Block nach dem Flachklopfen aussehen:\n")
        
        yaml_str = self.yaml_engine.generate_yaml_string(self.tree_data, base_indent="  ")
        report.append(yaml_str if yaml_str else "  [Leer - Baum enthält keine Struktur]")
        
        # TEIL 2: OFFSET MATRIX
        report.append("\n\n" + "="*70)
        report.append("2. OFFSET-MATRIX (Der Amalgamierungs-Plan für den Export)")
        report.append("="*70)
        report.append("So müssen die Markdown-Dateien physisch im 'export'-Ordner angepasst")
        report.append("werden, damit Quarto die Hierarchien im Inhaltsverzeichnis korrekt baut.\n")
        
        self._build_offset_matrix(self.tree_data, current_level=0, report=report)
        
        self.txt.insert(tk.END, "\n".join(report))
        self.txt.config(state="disabled") # Read-only, damit man nicht versehentlich tippt
        
    def _build_offset_matrix(self, data, current_level, report):
        for item in data:
            title = item["title"]
            path = item["path"]
            children = item.get("children", [])
            
            # Visuelle Einrückung für den Report
            indent_str = "    " * current_level
            
            # Wie viele Rauten müssen VOR die bestehenden Rauten in der Datei?
            offset_str = f"+{current_level}"
            
            # Beispiel, was mit einer H1 (#) passieren wird:
            h1_transformation = "#" + ("#" * current_level)
            
            report.append(f"{indent_str}📄 {title}")
            report.append(f"{indent_str}   Pfad  : {path}")
            report.append(f"{indent_str}   Ebene : {current_level} (Offset {offset_str})")
            report.append(f"{indent_str}   Aktion: Aus jedem '#' in der Datei muss ein '{h1_transformation}' werden.\n")
            
            if children:
                self._build_offset_matrix(children, current_level + 1, report)
```


======================================================================
📁 FILE: quarto_config_editor.py
======================================================================

```py
import copy
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import yaml

from dialog_dirty_utils import DirtyStateController, confirm_discard_changes
from ui_theme import COLORS, center_on_parent, style_dialog


class QuartoConfigEditor(tk.Toplevel):
    PROJECT_TYPES = ("book", "website", "article", "manuscript")
    LANG_OPTIONS = ("de", "en", "fr", "es", "it", "nl", "pl")
    TOC_DEPTH_OPTIONS = ("1", "2", "3", "4", "5", "6")
    SECTION_NUMBERING_OPTIONS = ("none", "1", "1.1", "1.1.1", "I", "A")
    PAPER_SIZE_OPTIONS = ("a4", "a5", "letter", "legal")
    WIDOW_ORPHAN_OPTIONS = ("auto", "1", "2", "3", "4")
    RIGHTS_LICENSE_OPTIONS = (
        "all-rights-reserved",
        "cc-by-4.0",
        "cc-by-sa-4.0",
        "cc-by-nd-4.0",
        "cc-by-nc-4.0",
        "cc-by-nc-sa-4.0",
        "cc-by-nc-nd-4.0",
        "public-domain",
    )
    FRONTMATTER_PROFILE_OPTIONS = (
        "none",
        "minimal",
        "standard",
        "extended",
        "publisher-print",
        "publisher-ebook",
    )
    HTML_THEME_OPTIONS = (
        "default",
        "cosmo",
        "flatly",
        "journal",
        "litera",
        "lumen",
        "lux",
        "materia",
        "minty",
        "morph",
        "pulse",
        "quartz",
        "sandstone",
        "simplex",
        "sketchy",
        "slate",
        "solar",
        "spacelab",
        "superhero",
        "united",
        "vapor",
        "yeti",
        "zephyr",
    )

    def __init__(self, parent, yaml_path, on_save=None):
        super().__init__(parent)
        self.parent = parent
        self.yaml_path = Path(yaml_path)
        self.on_save = on_save

        self._base_title = "Quarto.yml konfigurieren"
        self.title(self._base_title)
        self._dirty_controller = DirtyStateController(self, self._base_title)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        center_on_parent(self, parent, 760, 620)
        self.config_data = self._load_config()

        self.project_type_var = None
        self.output_dir_var = None
        self.book_title_var = None
        self.book_subtitle_var = None
        self.author_var = None
        self.lang_var = None
        self.book_description_var = None
        self.book_keywords_var = None
        self.publisher_var = None
        self.imprint_var = None
        self.isbn_print_var = None
        self.isbn_ebook_var = None
        self.edition_var = None
        self.rights_holder_var = None
        self.rights_license_var = None
        self.frontmatter_profile_var = None
        self.profile_hint_var = None
        self.typst_keep_typ_var = None
        self.typst_toc_var = None
        self.typst_toc_depth_var = None
        self.typst_number_sections_var = None
        self.typst_section_numbering_var = None
        self.typst_papersize_var = None
        self.typst_widows_var = None
        self.typst_orphans_var = None
        self.html_theme_var = None
        self.html_toc_var = None
        self._initial_form_values = {}

        self._build_ui()

    def _load_config(self):
        if not self.yaml_path.exists():
            return {}
        try:
            with self.yaml_path.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
            return loaded if isinstance(loaded, dict) else {}
        except (OSError, yaml.YAMLError, ValueError, TypeError) as exc:
            messagebox.showerror(
                "Fehler beim Laden von _quarto.yml",
                f"Die Datei konnte nicht gelesen oder geparst werden:\n{self.yaml_path}\n\nGrund:\n{exc}",
                parent=self,
            )
            return {}

    def _build_ui(self):
        style_dialog(self)

        root = tk.Frame(self, bg=COLORS["app_bg"])
        root.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(root, bg=COLORS["app_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=COLORS["app_bg"])
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(content_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        header = tk.Frame(content, bg=COLORS["app_bg"], padx=16, pady=14)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="Quarto-Konfiguration",
            bg=COLORS["app_bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Bearbeitet die wichtigsten Buch- und Formatoptionen in _quarto.yml.",
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        self._build_project_section(content)
        self._build_book_section(content)
        self._build_publisher_section(content)
        self._build_typst_section(content)
        self._build_html_section(content)
        self._capture_initial_form_values()
        self._refresh_dirty_state()
        self._start_dirty_watch()

        btn_row = ttk.Frame(content, padding=(16, 16))
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="Abbrechen", style="Tool.TButton", command=self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(btn_row, text="Speichern", style="Accent.TButton", command=self._save).pack(side=tk.RIGHT)

    def _build_project_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Projekt", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        project_type = str(self._get_nested("project", "type", default="book"))
        if project_type not in self.PROJECT_TYPES:
            project_type = "book"
        self.project_type_var = tk.StringVar(value=project_type)
        self.output_dir_var = tk.StringVar(value=self._get_nested("project", "output-dir", default="export/_book"))

        self._add_row(
            body,
            "Projekt-Typ",
            self._readonly_combo(body, self.project_type_var, self.PROJECT_TYPES, width=18),
            0,
        )
        self._add_row(body, "Output-Ordner", ttk.Entry(body, textvariable=self.output_dir_var, width=40), 1)

    def _build_book_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Buch", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        self.book_title_var = tk.StringVar(value=self._get_nested("book", "title", default=""))
        self.book_subtitle_var = tk.StringVar(value=self._get_root_or_book("subtitle", default=""))
        self.author_var = tk.StringVar(value=self._normalize_author(self._get_nested("author", default="")))
        lang_value = str(self._get_nested("lang", default="de"))
        if lang_value not in self.LANG_OPTIONS:
            lang_value = "de"
        self.lang_var = tk.StringVar(value=lang_value)
        self.book_description_var = tk.StringVar(value=self._get_root_or_book("description", default=""))
        self.book_keywords_var = tk.StringVar(value=self._normalize_keywords(self._get_root_or_book("keywords", default=[])))

        self._add_row(body, "Buchtitel", ttk.Entry(body, textvariable=self.book_title_var, width=50), 0)
        self._add_row(body, "Untertitel", ttk.Entry(body, textvariable=self.book_subtitle_var, width=50), 1)
        self._add_row(body, "Autor(en)", ttk.Entry(body, textvariable=self.author_var, width=50), 2)
        self._add_row(
            body,
            "Sprache",
            self._readonly_combo(body, self.lang_var, self.LANG_OPTIONS, width=10),
            3,
        )
        self._add_row(body, "Beschreibung", ttk.Entry(body, textvariable=self.book_description_var, width=60), 4)
        self._add_row(body, "Keywords (CSV)", ttk.Entry(body, textvariable=self.book_keywords_var, width=60), 5)

    def _build_publisher_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Verlagsspezifika", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        self.publisher_var = tk.StringVar(value=self._get_root_or_book("publisher", default=""))
        self.imprint_var = tk.StringVar(value=self._get_root_or_book("imprint", default=""))
        self.isbn_print_var = tk.StringVar(value=self._get_root_or_book("isbn-print", default=""))
        self.isbn_ebook_var = tk.StringVar(value=self._get_root_or_book("isbn-ebook", default=""))
        self.edition_var = tk.StringVar(value=str(self._get_root_or_book("edition", default="1")))
        self.rights_holder_var = tk.StringVar(value=self._get_root_or_book("rights-holder", default=""))
        rights_license = str(self._get_root_or_book("rights-license", default="all-rights-reserved"))
        if rights_license not in self.RIGHTS_LICENSE_OPTIONS:
            rights_license = "all-rights-reserved"
        self.rights_license_var = tk.StringVar(value=rights_license)
        frontmatter_profile = str(self._get_root_or_book("frontmatter-profile", default="standard"))
        if frontmatter_profile not in self.FRONTMATTER_PROFILE_OPTIONS:
            frontmatter_profile = "standard"
        self.frontmatter_profile_var = tk.StringVar(value=frontmatter_profile)
        self.profile_hint_var = tk.StringVar(value="")

        edition_values = tuple(str(index) for index in range(1, 11))
        if self.edition_var.get() not in edition_values:
            self.edition_var.set("1")

        self._add_row(body, "Verlag", ttk.Entry(body, textvariable=self.publisher_var, width=40), 0)
        self._add_row(body, "Imprint", ttk.Entry(body, textvariable=self.imprint_var, width=40), 1)
        self._add_row(body, "ISBN Print", ttk.Entry(body, textvariable=self.isbn_print_var, width=24), 2)
        self._add_row(body, "ISBN eBook", ttk.Entry(body, textvariable=self.isbn_ebook_var, width=24), 3)
        self._add_row(
            body,
            "Auflage",
            self._readonly_combo(body, self.edition_var, edition_values, width=8),
            4,
        )
        self._add_row(body, "Rechteinhaber", ttk.Entry(body, textvariable=self.rights_holder_var, width=40), 5)
        rights_combo = self._readonly_combo(body, self.rights_license_var, self.RIGHTS_LICENSE_OPTIONS, width=20)
        self._add_row(
            body,
            "Rechte/Lizenz",
            rights_combo,
            6,
        )
        frontmatter_combo = self._readonly_combo(body, self.frontmatter_profile_var, self.FRONTMATTER_PROFILE_OPTIONS, width=20)
        self._add_row(
            body,
            "Frontmatter-Profil",
            frontmatter_combo,
            7,
        )

        rights_combo.bind("<<ComboboxSelected>>", self._on_profile_related_change)
        frontmatter_combo.bind("<<ComboboxSelected>>", self._on_profile_related_change)

        tk.Label(
            body,
            text=(
                "Profil-Mapping: none=ohne Frontmatter, minimal=Basisdaten, standard=Standardbuch, "
                "extended=erweiterte Metadaten, publisher-print=Druckfokus, publisher-ebook=eBook-Fokus"
            ),
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8),
            justify="left",
            wraplength=640,
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))

        tk.Label(
            body,
            text=(
                "Lizenz-Mapping: all-rights-reserved=alle Rechte vorbehalten, cc-*=Creative-Commons-Varianten, "
                "public-domain=gemeinfrei"
            ),
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8),
            justify="left",
            wraplength=640,
        ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(2, 0))

        tk.Label(
            body,
            textvariable=self.profile_hint_var,
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8, "italic"),
            justify="left",
            wraplength=640,
        ).grid(row=10, column=0, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Button(
            body,
            text="Empfohlene Defaults anwenden",
            style="Tool.TButton",
            command=self._apply_profile_defaults,
        ).grid(row=11, column=1, sticky="w", pady=(8, 0))

        ttk.Button(
            body,
            text="Auf Dateistand zurücksetzen",
            style="Tool.TButton",
            command=self._reset_to_loaded_defaults,
        ).grid(row=11, column=2, sticky="w", padx=(8, 0), pady=(8, 0))

        self._update_profile_recommendation_hint()

    def _build_typst_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Format: typst", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        self.typst_keep_typ_var = tk.BooleanVar(value=bool(self._get_nested("format", "typst", "keep-typ", default=True)))
        self.typst_toc_var = tk.BooleanVar(value=bool(self._get_nested("format", "typst", "toc", default=True)))
        self.typst_toc_depth_var = tk.StringVar(value=str(self._get_nested("format", "typst", "toc-depth", default=3)))
        self.typst_number_sections_var = tk.BooleanVar(value=bool(self._get_nested("format", "typst", "number-sections", default=True)))
        section_numbering = str(self._get_nested("format", "typst", "section-numbering", default="1.1.1"))
        if section_numbering not in self.SECTION_NUMBERING_OPTIONS:
            section_numbering = "1.1.1"
        self.typst_section_numbering_var = tk.StringVar(value=section_numbering)

        papersize = str(self._get_nested("format", "typst", "papersize", default="a4"))
        if papersize not in self.PAPER_SIZE_OPTIONS:
            papersize = "a4"
        self.typst_papersize_var = tk.StringVar(value=papersize)

        widows_value = self._normalize_widow_orphan(self._get_nested("format", "typst", "widows", default="auto"))
        orphans_value = self._normalize_widow_orphan(self._get_nested("format", "typst", "orphans", default="auto"))
        self.typst_widows_var = tk.StringVar(value=widows_value)
        self.typst_orphans_var = tk.StringVar(value=orphans_value)

        if self.typst_toc_depth_var.get() not in self.TOC_DEPTH_OPTIONS:
            self.typst_toc_depth_var.set("3")

        ttk.Checkbutton(body, text="keep-typ", variable=self.typst_keep_typ_var).grid(row=0, column=0, sticky="w", padx=(0, 18), pady=4)
        ttk.Checkbutton(body, text="toc", variable=self.typst_toc_var).grid(row=0, column=1, sticky="w", padx=(0, 18), pady=4)
        ttk.Checkbutton(body, text="number-sections", variable=self.typst_number_sections_var).grid(row=0, column=2, sticky="w", pady=4)

        self._add_row(
            body,
            "toc-depth",
            self._readonly_combo(body, self.typst_toc_depth_var, self.TOC_DEPTH_OPTIONS, width=8),
            1,
        )
        self._add_row(
            body,
            "section-numbering",
            self._readonly_combo(body, self.typst_section_numbering_var, self.SECTION_NUMBERING_OPTIONS, width=10),
            2,
        )
        self._add_row(
            body,
            "papersize",
            self._readonly_combo(body, self.typst_papersize_var, self.PAPER_SIZE_OPTIONS, width=10),
            3,
        )
        self._add_row(
            body,
            "Schusterjungen (widows)",
            self._readonly_combo(body, self.typst_widows_var, self.WIDOW_ORPHAN_OPTIONS, width=10),
            4,
        )
        self._add_row(
            body,
            "Hurenkinder (orphans)",
            self._readonly_combo(body, self.typst_orphans_var, self.WIDOW_ORPHAN_OPTIONS, width=10),
            5,
        )

        tk.Label(
            body,
            text="Hinweis: widows/orphans wirken nur, wenn Template/Renderer diese Typst-Optionen auswertet.",
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8),
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _build_html_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Format: html", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        html_theme = str(self._get_nested("format", "html", "theme", default="cosmo"))
        if html_theme not in self.HTML_THEME_OPTIONS:
            html_theme = "cosmo"
        self.html_theme_var = tk.StringVar(value=html_theme)
        self.html_toc_var = tk.BooleanVar(value=bool(self._get_nested("format", "html", "toc", default=True)))

        self._add_row(
            body,
            "theme",
            self._readonly_combo(body, self.html_theme_var, self.HTML_THEME_OPTIONS, width=16),
            0,
        )
        ttk.Checkbutton(body, text="toc", variable=self.html_toc_var).grid(row=0, column=2, sticky="w", padx=(12, 0), pady=4)

    def _readonly_combo(self, parent, variable, values, width):
        combo = ttk.Combobox(parent, textvariable=variable, values=list(values), state="readonly", width=width)
        return combo

    def _add_row(self, parent, label_text, widget, row):
        tk.Label(
            parent,
            text=label_text,
            bg=COLORS["app_bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        widget.grid(row=row, column=1, sticky="w", pady=4)

    def _get_nested(self, *keys, default=None):
        cur = self.config_data
        for key in keys:
            if not isinstance(cur, dict) or key not in cur:
                return default
            cur = cur[key]
        return cur

    def _get_root_or_book(self, key, default=None):
        if isinstance(self.config_data, dict) and key in self.config_data:
            return self.config_data[key]
        return self._get_nested("book", key, default=default)

    def _set_nested(self, target, keys, value):
        cur = target
        for key in keys[:-1]:
            nxt = cur.get(key)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[key] = nxt
            cur = nxt
        cur[keys[-1]] = value

    def _remove_nested(self, target, keys):
        cur = target
        parents = []
        for key in keys[:-1]:
            if not isinstance(cur, dict) or key not in cur:
                return
            parents.append((cur, key))
            cur = cur[key]

        if isinstance(cur, dict) and keys[-1] in cur:
            del cur[keys[-1]]

        for parent, key in reversed(parents):
            node = parent.get(key)
            if isinstance(node, dict) and not node:
                del parent[key]
            else:
                break

    def _normalize_author(self, author_value):
        if isinstance(author_value, list):
            return ", ".join(str(item) for item in author_value if str(item).strip())
        return str(author_value or "")

    def _normalize_keywords(self, keywords_value):
        if isinstance(keywords_value, list):
            return ", ".join(str(item) for item in keywords_value if str(item).strip())
        return str(keywords_value or "")

    def _parse_csv_list(self, raw_text):
        return [part.strip() for part in str(raw_text or "").split(",") if part.strip()]

    def _normalize_widow_orphan(self, raw_value):
        value = str(raw_value).strip().lower()
        if value in self.WIDOW_ORPHAN_OPTIONS:
            return value
        if value.isdigit() and value in self.WIDOW_ORPHAN_OPTIONS:
            return value
        return "auto"

    def _on_profile_related_change(self, _event=None):
        self._update_profile_recommendation_hint()

    def _collect_form_values(self):
        return {
            "project_type": self.project_type_var.get(),
            "output_dir": self.output_dir_var.get(),
            "book_title": self.book_title_var.get(),
            "book_subtitle": self.book_subtitle_var.get(),
            "author": self.author_var.get(),
            "lang": self.lang_var.get(),
            "book_description": self.book_description_var.get(),
            "book_keywords": self.book_keywords_var.get(),
            "publisher": self.publisher_var.get(),
            "imprint": self.imprint_var.get(),
            "isbn_print": self.isbn_print_var.get(),
            "isbn_ebook": self.isbn_ebook_var.get(),
            "edition": self.edition_var.get(),
            "rights_holder": self.rights_holder_var.get(),
            "rights_license": self.rights_license_var.get(),
            "frontmatter_profile": self.frontmatter_profile_var.get(),
            "typst_keep_typ": bool(self.typst_keep_typ_var.get()),
            "typst_toc": bool(self.typst_toc_var.get()),
            "typst_toc_depth": self.typst_toc_depth_var.get(),
            "typst_number_sections": bool(self.typst_number_sections_var.get()),
            "typst_section_numbering": self.typst_section_numbering_var.get(),
            "typst_papersize": self.typst_papersize_var.get(),
            "typst_widows": self.typst_widows_var.get(),
            "typst_orphans": self.typst_orphans_var.get(),
            "html_theme": self.html_theme_var.get(),
            "html_toc": bool(self.html_toc_var.get()),
        }

    def _capture_initial_form_values(self):
        self._initial_form_values = self._collect_form_values()
        self._dirty_controller.capture_initial(self._initial_form_values)

    def _start_dirty_watch(self):
        self._dirty_controller.start_polling(self._collect_form_values, interval_ms=350)

    def _refresh_dirty_state(self):
        if not self._initial_form_values:
            return
        current_values = self._collect_form_values()
        self._dirty_controller.refresh(current_values)

    def _apply_form_values(self, values):
        self.project_type_var.set(values.get("project_type", "book"))
        self.output_dir_var.set(values.get("output_dir", "export/_book"))
        self.book_title_var.set(values.get("book_title", ""))
        self.book_subtitle_var.set(values.get("book_subtitle", ""))
        self.author_var.set(values.get("author", ""))
        self.lang_var.set(values.get("lang", "de"))
        self.book_description_var.set(values.get("book_description", ""))
        self.book_keywords_var.set(values.get("book_keywords", ""))
        self.publisher_var.set(values.get("publisher", ""))
        self.imprint_var.set(values.get("imprint", ""))
        self.isbn_print_var.set(values.get("isbn_print", ""))
        self.isbn_ebook_var.set(values.get("isbn_ebook", ""))
        self.edition_var.set(values.get("edition", "1"))
        self.rights_holder_var.set(values.get("rights_holder", ""))
        self.rights_license_var.set(values.get("rights_license", "all-rights-reserved"))
        self.frontmatter_profile_var.set(values.get("frontmatter_profile", "standard"))
        self.typst_keep_typ_var.set(bool(values.get("typst_keep_typ", True)))
        self.typst_toc_var.set(bool(values.get("typst_toc", True)))
        self.typst_toc_depth_var.set(values.get("typst_toc_depth", "3"))
        self.typst_number_sections_var.set(bool(values.get("typst_number_sections", True)))
        self.typst_section_numbering_var.set(values.get("typst_section_numbering", "1.1.1"))
        self.typst_papersize_var.set(values.get("typst_papersize", "a4"))
        self.typst_widows_var.set(values.get("typst_widows", "auto"))
        self.typst_orphans_var.set(values.get("typst_orphans", "auto"))
        self.html_theme_var.set(values.get("html_theme", "cosmo"))
        self.html_toc_var.set(bool(values.get("html_toc", True)))
        self._update_profile_recommendation_hint()
        self._refresh_dirty_state()

    def _reset_to_loaded_defaults(self):
        if not self._initial_form_values:
            return

        current_values = self._collect_form_values()
        has_unsaved_changes = current_values != self._initial_form_values
        if has_unsaved_changes:
            proceed = confirm_discard_changes(
                self,
                "Änderungen verwerfen?",
                "Es gibt ungespeicherte Änderungen.\n\n"
                "Soll wirklich auf den geladenen Dateistand zurückgesetzt werden?",
            )
            if not proceed:
                return

        self._apply_form_values(self._initial_form_values)
        messagebox.showinfo(
            "Zurückgesetzt",
            "Alle Felder wurden auf den beim Öffnen geladenen Dateistand zurückgesetzt (noch nicht gespeichert).",
            parent=self,
        )

    def _update_profile_recommendation_hint(self):
        profile = (self.frontmatter_profile_var.get() if self.frontmatter_profile_var else "standard") or "standard"
        license_value = (self.rights_license_var.get() if self.rights_license_var else "all-rights-reserved") or "all-rights-reserved"

        profile_hints = {
            "none": "ohne Frontmatter; setze mind. Rechteinhaber/Lizenz explizit",
            "minimal": "reduziert; empfehlenswert für kurze Non-Fiction oder interne Dokumente",
            "standard": "ausgewogen; guter Default für die meisten Buchprojekte",
            "extended": "umfangreich; geeignet für größere Metadaten-/Reihenprojekte",
            "publisher-print": "Druckfokus; Empfehlung: typst papersize a5/a4, toc-depth 2-3, widows/orphans >= 2",
            "publisher-ebook": "eBook-Fokus; Empfehlung: html toc aktiv, schlanke Frontmatter, klare Kapitelstruktur",
        }
        license_hints = {
            "all-rights-reserved": "klassischer Verlagsstandard",
            "cc-by-4.0": "Nutzung mit Namensnennung erlaubt",
            "cc-by-sa-4.0": "wie CC-BY, aber Weitergabe unter gleichen Bedingungen",
            "cc-by-nd-4.0": "Weitergabe erlaubt, keine Bearbeitungen",
            "cc-by-nc-4.0": "nicht-kommerzielle Nutzung mit Namensnennung",
            "cc-by-nc-sa-4.0": "nicht-kommerziell + ShareAlike",
            "cc-by-nc-nd-4.0": "nicht-kommerziell, keine Bearbeitungen",
            "public-domain": "weitgehend frei nutzbar ohne klassische Rechtebindung",
        }

        profile_hint = profile_hints.get(profile, "projektspezifisch")
        license_hint = license_hints.get(license_value, "lizenzabhängig")
        self.profile_hint_var.set(
            f"Kontext-Hinweis: Profil '{profile}' = {profile_hint}. Lizenz '{license_value}' = {license_hint}. "
            "(Empfehlungstext; setzt keine Werte automatisch.)"
        )

    def _apply_profile_defaults(self):
        profile = (self.frontmatter_profile_var.get() if self.frontmatter_profile_var else "standard") or "standard"

        defaults_by_profile = {
            "none": {
                "typst_toc": True,
                "typst_toc_depth": "2",
                "typst_number_sections": True,
                "typst_papersize": "a4",
                "typst_widows": "auto",
                "typst_orphans": "auto",
                "html_toc": True,
            },
            "minimal": {
                "typst_toc": True,
                "typst_toc_depth": "2",
                "typst_number_sections": True,
                "typst_papersize": "a5",
                "typst_widows": "auto",
                "typst_orphans": "auto",
                "html_toc": True,
            },
            "standard": {
                "typst_toc": True,
                "typst_toc_depth": "3",
                "typst_number_sections": True,
                "typst_papersize": "a5",
                "typst_widows": "2",
                "typst_orphans": "2",
                "html_toc": True,
            },
            "extended": {
                "typst_toc": True,
                "typst_toc_depth": "4",
                "typst_number_sections": True,
                "typst_papersize": "a5",
                "typst_widows": "2",
                "typst_orphans": "2",
                "html_toc": True,
            },
            "publisher-print": {
                "typst_toc": True,
                "typst_toc_depth": "3",
                "typst_number_sections": True,
                "typst_papersize": "a5",
                "typst_widows": "2",
                "typst_orphans": "2",
                "html_toc": False,
            },
            "publisher-ebook": {
                "typst_toc": True,
                "typst_toc_depth": "2",
                "typst_number_sections": True,
                "typst_papersize": "a4",
                "typst_widows": "auto",
                "typst_orphans": "auto",
                "html_toc": True,
            },
        }

        chosen = defaults_by_profile.get(profile, defaults_by_profile["standard"])

        self.typst_toc_var.set(bool(chosen["typst_toc"]))
        self.typst_toc_depth_var.set(chosen["typst_toc_depth"])
        self.typst_number_sections_var.set(bool(chosen["typst_number_sections"]))
        self.typst_papersize_var.set(chosen["typst_papersize"])
        self.typst_widows_var.set(chosen["typst_widows"])
        self.typst_orphans_var.set(chosen["typst_orphans"])
        self.html_toc_var.set(bool(chosen["html_toc"]))

        self._update_profile_recommendation_hint()
        self._refresh_dirty_state()
        messagebox.showinfo(
            "Defaults angewendet",
            (
                "Folgende Empfehlungen wurden gesetzt (noch nicht gespeichert):\n"
                f"- typst.toc: {chosen['typst_toc']}\n"
                f"- typst.toc-depth: {chosen['typst_toc_depth']}\n"
                f"- typst.number-sections: {chosen['typst_number_sections']}\n"
                f"- typst.papersize: {chosen['typst_papersize']}\n"
                f"- typst.widows: {chosen['typst_widows']}\n"
                f"- typst.orphans: {chosen['typst_orphans']}\n"
                f"- html.toc: {chosen['html_toc']}"
            ),
            parent=self,
        )

    def _save(self):
        title = self.book_title_var.get().strip()
        subtitle = self.book_subtitle_var.get().strip()
        author = self.author_var.get().strip()
        lang = self.lang_var.get().strip() or "de"
        description = self.book_description_var.get().strip()
        keywords = self._parse_csv_list(self.book_keywords_var.get())

        publisher = self.publisher_var.get().strip()
        imprint = self.imprint_var.get().strip()
        isbn_print = self.isbn_print_var.get().strip()
        isbn_ebook = self.isbn_ebook_var.get().strip()
        edition = self.edition_var.get().strip() or "1"
        rights_holder = self.rights_holder_var.get().strip()
        rights_license = self.rights_license_var.get().strip() or "all-rights-reserved"
        frontmatter_profile = self.frontmatter_profile_var.get().strip() or "standard"

        project_type = self.project_type_var.get().strip() or "book"
        output_dir = self.output_dir_var.get().strip() or "export/_book"
        theme = self.html_theme_var.get().strip() or "cosmo"
        section_numbering = self.typst_section_numbering_var.get().strip() or "1.1.1"
        papersize = self.typst_papersize_var.get().strip() or "a4"
        widows = self.typst_widows_var.get().strip().lower() or "auto"
        orphans = self.typst_orphans_var.get().strip().lower() or "auto"

        if project_type not in self.PROJECT_TYPES:
            messagebox.showerror("Ungültiger Wert", "Projekt-Typ ist ungültig.", parent=self)
            return
        if lang not in self.LANG_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "Sprache ist ungültig.", parent=self)
            return
        if self.typst_toc_depth_var.get() not in self.TOC_DEPTH_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "toc-depth ist ungültig.", parent=self)
            return
        toc_depth = int(self.typst_toc_depth_var.get())
        if section_numbering not in self.SECTION_NUMBERING_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "section-numbering ist ungültig.", parent=self)
            return
        if papersize not in self.PAPER_SIZE_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "papersize ist ungültig.", parent=self)
            return
        if theme not in self.HTML_THEME_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "HTML-Theme ist ungültig.", parent=self)
            return
        if widows not in self.WIDOW_ORPHAN_OPTIONS or orphans not in self.WIDOW_ORPHAN_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "widows/orphans ist ungültig.", parent=self)
            return
        if rights_license not in self.RIGHTS_LICENSE_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "Rechte/Lizenz ist ungültig.", parent=self)
            return
        if frontmatter_profile not in self.FRONTMATTER_PROFILE_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "Frontmatter-Profil ist ungültig.", parent=self)
            return

        updated = copy.deepcopy(self.config_data)

        self._set_nested(updated, ("project", "type"), project_type)
        self._set_nested(updated, ("project", "output-dir"), output_dir)
        self._set_nested(updated, ("book", "title"), title)
        self._set_nested(updated, ("subtitle",), subtitle)
        self._set_nested(updated, ("description",), description)
        self._set_nested(updated, ("keywords",), keywords)
        self._set_nested(updated, ("author",), author)
        self._set_nested(updated, ("lang",), lang)

        self._set_nested(updated, ("publisher",), publisher)
        self._set_nested(updated, ("imprint",), imprint)
        self._set_nested(updated, ("isbn-print",), isbn_print)
        self._set_nested(updated, ("isbn-ebook",), isbn_ebook)
        self._set_nested(updated, ("edition",), edition)
        self._set_nested(updated, ("rights-holder",), rights_holder)
        self._set_nested(updated, ("rights-license",), rights_license)
        self._set_nested(updated, ("frontmatter-profile",), frontmatter_profile)

        for legacy_key in (
            "subtitle",
            "description",
            "keywords",
            "publisher",
            "imprint",
            "isbn-print",
            "isbn-ebook",
            "edition",
            "rights-holder",
            "rights-license",
            "frontmatter-profile",
        ):
            self._remove_nested(updated, ("book", legacy_key))

        self._set_nested(updated, ("format", "typst", "keep-typ"), bool(self.typst_keep_typ_var.get()))
        self._set_nested(updated, ("format", "typst", "toc"), bool(self.typst_toc_var.get()))
        self._set_nested(updated, ("format", "typst", "toc-depth"), toc_depth)
        self._set_nested(updated, ("format", "typst", "number-sections"), bool(self.typst_number_sections_var.get()))
        self._set_nested(updated, ("format", "typst", "section-numbering"), section_numbering)
        self._set_nested(updated, ("format", "typst", "papersize"), papersize)
        if widows == "auto":
            self._remove_nested(updated, ("format", "typst", "widows"))
        else:
            self._set_nested(updated, ("format", "typst", "widows"), int(widows))
        if orphans == "auto":
            self._remove_nested(updated, ("format", "typst", "orphans"))
        else:
            self._set_nested(updated, ("format", "typst", "orphans"), int(orphans))

        self._set_nested(updated, ("format", "html", "theme"), theme)
        self._set_nested(updated, ("format", "html", "toc"), bool(self.html_toc_var.get()))

        try:
            with self.yaml_path.open("w", encoding="utf-8") as handle:
                yaml.dump(updated, handle, sort_keys=False, allow_unicode=True, indent=2)
        except OSError as exc:
            messagebox.showerror("Fehler", f"Konnte _quarto.yml nicht speichern:\n{exc}", parent=self)
            return

        if callable(self.on_save):
            self.on_save(updated)

        self._dirty_controller.stop_polling()

        self.destroy()

```


======================================================================
📁 FILE: quarto_render_safe.py
======================================================================

```py
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from pre_processor import PreProcessor
from yaml_engine import QuartoYamlEngine


IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    ".quarto",
    "__pycache__",
    "processed",
    "export",
}

ROOT_OUTPUT_SUFFIXES = {".typ", ".pdf", ".html", ".docx", ".tex"}
VALID_FOOTNOTE_MODES = {"footnotes", "endnotes", "pandoc"}


def _iter_tree_paths(tree_data):
    for item in tree_data:
        path = item.get("path") if isinstance(item, dict) else None
        if isinstance(path, str):
            yield path
        children = item.get("children") if isinstance(item, dict) else None
        if isinstance(children, list) and children:
            yield from _iter_tree_paths(children)


def _detect_fenced_div_issues(lines):
    issues = []
    stack = []
    marker_pattern = re.compile(r"^\s*(:{3,})(\s*.*)$")
    code_fence_pattern = re.compile(r"^\s*(```+|~~~+)")
    in_code_block = False

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r")

        if code_fence_pattern.match(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        marker_match = marker_pattern.match(line)
        if marker_match:
            colon_count = len(marker_match.group(1))
            tail = marker_match.group(2).strip()
            if tail:
                stack.append((colon_count, line_number))
            else:
                if stack:
                    top_colon_count, _top_line = stack[-1]
                    if colon_count >= top_colon_count:
                        stack.pop()
                    else:
                        issues.append((line_number, "mismatched-close"))
                else:
                    issues.append((line_number, "orphan-close"))
            continue

        if ":::" in line:
            issues.append((line_number, "inline"))

    for _colon_count, open_line in stack:
        issues.append((open_line, "unclosed-open"))

    return issues


def _collect_processed_colon_occurrences(book_path: Path, processed_tree):
    structural_occurrences = []
    raw_occurrences = []

    for rel_path in _iter_tree_paths(processed_tree):
        if not isinstance(rel_path, str) or not rel_path.lower().endswith(".md"):
            continue

        processed_file = book_path / rel_path
        if not processed_file.exists() or not processed_file.is_file():
            continue

        try:
            lines = processed_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        source_rel_path = rel_path[len("processed/") :] if rel_path.startswith("processed/") else rel_path
        structural_issues = _detect_fenced_div_issues(lines)
        for line_number, issue_kind in structural_issues:
            structural_occurrences.append(
                {
                    "source_path": source_rel_path,
                    "line_number": line_number,
                    "issue_kind": issue_kind,
                    "is_structural": True,
                }
            )

        for line_number, line in enumerate(lines, start=1):
            if ":::" not in line:
                continue
            raw_occurrences.append(
                {
                    "source_path": source_rel_path,
                    "line_number": line_number,
                    "issue_kind": "raw-match",
                    "is_structural": False,
                }
            )

    return structural_occurrences if structural_occurrences else raw_occurrences


def _print_colon_occurrence_hints(occurrences):
    if not occurrences:
        return

    has_structural_hits = any(bool(item.get("is_structural")) for item in occurrences if isinstance(item, dict))
    if has_structural_hits:
        print("[safe-render] ::: Hinweis: strukturell auffällige Stelle(n) gefunden:")
    else:
        print("[safe-render] ::: Hinweis: keine strukturellen Defekte erkannt – mögliche Auslöser:")

    shown = []
    seen = set()
    max_hits = 20
    for item in occurrences:
        if not isinstance(item, dict):
            continue
        source_path = item.get("source_path")
        line_number = item.get("line_number")
        issue_kind = item.get("issue_kind")
        is_structural = bool(item.get("is_structural"))
        if not isinstance(source_path, str) or not isinstance(line_number, int):
            continue
        key = (source_path, line_number)
        if key in seen:
            continue
        seen.add(key)
        shown.append((source_path, line_number, issue_kind, is_structural))
        if len(shown) >= max_hits:
            break

    for source_path, line_number, issue_kind, is_structural in shown:
        prefix = "ERROR" if is_structural else "INFO"
        print(f"[safe-render] {prefix} [{source_path}] L{line_number} ({issue_kind})")

    if len(occurrences) > len(shown):
        print(f"[safe-render] ... {len(occurrences) - len(shown)} weitere Treffer ausgeblendet.")

    primary_path, primary_line, _primary_kind, _primary_structural = shown[0]
    print(f"[safe-render] KLICK: [{primary_path}] L{primary_line}")
    if len(shown) > 1:
        alt_path, alt_line, _alt_kind, _alt_structural = shown[1]
        print(f"[safe-render] Alternative: [{alt_path}] L{alt_line}")


def _load_default_footnote_mode(project_root: Path) -> str:
    config_path = project_root / "studio_config.json"
    if not config_path.exists():
        return "endnotes"

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return "endnotes"

    mode = str(data.get("default_footnote_mode", "endnotes")).strip().lower()
    return mode if mode in VALID_FOOTNOTE_MODES else "endnotes"


def _load_enable_footnote_backlinks(project_root: Path) -> bool:
    config_path = project_root / "studio_config.json"
    if not config_path.exists():
        return True

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return True

    return bool(data.get("enable_footnote_backlinks", True))


def _copy_book_to_temp(source_book: Path, temp_root: Path) -> Path:
    destination = temp_root / source_book.name

    def ignore_filter(_dir: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if name in IGNORED_DIR_NAMES:
                ignored.add(name)
        return ignored

    shutil.copytree(source_book, destination, ignore=ignore_filter)
    return destination


def _read_output_dir(book_path: Path) -> str:
    yaml_path = book_path / "_quarto.yml"
    if not yaml_path.exists():
        return "export/_book"

    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError, TypeError, ValueError):
        return "export/_book"

    project = data.get("project") if isinstance(data, dict) else None
    if not isinstance(project, dict):
        return "export/_book"
    output_dir = project.get("output-dir", "export/_book")
    return str(output_dir)


def _restore_output_dir(book_path: Path, output_dir: str) -> None:
    yaml_path = book_path / "_quarto.yml"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    project = data.setdefault("project", {})
    project["output-dir"] = output_dir
    yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, indent=2), encoding="utf-8")


def _copy_render_artifacts(temp_book: Path, source_book: Path, output_dir: str) -> None:
    temp_output = temp_book / output_dir
    if temp_output.exists():
        destination_output = source_book / output_dir
        destination_output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(temp_output, destination_output, dirs_exist_ok=True)

    for artifact in temp_book.iterdir():
        if not artifact.is_file():
            continue
        if artifact.suffix.lower() not in ROOT_OUTPUT_SUFFIXES:
            continue
        shutil.copy2(artifact, source_book / artifact.name)


def run_safe_render(
    book_path: Path,
    output_format: str,
    footnote_mode: str,
    enable_footnote_backlinks: bool,
    profile_name: str | None = None,
    extra_format_options: dict | None = None,
) -> int:
    project_root = Path(__file__).resolve().parent
    original_output_dir = _read_output_dir(book_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        temp_book = _copy_book_to_temp(book_path, temp_root)

        engine = QuartoYamlEngine(temp_book)
        tree_data = engine.parse_chapters()
        processor = PreProcessor(
            temp_book,
            footnote_mode=footnote_mode,
            enable_footnote_backlinks=enable_footnote_backlinks,
            output_format=output_format,
        )
        processed_tree = processor.prepare_render_environment(tree_data)
        colon_occurrences = _collect_processed_colon_occurrences(temp_book, processed_tree)
        _print_colon_occurrence_hints(colon_occurrences)
        engine.save_chapters(
            processed_tree,
            profile_name=profile_name,
            save_gui_state=False,
            extra_format_options=extra_format_options,
        )
        _restore_output_dir(temp_book, original_output_dir)

        cmd = ["quarto", "render", str(temp_book), "--to", output_format]
        print(
            f"[safe-render] book={book_path.name} format={output_format} "
            f"footnotes={footnote_mode} backlinks={enable_footnote_backlinks}"
        )
        result = subprocess.run(cmd, cwd=project_root, check=False)
        if result.returncode != 0:
            return result.returncode

        _copy_render_artifacts(temp_book, book_path, original_output_dir)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rendert ein Quarto-Buch sicher über eine temporäre Studio-Kopie.")
    parser.add_argument("book", help="Pfad zum Buchordner mit _quarto.yml")
    parser.add_argument("--to", default="typst", dest="output_format", help="Quarto-Zielformat, z. B. typst")
    parser.add_argument("--footnote-mode", choices=sorted(VALID_FOOTNOTE_MODES), help="Override für Fußnotenmodus")
    parser.add_argument("--profile-name", help="Optionaler Profilname für export/_book_<profil>.")
    parser.add_argument(
        "--extra-format-options-json",
        help="JSON-Objekt mit zusätzlichen format-Optionen, die nur im temporären Render-Klon injiziert werden.",
    )
    parser.add_argument(
        "--footnote-backlinks",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Aktiviert oder deaktiviert Fußnoten-Rücksprunglinks.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    book_path = (project_root / args.book).resolve() if not Path(args.book).is_absolute() else Path(args.book).resolve()
    if not book_path.exists() or not (book_path / "_quarto.yml").exists():
        print(f"[safe-render] Buchordner ungültig: {book_path}")
        return 2

    footnote_mode = args.footnote_mode or _load_default_footnote_mode(project_root)
    if args.footnote_backlinks is None:
        enable_footnote_backlinks = _load_enable_footnote_backlinks(project_root)
    else:
        enable_footnote_backlinks = bool(args.footnote_backlinks)

    extra_format_options = None
    if args.extra_format_options_json:
        try:
            extra_format_options = json.loads(args.extra_format_options_json)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            print(f"[safe-render] Ungültiges JSON für --extra-format-options-json: {error}")
            return 2
        if not isinstance(extra_format_options, dict):
            print("[safe-render] --extra-format-options-json muss ein JSON-Objekt sein.")
            return 2

    return run_safe_render(
        book_path,
        args.output_format,
        footnote_mode,
        enable_footnote_backlinks,
        profile_name=args.profile_name,
        extra_format_options=extra_format_options,
    )


if __name__ == "__main__":
    raise SystemExit(main())
```


======================================================================
📁 FILE: render_current_book.py
======================================================================

```py
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_book_root(start_path: Path) -> Path | None:
    current = start_path.resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "_quarto.yml").exists():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Findet zum aktiven Pfad das zugehoerige Quarto-Buch und rendert es sicher.",
    )
    parser.add_argument("path", help="Aktive Datei oder Ordner innerhalb eines Buchprojekts.")
    parser.add_argument("--to", default="typst", dest="output_format", help="Quarto-Zielformat, z. B. typst")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    input_path = Path(args.path)
    if not input_path.is_absolute():
        input_path = (project_root / input_path).resolve()

    book_root = find_book_root(input_path)
    if book_root is None:
        print(f"[render-current-book] Kein Buchordner mit _quarto.yml ueber {input_path} gefunden.")
        return 2

    cmd = [
        sys.executable,
        str(project_root / "quarto_render_safe.py"),
        str(book_root),
        "--to",
        args.output_format,
    ]
    return subprocess.run(cmd, cwd=project_root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
```


======================================================================
📁 FILE: Sanitizer.py
======================================================================

```py
import argparse
import re
import unicodedata
import importlib
import logging
import sys
import subprocess
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    tomllib = importlib.import_module("tomllib")
except ModuleNotFoundError:
    try:
        tomllib = importlib.import_module("tomli")
    except ModuleNotFoundError:
        tomllib = None

try:
    yaml = importlib.import_module("yaml")
except ModuleNotFoundError:
    yaml = None

# Dieses Skript durchsucht rekursiv ein Verzeichnis nach Markdown-Dateien,
# wendet Bereinigungen für Quarto/Pandoc/Typst an und überschreibt die Originaldateien.
# Die YAML-Frontmatter (---) bleiben absolut unangetastet, AUßER sie sind fehlerhaft gedoppelt!
# Es wird automatisch ein Logfile im Zielverzeichnis erstellt.

# Statische Ersetzungen (strukturelle Fehler und Typst-inkompatible Steuerzeichen)
# HINWEIS: Um Parser-Fehler zu vermeiden, werden Backticks als Unicode \x60 geschrieben.
REPLACEMENTS = {
    "## ## ": ("## ", "Doppelte Überschriften-Tags repariert"),
    "\x60\x60\x60text\n\n\x60\x60\x60\n": ("", "Leeren Code-Block (LF) entfernt"),
    "\x60\x60\x60text\r\n\r\n\x60\x60\x60\r\n": (
        "",
        "Leeren Code-Block (CRLF) entfernt",
    ),
    "\u200b": ("", "Zero-Width Space entfernt"),
    "\u00ad": ("", "Soft Hyphen entfernt"),
    "\u00a0": (" ", "Non-Breaking Space durch Leerzeichen ersetzt"),
    "\ufeff": ("", "BOM (Byte Order Mark) entfernt"),
}

# Weitere Unicode-Steuerzeichen, die in Quarto/Pandoc -> Typst oft Probleme verursachen.
UNICODE_STRIP_RANGES = [
    (0x200B, 0x200F),  # Zero-width + LRM/RLM
    (0x202A, 0x202E),  # bidi embedding/override
    (0x2060, 0x206F),  # word joiner + directional isolates + invisibles
]

DIV_OPEN_PATTERN = re.compile(r"^\s*:::+\s*\{[^}]+\}\s*$")
DIV_CLOSE_PATTERN = re.compile(r"^\s*:::+\s*$")
ANSWER_DIV_OPEN_PATTERN = re.compile(r"^\s*:::+\s*\{[^}]*\B\.answer\b[^}]*\}\s*$")


def _load_config(config_path=None):
    """Lädt die Sanitizer-Konfiguration aus TOML-Datei."""
    if config_path is None:
        config_path = Path(__file__).parent / "sanitizer_config.toml"

    _defaults = {
        "tags": {
            "C": ".author",
            "Q": ".Inquirer",
            "A": ".answer",
            "MONO": ".monospace",
        },
        "features": {
            "normalize_headings": True,
            "convert_bold_tags": True,
            "remove_double_delimiters": True,
            "convert_inline_tags": True,
            "repair_encoding": True,
            "prompt_unclosed_answer_div": False,
            "only_unclosed_answer_div_check": False,
            "preserve_frontmatter_style_in_repair": True,
        },
        "logging": {"verbose": True},
    }

    if not config_path.exists():
        logger.warning("Sanitizer-Config nicht gefunden, nutze Defaults: %s", config_path)
        return _defaults

    if tomllib is None:
        logger.warning("tomllib/tomli nicht verfügbar, Sanitizer nutzt Defaults")
        return _defaults

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        return config
    except (OSError, ValueError) as error:
        logger.warning("Sanitizer-Config konnte nicht gelesen werden (%s): %s", config_path, error)
        return _defaults


def _repair_encoding(content):
    """Repariert Mojibake: UTF-8-Text, der als Windows-1252 (CP1252) gelesen/gespeichert wurde.
    Beispiel: 'Ã¤' -> 'ä', 'â€ž' -> '„'
    Gibt (content, changes) zurück. Wenn keine Reparatur möglich, bleibt content unverändert."""
    changes = []
    try:
        repaired = content.encode("cp1252").decode("utf-8")
        if repaired != content:
            changes.append("Encoding-Fehler repariert (UTF-8 Mojibake/CP1252 behoben)")
            return repaired, changes
    except (UnicodeEncodeError, UnicodeDecodeError) as error:
        # Kein Mojibake oder gemischtes Encoding – unverändert lassen
        logger.debug("Encoding-Reparatur übersprungen: %s", error)
    return content, changes


def _remove_double_delimiters(body):
    """Entfernt doppelte --- Trennlinien am Anfang des Body.
    Der Body kann direkt mit --- oder mit \\n--- starten, je nach Dateistruktur."""
    changes = []

    # Alle vier möglichen Varianten am Body-Anfang:
    # 1. Kein Leerzeichen davor, LF:    "---\n..."
    # 2. Kein Leerzeichen davor, CRLF:  "---\r\n..."
    # 3. Leerzeile davor, LF:           "\n---\n..."
    # 4. Leerzeile davor, CRLF:         "\r\n---\r\n..."
    for prefix, triple_dash in [
        ("", "---\n"),
        ("", "---\r\n"),
        ("\n", "---\n"),
        ("\r\n", "---\r\n"),
    ]:
        candidate = prefix + triple_dash
        if body.startswith(candidate):
            body = prefix + body[len(candidate) :]
            changes.append("Doppelte '---' Trennlinie nach Frontmatter gelöscht")
            break

    return body, changes


def _convert_bold_tags(body, config):
    """Konvertiert **[TAG]: Text.** Blöcke zu ::: {.class} ... ::: Divs.
    Handhabt auch blockquote-prefixed Varianten: > **[TAG]: Text**
    Der Blockquote-Marker > wird dabei entfernt."""
    changes = []
    tags = config.get("tags", {})

    for tag, div_class in tags.items():
        # Regex: optional blockquote-prefix (wird ignoriert/entfernt), dann bold-tag mit Text.
        # ^ = Zeilenanfang
        # [ \t]* = Optional führendes Whitespace (z.B. versehentliche Einrückungen)
        # (?:>[ \t]*)? = Optional Blockquote-Prefix > (wird entfernt)
        # \*\*\[{tag}\]:? = **[TAG]: oder **[TAG]:
        # \s* = Whitespace nach Doppelpunkt
        # ([^\n]*?) = Text bis Zeilenende (non-greedy, Gruppe 1)
        # \*\*\s*$ = **-Ende und Zeilenende
        pattern = re.compile(
            rf"^[ \t]*(?:>[ \t]*)?\*\*\[{tag}\]:?\s*([^\n]*?)\*\*\s*$",
            re.IGNORECASE | re.MULTILINE,
        )

        if pattern.search(body):
            # Factory-Funktion, um die Closure korrekt zu binden
            def make_replacer(cls_name):
                def replacer(m):
                    text = m.group(1).strip()
                    return f"::: {{{cls_name}}}\n{text}\n:::"

                return replacer

            body = pattern.sub(make_replacer(div_class), body)
            changes.append(f"**[{tag}]:** Blöcke zu ::: {{{div_class}}} konvertiert")

    return body, changes


def _convert_inline_tags(body, config):
    """Konvertiert [TAG]: Absatzblöcke robust zu ::: {.class} ... ::: Divs."""
    changes = []
    tags = config.get("tags", {})

    for tag, div_class in tags.items():
        # Strikt: nur Zeilenstart (optional mit Blockquote) und verpflichtendem Doppelpunkt.
        pattern = re.compile(
            rf"^(?P<prefix>(?:>[ \t]*)*)\[{tag}\]:[ \t]*(?P<text>.*)$",
            re.IGNORECASE,
        )

        lines = body.splitlines(keepends=True)
        i = 0
        out = []
        changed_for_tag = False

        while i < len(lines):
            line = lines[i]
            m = pattern.match(line.rstrip("\r\n"))
            if not m:
                out.append(line)
                i += 1
                continue

            para_lines = [m.group("text")]
            i += 1
            while i < len(lines):
                next_line = lines[i]
                raw = next_line.rstrip("\r\n")
                if raw.strip() == "":
                    break
                # Entfernt nur führende Blockquote-Pfeile im laufenden Absatz.
                raw = re.sub(r"^>[ \t]*", "", raw)
                para_lines.append(raw)
                i += 1

            block_text = "\n".join(x.strip() for x in para_lines).strip()
            out.append(f"::: {{{div_class}}}\n{block_text}\n:::")
            changed_for_tag = True

            # Leerzeile nach Absatz unverändert übernehmen.
            if i < len(lines) and lines[i].strip() == "":
                out.append(lines[i])
                i += 1

        if changed_for_tag:
            body = "".join(out)
            changes.append(f"[{tag}]-Tags in ::: {{{div_class}}} konvertiert")

    return body, changes


def _normalize_headings(body):
    """
    Normalisiert Überschriftsebenen: erste Ebene wird #, zweite ##, etc.
    Beispiel: ##, ###, #### wird zu #, ##, ###
    """
    changes = []
    lines = body.splitlines(keepends=True)
    heading_levels_found = {}

    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+(.+)$", line)
        if m:
            original_level = len(m.group(1))
            content = m.group(2)

            if original_level not in heading_levels_found:
                heading_levels_found[original_level] = len(heading_levels_found) + 1

            new_level = heading_levels_found[original_level]
            new_hashes = "#" * new_level
            lines[i] = f"{new_hashes} {content}\n"

    if heading_levels_found:
        for orig, norm in sorted(heading_levels_found.items()):
            changes.append(
                f"Überschriftsebene {'#' * orig} -> {'#' * norm} normalisiert"
            )

    body = "".join(lines)
    return body, changes


def _detect_newline(text):
    if "\r\n" in text:
        return "\r\n"
    return "\n"


def _is_yaml_delimiter(line):
    return line.strip() in {"---", "..."}


def _split_frontmatter(content):
    """
    Trennt Frontmatter vom Body.
    Erkennt Frontmatter nur am Dateianfang (optional mit BOM).
    """
    bom = ""
    if content.startswith("\ufeff"):
        bom = "\ufeff"
        content = content[1:]

    if not content.startswith("---"):
        return bom, None, None, content

    lines = content.splitlines(keepends=True)
    if not lines:
        return bom, None, None, content

    first = lines[0].strip()
    if first != "---":
        return bom, None, None, content

    idx = 1
    duplicate_opening_count = 0
    while idx < len(lines) and lines[idx].strip() == "---":
        duplicate_opening_count += 1
        idx += 1

    closing_idx = None
    for i in range(idx, len(lines)):
        if _is_yaml_delimiter(lines[i]):
            closing_idx = i
            break

    if closing_idx is None:
        # Heuristik: Wenn der Endtrenner fehlt, endet der Header meist am ersten Leerabsatz.
        header_lines = []
        body_lines = []
        in_body = False
        for line in lines[idx:]:
            if not in_body:
                if line.strip() == "":
                    in_body = True
                    continue
                header_lines.append(line)
            else:
                body_lines.append(line)

        header_text = "".join(header_lines)
        body_text = "".join(body_lines)
        has_closing = False
    else:
        header_text = "".join(lines[idx:closing_idx])
        body_text = "".join(lines[closing_idx + 1 :])
        has_closing = True

    meta = {
        "duplicate_opening_count": duplicate_opening_count,
        "had_closing_delimiter": has_closing,
    }
    return bom, header_text, body_text, meta


def _salvage_simple_yaml_mapping(header_text):
    """Ein defensiver Fallback, falls YAML nicht parsebar ist."""
    result = {}
    for raw_line in header_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        result[key] = value.strip().strip('"').strip("'")
    return result


def _validate_and_repair_frontmatter(
    content, header_mode="repair", preserve_style_in_repair=False
):
    """
    Repariert/validiert Frontmatter-Blöcke robust:
    - doppelte Starttrenner werden auf einen reduziert
    - fehlender Endtrenner wird ergänzt
    - YAML wird geparst; im repair-Mode bei Bedarf konservativ rekonstruiert
    - im preserve-Mode bleibt Header-Inhalt unverändert (nur Struktur-Fixes)
    """
    changes = []
    is_valid = True

    bom, header_text, body_text, meta = _split_frontmatter(content)
    if header_text is None:
        return content, changes, is_valid

    newline = _detect_newline(content)

    if meta["duplicate_opening_count"] > 0:
        changes.append(
            "Frontmatter repariert: Doppelte YAML-Starttrenner auf einen reduziert"
        )

    if not meta["had_closing_delimiter"]:
        changes.append("Frontmatter repariert: Fehlender YAML-Endtrenner ergänzt")

    parsed_data = None
    yaml_repaired = False
    parse_attempted = False

    if yaml is not None:
        parse_attempted = True
        try:
            parsed_data = yaml.safe_load(header_text) if header_text.strip() else {}
        except (yaml.YAMLError, ValueError, TypeError):
            parsed_data = None

    if isinstance(parsed_data, dict):
        if header_mode == "repair":
            if preserve_style_in_repair:
                normalized_header = header_text
                changes.append(
                    "Frontmatter validiert (repair + preserve-style: Inhalt unverändert)"
                )
            else:
                normalized_header = (
                    yaml.safe_dump(
                        parsed_data,
                        allow_unicode=True,
                        sort_keys=False,
                        default_flow_style=False,
                    )
                    if yaml is not None
                    else header_text
                )
                yaml_repaired = True
        else:
            normalized_header = header_text
            changes.append("Frontmatter validiert (preserve-mode: Inhalt unverändert)")
    else:
        fallback_data = _salvage_simple_yaml_mapping(header_text)
        if fallback_data and header_mode == "repair":
            if preserve_style_in_repair:
                normalized_header = header_text
                is_valid = False
                changes.append(
                    "CAVEAT: Frontmatter YAML ungültig (repair + preserve-style: unverändert belassen)"
                )
            elif yaml is not None:
                normalized_header = yaml.safe_dump(
                    fallback_data,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                )
                yaml_repaired = True
                changes.append(
                    "Frontmatter repariert: YAML war defekt und wurde konservativ rekonstruiert"
                )
            else:
                normalized_header = "".join(
                    f"{k}: {v}{newline}" for k, v in fallback_data.items()
                )
                yaml_repaired = True
                changes.append(
                    "Frontmatter repariert: YAML war defekt und wurde konservativ rekonstruiert"
                )
        elif fallback_data and header_mode == "preserve":
            normalized_header = header_text
            is_valid = False
            changes.append(
                "CAVEAT: Frontmatter YAML ungültig (preserve-mode: unverändert belassen)"
            )
        else:
            normalized_header = header_text
            is_valid = False
            changes.append(
                "CAVEAT: Frontmatter erkannt, aber nicht parsebar/reparierbar"
            )

    if not parse_attempted and header_text.strip():
        # Ohne YAML-Library kann nur begrenzt validiert werden.
        fallback_data = _salvage_simple_yaml_mapping(header_text)
        if not fallback_data:
            is_valid = False
            changes.append(
                "CAVEAT: YAML-Validierung nicht möglich (PyYAML fehlt, Header verdächtig)"
            )

    if yaml_repaired and not changes:
        # Kein struktureller Defekt, aber Header wurde erfolgreich validiert/normalisiert.
        changes.append("Frontmatter validiert")

    normalized_header = normalized_header.rstrip("\r\n")
    rebuilt = f"{bom}---{newline}{normalized_header}{newline}---{newline}{body_text}"
    return rebuilt, changes, is_valid


def _strip_problematic_unicode_controls(content):
    removed = {}

    def should_remove(ch):
        cp = ord(ch)
        in_explicit_range = any(
            start <= cp <= end for start, end in UNICODE_STRIP_RANGES
        )
        # Zusätzliche unsichtbare Controls außerhalb klassischer Newlines/Tabs.
        is_control = unicodedata.category(ch) in {"Cf", "Cc"} and ch not in {
            "\n",
            "\r",
            "\t",
        }
        return in_explicit_range or is_control

    out = []
    for ch in content:
        if should_remove(ch):
            removed[ch] = removed.get(ch, 0) + 1
            continue
        out.append(ch)

    if not removed:
        return content, []

    messages = []
    for ch, count in sorted(removed.items(), key=lambda x: ord(x[0])):
        cp = ord(ch)
        name = unicodedata.name(ch, "UNNAMED")
        messages.append(f"Unicode-Control entfernt: U+{cp:04X} ({name}) x{count}")

    return "".join(out), messages


def _split_for_processing(content):
    """
    Liefert strikt typisierte Teile für die Verarbeitung.
    Rückgabe: (has_frontmatter, bom, header, body, newline)
    """
    bom, header_text, body_text, _meta = _split_frontmatter(content)
    newline = _detect_newline(content)

    if header_text is None:
        return False, "", "", content, newline

    return True, bom, header_text, body_text or "", newline


def _find_unclosed_answer_divs(body):
    """Findet ungeschlossene ::: {.answer}-Divs in einem Markdown-Body."""
    stack = []

    for line_number, line in enumerate(body.splitlines(), start=1):
        if DIV_CLOSE_PATTERN.match(line):
            if stack:
                stack.pop()
            continue

        if DIV_OPEN_PATTERN.match(line):
            stack.append(
                {
                    "is_answer": bool(ANSWER_DIV_OPEN_PATTERN.match(line)),
                    "line_number": line_number,
                }
            )

    return [entry for entry in stack if entry["is_answer"]]


def _prompt_and_reveal_file(filepath, unclosed_entries):
    """Warnt interaktiv und markiert betroffene Datei im Windows Explorer."""
    line_numbers = ", ".join(str(item["line_number"]) for item in unclosed_entries)
    print("\n[WARNUNG] Ungeschlossener ::: {.answer}-Block erkannt!")
    print(f"Datei: {filepath}")
    print(f"Betroffene Zeile(n) im Body: {line_numbers}")

    if sys.platform.startswith("win"):
        try:
            subprocess.run(
                ["explorer", "/select,", str(Path(filepath).resolve())], check=False
            )
            print("Datei wurde im Windows Explorer markiert.")
        except OSError as error:
            print(f"Explorer konnte nicht geöffnet werden: {error}")

    try:
        input("Bitte Datei prüfen und mit Enter fortfahren...")
    except EOFError:
        # Nicht-interaktive Umgebungen dürfen weiterlaufen.
        print("Hinweis: Nicht-interaktive Umgebung erkannt – fortgesetzt ohne Eingabe.")


def sanitize_file(filepath, header_mode="repair"):
    """Liest eine Datei ein, wendet Bereinigungen an und liefert Ergebnisdetails zurück."""
    changes_made = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # -1. Encoding-Reparatur VOR allem anderen (betrifft Header + Body gleichmäßig)
        config = _load_config()
        features = config.get("features", {})

        if features.get("only_unclosed_answer_div_check", False):
            _has_frontmatter, _bom, _header_text, body, _newline = _split_for_processing(
                content
            )
            unclosed_answer_divs = _find_unclosed_answer_divs(body)
            if unclosed_answer_divs:
                changes_made.append(
                    "WARNUNG: Ungeschlossener ::: {.answer}-Block erkannt"
                )
                if features.get("prompt_unclosed_answer_div", False):
                    _prompt_and_reveal_file(filepath, unclosed_answer_divs)
            return {"changes": changes_made, "written": False, "skipped": False}

        if features.get("repair_encoding", True):
            content, enc_changes = _repair_encoding(content)
            changes_made.extend(enc_changes)

        # 0. Frontmatter zuerst robust validieren/reparieren.
        content, fm_changes, frontmatter_valid = _validate_and_repair_frontmatter(
            content,
            header_mode=header_mode,
            preserve_style_in_repair=features.get(
                "preserve_frontmatter_style_in_repair", True
            ),
        )
        changes_made.extend(fm_changes)

        if header_mode == "strict" and not frontmatter_valid:
            changes_made.append(
                "STRICT-MODUS: Datei wegen ungültigem Frontmatter nicht geschrieben"
            )
            return {"changes": changes_made, "written": False, "skipped": True}

        # Danach strikt trennen: Nur der Body wird mit Sanitizer-Regeln bearbeitet.
        # Der Frontmatter-Block bleibt (abseits der Reparatur oben) unverändert.
        has_frontmatter, bom, header_text, body, newline = _split_for_processing(
            content
        )

        if features.get("prompt_unclosed_answer_div", False):
            unclosed_answer_divs = _find_unclosed_answer_divs(body)
            if unclosed_answer_divs:
                changes_made.append(
                    "WARNUNG: Ungeschlossener ::: {.answer}-Block erkannt"
                )
                _prompt_and_reveal_file(filepath, unclosed_answer_divs)

        if features.get("remove_double_delimiters"):
            body, dd_changes = _remove_double_delimiters(body)
            changes_made.extend(dd_changes)
        # 1. Statische Ersetzungen anwenden
        for search_string, (replace_string, log_message) in REPLACEMENTS.items():
            if search_string in body:
                body = body.replace(search_string, replace_string)
                changes_made.append(log_message)

        # 1b. Erweiterte Bereinigung unsichtbarer/problematischer Unicode-Steuerzeichen
        body, unicode_changes = _strip_problematic_unicode_controls(body)
        changes_made.extend(unicode_changes)

        if features.get("normalize_headings"):
            body, heading_changes = _normalize_headings(body)
            changes_made.extend(heading_changes)

        if features.get("convert_bold_tags"):
            body, bold_changes = _convert_bold_tags(body, config)
            changes_made.extend(bold_changes)

        # 2. Dynamische Ersetzungen per Regex (HTML Tags)
        if re.search(r"<(\d+)", body):
            body = re.sub(r"<(\d+)", r"< \1", body)
            changes_made.append("Spitze Klammern vor Zahlen maskiert (HTML-Fix)")

        # 3. Inline-Tags ([C]:, [Q]:, [A]:, [MONO]:) in Quarto-Div-Fences konvertieren.
        if features.get("convert_inline_tags", True):
            body, inline_changes = _convert_inline_tags(body, config)
            changes_made.extend(inline_changes)

        # 4. Quarto Div-Fences für ```text Blöcke (analog zu MONO)
        text_block_pattern = r"\x60\x60\x60text[ \t]*\r?\n(.*?)\r?\n\x60\x60\x60"
        if re.search(text_block_pattern, body, flags=re.DOTALL):
            body = re.sub(
                text_block_pattern,
                r"::: {.monospace}\n\1\n:::",
                body,
                flags=re.DOTALL,
            )
            changes_made.append(
                "Code-Blöcke (text) in ::: {.monospace} Div-Fences konvertiert"
            )

        # 5. Quarto Callout-Boxen für [BOX: ...]
        if re.search(r"^::::?\s*\[BOX:\s*(.*?)\]", body, flags=re.MULTILINE):
            body = re.sub(
                r"^::::?\s*\[BOX:\s*(.*?)\]",
                r'::: {.callout-note title="\1"}',
                body,
                flags=re.MULTILINE,
            )
            changes_made.append(
                "BOX-Tags in Quarto Callouts (.callout-note) konvertiert"
            )

        if has_frontmatter:
            normalized_header = header_text.rstrip("\r\n")
            content = f"{bom}---{newline}{normalized_header}{newline}---{newline}{body}"
        else:
            content = body

        # Nur neu speichern, wenn sich tatsächlich etwas geändert hat
        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return {"changes": changes_made, "written": True, "skipped": False}

        return {"changes": changes_made, "written": False, "skipped": False}

    except (OSError, UnicodeError, ValueError) as e:
        print(f"Fehler beim Bearbeiten von '{filepath}': {e}")
        return {
            "changes": [f"FEHLER beim Lesen/Schreiben: {e}"],
            "written": False,
            "skipped": True,
        }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Bereinigt rekursiv Markdown-Dateien fuer eine Quarto (pandoc) -> typst Pipeline, "
            "repariert optional Frontmatter und erstellt ein Logfile."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
        epilog=(
            "\n"
            "Ausfuehrliche Beispiele:\n"
            "  python Sanitizer.py <ordner> --header-mode repair\n"
            "    - Empfohlen fuer Standardlaeufe.\n"
            "    - Frontmatter wird validiert und bei Defekten rekonstruiert.\n"
            "    - Body wird sanitiziert (Typst-/Parser-problematische Zeichen, Marker-Konvertierung).\n"
            "\n"
            "  python Sanitizer.py <ordner> --header-mode preserve\n"
            "    - Frontmatter-Inhalt bleibt unveraendert.\n"
            "    - Nur strukturelle Frontmatter-Reparaturen (z. B. fehlender Endtrenner) sind erlaubt.\n"
            "    - Bei ungueltigem YAML wird ein CAVEAT geloggt.\n"
            "\n"
            "  python Sanitizer.py <ordner> --header-mode strict\n"
            "    - Wenn Frontmatter ungueltig ist, wird die Datei NICHT geschrieben.\n"
            "    - Die Datei wird als UEBERSPRUNGEN protokolliert.\n"
            "\n"
            "Hinweise:\n"
            "  - Hilfe aufrufen mit: -h, --help oder -help\n"
            "  - PyYAML ist Pflicht: pip install pyyaml\n"
            "  - Ausgabe-Log: sanitizer_log.txt im Zielordner\n"
        ),
    )
    parser.add_argument(
        "-h",
        "--help",
        "-help",
        action="help",
        help="Zeigt diese Hilfe mit Erklaerungen und Beispielen an.",
    )
    parser.add_argument(
        "directory", help="Der Pfad zum Verzeichnis, das durchsucht werden soll."
    )
    parser.add_argument(
        "--header-mode",
        choices=["repair", "preserve", "strict"],
        default="repair",
        help=(
            "Steuert die Frontmatter-Behandlung: "
            "repair = validieren + ggf. rekonstruieren/normalisieren, "
            "preserve = nur validieren, Header-Inhalt unverändert lassen, "
            "strict = bei ungültigem Header nicht schreiben."
        ),
    )
    args = parser.parse_args()

    if yaml is None:
        print("Fehler: PyYAML ist erforderlich, aber nicht installiert.")
        print("Installiere es mit: pip install pyyaml")
        sys.exit(2)

    target_dir = Path(args.directory)

    if not target_dir.is_dir():
        print(
            f"Fehler: Das angegebene Verzeichnis '{target_dir}' existiert nicht oder ist kein Ordner."
        )
        return

    # =========================================================================
    # NEU: INTELLIGENTER ORDNER-SCHUTZ
    # =========================================================================
    if (target_dir / "_quarto.yml").exists() and (target_dir / "content").exists():
        scan_dir = target_dir / "content"
        print(f"📚 Book Studio Projekt erkannt! Begrenze Scan strikt auf: {scan_dir.relative_to(target_dir)}\\")
    else:
        scan_dir = target_dir

    print(f"Durchsuche '{scan_dir}' und alle Unterordner nach .md-Dateien...")

    total_files = 0
    changed_files = 0
    skipped_files = 0
    warning_files = 0

    log_path = target_dir / "sanitizer_log.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write("=== SANITIZER LOG ===\n")
        log_file.write(f"Datum/Zeit: {timestamp}\n")
        log_file.write(f"Basis-Verzeichnis: {target_dir.absolute()}\n")
        log_file.write(f"Scan-Verzeichnis: {scan_dir.absolute()}\n") # <-- NEU: Protokolliert echten Scan-Pfad
        log_file.write("=====================\n\n")

        # HIER WIRD JETZT scan_dir STATT target_dir VERWENDET
        for md_file in scan_dir.rglob("*.md"):
            
            # NEU: HARDCORE BLACKLIST FÜR PIPELINE-ORDNER
            if any(forbidden in md_file.parts for forbidden in ['.backups', 'export', 'processed', '.venv', '.git']):
                continue

            total_files += 1
            result = sanitize_file(md_file, header_mode=args.header_mode)
            changes = result["changes"]
            written = result["written"]
            skipped = result["skipped"]

            has_answer_warning = any(
                "Ungeschlossener ::: {.answer}" in c for c in changes
            )

            if written:
                changed_files += 1
                rel_path = md_file.relative_to(target_dir)
                print(f"[BEREINIGT] {rel_path.name} ({len(changes)} Änderungen)")
                log_file.write(f"Datei: {rel_path}\n")
                for change in changes:
                    log_file.write(f"  - {change}\n")
                log_file.write("\n")
            elif skipped:
                skipped_files += 1
                rel_path = md_file.relative_to(target_dir)
                print(f"[ÜBERSPRUNGEN] {rel_path.name} ({len(changes)} Hinweise)")
                log_file.write(f"Datei: {rel_path}\n")
                for change in changes:
                    log_file.write(f"  - {change}\n")
                log_file.write("\n")
            elif has_answer_warning:
                warning_files += 1
                rel_path = md_file.relative_to(target_dir)
                print(f"[WARNUNG] {rel_path.name} — ungeschlossener ::: {{.answer}}-Block!")
                log_file.write(f"[WARNUNG] Datei: {rel_path}\n")
                for change in changes:
                    log_file.write(f"  - {change}\n")
                log_file.write("\n")
            elif changes:
                rel_path = md_file.relative_to(target_dir)
                print(f"[GEPRÜFT] {rel_path.name} ({len(changes)} Hinweise)")
                log_file.write(f"Datei: {rel_path}\n")
                for change in changes:
                    log_file.write(f"  - {change}\n")
                log_file.write("\n")

        log_file.write("--- Zusammenfassung ---\n")
        log_file.write(f"Geprüfte Dateien: {total_files}\n")
        log_file.write(f"Geänderte Dateien: {changed_files}\n")
        log_file.write(f"Übersprungene Dateien: {skipped_files}\n")
        log_file.write(f"Dateien mit ungeschlossenem {{.answer}}-Block: {warning_files}\n")
        if warning_files == 0:
            log_file.write("ERGEBNIS: OK — keine ungeschlossenen {.answer}-Blöcke gefunden.\n")
        else:
            log_file.write(f"ERGEBNIS: {warning_files} Datei(en) mit ungeschlossenem {{.answer}}-Block!\n")

    print("\n--- Vorgang abgeschlossen ---")
    print(f"Geprüfte .md-Dateien gesamt:        {total_files}")
    print(f"Davon bereinigt und überschrieben:  {changed_files}")
    print(f"Davon übersprungen (strict/Fehler): {skipped_files}")
    if warning_files == 0:
        print("✅  Keine ungeschlossenen {.answer}-Blöcke gefunden.")
    else:
        print(f"⚠️   {warning_files} Datei(en) mit ungeschlossenem {{.answer}}-Block!")
    print(f"Logfile: {log_path}")

if __name__ == "__main__":
    main()

```


======================================================================
📁 FILE: sanitizer_config_editor.py
======================================================================

```py
import importlib
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from dialog_dirty_utils import DirtyStateController, confirm_discard_changes
from ui_theme import COLORS, ThemedTooltip, center_on_parent, style_dialog


try:
    tomllib = importlib.import_module("tomllib")
except ModuleNotFoundError:
    try:
        tomllib = importlib.import_module("tomli")
    except ModuleNotFoundError:
        tomllib = None


def _parse_toml_value(value_str: str):
    """Parsiert einen TOML-Wert (Boolean, Int, Float, String)."""
    value_str = value_str.strip()

    # Boolean
    if value_str.lower() == "true":
        return True
    if value_str.lower() == "false":
        return False

    # Array (einfach: nur Strings in Anführungszeichen)
    if value_str.startswith("[") and value_str.endswith("]"):
        # Nutze tomllib zum korrekt parsen
        try:
            import importlib
            try:
                tomllib = importlib.import_module("tomllib")
            except ModuleNotFoundError:
                tomllib = importlib.import_module("tomli")
            
            # Parsiere als TOML array
            dummy_toml = f"arr = {value_str}"
            parsed = tomllib.loads(dummy_toml)
            return parsed.get("arr", [])
        except Exception:
            # Fallback: simple parsing
            content = value_str[1:-1]
            items = [item.strip().strip('"\'') for item in content.split(",")]
            return [item for item in items if item]

    # String (quoted)
    if (value_str.startswith('"') and value_str.endswith('"')) or (
        value_str.startswith("'") and value_str.endswith("'")
    ):
        # Entferne Quotes und unescape
        content = value_str[1:-1]
        content = content.replace('\\"', '"').replace("\\\\", "\\")
        return content

    # Int/Float
    try:
        if "." in value_str:
            return float(value_str)
        return int(value_str)
    except ValueError:
        pass

    # Default: string
    return value_str


def _infer_type(value):
    """Leitet einen Typ vom Wert ab."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, float):
        return "float"
    if isinstance(value, int):
        return "int"
    if isinstance(value, list):
        return "array"
    return "string"


def extract_enum_constraints(config_path: Path) -> dict:
    """
    Extrahiert Enum-Constraints aus dem __config Abschnitt der TOML-Datei.
    Nutzt tomllib zum korrekten Parsen der Struktur.
    Rückgabe: {section.key: [values, ...], ...}
    Beispiel: {'tags.C': ['.author', '.note', '.warning'], ...}
    """
    constraints = {}
    
    if not config_path.exists() or tomllib is None:
        return constraints
    
    try:
        with open(config_path, "rb") as f:
            full_toml = tomllib.load(f)
        
        config_section = full_toml.get("__config", {})
        
        # Iteriere über __config.section.key.enum Struktur
        for section_name, section_dict in config_section.items():
            if section_name == "__meta__" or not isinstance(section_dict, dict):
                continue
            
            for key_name, key_dict in section_dict.items():
                if not isinstance(key_dict, dict):
                    continue
                
                enum_values = key_dict.get("enum")
                if isinstance(enum_values, list):
                    constraints[f"{section_name}.{key_name}"] = enum_values
    except Exception:
        pass
    
    return constraints


def parse_toml_with_comments(config_path: Path):
    """
    Parst eine TOML-Datei mit Kommentarextraktion.
    Rückgabe: {section: {key: {value, type, doc, comments_before}}}
    """
    result = {}

    if not config_path.exists():
        return result

    lines = config_path.read_text(encoding="utf-8").splitlines()

    current_section = None
    pending_comments = []

    for line in lines:
        stripped = line.strip()

        # Kommentarzeile sammeln
        if stripped.startswith("#"):
            comment_text = stripped[1:].strip()
            pending_comments.append(comment_text)
            continue

        # Leerzeile
        if not stripped:
            continue

        # Section [name]
        if stripped.startswith("[") and stripped.endswith("]"):
            section_name = stripped[1:-1].strip()
            current_section = section_name
            result[section_name] = {"__meta__": {"comments_before": pending_comments.copy()}}
            pending_comments = []
            continue

        # Key = Value
        if "=" in stripped and current_section:
            key, _, value_str = stripped.partition("=")
            key = key.strip()
            value_str = value_str.strip()

            # Parse TOML-Wert
            value = _parse_toml_value(value_str)

            result[current_section][key] = {
                "value": value,
                "type": _infer_type(value),
                "doc": " ".join(pending_comments) if pending_comments else "",
                "comments_before": pending_comments.copy(),
            }
            pending_comments = []

    return result


SANITIZER_SCHEMA = {
    "tags": {
        "__meta__": {
            "label": "Tag-Mapping",
            "doc": "Mapping von Kurz-Tags zu Quarto-Div-Klassen. Diese Tabelle ist dynamisch und erlaubt beliebig viele Einträge.",
            "kind": "mapping",
        },
        "C": {
            "type": "string",
            "label": "Tag C",
            "doc": "Mapping für [C]: Pattern, standardmäßig auf die Klasse .author.",
            "default": ".author",
        },
        "Q": {
            "type": "string",
            "label": "Tag Q",
            "doc": "Mapping für [Q]: Pattern, standardmäßig auf die Klasse .Inquirer.",
            "default": ".Inquirer",
        },
        "A": {
            "type": "string",
            "label": "Tag A",
            "doc": "Mapping für [A]: Pattern, standardmäßig auf die Klasse .answer.",
            "default": ".answer",
        },
        "MONO": {
            "type": "string",
            "label": "Tag MONO",
            "doc": "Mapping für [MONO]: Pattern, standardmäßig auf die Klasse .monospace.",
            "default": ".monospace",
        },
    },
    "features": {
        "__meta__": {
            "label": "Features",
            "doc": "Steuert, welche Sanitizer-Funktionen aktiv sind.",
        },
        "normalize_headings": {
            "type": "bool",
            "label": "Headings normalisieren",
            "doc": "Bereinigt problematische Überschriftenmuster und vereinheitlicht Heading-Strukturen.",
            "default": True,
        },
        "convert_bold_tags": {
            "type": "bool",
            "label": "Fett-Tags konvertieren",
            "doc": "Konvertiert markierte Tag-Muster in die vorgesehenen Strukturen.",
            "default": True,
        },
        "remove_double_delimiters": {
            "type": "bool",
            "label": "Doppelte Delimiter entfernen",
            "doc": "Entfernt doppelte --- Trenner direkt nach dem Frontmatter.",
            "default": True,
        },
        "convert_inline_tags": {
            "type": "bool",
            "label": "Inline-Tags konvertieren",
            "doc": "Wandelt Inline-Tag-Marker in die gewünschte Quarto-/Typst-Struktur um.",
            "default": True,
        },
        "repair_encoding": {
            "type": "bool",
            "label": "Encoding reparieren",
            "doc": "Repariert Mojibake wie Ã¤ -> ä. Deaktivieren, wenn dadurch Sonderzeichen verfälscht werden.",
            "default": False,
        },
        "prompt_unclosed_answer_div": {
            "type": "bool",
            "label": "Bei offenen Answer-Divs anhalten",
            "doc": "Erkennt ungeschlossene ::: {.answer}-Blöcke, öffnet die Datei im Explorer und wartet auf Bestätigung.",
            "default": True,
        },
        "only_unclosed_answer_div_check": {
            "type": "bool",
            "label": "Nur Answer-Div-Prüfung",
            "doc": "Führt ausschließlich die Prüfung auf ungeschlossene ::: {.answer}-Blöcke aus.",
            "default": True,
        },
        "preserve_frontmatter_style_in_repair": {
            "type": "bool",
            "label": "Frontmatter-Stil erhalten",
            "doc": "Lässt beim Repair den bisherigen Header-Stil unverändert und repariert nur die Struktur.",
            "default": True,
        },
    },
    "logging": {
        "__meta__": {
            "label": "Logging",
            "doc": "Steuert die Ausführlichkeit der Sanitizer-Protokollierung.",
        },
        "verbose": {
            "type": "bool",
            "label": "Verbose Logging",
            "doc": "Aktiviert ausführliche Debug-Ausgaben im Sanitizer-Log.",
            "default": True,
        },
    },
}
def _extract_label_from_doc(doc_text: str, key: str) -> str:
    """Extrahiert ein Label aus Dokumenttext oder generiert eines vom Key."""
    if not doc_text:
        # Fallback: Key in schöne Form wandeln (snake_case -> Title Case)
        return key.replace("_", " ").title()
    # Erste Zeile des Docs als Label, oder ganzes Doc wenn sehr kurz
    lines = doc_text.split("\n")
    return lines[0].strip() if lines[0].strip() else key.replace("_", " ").title()


class SanitizerConfigEditor(tk.Toplevel):
    def __init__(self, parent, config_path, on_save=None):
        super().__init__(parent)
        self.parent = parent
        self.config_path = Path(config_path)
        self.on_save = on_save
        self.field_vars = {}
        self.tag_rows = []
        self.tags_rows_frame = None
        self._base_title = "Sanitizer-Konfiguration"
        self._dirty_controller = DirtyStateController(self, self._base_title)

        self.title(self._base_title)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._request_close)

        width, height = 760, 680
        center_on_parent(self, parent, width, height)

        # Parse TOML mit Kommentaren (Single Source of Truth)
        self.config_parsed = parse_toml_with_comments(self.config_path)
        self.config_data = self._extract_config_values()
        self.enum_constraints = extract_enum_constraints(self.config_path)
        self.schema = self._build_runtime_schema()
        self._build_ui()
        self._capture_initial_dirty_snapshot()
        self._start_dirty_watch()

    def _extract_config_values(self):
        """Extrahiert nur die Werte aus der geparsten TOML."""
        result = {}
        for section_name, section_dict in self.config_parsed.items():
            result[section_name] = {}
            for key, spec in section_dict.items():
                if key == "__meta__":
                    continue
                result[section_name][key] = spec.get("value")
        return result

    def _build_runtime_schema(self):
        """
        Baue Laufzeit-Schema aus geparster TOML mit Metadaten aus Kommentaren.
        Fallback zu SANITIZER_SCHEMA für fehlende Dokumentation.
        """
        runtime_schema = {}

        # Alle Sections aus der Datei (plus fallback aus Schema)
        section_names = list(self.config_parsed.keys())
        for section_name in SANITIZER_SCHEMA.keys():
            if section_name not in section_names:
                section_names.append(section_name)

        for section_name in section_names:
            parsed_section = self.config_parsed.get(section_name, {})
            schema_section = SANITIZER_SCHEMA.get(section_name, {})
            config_section = self.config_data.get(section_name, {})

            section_schema = {}
            section_meta = parsed_section.get("__meta__", {})

            # Section-Metadaten aus Kommentaren oder Fallback
            section_doc = "\n".join(section_meta.get("comments_before", []))
            section_label = schema_section.get("__meta__", {}).get("label") or section_name.replace("_", " ").title()

            section_schema["__meta__"] = {
                "label": section_label,
                "doc": section_doc or schema_section.get("__meta__", {}).get("doc", ""),
                "kind": schema_section.get("__meta__", {}).get("kind", "section"),
            }

            # Alle Keys aus der Datei + Schema
            all_keys = set(k for k in parsed_section.keys() if k != "__meta__")
            all_keys.update(k for k in schema_section.keys() if k != "__meta__")

            for key in sorted(all_keys):
                parsed_spec = parsed_section.get(key, {})
                schema_spec = schema_section.get(key, {})

                # Priorität: geparste TOML > SCHEMA
                value = config_section.get(key, schema_spec.get("default"))
                field_type = parsed_spec.get("type") or schema_spec.get("type") or self._infer_type(value)
                doc = parsed_spec.get("doc") or schema_spec.get("doc", "")
                label = _extract_label_from_doc(doc, key) or schema_spec.get("label", key)

                section_schema[key] = {
                    "type": field_type,
                    "label": label,
                    "doc": doc,
                    "default": schema_spec.get("default", value),
                    "value": value,
                }

            runtime_schema[section_name] = section_schema

        return runtime_schema

    def _build_ui(self):
        style_dialog(self)
        root_frame = tk.Frame(self, bg=COLORS["app_bg"])
        root_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(root_frame, bg=COLORS["app_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(root_frame, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=COLORS["app_bg"])
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(content_window, width=event.width),
        )

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        header = tk.Frame(content, bg=COLORS["app_bg"], padx=16, pady=14)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="Sanitizer-Konfiguration",
            bg=COLORS["app_bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Typbewusster Editor für sanitizer_config.toml mit Hover-Hinweisen.",
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        for section_name, section_schema in self.schema.items():
            if section_schema.get("__meta__", {}).get("kind") == "mapping":
                self._build_mapping_section(content, section_name)
            else:
                self._build_scalar_section(content, section_name)

        button_row = ttk.Frame(content, padding=(16, 16))
        button_row.pack(fill=tk.X)
        ttk.Button(button_row, text="Abbrechen", style="Tool.TButton", command=self._request_close).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(button_row, text="Speichern", style="Accent.TButton", command=self._save).pack(side=tk.RIGHT)

    def _build_mapping_section(self, parent, section_name):
        section_schema = self.schema[section_name]
        meta = section_schema.get("__meta__", {})
        frame = ttk.LabelFrame(
            parent,
            text=meta.get("label", section_name),
            style="Section.TLabelframe",
        )
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        doc_label = tk.Label(frame, text="?", bg="#d6eaf8", fg="#1f618d", width=2, cursor="question_arrow")
        doc_label.place(relx=1.0, x=-20, y=-1, anchor="ne")
        ThemedTooltip(doc_label, meta.get("doc", ""))

        header = tk.Frame(body, bg=COLORS["app_bg"])
        header.pack(fill=tk.X, pady=(0, 6))
        tk.Label(header, text="Key", width=18, anchor="w", bg=COLORS["app_bg"], fg=COLORS["heading"], font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="Wert", anchor="w", bg=COLORS["app_bg"], fg=COLORS["heading"], font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)

        rows_frame = tk.Frame(body, bg=COLORS["app_bg"])
        rows_frame.pack(fill=tk.X)
        self.tags_rows_frame = rows_frame

        tag_section = self.config_data.get(section_name, {})
        for key, value in tag_section.items():
            spec = section_schema.get(key, {})
            self._add_tag_row(section_name, key, value, spec.get("doc", "Benutzerdefinierter Tag-Eintrag."))

        ttk.Button(body, text="+ Eintrag hinzufügen", style="Tool.TButton", command=lambda: self._add_tag_row(section_name, "", "", "Benutzerdefinierter Tag-Eintrag.")).pack(anchor="w", pady=(8, 0))

    def _add_tag_row(self, section_name, key, value, doc_text):
        row = tk.Frame(self.tags_rows_frame, bg=COLORS["app_bg"])
        row.pack(fill=tk.X, pady=2)

        key_var = tk.StringVar(value=key)
        value_var = tk.StringVar(value=value)

        key_entry = ttk.Entry(row, textvariable=key_var, width=20)
        key_entry.pack(side=tk.LEFT, padx=(0, 8))
        
        # Prüfe, ob ein Enum für tags.key existiert
        enum_key = f"{section_name}.{key}" if key else None
        enum_values = self.enum_constraints.get(enum_key, []) if enum_key else []
        
        if enum_values:
            # Dropdown verwenden
            value_widget = ttk.Combobox(row, textvariable=value_var, values=enum_values, state="readonly", width=30)
        else:
            # Text-Input verwenden
            value_widget = ttk.Entry(row, textvariable=value_var)
        
        value_widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
        remove_btn = ttk.Button(row, text="Entfernen", style="Tool.TButton", command=lambda: self._remove_tag_row(row))
        remove_btn.pack(side=tk.LEFT, padx=(8, 0))

        ThemedTooltip(key_entry, doc_text)
        ThemedTooltip(value_widget, doc_text)
        ThemedTooltip(remove_btn, "Entfernt diesen Tag-Eintrag aus der Konfiguration.")

        self.tag_rows.append({
            "frame": row,
            "key_var": key_var,
            "value_var": value_var,
            "section": section_name,
        })

    def _remove_tag_row(self, row):
        self.tag_rows = [item for item in self.tag_rows if item["frame"] is not row]
        row.destroy()

    def _build_scalar_section(self, parent, section_name):
        section_schema = self.schema[section_name]
        meta = section_schema.get("__meta__", {})
        frame = ttk.LabelFrame(
            parent,
            text=meta.get("label", section_name),
            style="Section.TLabelframe",
        )
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        doc_label = tk.Label(frame, text="?", bg="#d6eaf8", fg="#1f618d", width=2, cursor="question_arrow")
        doc_label.place(relx=1.0, x=-20, y=-1, anchor="ne")
        ThemedTooltip(doc_label, meta.get("doc", ""))

        self.field_vars[section_name] = {}
        current_section = self.config_data.get(section_name, {})

        row_index = 0
        for key, spec in section_schema.items():
            if key == "__meta__":
                continue

            label = tk.Label(body, text=spec.get("label", key), bg=COLORS["app_bg"], fg=COLORS["heading"], anchor="w", width=32)
            label.grid(row=row_index, column=0, sticky="w", padx=(0, 12), pady=4)
            ThemedTooltip(label, spec.get("doc", ""))

            value = current_section.get(key, spec.get("default"))
            field_type = spec.get("type", self._infer_type(value))
            if field_type == "bool":
                var = tk.StringVar(value="true" if value else "false")
                widget = ttk.Combobox(body, textvariable=var, values=["true", "false"], state="readonly", width=12)
            elif field_type in {"int", "float"}:
                var = tk.StringVar(value="" if value is None else str(value))
                widget = ttk.Entry(body, textvariable=var, width=18)
            else:
                var = tk.StringVar(value="" if value is None else str(value))
                widget = ttk.Entry(body, textvariable=var, width=50)

            widget.grid(row=row_index, column=1, sticky="ew", pady=4)
            ThemedTooltip(widget, spec.get("doc", ""))
            self.field_vars[section_name][key] = {"var": var, "type": field_type}
            row_index += 1

        body.grid_columnconfigure(1, weight=1)

    def _infer_type(self, value):
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int) and not isinstance(value, bool):
            return "int"
        if isinstance(value, float):
            return "float"
        return "string"

    def _collect_dirty_snapshot(self):
        snapshot = {
            "tags": [
                {
                    "key": row["key_var"].get(),
                    "value": row["value_var"].get(),
                }
                for row in self.tag_rows
            ],
            "sections": {},
        }
        for section_name, fields in self.field_vars.items():
            section_snapshot = {}
            for key, payload in fields.items():
                section_snapshot[key] = payload["var"].get()
            snapshot["sections"][section_name] = section_snapshot
        return snapshot

    def _capture_initial_dirty_snapshot(self):
        initial_snapshot = self._collect_dirty_snapshot()
        self._dirty_controller.capture_initial(initial_snapshot)

    def _refresh_dirty_state(self):
        current_snapshot = self._collect_dirty_snapshot()
        self._dirty_controller.refresh(current_snapshot)

    def _start_dirty_watch(self):
        self._dirty_controller.start_polling(self._collect_dirty_snapshot, interval_ms=350)

    def _stop_dirty_watch(self):
        self._dirty_controller.stop_polling()

    def _request_close(self):
        self._refresh_dirty_state()
        if self._dirty_controller.is_dirty:
            proceed = confirm_discard_changes(
                self,
                "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen.\n\nFenster wirklich schließen und Änderungen verwerfen?",
            )
            if not proceed:
                return
        self._stop_dirty_watch()
        self.destroy()

    def _collect_config(self):
        config = {}

        tags = {}
        seen_keys = set()
        for row in self.tag_rows:
            key = row["key_var"].get().strip()
            value = row["value_var"].get().strip()
            if not key:
                continue
            if key in seen_keys:
                raise ValueError(f"Doppelter Tag-Key: {key}")
            seen_keys.add(key)
            tags[key] = value
        config["tags"] = tags

        for section_name, fields in self.field_vars.items():
            section_data = {}
            for key, payload in fields.items():
                raw_value = payload["var"].get()
                if payload["type"] == "bool":
                    section_data[key] = raw_value == "true"
                elif payload["type"] == "int":
                    section_data[key] = int(raw_value)
                elif payload["type"] == "float":
                    section_data[key] = float(raw_value)
                else:
                    section_data[key] = raw_value
            config[section_name] = section_data

        return config

    def _save(self):
        try:
            config = self._collect_config()
            self.config_path.write_text(self._render_toml(config), encoding="utf-8")
            if self.on_save:
                self.on_save(config)
            messagebox.showinfo("Gespeichert", "Sanitizer-Konfiguration wurde gespeichert.")
            self._capture_initial_dirty_snapshot()
            self._stop_dirty_watch()
            self.destroy()
        except (OSError, ValueError) as err:
            messagebox.showerror("Fehler", f"Konnte Konfiguration nicht speichern:\n{err}")

    def _render_toml(self, config):
        """
        Rendert eine TOML-Datei, wobei Originalkommentare aus der geparsten Datei bewahrt werden.
        Dies ist die dateigetriebene Speicher-Logik für Priorität 4.
        Der __config Abschnitt wird am Ende bewahrt.
        """
        lines = ["# Sanitizer-Konfiguration für Quarto/Pandoc -> Typst Pipeline", ""]
        section_names = list(self.schema.keys())
        for section_name in config.keys():
            if section_name not in section_names and section_name != "__config":
                section_names.append(section_name)

        for idx, section_name in enumerate(section_names):
            # Überspringe __config und alle seine Sub-Sections
            if section_name == "__config" or section_name.startswith("__config."):
                continue

            section_data = config.get(section_name, {})
            parsed_section = self.config_parsed.get(section_name, {})
            section_schema = self.schema.get(section_name, {})
            meta = section_schema.get("__meta__", {})

            # Sektions-Kommentare aus dem Original bewahren
            section_meta = parsed_section.get("__meta__", {})
            comments_before = section_meta.get("comments_before", [])
            if comments_before:
                for line in comments_before:
                    lines.append(f"# {line}")
            elif meta.get("doc"):
                # Fallback zu dem doc aus dem Schema
                for line in meta["doc"].splitlines():
                    lines.append(f"# {line}")

            lines.append(f"[{section_name}]")

            # Bestimme die Reihenfolge der Keys
            ordered_keys = [key for key in section_schema.keys() if key != "__meta__"]
            for key in section_data.keys():
                if key not in ordered_keys:
                    ordered_keys.append(key)

            for key in ordered_keys:
                if key not in section_data:
                    continue

                # Originalkommentare aus der geparsten Datei
                parsed_key_spec = parsed_section.get(key, {})
                key_comments_before = parsed_key_spec.get("comments_before", [])

                if key_comments_before:
                    for line in key_comments_before:
                        lines.append(f"# {line}")
                else:
                    # Fallback zu dem doc aus dem Schema
                    spec = section_schema.get(key, {})
                    doc = spec.get("doc")
                    if doc:
                        for line in doc.splitlines():
                            lines.append(f"# {line}")

                lines.append(f"{key} = {self._to_toml_value(section_data[key])}")

            if idx < len([s for s in section_names if s != "__config"]) - 1:
                lines.append("")

        # Anhängen von __config am Ende
        # __config hat nested structure, daher nutzen wir tomllib direkter Struktur
        if self.config_path.exists() and tomllib is not None:
            try:
                with open(self.config_path, "rb") as f:
                    full_toml = tomllib.load(f)
                config_section = full_toml.get("__config", {})
                
                if config_section:
                    lines.append("")
                    lines.append("[__config]")
                    lines.append("# Konfiguration für UI-Constraints und Enums")
                    lines.append("# Format: [__config.section.key] mit 'enum' Liste für Dropdown-Werte")
                    
                    # Iteriere über subsections (tags, features, etc.)
                    for subsection_name in sorted(config_section.keys()):
                        subsection_dict = config_section[subsection_name]
                        if not isinstance(subsection_dict, dict):
                            continue
                        
                        # Iteriere über keys in Subsection (C, Q, A, etc.)
                        for key_name in sorted(subsection_dict.keys()):
                            key_dict = subsection_dict[key_name]
                            if not isinstance(key_dict, dict):
                                continue
                            
                            # Render [__config.subsection.key]
                            lines.append(f"[__config.{subsection_name}.{key_name}]")
                            
                            # Render Keys in dieser subsection (enum = [...])
                            for enum_key in sorted(key_dict.keys()):
                                enum_value = key_dict[enum_key]
                                lines.append(f"{enum_key} = {self._to_toml_value(enum_value)}")
            except Exception:
                pass

        lines.append("")
        return "\n".join(lines)

    def _to_toml_value(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, list):
            # Render as TOML array
            items = [f'"{item}"' if isinstance(item, str) else str(item) for item in value]
            return "[" + ", ".join(items) + "]"
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

```


======================================================================
📁 FILE: search_filter.py
======================================================================

```py
def normalize_search_term(value):
    return str(value or "").strip().lower()


def matches_title_path(search_term, title, path):
    if not search_term:
        return True
    title_text = str(title or "").lower()
    path_text = str(path or "").lower()
    return (search_term in title_text) or (search_term in path_text)


def matches_tree_node(
    search_term,
    node_text,
    path_text,
    raw_title,
    content_text,
    is_fulltext,
):
    if not search_term:
        return True

    node_text = str(node_text or "").lower()
    path_text = str(path_text or "").lower()
    raw_title = str(raw_title or "").lower()
    content_text = str(content_text or "").lower()

    if is_fulltext:
        return (
            (search_term in raw_title)
            or (search_term in path_text)
            or (search_term in content_text)
        )

    return (search_term in node_text) or (search_term in path_text)


def should_include_available_item(
    search_term,
    apply_left_search,
    is_fulltext,
    title,
    path,
    content_text,
):
    if not apply_left_search or not search_term:
        return True

    if is_fulltext:
        return (
            matches_title_path(search_term, title, path)
            or (search_term in str(content_text or "").lower())
        )

    return matches_title_path(search_term, title, path)

```


======================================================================
📁 FILE: session_manager.py
======================================================================

```py
import json
import tkinter as tk


class SessionManager:
    """Manages session state: persisting and restoring book, profile, UI, and filter state."""

    def __init__(self, studio):
        self.studio = studio

    # =========================================================================
    # LOAD / SAVE
    # =========================================================================
    def load(self) -> dict:
        try:
            cfg = self.studio.read_config()
            state = cfg.get("session_state", {})
            return state if isinstance(state, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def book_key(self, book_path) -> str:
        root_path = getattr(self.studio, "projects_root_path", self.studio.base_path)
        try:
            return str(book_path.relative_to(root_path))
        except ValueError:
            return book_path.name

    def save(self):
        try:
            cfg = self.studio.read_config()
            studio = self.studio
            active_book_path = None
            active_book_name = None
            if studio.current_book:
                active_book_path = self.book_key(studio.current_book)
                active_book_name = studio.current_book.name
            cfg["session_state"] = {
                "active_book_path": active_book_path,
                "active_book_name": active_book_name,
                "current_profile_name": studio.current_profile_name,
                "export_options": dict(studio.last_export_options),
                "ui_state": self._collect_ui_state(),
            }
            studio.write_config(cfg)
        except (OSError, TypeError, ValueError):
            pass

    # =========================================================================
    # UI STATE COLLECTION
    # =========================================================================
    def _collect_ui_state(self) -> dict:
        studio = self.studio
        if not hasattr(studio, "search_var") or not hasattr(studio, "tree_book"):
            return {}
        return {
            "search_text": studio.search_var.get(),
            "search_scope": studio.search_scope_var.get() if hasattr(studio, "search_scope_var") else "Links",
            "search_mode": studio.search_mode_var.get() if hasattr(studio, "search_mode_var") else "Titel/Pfad",
            "file_state_filter": studio.file_state_filter_var.get() if hasattr(studio, "file_state_filter_var") else "Alle",
            "status_filter": studio.status_filter_var.get() if hasattr(studio, "status_filter_var") else "Alle",
            "log_filter": studio.log_filter_var.get(),
            "log_auto_clear": bool(studio.log_auto_clear_var.get()),
            "log_max_lines": studio.log_max_lines_var.get(),
            "avail_selected_paths": self._get_selected_paths(studio.list_avail),
            "tree_selected_paths": self._get_selected_paths(studio.tree_book),
            "avail_yview": list(studio.list_avail.yview()),
            "tree_yview": list(studio.tree_book.yview()),
        }

    def _get_selected_paths(self, tree_widget) -> list:
        selected = []
        for item_id in tree_widget.selection():
            vals = tree_widget.item(item_id, "values")
            if vals:
                selected.append(vals[0])
        return selected

    # =========================================================================
    # TREE NAVIGATION HELPERS
    # =========================================================================
    def find_tree_node(self, path, parent=""):
        tree = self.studio.tree_book
        for node in tree.get_children(parent):
            vals = tree.item(node, "values")
            if vals and vals[0] == path:
                return node
            found = self.find_tree_node(path, node)
            if found:
                return found
        return None

    def find_avail_node(self, path):
        avail = self.studio.list_avail
        for node in avail.get_children(""):
            vals = avail.item(node, "values")
            if vals and vals[0] == path:
                return node
        return None

    # =========================================================================
    # UI STATE RESTORE
    # =========================================================================
    def restore_ui(self, ui_state: dict):
        if not isinstance(ui_state, dict):
            return
        studio = self.studio

        search_scope = ui_state.get("search_scope", "Links")
        if hasattr(studio, "search_scope_var") and search_scope in {"Links", "Rechts", "Beide"}:
            studio.search_scope_var.set(search_scope)

        search_mode = ui_state.get("search_mode", "Titel/Pfad")
        if hasattr(studio, "search_mode_var") and search_mode in {"Titel/Pfad", "Volltext"}:
            studio.search_mode_var.set(search_mode)

        if hasattr(studio, "search_var"):
            studio.search_var.set(ui_state.get("search_text", ""))

        file_state_filter = ui_state.get("file_state_filter", "Alle")
        if file_state_filter == "Typst-Seitenumbruch (Dateiende)":
            file_state_filter = "PDF-Seitenumbruch am Dateiende"
        elif file_state_filter == "Beides":
            file_state_filter = "Alle"
        if hasattr(studio, "file_state_filter_box"):
            valid = set(studio.file_state_filter_box.cget("values"))
            studio.file_state_filter_var.set(file_state_filter if file_state_filter in valid else "Alle")

        status_filter = ui_state.get("status_filter", "Alle")
        if hasattr(studio, "status_combo"):
            valid = set(studio.status_combo.cget("values"))
            studio.status_filter_var.set(status_filter if status_filter in valid else "Alle")

        log_filter = ui_state.get("log_filter", "Alle")
        studio.log_filter_var.set(log_filter if log_filter in studio.log_filter_labels else "Alle")
        studio.log_auto_clear_var.set(bool(ui_state.get("log_auto_clear", False)))
        log_max_lines = str(ui_state.get("log_max_lines", "500"))
        studio.log_max_lines_var.set(log_max_lines if log_max_lines.isdigit() else "500")

        studio.on_title_search_change()
        studio.apply_status_filter()
        studio.refresh_log_view()

        studio.list_avail.selection_set(())
        studio.tree_book.selection_set(())

        for path in ui_state.get("avail_selected_paths", []):
            node = self.find_avail_node(path)
            if node:
                studio.list_avail.selection_add(node)

        for path in ui_state.get("tree_selected_paths", []):
            node = self.find_tree_node(path)
            if node:
                studio.tree_book.selection_add(node)

        avail_yview = ui_state.get("avail_yview")
        if isinstance(avail_yview, list) and avail_yview:
            try:
                studio.list_avail.yview_moveto(float(avail_yview[0]))
            except (TypeError, ValueError, tk.TclError):
                pass

        tree_yview = ui_state.get("tree_yview")
        if isinstance(tree_yview, list) and tree_yview:
            try:
                studio.tree_book.yview_moveto(float(tree_yview[0]))
            except (TypeError, ValueError, tk.TclError):
                pass

        if not tree_yview:
            sel = studio.tree_book.selection()
            if sel:
                studio.tree_book.see(sel[0])

        if not avail_yview:
            sel = studio.list_avail.selection()
            if sel:
                studio.list_avail.see(sel[0])

    # =========================================================================
    # FULL SESSION RESTORE
    # =========================================================================
    def restore(self):
        studio = self.studio
        studio.is_restoring_session = True
        session_state = studio.restored_session_state or {}

        target_index = 0
        target_book_path = session_state.get("active_book_path")
        target_book_name = session_state.get("active_book_name")

        for idx, book in enumerate(studio.books):
            if target_book_path and self.book_key(book) == target_book_path:
                target_index = idx
                break
            if target_book_name and book.name == target_book_name:
                target_index = idx
                break

        studio.book_combo.current(target_index)
        studio.load_book(None)

        export_options = session_state.get("export_options", {})
        if isinstance(export_options, dict):
            studio.last_export_options.update(export_options)

        profile_name = session_state.get("current_profile_name")
        if profile_name and studio.current_book:
            profile_path = studio.current_book / "bookconfig" / f"{profile_name}.json"
            if profile_path.exists():
                studio.load_profile_from_file(profile_path, show_message=False, track_undo=False)

        self.restore_ui(session_state.get("ui_state", {}))

        studio.is_restoring_session = False
        self.save()

```


======================================================================
📁 FILE: smoke_tests.py
======================================================================

```py
from __future__ import annotations

import argparse
import importlib
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path


def _ok(message: str):
    print(f"✅ {message}")


def _fail(message: str):
    print(f"❌ {message}")


def run_non_gui_smoke(project_root: Path) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, passed: bool, detail: str = ""):
        results.append((name, passed, detail))

    critical_files = [
        project_root / "version.txt",
        project_root / "studio_config.json",
        project_root / "book_studio.py",
        project_root / "yaml_engine.py",
    ]
    missing = [str(p.relative_to(project_root)) for p in critical_files if not p.exists()]
    if missing:
        record("Dateien vorhanden", False, f"Fehlen: {', '.join(missing)}")
    else:
        record("Dateien vorhanden", True)

    modules = [
        "yaml_engine",
        "search_filter",
        "markdown_asset_scanner",
        "dialog_dirty_utils",
        "unmanned_trigger",
    ]
    import_errors = []
    for module_name in modules:
        try:
            importlib.import_module(module_name)
        except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:  # Smoke: nur Importstabilität
            import_errors.append(f"{module_name}: {exc}")

    if import_errors:
        record("Modul-Imports", False, " | ".join(import_errors))
    else:
        record("Modul-Imports", True)

    try:
        from yaml_engine import QuartoYamlEngine

        book_path = project_root / "Band_Dummy"
        engine = QuartoYamlEngine(book_path)
        registry = engine.build_title_registry()
        if not isinstance(registry, dict):
            raise TypeError("build_title_registry() liefert kein dict")
        status_registry = engine.build_status_registry()
        if not isinstance(status_registry, dict):
            raise TypeError("build_status_registry() liefert kein dict")
        record("YAML-Engine Kernpfade", True)
    except (OSError, RuntimeError, TypeError, ValueError, ImportError, AttributeError) as exc:
        record("YAML-Engine Kernpfade", False, str(exc))

    try:
        from book_doctor import BookDoctor

        book_path = project_root / "Band_Dummy"
        doctor = BookDoctor(book_path, {})
        healthy, report = doctor.check_health([], 0)
        if not isinstance(healthy, bool) or not isinstance(report, str):
            raise TypeError("BookDoctor.check_health() Rückgabetyp unerwartet")
        record("Book-Doctor Basislauf", True)
    except (OSError, RuntimeError, TypeError, ValueError, ImportError, AttributeError) as exc:
        record("Book-Doctor Basislauf", False, str(exc))

    try:
        from dialog_dirty_utils import DirtyStateController

        class FakeWindow:
            def __init__(self):
                self.current_title = ""

            def title(self, text: str):
                self.current_title = text

            def after(self, *_args, **_kwargs):
                return 1

            def after_cancel(self, *_args, **_kwargs):
                return None

        fake = FakeWindow()
        controller = DirtyStateController(fake, "Test")
        controller.capture_initial({"a": 1})
        controller.refresh({"a": 1})
        if controller.is_dirty:
            raise AssertionError("Controller sollte clean sein")
        controller.refresh({"a": 2})
        if not controller.is_dirty:
            raise AssertionError("Controller sollte dirty sein")
        if fake.current_title != "Test *":
            raise AssertionError("Titel-Marker fehlt")
        record("DirtyStateController Kernlogik", True)
    except (RuntimeError, TypeError, ValueError, ImportError, AttributeError) as exc:
        record("DirtyStateController Kernlogik", False, str(exc))

    try:
        from yaml_engine import QuartoYamlEngine

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            md = tmp_root / "sample.md"
            md.write_text("# Hallo", encoding="utf-8")
            engine = QuartoYamlEngine(tmp_root)
            changed = engine.ensure_required_frontmatter(md, fallback_title="Hallo")
            content = md.read_text(encoding="utf-8")
            if not changed and "title:" not in content:
                raise AssertionError("Frontmatter wurde nicht ergänzt")
            if "description:" not in content:
                raise AssertionError("description fehlt nach Ergänzung")
        record("Frontmatter-Ergänzung", True)
    except (OSError, RuntimeError, TypeError, ValueError, ImportError, AttributeError) as exc:
        record("Frontmatter-Ergänzung", False, str(exc))

    try:
        source_book = project_root / "Band_Dummy"
        if not source_book.exists():
            raise FileNotFoundError("Band_Dummy fehlt")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            book_copy = tmp_root / "Band_Dummy"
            shutil.copytree(source_book, book_copy)

            render_proc = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "quarto_render_safe.py"),
                    str(book_copy),
                    "--to",
                    "typst",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if render_proc.returncode != 0:
                detail = (render_proc.stderr or render_proc.stdout or "Render fehlgeschlagen").strip()
                raise RuntimeError(detail)

        record("Buch-Generierung (Quarto Render)", True)
    except (FileNotFoundError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        record("Buch-Generierung (Quarto Render)", False, str(exc))

    return results


def run_gui_smoke(project_root: Path) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, passed: bool, detail: str = ""):
        results.append((name, passed, detail))

    try:
        root = tk.Tk()
        root.withdraw()
    except (RuntimeError, TypeError, OSError, tk.TclError) as exc:
        return [("GUI-Initialisierung", False, str(exc))]

    try:
        from export_dialog import ExportDialog

        dialog = ExportDialog(root, templates=["Standard"], initial={"format": "typst", "template": "Standard", "footnote_mode": "endnotes"})
        dialog.update_idletasks()
        dialog.destroy()
        record("ExportDialog öffnet", True)
    except (RuntimeError, TypeError, OSError, ImportError, AttributeError, tk.TclError) as exc:
        record("ExportDialog öffnet", False, str(exc))

    try:
        from quarto_config_editor import QuartoConfigEditor

        yaml_path = project_root / "Band_Dummy" / "_quarto.yml"
        dialog = QuartoConfigEditor(root, yaml_path=yaml_path)
        dialog.update_idletasks()
        dialog.destroy()
        record("QuartoConfigEditor öffnet", True)
    except (RuntimeError, TypeError, OSError, ImportError, AttributeError, tk.TclError) as exc:
        record("QuartoConfigEditor öffnet", False, str(exc))

    try:
        from sanitizer_config_editor import SanitizerConfigEditor

        config_path = project_root / "sanitizer_config.toml"
        dialog = SanitizerConfigEditor(root, config_path=config_path)
        dialog.update_idletasks()
        dialog.destroy()
        record("SanitizerConfigEditor öffnet", True)
    except (RuntimeError, TypeError, OSError, ImportError, AttributeError, tk.TclError) as exc:
        record("SanitizerConfigEditor öffnet", False, str(exc))

    try:
        from app_config_editor import AppConfigEditor

        config_path = project_root / "studio_config.json"
        dialog = AppConfigEditor(root, config_path=config_path)
        dialog.update_idletasks()
        dialog.destroy()
        record("AppConfigEditor öffnet", True)
    except (RuntimeError, TypeError, OSError, ImportError, AttributeError, tk.TclError) as exc:
        record("AppConfigEditor öffnet", False, str(exc))

    root.destroy()
    return results


def print_summary(results: list[tuple[str, bool, str]]) -> int:
    failed = 0
    for name, passed, detail in results:
        if passed:
            _ok(name)
        else:
            failed += 1
            _fail(f"{name}: {detail}")

    total = len(results)
    print("-" * 60)
    print(f"Smoke-Tests: {total - failed}/{total} erfolgreich")
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-Tests für Book Studio")
    parser.add_argument("--gui", action="store_true", help="zusätzliche GUI-Dialog-Smoke-Tests ausführen")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    results = run_non_gui_smoke(project_root)
    if args.gui:
        results.extend(run_gui_smoke(project_root))

    failed = print_summary(results)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

```


======================================================================
📁 FILE: studio_config.json
======================================================================

```json
{
    "help_manual_path": "doc/handbuch.md",
    "reset_quarto_template_path": "templates/quarto_reset_minimal.yml",
    "content_root_path": ".",
    "prep_sources": [],
    "prep_dest_folder": "",
    "indexer_target_folder": "",
    "abort_on_first_preflight_error": false,
    "abort_on_first_render_colon_warning": false,
    "enable_footnote_backlinks": false,
    "default_export_format": "typst",
    "default_export_template": "EXT: typstdoc",
    "default_footnote_mode": "footnotes",
    "frontmatter_requirements": {
        "title": "<filename>",
        "description": "<title>",
        "status": "bookstudio"
    },
    "frontmatter_update_mode": "append_only",
    "sanitizer_backup_path": "C:/Users/Daniel/Documents/Python/IFJN/Sanitizer_Backups",
    "editor_end_commands": [
        {
            "id": "pdf_pagebreak_end",
            "label": "PDF-Seitenumbruch am Dateiende",
            "append_text": "```{=typst}\n#pagebreak()\n```\n",
            "detect_pattern": "```\\{=typst\\}\\s*#pagebreak(?:\\([^\\)]*\\))?\\s*```\\s*\\Z",
            "marks_state": "pdf_pagebreak_end"
        },
        {
            "id": "pdf_pagebreak_end_weak",
            "label": "Schwacher PDF-Seitenumbruch am Dateiende",
            "append_text": "```{=typst}\n#pagebreak(weak: true)\n```\n",
            "detect_pattern": "```\\{=typst\\}\\s*#pagebreak\\(weak:\\s*true\\)\\s*```\\s*\\Z",
            "marks_state": "pdf_pagebreak_end"
        }
    ],
    "window_geometry": "1536x773+0+0",
    "log_font_size": 12,
    "log_auto_clear_default": false,
    "log_max_lines_default": 500,
    "session_state": {
        "active_book_path": "Band_Stoffwechselgesundheit",
        "active_book_name": "Band_Stoffwechselgesundheit",
        "current_profile_name": "Required_Test",
        "export_options": {
            "format": "typst",
            "template": "EXT: typstdoc",
            "footnote_mode": "footnotes"
        },
        "ui_state": {
            "search_text": "",
            "search_scope": "Rechts",
            "search_mode": "Volltext",
            "file_state_filter": "Alle",
            "status_filter": "Alle",
            "log_filter": "Alle",
            "log_auto_clear": false,
            "log_max_lines": "500",
            "avail_selected_paths": [],
            "tree_selected_paths": [
                "content/required/Widmung.md"
            ],
            "avail_yview": [
                0.0,
                0.12
            ],
            "tree_yview": [
                0.2,
                1.0
            ]
        }
    }
}
```


======================================================================
📁 FILE: template_manager.py
======================================================================

```py
from pathlib import Path

class TemplateManager:
    @staticmethod
    def discover_templates(book_path):
        """Scannt nach lokalen Dateien im 'templates' Ordner UND nach Quarto-Extensions."""
        if not book_path:
            return ["Standard"]
            
        book_path = Path(book_path)
        templates = ["Standard"]
        
        # 1. Lokale Dateien (.typ, .tex)
        tpl_dir = book_path / "templates"
        if tpl_dir.exists():
            found = [f.name for f in tpl_dir.glob("*.*") if f.suffix in [".typ", ".tex"]]
            templates.extend(sorted(found))
            
        # 2. Quarto Extensions scannen
        ext_dir = book_path / "_extensions"
        if ext_dir.exists():
            for ext_file in ext_dir.rglob("_extension.yml"):
                # Der Name der Extension ist immer der Name des Ordners!
                ext_name = ext_file.parent.name
                templates.append(f"EXT: {ext_name}")
                
        return templates
```


======================================================================
📁 FILE: templates/quarto_reset_minimal.yml
======================================================================

```yaml
project:
  type: book
  output-dir: export/_book

book:
  title: "{{BOOK_TITLE}}"
  chapters:
    - index.md

format:
  typst:
    keep-typ: true
    toc: true
    toc-depth: 3
    number-sections: true
    section-numbering: 1.1.1
    papersize: a4
  html:
    theme: cosmo
    toc: true

```


======================================================================
📁 FILE: test.py
======================================================================

```py
# eine funktion, die primzahlen findet
def find_primes(n):
    primes = []
    for num in range(2, n + 1):
        is_prime = True
        for divisor in range(2, int(num**0.5) + 1):
            if num % divisor == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(num)
    return primes
```


======================================================================
📁 FILE: tests/test_book_doctor_regression.py
======================================================================

```py
from __future__ import annotations

from pathlib import Path

from book_doctor import BookDoctor


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _valid_markdown(title: str, description: str | None = None) -> str:
    description = description if description is not None else title
    return (
        "---\n"
        f'title: "{title}"\n'
        f'description: "{description}"\n'
        "---\n\n"
        f"# {title}\n"
    )


def test_check_health_rejects_missing_index_and_ghost_files(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()

    doctor = BookDoctor(book, {"content/missing.md": "Kapitel"})

    healthy, report = doctor.check_health(["content/missing.md"], 0)

    assert healthy is False
    assert "index.md' fehlt komplett" in report
    assert "Geister-Datei" in report


def test_check_health_flags_missing_required_frontmatter_fields(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(book / "content" / "chapter.md", "---\ntitle: \"Kapitel\"\n---\n\nText\n")

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    healthy, report = doctor.check_health(["content/chapter.md"], 0)

    assert healthy is False
    assert "FEHLENDES FELD" in report
    assert "description" in report


def test_check_health_accepts_valid_minimal_project(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(book / "content" / "chapter.md", _valid_markdown("Kapitel"))

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    healthy, report = doctor.check_health(["content/chapter.md"], 0)

    assert healthy is True
    assert "perfektem Zustand" in report


def test_analyze_health_returns_issue_paths_for_gui_markers(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(book / "content" / "chapter.md", "---\ntitle: \"Kapitel\"\n---\n\nText\n")

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 2)

    assert analysis["is_healthy"] is False
    assert "content/chapter.md" in analysis["issues_by_path"]
    assert any("description" in message for message in analysis["issues_by_path"]["content/chapter.md"])
    assert analysis["issue_first_line_by_path"]["content/chapter.md"] == 1
    assert analysis["warning_count"] == 1


def test_analyze_health_reports_hidden_separator_body_line(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(
        book / "content" / "chapter.md",
        "---\ntitle: \"Kapitel\"\ndescription: \"Kapitel\"\n---\n\nAbsatz\n---\nMehr Text\n",
    )

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is False
    assert analysis["issue_first_line_by_path"]["content/chapter.md"] == 7
    assert analysis["issue_details_by_path"]["content/chapter.md"][0]["line_number"] == 7


def test_analyze_health_single_file_mode_skips_index_requirement(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "content" / "chapter.md", _valid_markdown("Kapitel"))

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0, include_index=False)

    assert analysis["is_healthy"] is True
    assert "index.md" not in analysis["issues_by_path"]


def test_analyze_health_flags_unclosed_fenced_div_with_line_number(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(
        book / "content" / "chapter.md",
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text davor\n"
        "::: {.callout-note}\n"
        "Inhalt\n",
    )

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is False
    messages = analysis["issues_by_path"]["content/chapter.md"]
    assert any("FENCED-DIV FEHLER" in message for message in messages)
    assert analysis["issue_first_line_by_path"]["content/chapter.md"] == 7


def test_analyze_health_accepts_balanced_fenced_div(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(
        book / "content" / "chapter.md",
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text davor\n"
        "::: {.callout-note}\n"
        "Inhalt\n"
        ":::\n",
    )

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is True
    assert "content/chapter.md" not in analysis["issues_by_path"]


def test_analyze_health_ignores_colons_inside_code_fence_but_flags_real_unclosed_div(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _write(book / "index.md", _valid_markdown("Index"))
    _write(
        book / "content" / "chapter.md",
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "```md\n"
        "::: nur beispiel im codeblock\n"
        "```\n\n"
        "::: {.callout-note}\n"
        "Defekter Block ohne Abschluss\n",
    )

    doctor = BookDoctor(book, {"content/chapter.md": "Kapitel"})

    analysis = doctor.analyze_health(["content/chapter.md"], 0)

    assert analysis["is_healthy"] is False
    messages = analysis["issues_by_path"]["content/chapter.md"]
    assert any("FENCED-DIV FEHLER" in message for message in messages)
    assert not any("WARNZEICHEN" in message for message in messages)
```


======================================================================
📁 FILE: tests/test_export_manager_regression.py
======================================================================

```py
from __future__ import annotations

from pathlib import Path

import export_manager
from export_manager import ExportManager


class _FakeStatus:
    def __init__(self):
        self.last = None

    def config(self, **kwargs):
        self.last = kwargs


class _FakeStudio:
    def __init__(self):
        self.current_book = object()
        self.root = object()
        self.available_templates = ["Standard"]
        self.last_export_options = {}
        self.status = _FakeStatus()
        self.logged = []
        self.preflight_calls = []
        self.save_calls = []

    def run_doctor_preflight(self, context_label, emit_success_log=False):
        self.preflight_calls.append((context_label, emit_success_log))
        return False, {"error_count": 1}

    def log(self, message, level="info"):
        self.logged.append((message, level))

    def persist_app_state(self):
        raise AssertionError("persist_app_state should not be called when preflight fails")

    def save_project(self, **kwargs):
        self.save_calls.append(kwargs)
        raise AssertionError("save_project should not be called when preflight fails")


def test_run_quarto_render_stops_immediately_on_doctor_preflight_failure() -> None:
    studio = _FakeStudio()
    manager = ExportManager(studio)

    manager.run_quarto_render()

    assert studio.preflight_calls == [("Render-Vorabcheck", False)]
    assert studio.save_calls == []
    assert any("Rendern abgebrochen" in message for message, _level in studio.logged)
    assert studio.status.last == {
        "text": "Render abgebrochen (Buch-Doktor-Befund)",
        "fg": "#e74c3c",
    }


def test_candidate_registry_paths_for_processed_file_maps_to_content(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()

    class Studio:
        current_book = book

    manager = ExportManager(Studio())

    abs_file = book / "processed" / "content" / "required" / "pladoyer.md"
    candidates = manager.candidate_registry_paths_for_error_file(abs_file)

    assert candidates == [
        "processed/content/required/pladoyer.md",
        "content/required/pladoyer.md",
    ]


def test_resolve_error_file_title_prefers_registry_title_for_processed_path(tmp_path: Path) -> None:
    book = tmp_path / "book"
    (book / "processed" / "content" / "required").mkdir(parents=True)
    abs_file = book / "processed" / "content" / "required" / "pladoyer.md"
    abs_file.write_text("# Fallback", encoding="utf-8")

    class Studio:
        current_book = book
        title_registry = {"content/required/pladoyer.md": "Plädoyer Titel"}
        yaml_engine = None

    manager = ExportManager(Studio())

    title, shown_path = manager.resolve_error_file_title(abs_file)

    assert title == "Plädoyer Titel"
    assert shown_path == "content/required/pladoyer.md"


def test_run_quarto_render_logs_affected_title_for_error_line(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    (book / "processed" / "content" / "required").mkdir(parents=True)
    error_file = (book / "processed" / "content" / "required" / "pladoyer.md").resolve()
    error_file.write_text("# Dummy", encoding="utf-8")

    class Root:
        def after(self, _delay, callback):
            callback()

    class Status:
        def __init__(self):
            self.last = None

        def config(self, **kwargs):
            self.last = kwargs

    class YamlEngine:
        def save_chapters(self, *_args, **_kwargs):
            return None

        def extract_title_from_md(self, _path):
            return "Fallback Titel"

    class Studio:
        def __init__(self):
            self.current_book = book
            self.root = Root()
            self.available_templates = ["Standard"]
            self.last_export_options = {}
            self.status = Status()
            self.logged = []
            self.current_profile_name = "default"
            self.yaml_engine = YamlEngine()
            self.title_registry = {"content/required/pladoyer.md": "Plädoyer Titel"}

        def run_doctor_preflight(self, _context_label, emit_success_log=False):
            return True, {"error_count": 0, "emit_success_log": emit_success_log}

        def persist_app_state(self):
            return None

        def save_project(self, **_kwargs):
            return True

        def get_tree_data_for_engine(self):
            return []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    class FakePreProcessor:
        def __init__(self, *_args, **_kwargs):
            self.harvester = type("Harvester", (), {"orphan_warnings": []})()

        def prepare_render_environment(self, tree):
            return tree

    class FakePopen:
        def __init__(self, *_args, **_kwargs):
            self.stdout = [f"ERROR: In file {error_file}\n"]
            self.returncode = 1

        def wait(self):
            return self.returncode

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr(export_manager.ExportDialog, "ask", staticmethod(lambda *_args, **_kwargs: {
        "format": "typst",
        "footnote_mode": "none",
        "template": "Standard",
    }))
    monkeypatch.setattr(export_manager, "PreProcessor", FakePreProcessor)
    monkeypatch.setattr(export_manager.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(export_manager.threading, "Thread", ImmediateThread)

    studio = Studio()
    manager = ExportManager(studio)

    manager.run_quarto_render()

    assert any(
        "Betroffener Titel: Plädoyer Titel [content/required/pladoyer.md]" in message
        and level == "error"
        for message, level in studio.logged
    )


def test_collect_processed_fenced_div_hits_reports_source_file_and_line(tmp_path: Path) -> None:
    book = tmp_path / "book"
    processed_file = book / "processed" / "content" / "required" / "kapitel.md"
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_file.write_text(
        "---\n"
        "title: Kapitel\n"
        "---\n\n"
        "Text\n"
        "::: {.callout-note}\n"
        "Inhalt\n"
        ":::\n",
        encoding="utf-8",
    )

    class Studio:
        current_book = book
        title_registry = {"content/required/kapitel.md": "Kapitel"}

    manager = ExportManager(Studio())

    findings = manager.collect_processed_fenced_div_hits(
        [{"path": "processed/content/required/kapitel.md", "children": []}]
    )

    assert findings == []


def test_collect_processed_fenced_div_hits_flags_unclosed_opening(tmp_path: Path) -> None:
    book = tmp_path / "book"
    processed_file = book / "processed" / "content" / "kapitel.md"
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_file.write_text(
        "Text\n"
        "::: {.callout-note}\n"
        "Inhalt ohne Ende\n",
        encoding="utf-8",
    )

    class Studio:
        current_book = book
        title_registry = {"content/kapitel.md": "Kapitel"}

    manager = ExportManager(Studio())

    findings = manager.collect_processed_fenced_div_hits(
        [{"path": "processed/content/kapitel.md", "children": []}]
    )

    assert len(findings) == 1
    assert findings[0]["source_path"] == "content/kapitel.md"
    assert findings[0]["line_number"] == 2
    assert findings[0]["issue_kind"] == "unclosed-open"


def test_build_processed_label_occurrences_collects_label_locations(tmp_path: Path) -> None:
    book = tmp_path / "book"
    processed_file = book / "processed" / "content" / "chapter.md"
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_file.write_text(
        "Text @AlphaRef[S. 10]\n"
        "Noch ein Verweis @AlphaRef\n"
        "Anderer Verweis @BetaRef\n",
        encoding="utf-8",
    )

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

    manager = ExportManager(Studio())

    occurrences = manager.build_processed_label_occurrences(
        [{"path": "processed/content/chapter.md", "children": []}]
    )

    assert occurrences["AlphaRef"] == [
        ("content/chapter.md", 1),
        ("content/chapter.md", 2),
    ]
    assert occurrences["BetaRef"] == [("content/chapter.md", 3)]


def test_run_quarto_render_aborts_on_first_processed_preflight_error(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    bad_processed = book / "processed" / "content" / "chapter.md"
    bad_processed.parent.mkdir(parents=True, exist_ok=True)
    bad_processed.write_text("::: {.callout-note}\nUnclosed\n", encoding="utf-8")

    class Root:
        def after(self, _delay, callback):
            callback()

    class Status:
        def __init__(self):
            self.last = None

        def config(self, **kwargs):
            self.last = kwargs

    class YamlEngine:
        def save_chapters(self, *_args, **_kwargs):
            return None

    class Studio:
        def __init__(self):
            self.current_book = book
            self.root = Root()
            self.available_templates = ["Standard"]
            self.last_export_options = {}
            self.status = Status()
            self.logged = []
            self.current_profile_name = "default"
            self.yaml_engine = YamlEngine()
            self.title_registry = {"content/chapter.md": "Chapter"}

        def run_doctor_preflight(self, _context_label, emit_success_log=False):
            return True, {"error_count": 0, "emit_success_log": emit_success_log}

        def persist_app_state(self):
            return None

        def save_project(self, **_kwargs):
            return True

        def get_tree_data_for_engine(self):
            return []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    class FakePreProcessor:
        def __init__(self, *_args, **_kwargs):
            self.harvester = type("Harvester", (), {"orphan_warnings": []})()

        def prepare_render_environment(self, _tree):
            return [{"path": "processed/content/chapter.md", "children": []}]

    class GuardPopen:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("quarto must not start when preflight error exists")

    monkeypatch.setattr(export_manager.ExportDialog, "ask", staticmethod(lambda *_args, **_kwargs: {
        "format": "typst",
        "footnote_mode": "none",
        "template": "Standard",
    }))
    monkeypatch.setattr(export_manager, "PreProcessor", FakePreProcessor)
    monkeypatch.setattr(export_manager.subprocess, "Popen", GuardPopen)

    studio = Studio()
    manager = ExportManager(studio)

    manager.run_quarto_render()

    assert any("defekter ':::'-Block" in message for message, _level in studio.logged)
    assert studio.status.last == {
        "text": "Render abgebrochen (erster Preflight-Fehler)",
        "fg": "#e74c3c",
    }


def test_log_processed_fenced_div_hits_does_not_abort_when_config_disabled(tmp_path: Path) -> None:
    book = tmp_path / "book"
    processed_file = book / "processed" / "content" / "chapter.md"
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_file.write_text(
        "Text\n"
        "::: {.callout-note}\n"
        "Inhalt ohne Ende\n",
        encoding="utf-8",
    )

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

        def __init__(self):
            self.logged = []

        def log(self, message, level="info"):
            self.logged.append((message, level))

        def read_config(self):
            return {"abort_on_first_preflight_error": False}

    studio = Studio()
    manager = ExportManager(studio)

    should_abort = manager.log_processed_fenced_div_hits(
        [{"path": "processed/content/chapter.md", "children": []}]
    )

    assert should_abort is False
    assert any("defekter ':::'-Block" in message for message, _level in studio.logged)


def test_log_render_line_emits_missing_label_hints_for_backtick_format(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

        def __init__(self):
            self.logged = []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    studio = Studio()
    manager = ExportManager(studio)
    manager._processed_label_occurrences = {
        "AlphaRef": [("content/chapter.md", 42)],
    }

    manager._log_render_line("error: label `<AlphaRef>` does not exist in the document")

    assert any("Fehlendes Label <AlphaRef>" in message for message, _level in studio.logged)
    assert any("[content/chapter.md] L42" in message for message, _level in studio.logged)


def test_log_render_line_emits_source_hint_for_raw_valid_colon_warning(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

        def __init__(self):
            self.logged = []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    studio = Studio()
    manager = ExportManager(studio)
    manager._processed_colon_occurrences = [
        ("content/chapter.md", 23),
        ("content/chapter.md", 41),
    ]

    manager._log_render_line("The following string was found in the document: :::")

    assert any("Früher Treffer für ':::': keine strukturellen Defekte erkannt" in message for message, _level in studio.logged)
    assert any("👉 KLICK: [content/chapter.md] L23" in message for message, _level in studio.logged)


def test_log_render_line_emits_source_hint_for_structural_colon_warning(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

        def __init__(self):
            self.logged = []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    studio = Studio()
    manager = ExportManager(studio)
    manager._processed_colon_occurrences = [
        {
            "source_path": "content/chapter.md",
            "line_number": 23,
            "issue_kind": "unclosed-open",
            "is_structural": True,
        }
    ]

    manager._log_render_line("The following string was found in the document: :::")

    assert any("Früher Treffer für ':::': strukturell auffällige Stelle(n):" in message for message, _level in studio.logged)
    assert any("👉 KLICK: [content/chapter.md] L23" in message for message, _level in studio.logged)


def test_should_abort_on_first_render_colon_warning_uses_config_value(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book

        def read_config(self):
            return {"abort_on_first_render_colon_warning": True}

    manager = ExportManager(Studio())

    assert manager.should_abort_on_first_render_colon_warning() is True


def test_should_enable_footnote_backlinks_uses_config_value(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book

        def read_config(self):
            return {"enable_footnote_backlinks": False}

    manager = ExportManager(Studio())

    assert manager.should_enable_footnote_backlinks() is False


def test_is_raw_colon_warning_line_detects_quarto_warning_line() -> None:
    class Studio:
        current_book = None

    manager = ExportManager(Studio())

    assert manager.is_raw_colon_warning_line("The following string was found in the document: :::") is True
    assert manager.is_raw_colon_warning_line("INFO: something else") is False


def test_run_quarto_render_writes_detailed_render_log_file(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    (book / "export").mkdir(parents=True, exist_ok=True)

    class Root:
        def after(self, _delay, callback):
            callback()

    class Status:
        def __init__(self):
            self.last = None

        def config(self, **kwargs):
            self.last = kwargs

    class YamlEngine:
        def save_chapters(self, *_args, **_kwargs):
            return None

    class Studio:
        def __init__(self):
            self.current_book = book
            self.root = Root()
            self.available_templates = ["Standard"]
            self.last_export_options = {}
            self.status = Status()
            self.logged = []
            self.current_profile_name = "default"
            self.yaml_engine = YamlEngine()
            self.title_registry = {}

        def run_doctor_preflight(self, _context_label, emit_success_log=False):
            return True, {"error_count": 0, "emit_success_log": emit_success_log}

        def persist_app_state(self):
            return None

        def save_project(self, **_kwargs):
            return True

        def get_tree_data_for_engine(self):
            return []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    class FakePreProcessor:
        def __init__(self, *_args, **_kwargs):
            self.harvester = type("Harvester", (), {"orphan_warnings": []})()

        def prepare_render_environment(self, tree):
            return tree

    class FakePopen:
        def __init__(self, *_args, **_kwargs):
            self.stdout = ["quarto: render started\n", "quarto: render done\n"]
            self.returncode = 0

        def wait(self):
            return self.returncode

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr(export_manager.ExportDialog, "ask", staticmethod(lambda *_args, **_kwargs: {
        "format": "typst",
        "footnote_mode": "endnotes",
        "template": "Standard",
    }))
    monkeypatch.setattr(export_manager, "PreProcessor", FakePreProcessor)
    monkeypatch.setattr(export_manager.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(export_manager.threading, "Thread", ImmediateThread)

    studio = Studio()
    manager = ExportManager(studio)

    manager.run_quarto_render()

    log_dir = book / "export" / "render_logs"
    log_files = list(log_dir.glob("render_*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text(encoding="utf-8")
    assert "=== Quarto Book Studio Render Log ===" in content
    assert "safe_command=" in content
    assert "quarto: render started" in content
    assert "quarto: render done" in content
    assert "status=success" in content
    assert "primary_returncode=0" in content
```


======================================================================
📁 FILE: tests/test_footnote_harvester_regression.py
======================================================================

```py
from footnote_harvester import FootnoteHarvester


def test_extract_definitions_is_linear_and_preserves_body_text() -> None:
    harvester = FootnoteHarvester(mode="endnotes")
    text = (
        "Einleitung\n"
        "[^a]: Erste Notiz\n"
        "  zweite Zeile\n"
        "\n"
        "Weiterer Text\n"
        "[^b]: Zweite Notiz\n"
        "Schluss\n"
    )

    cleaned = harvester.extract_definitions(text, file_key="content/a.md")

    assert "[^a]:" not in cleaned
    assert "[^b]:" not in cleaned
    assert "Einleitung" in cleaned
    assert "Weiterer Text" in cleaned
    assert "Schluss" in cleaned
    assert harvester.definitions[("content/a.md", "a")] == "Erste Notiz\n  zweite Zeile"
    assert harvester.definitions[("content/a.md", "b")] == "Zweite Notiz"


def test_extract_definitions_accepts_lightly_indented_definition() -> None:
    harvester = FootnoteHarvester(mode="endnotes")
    text = "Text\n [^x]: Leicht eingerückt\nMehr Text\n"

    cleaned = harvester.extract_definitions(text, file_key="content/b.md")

    assert "[^x]:" not in cleaned
    assert "Text" in cleaned
    assert "Mehr Text" in cleaned
    assert harvester.definitions[("content/b.md", "x")] == "Leicht eingerückt"

```


======================================================================
📁 FILE: tests/test_pre_processor_regression.py
======================================================================

```py
from __future__ import annotations

import re
from pathlib import Path

from pre_processor import PreProcessor


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_book(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    book.mkdir(parents=True, exist_ok=True)
    return book


def test_prepare_render_environment_strips_non_numeric_order_from_processed_frontmatter(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "required" / "Literaturverzeichnis.md"
    _write(
        source,
        "---\n"
        "title: \"Quellenverzeichnis\"\n"
        "order: END-50\n"
        "---\n\n"
        "# Quellenverzeichnis\n",
    )

    processor = PreProcessor(book)
    tree_data = [{"title": "Quellenverzeichnis", "path": "content/required/Literaturverzeichnis.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed = (book / "processed" / "content" / "required" / "Literaturverzeichnis.md").read_text(encoding="utf-8")
    original = source.read_text(encoding="utf-8")

    assert "order: END-50" in original
    assert "order:" not in processed
    assert "title: Quellenverzeichnis" in processed


def test_prepare_render_environment_keeps_numeric_order_in_processed_frontmatter(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "required" / "Vorwort.md"
    _write(
        source,
        "---\n"
        "title: \"Vorwort\"\n"
        "order: 5\n"
        "---\n\n"
        "# Vorwort\n",
    )

    processor = PreProcessor(book)
    tree_data = [{"title": "Vorwort", "path": "content/required/Vorwort.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed = (book / "processed" / "content" / "required" / "Vorwort.md").read_text(encoding="utf-8")

    assert "order: 5" in processed


def test_prepare_render_environment_prunes_unused_footnote_definitions_in_footnotes_mode(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text mit Referenz[^used].\n\n"
        "[^used]: Verwendete Notiz.\n"
        "[^unused]: Unbenutzte Notiz.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes")
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")
    original = source.read_text(encoding="utf-8")

    assert "Verwendete Notiz." in processed
    assert "Unbenutzte Notiz." not in processed
    assert "[^unused]:" in original


def test_prepare_render_environment_converts_bracket_citations_with_locators_to_endnotes(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text mit Verweis [@DiamantiKandarakisDunaif2012, S. 331] und [vgl. @NestlerCharney2008].\n\n"
        "[@DiamantiKandarakisDunaif2012, S. 331]: Diamanti-Kandarakis & Dunaif (2012), S. 331.\n"
        "[@NestlerCharney2008]: Nestler (2008), S. 1878.\n",
    )

    processor = PreProcessor(book)
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")
    endnotes = (book / "processed" / "Endnoten.md").read_text(encoding="utf-8")

    assert "@DiamantiKandarakisDunaif2012" not in processed_content
    assert "@NestlerCharney2008" not in processed_content
    # Typst-native forward links (default output_format="typst")
    assert "`#super[#link(<fn-1>)[1]]`{=typst}" in processed_content
    assert "`#super[#link(<fn-2>)[2]]`{=typst}" in processed_content
    assert "Diamanti-Kandarakis & Dunaif" in endnotes
    assert "Nestler (2008)" in endnotes
    # Typst labels for link targets in endnotes chapter
    assert '`#label("fn-1")`{=typst}' in endnotes
    assert '`#label("fn-2")`{=typst}' in endnotes


def test_prepare_render_environment_preserves_regular_footnotes_semantics_in_footnotes_mode(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text mit Fussnote[^local-note].\n\n"
        "[^local-note]: Lokale Fussnote bleibt unveraendert.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes")
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processed_tree = processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")
    original_content = source.read_text(encoding="utf-8")

    assert "Text mit Fussnote" in processed_content
    assert "Lokale Fussnote bleibt unveraendert." in processed_content
    assert "[^local-note]" in original_content
    assert "[^local-note]: Lokale Fussnote bleibt unveraendert." in original_content
    assert not (book / "processed" / "Endnoten.md").exists()
    assert all(item["path"] != "processed/Endnoten.md" for item in processed_tree)


def test_prepare_render_environment_namespaces_duplicate_footnote_labels_in_footnotes_mode(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source_a = book / "content" / "a.md"
    source_b = book / "content" / "b.md"
    _write(
        source_a,
        "---\n"
        "title: \"A\"\n"
        "description: \"A\"\n"
        "---\n\n"
        "Text A[^1].\n\n"
        "[^1]: Fussnote A.\n",
    )
    _write(
        source_b,
        "---\n"
        "title: \"B\"\n"
        "description: \"B\"\n"
        "---\n\n"
        "Text B[^1].\n\n"
        "[^1]: Fussnote B.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes")
    tree_data = [
        {"title": "A", "path": "content/a.md", "children": []},
        {"title": "B", "path": "content/b.md", "children": []},
    ]

    processor.prepare_render_environment(tree_data)

    processed_a = (book / "processed" / "content" / "a.md").read_text(encoding="utf-8")
    processed_b = (book / "processed" / "content" / "b.md").read_text(encoding="utf-8")

    assert "[^1]" not in processed_a
    assert "[^1]" not in processed_b
    assert "Fussnote A." in processed_a
    assert "Fussnote B." in processed_b


def test_prepare_render_environment_adds_footnote_backlink_in_footnotes_mode(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text mit Fussnote[^local-note].\n\n"
        "[^local-note]: Lokale Fussnote.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes")
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")

    assert re.search(r"\[\]\{#fnref-[A-Za-z0-9_-]+-1\}\[\^[^\]]+\]", processed_content)
    assert re.search(r"\[↩\]\(#fnref-[A-Za-z0-9_-]+-1\)", processed_content)


def test_prepare_render_environment_adds_multiple_backlinks_for_reused_footnote(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Erster Verweis[^same-note]. Zweiter Verweis[^same-note].\n\n"
        "[^same-note]: Geteilte Fussnote.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes")
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")

    assert re.search(r"\[↩1\]\(#fnref-[A-Za-z0-9_-]+-1\)", processed_content)
    assert re.search(r"\[↩2\]\(#fnref-[A-Za-z0-9_-]+-2\)", processed_content)


def test_prepare_render_environment_can_disable_footnote_backlinks(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    source = book / "content" / "chapter.md"
    _write(
        source,
        "---\n"
        "title: \"Kapitel\"\n"
        "description: \"Kapitel\"\n"
        "---\n\n"
        "Text mit Fussnote[^local-note].\n\n"
        "[^local-note]: Lokale Fussnote.\n",
    )

    processor = PreProcessor(book, footnote_mode="footnotes", enable_footnote_backlinks=False)
    tree_data = [{"title": "Kapitel", "path": "content/chapter.md", "children": []}]

    processor.prepare_render_environment(tree_data)

    processed_content = (book / "processed" / "content" / "chapter.md").read_text(encoding="utf-8")

    assert "[↩]" not in processed_content
    assert "fnref-" not in processed_content

```


======================================================================
📁 FILE: tests/test_yaml_engine_regression.py
======================================================================

```py
from __future__ import annotations

from pathlib import Path

import yaml

import yaml_engine as yaml_engine_module
from yaml_engine import QuartoYamlEngine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _frontmatter(order: str | None = None, title: str = "Titel") -> str:
    lines = ["---", f'title: "{title}"', f'description: "{title}"']
    if order is not None:
        lines.append(f'order: "{order}"')
    lines.extend(["---", "", f"# {title}"])
    return "\n".join(lines)


def _create_book(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    _write(
        book / "_quarto.yml",
        "project:\n  type: book\nbook:\n  chapters:\n    - index.md\n",
    )
    _write(book / "index.md", _frontmatter(title="Index"))
    return book


def _load_chapters(book: Path):
    config = yaml.safe_load((book / "_quarto.yml").read_text(encoding="utf-8"))
    return config["book"]["chapters"]


def test_save_chapters_keeps_index_first_and_orders_required_files(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    _write(book / "content" / "chapter-1.md", _frontmatter(title="Kapitel 1"))
    _write(book / "content" / "chapter-2.md", _frontmatter(title="Kapitel 2"))
    _write(book / "content" / "required" / "preface.md", _frontmatter(order="1", title="Vorne"))
    _write(book / "content" / "required" / "appendix.md", _frontmatter(order="END-2", title="Hinten"))

    engine = QuartoYamlEngine(book)
    tree_data = [
        {"path": "content\\chapter-1.md", "children": []},
        {
            "path": "PART:Teil A",
            "children": [
                {"path": "content\\required\\appendix.md", "children": []},
                {"path": "content\\chapter-2.md", "children": []},
                {"path": "content\\required\\preface.md", "children": []},
            ],
        },
    ]

    engine.save_chapters(tree_data, save_gui_state=False)

    assert _load_chapters(book) == [
        "index.md",
        "content/required/preface.md",
        "content/chapter-1.md",
        {"part": "Teil A", "chapters": ["content/chapter-2.md"]},
        "content/required/appendix.md",
    ]


def test_parse_chapters_reads_quarto_yaml_when_no_gui_state_exists(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    _write(
        book / "_quarto.yml",
        "project:\n"
        "  type: book\n"
        "book:\n"
        "  chapters:\n"
        "    - index.md\n"
        "    - part: Grundlagen\n"
        "      chapters:\n"
        "        - content/chapter-1.md\n"
        "    - content/chapter-2.md\n",
    )

    engine = QuartoYamlEngine(book)

    assert engine.parse_chapters() == [
        {"path": "index.md", "children": []},
        {
            "path": "PART:Grundlagen",
            "children": [{"path": "content/chapter-1.md", "children": []}],
        },
        {"path": "content/chapter-2.md", "children": []},
    ]


def test_parse_chapters_prefers_saved_gui_state_over_yaml(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    gui_state = [{"path": "content/custom.md", "children": []}]
    _write(book / "bookconfig" / ".gui_state.json", '[{"path": "content/custom.md", "children": []}]')

    engine = QuartoYamlEngine(book)

    assert engine.parse_chapters() == gui_state


def test_ensure_required_frontmatter_append_only_preserves_existing_title_and_body(
    tmp_path: Path, monkeypatch
) -> None:
    book = _create_book(tmp_path)
    article = book / "content" / "sample.md"
    original = "---\ntitle: \"Bestehend\"\ncustom: \"x\"\n---\n\n# Heading\n\nText bleibt.\n"
    _write(article, original)

    config_dir = tmp_path / "config_append"
    _write(
        config_dir / "studio_config.json",
        '{"frontmatter_requirements":{"title":"<filename>","description":"<title>","status":"bookstudio"},"frontmatter_update_mode":"append_only"}',
    )
    monkeypatch.setattr(yaml_engine_module, "__file__", str(config_dir / "module_stub.py"))

    engine = QuartoYamlEngine(book)

    changed = engine.ensure_required_frontmatter(article, fallback_title="Fallback")
    content = article.read_text(encoding="utf-8")

    assert changed is True
    assert 'title: "Bestehend"' in content
    assert 'description: "Bestehend"' in content
    assert 'status: "bookstudio"' in content
    assert 'custom: "x"' in content
    assert content.endswith("# Heading\n\nText bleibt.\n")


def test_ensure_required_frontmatter_reserialize_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    book = _create_book(tmp_path)
    article = book / "content" / "sample.md"
    _write(article, "---\ntitle: Bereits da\n---\n\nInhalt\n")

    config_dir = tmp_path / "config_reserialize"
    _write(
        config_dir / "studio_config.json",
        '{"frontmatter_requirements":{"title":"<filename>","description":"<title>","status":"bookstudio"},"frontmatter_update_mode":"reserialize"}',
    )
    monkeypatch.setattr(yaml_engine_module, "__file__", str(config_dir / "module_stub.py"))

    engine = QuartoYamlEngine(book)

    first_change = engine.ensure_required_frontmatter(article)
    second_change = engine.ensure_required_frontmatter(article)
    content = article.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(content.split("---", 2)[1])

    assert first_change is True
    assert second_change is False
    assert frontmatter == {
        "title": "Bereits da",
        "description": "Bereits da",
        "status": "bookstudio",
    }


def test_build_title_registry_marks_required_outline_with_both_prefix_icons(tmp_path: Path) -> None:
    book = _create_book(tmp_path)
    _write(
        book / "content" / "required" / "gliederungspunkt.md",
        "---\n"
        "title: \"Nur Gliederung\"\n"
        "content_role: \"outline\"\n"
        "---\n\n"
        "# Nur Gliederung\n",
    )

    engine = QuartoYamlEngine(book)

    registry = engine.build_title_registry()

    assert registry["content/required/gliederungspunkt.md"].startswith("📌 🧭 ")
    assert "Nur Gliederung" in registry["content/required/gliederungspunkt.md"]
```


======================================================================
📁 FILE: tools/Book_Preper_Scripter.py
======================================================================

```py
import argparse
import csv
import json
import logging
import os
import re
import shutil
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sammelt Markdown-Dateien aus konfigurierten Quellordnern.")
    parser.add_argument("--config", default="studio_config.json", help="Pfad zur Konfigurationsdatei (Default: studio_config.json)")
    parser.add_argument("--sources", nargs="*", help="Optionale Quellordner-Overrides")
    parser.add_argument("--dest", help="Optionaler Zielordner-Override")
    return parser.parse_args()

def get_frontmatter_title(filepath):
    """Extrahiert den Titel aus dem YAML-Frontmatter."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(2000) 
            match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
            return match.group(1).strip() if match else "Kein Titel gefunden"
    except OSError as e:
        logging.error("Fehler beim Lesen von %s: %s", filepath, e)
        return "Lese-Fehler"


def main() -> int:
    args = _parse_args()
    project_root = _project_root()
    config_path = _resolve_path(args.config, project_root)
    config = _load_config(config_path)

    configured_sources = args.sources if args.sources else config.get("prep_sources", [])
    configured_dest = args.dest if args.dest else config.get("prep_dest_folder", "")

    if not configured_sources:
        print("❌ Keine Merge-Quellpfade konfiguriert. Bitte in Studio-Konfiguration 'prep_sources' setzen.")
        return 2
    if not configured_dest:
        print("❌ Kein Merge-Zielordner konfiguriert. Bitte in Studio-Konfiguration 'prep_dest_folder' setzen.")
        return 2

    sources = [_resolve_path(str(src), project_root) for src in configured_sources if str(src).strip()]
    dest_folder = _resolve_path(str(configured_dest), project_root)

    mapping_csv = dest_folder / "buch_struktur_mapping.csv"
    log_file = dest_folder / "migration.log"

    dest_folder.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        encoding='utf-8'
    )

    data_rows = []

    print("🚀 Starte Prozess. Details werden in die Log-Datei geschrieben...")
    logging.info("=== NEUER MERGE-LAUF GESTARTET ===")

    for src in sources:
        if not src.exists() or not src.is_dir():
            logging.warning("Quellordner nicht gefunden und uebersprungen: %s", src)
            continue

        logging.info("Starte rekursive Durchsuchung von: %s", src)

        for root, _dirs, files in os.walk(src):
            for file in files:
                if file.endswith('.md'):
                    old_path = Path(root) / file
                    title = get_frontmatter_title(str(old_path))

                    base_name, ext = os.path.splitext(file)
                    target_name = file
                    target_path = dest_folder / target_name
                    counter = 1

                    while target_path.exists():
                        target_name = f"{base_name}_{counter}{ext}"
                        target_path = dest_folder / target_name
                        counter += 1

                    if target_name != file:
                        logging.info("Namenskonflikt gelöst: '%s' umbenannt in '%s'", file, target_name)

                    try:
                        shutil.copy2(old_path, target_path)
                        logging.info("Kopiert: %s -> %s", old_path, target_path)
                    except OSError as e:
                        logging.error("Fehler beim Kopieren von %s: %s", old_path, e)
                        continue

                    data_rows.append({
                        'DATEINAME_ZIEL': target_name,
                        'TITEL_FRONTMATTER': title,
                        'PFAD_QUELLE': str(old_path)
                    })

    logging.info("Erstelle Mapping-CSV...")
    with mapping_csv.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['DATEINAME_ZIEL', 'TITEL_FRONTMATTER', 'PFAD_QUELLE'], delimiter=';')
        writer.writeheader()
        writer.writerows(data_rows)

    logging.info("=== LAUF BEENDET. %s Dateien verarbeitet. ===", len(data_rows))

    print(f"✅ Fertig! {len(data_rows)} .md-Dateien wurden gesammelt.")
    print(f"📂 Alle Dateien + CSV + Logbuch liegen hier: {dest_folder}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```


======================================================================
📁 FILE: tools/Files_Indexer.py
======================================================================

```py
import argparse
import csv
import json
import os
import re
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Erzeugt eine finale CSV-Übersicht aus einem Zielordner.")
    parser.add_argument("--config", default="studio_config.json", help="Pfad zur Konfigurationsdatei (Default: studio_config.json)")
    parser.add_argument("--target", help="Optionaler Zielordner-Override")
    return parser.parse_args()

def get_frontmatter_title(filepath):
    """Extrahiert den Titel aus dem YAML-Frontmatter."""
    try:
        with open(filepath, 'r', encoding='utf-8') as source_file:
            content = source_file.read(2000)
            match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
            return match.group(1).strip() if match else "Kein Titel"
    except (OSError, ValueError, TypeError):
        return "Lese-Fehler"

def main() -> int:
    args = _parse_args()
    project_root = _project_root()
    config_path = _resolve_path(args.config, project_root)
    config = _load_config(config_path)

    configured_target = args.target if args.target else config.get("indexer_target_folder", "")
    if not configured_target:
        print("❌ Kein Indexer-Zielordner konfiguriert. Bitte in Studio-Konfiguration 'indexer_target_folder' setzen.")
        return 2

    target_folder = _resolve_path(str(configured_target), project_root)
    if not target_folder.exists() or not target_folder.is_dir():
        print(f"❌ Indexer-Zielordner existiert nicht: {target_folder}")
        return 2

    csv_file = target_folder / 'buch_struktur_final.csv'
    data_rows = []

    print("📂 Lese Dateien im Zielordner...")

    for file in os.listdir(target_folder):
        if file.endswith('.md'):
            full_path = target_folder / file
            title = get_frontmatter_title(str(full_path))

            data_rows.append({
                'DATEINAME': file,
                'TITEL_FRONTMATTER': title
            })

    with csv_file.open('w', newline='', encoding='utf-8') as csv_handle:
        writer = csv.DictWriter(csv_handle, fieldnames=['DATEINAME', 'TITEL_FRONTMATTER'], delimiter=';')
        writer.writeheader()
        writer.writerows(data_rows)

    print(f"✅ Fertig! {len(data_rows)} Dateien indexiert.")
    print(f"📄 Die CSV liegt hier: {csv_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```


======================================================================
📁 FILE: ui_actions_manager.py
======================================================================

```py
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from ui_theme import COLORS, ThemedTooltip, apply_menu_theme, style_code_text


class UiActionsManager:
    def __init__(self, studio):
        self.studio = studio
        self._middle_button_style = {
            "width": 18,
            "style": "Soft.TButton",
        }

    def _root(self):
        return getattr(self.studio, "root", None)

    def _get_attr(self, name, default=None):
        return getattr(self.studio, name, default)

    def _set_attr(self, name, value):
        setattr(self.studio, name, value)
        return value

    def _host_method(self, name):
        method = getattr(self.studio, name, None)
        return method if callable(method) else None

    def _call_host(self, name, *args, **kwargs):
        method = self._host_method(name)
        if method is None:
            return None
        return method(*args, **kwargs)

    def _register_widget(self, register_method_name, attr_name, widget):
        register = self._host_method(register_method_name)
        if register is not None:
            return register(widget)
        return self._set_attr(attr_name, widget)

    def build_middle_panel(self, parent):
        middle_frame = tk.Frame(parent, bg=COLORS["app_bg"], width=196)
        middle_frame.pack_propagate(False)
        parent.add(middle_frame)

        self._add_middle_buttons(middle_frame)
        return middle_frame

    def build_footer(self, parent):
        footer = tk.Frame(parent, bg=COLORS["panel_dark"], pady=15)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(footer, text="Aktionen über Menü: Datei / Export / Tools", bg=COLORS["panel_dark"], fg=COLORS["text_soft"], font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=20)

        status = self._register_widget(
            "register_status_widget",
            "status",
            tk.Label(footer, text="Bereit.", bg=COLORS["panel_dark"], fg="#cbd5e1", font=("Consolas", 9)),
        )
        status.pack(side=tk.RIGHT, padx=20)
        return footer

    def _add_middle_buttons(self, middle_frame):
        button_specs = [
            {"text": "Hinzufügen ➡️", "style": "Accent.TButton", "command": self._host_method("add_files"), "pack": {"pady": (36, 6)}},
            {"text": "⬅️ Entfernen", "style": "Soft.TButton", "command": self._host_method("remove_files"), "pack": {}},
            {"separator": True, "options": {"height": 20, "bg": COLORS["app_bg"]}},
            {"text": "⬆️ Hoch", "command": self._host_method("move_up"), "pack": {"pady": 2}},
            {"text": "⬇️ Runter", "command": self._host_method("move_down"), "pack": {"pady": 2}},
            {"text": "➡️ Einrücken", "command": self._host_method("indent_item"), "pack": {"pady": (10, 2)}},
            {"text": "⬅️ Ausrücken", "command": self._host_method("outdent_item"), "pack": {"pady": 2}},
            {"separator": True, "ttk": True},
        ]

        for spec in button_specs:
            if spec.get("separator"):
                if spec.get("ttk"):
                    ttk.Separator(middle_frame, orient="horizontal").pack(fill="x", pady=15, padx=10)
                else:
                    tk.Frame(middle_frame, **spec["options"]).pack()
                continue

            self._create_button(middle_frame, spec)

        undo_redo_row = tk.Frame(middle_frame, bg=COLORS["app_bg"])
        undo_redo_row.pack(fill=tk.X, padx=10, pady=(0, 4))
        ttk.Button(
            undo_redo_row,
            text="↩ Undo",
            command=self._host_method("undo"),
            style="Tool.TButton",
            width=8,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        ttk.Button(
            undo_redo_row,
            text="↪ Redo",
            command=self._host_method("redo"),
            style="Tool.TButton",
            width=8,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))

        self._add_middle_icon_legend(middle_frame)

    def _add_middle_icon_legend(self, middle_frame):
        ttk.Separator(middle_frame, orient="horizontal").pack(fill="x", pady=(14, 8), padx=10)

        legend = tk.Frame(middle_frame, bg=COLORS["app_bg"])
        legend.pack(fill=tk.X, padx=8)

        tk.Label(
            legend,
            text="Icon-Legende",
            bg=COLORS["app_bg"],
            fg=COLORS["heading"],
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", pady=(0, 4))

        legend_lines = [
            "📌 required",
            "🧭 Nur Gliederungspunkt",
            "● Verwaiste Fußnoten",
            "↵ Seitenumbruch-Ende",
            "🖼 Fehlende Bilder",
            "☠ Buch-Doktor-Fehler",
            "📌/🧭 vor dem Titel",
            "hinter den Titel ●/↵/🖼/☠",
        ]
        for line in legend_lines:
            tk.Label(
                legend,
                text=line,
                bg=COLORS["app_bg"],
                fg="#475569",
                font=("Segoe UI", 8),
                justify="left",
            ).pack(anchor="w")

    def _create_button(self, parent, spec):
        kwargs = dict(self._middle_button_style)
        kwargs.update({
            "text": spec["text"],
            "command": spec["command"],
        })

        if "style" in spec:
            kwargs["style"] = spec["style"]
        if "width" in spec:
            kwargs["width"] = spec["width"]

        ttk.Button(parent, **kwargs).pack(**spec.get("pack", {}))

    # =========================================================================
    # LOG-TERMINAL
    # =========================================================================
    def build_log_panel(self, parent):
        outer = tk.Frame(parent, bg=COLORS["log_panel"], height=170)
        outer.pack_propagate(False)

        # Header-Leiste
        header = tk.Frame(outer, bg=COLORS["log_header"], pady=5)
        header.pack(fill=tk.X)

        title_block = tk.Frame(header, bg=COLORS["log_header"])
        title_block.pack(side=tk.LEFT, padx=10)
        tk.Label(
            title_block,
            text="LOG",
            bg=COLORS["log_header"],
            fg="#7dd3fc",
            font=("Consolas", 8, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            title_block,
            text="Live-Ausgabe",
            bg=COLORS["log_header"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 8),
        ).pack(side=tk.LEFT, padx=(6, 0))

        controls = tk.Frame(header, bg=COLORS["log_header"])
        controls.pack(side=tk.RIGHT, padx=6)

        action_group = self._build_log_group(controls)
        action_group.pack(side=tk.RIGHT, padx=(6, 0))

        filter_group = self._build_log_group(controls)
        filter_group.pack(side=tk.RIGHT, padx=(6, 0))

        filter_box = ttk.Combobox(
            filter_group,
            textvariable=self._call_host("get_log_filter_var") or self._get_attr("log_filter_var"),
            values=self._call_host("get_log_filter_labels") or self._get_attr("log_filter_labels", []),
            state="readonly",
            width=9,
                style="Log.TCombobox",
        )
        filter_box.pack(side=tk.RIGHT, padx=(6, 0), pady=0)
        filter_box.bind("<<ComboboxSelected>>", self._on_log_preferences_changed)
        ThemedTooltip(filter_box, "Zeigt nur Log-Zeilen des gewählten Levels an.")

        tk.Label(
            filter_group,
            text="Filter",
            bg=COLORS["log_chip_bg"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 8),
        ).pack(side=tk.RIGHT, padx=(0, 2), pady=0)

        self._add_log_divider(filter_group).pack(side=tk.RIGHT, padx=6, pady=2, fill=tk.Y)

        max_lines_box = ttk.Combobox(
            filter_group,
            textvariable=self._call_host("get_log_max_lines_var") or self._get_attr("log_max_lines_var"),
            values=["200", "500", "1000", "2000"],
            state="readonly",
            width=6,
                style="Log.TCombobox",
        )
        max_lines_box.pack(side=tk.RIGHT, padx=(6, 0), pady=0)
        max_lines_box.bind("<<ComboboxSelected>>", self._on_log_preferences_changed)
        ThemedTooltip(max_lines_box, "Maximale Anzahl gespeicherter Log-Zeilen bei aktiviertem Auto-Clear.")

        tk.Label(
            filter_group,
            text="Limit",
            bg=COLORS["log_chip_bg"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 8),
        ).pack(side=tk.RIGHT, padx=(0, 2), pady=0)

        self._add_log_divider(filter_group).pack(side=tk.RIGHT, padx=6, pady=2, fill=tk.Y)

        auto_clear_toggle = ttk.Checkbutton(
            filter_group,
            text="Auto-Clear",
            variable=self._call_host("get_log_auto_clear_var") or self._get_attr("log_auto_clear_var"),
            command=self._on_log_preferences_changed,
            style="LogSwitch.TCheckbutton",
        )
        auto_clear_toggle.pack(side=tk.RIGHT, padx=(0, 1), pady=0)
        ThemedTooltip(auto_clear_toggle, "Behält nur die letzten N Log-Zeilen und räumt ältere Einträge automatisch weg.")

        self._create_log_action_button(
            action_group,
            text="Kopieren",
            command=self._copy_log,
            variant="default",
        ).pack(side=tk.RIGHT, padx=(6, 0), pady=0)
        self._add_log_divider(action_group).pack(side=tk.RIGHT, padx=6, pady=2, fill=tk.Y)
        self._create_log_action_button(
            action_group,
            text="Leeren",
            command=self._clear_log,
            variant="danger",
        ).pack(side=tk.RIGHT, pady=0)

        # Weißer Trennstreifen zur Footer-Leiste — MUSS vor dem expand=True-Widget gepackt werden!
        tk.Frame(outer, bg="#ffffff", height=2).pack(fill=tk.X, side=tk.BOTTOM)

        # Text-Widget
        log_output = self._register_widget("register_log_output_widget", "log_output", ScrolledText(
            outer,
            state="disabled", wrap=tk.WORD,
        ))
        style_code_text(log_output)
        get_log_font_size = self._host_method("get_log_font_size")
        log_font_size = get_log_font_size() if callable(get_log_font_size) else 9
        log_output.configure(font=("Consolas", log_font_size), padx=8, pady=6, state="disabled")
        log_output.pack(fill=tk.BOTH, expand=True)
        log_output.bind("<Button-3>", self._show_log_menu)
        log_output.bind("<Double-1>", self._on_log_double_click)
        log_output.bind("<Button-1>", self._on_log_click, add="+")

        # Farb-Tags definieren
        w = log_output
        w.tag_configure("info",    foreground="#c9d1d9")
        w.tag_configure("success", foreground="#3fb950")
        w.tag_configure("error",   foreground="#f85149")
        w.tag_configure("warning", foreground="#d29922")
        w.tag_configure("header",  foreground="#58a6ff")
        w.tag_configure("dim",     foreground="#484f58")

        log_menu = self._register_widget("register_log_menu_widget", "log_menu", tk.Menu(self._root(), tearoff=0))
        apply_menu_theme(log_menu)
        log_menu.add_command(label="Kopieren", command=self._copy_log)
        log_menu.add_command(label="Alles kopieren", command=lambda: self._copy_log(copy_all=True))
        log_menu.add_separator()
        log_menu.add_command(label="Leeren", command=self._clear_log)

        return outer

    def _build_log_group(self, parent):
        group = tk.Frame(
            parent,
            bg=COLORS["log_chip_bg"],
            highlightthickness=1,
            highlightbackground=COLORS["log_chip_border"],
            highlightcolor=COLORS["log_chip_border"],
            bd=0,
            padx=8,
            pady=2,
        )
        return group

    def _create_log_action_button(self, parent, text, command, variant="default"):
        if variant == "danger":
            bg = COLORS["log_button_danger_bg"]
            fg = COLORS["log_button_danger_text"]
            active_bg = COLORS["log_button_danger_hover"]
            border = COLORS["log_button_danger_border"]
        else:
            bg = COLORS["log_button_bg"]
            fg = COLORS["log_chip_text"]
            active_bg = COLORS["log_button_hover"]
            border = COLORS["log_button_border"]

        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=COLORS["surface"],
            bd=0,
            relief="flat",
            overrelief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=9,
            pady=2,
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=border,
            cursor="hand2",
        )

    def _add_log_divider(self, parent):
        return tk.Frame(parent, bg=COLORS["log_chip_border"], width=1)

    def _on_log_preferences_changed(self, _event=None):
        self._call_host("on_log_preferences_changed")

    def _clear_log(self):
        self._call_host("clear_log")

    def _copy_log(self, copy_all=False):
        self._call_host("copy_log_to_clipboard", copy_all=copy_all)

    def _show_log_menu(self, event):
        log_menu = self._get_attr("log_menu")
        if log_menu is None:
            return None
        try:
            log_menu.tk_popup(event.x_root, event.y_root)
        finally:
            log_menu.grab_release()

    def _on_log_double_click(self, event):
        return self._call_host("on_log_double_click", event)

    def _on_log_click(self, event):
        return self._call_host("on_log_click", event)

```


======================================================================
📁 FILE: ui_theme.py
======================================================================

```py
import tkinter as tk


COLORS = {
    "app_bg": "#edf3f8",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "surface_muted": "#eef2f7",
    "panel_dark": "#1f2937",
    "panel_dark_alt": "#16202c",
    "text": "#1f2937",
    "text_muted": "#64748b",
    "text_soft": "#94a3b8",
    "heading": "#334155",
    "border": "#d6dee8",
    "accent": "#2563eb",
    "accent_soft": "#dbeafe",
    "accent_text": "#1d4ed8",
    "danger_soft": "#fee2e2",
    "danger_text": "#b91c1c",
    "success": "#16a34a",
    "warning": "#d97706",
    "log_bg": "#0d1117",
    "log_panel": "#10161f",
    "log_header": "#16202c",
    "log_text": "#c9d1d9",
    "log_chip_bg": "#1d2836",
    "log_chip_border": "#314154",
    "log_chip_text": "#d9e4ef",
    "log_button_bg": "#223244",
    "log_button_hover": "#2b3f56",
    "log_button_pressed": "#182331",
    "log_button_border": "#405062",
    "log_button_danger_bg": "#3a2328",
    "log_button_danger_hover": "#522d34",
    "log_button_danger_text": "#ffd9df",
    "log_button_danger_border": "#6b434b",
    "tooltip_bg": "#fffdf2",
    "tooltip_border": "#d6c98a",
    "menu_bg": "#f8fbff",
    "menu_fg": "#1f2937",
    "menu_active_bg": "#dbeafe",
    "menu_active_fg": "#0f172a",
    "menu_border": "#cbd5e1",
}

FONTS = {
    "ui": ("Segoe UI", 10),
    "ui_small": ("Segoe UI", 9),
    "ui_semibold": ("Segoe UI Semibold", 10),
    "ui_semibold_small": ("Segoe UI Semibold", 9),
    "title": ("Segoe UI Semibold", 11),
    "title_large": ("Segoe UI", 13, "bold"),
    "mono": ("Consolas", 9),
    "mono_large": ("Consolas", 11),
}


def configure_root(root):
    root.configure(bg=COLORS["app_bg"])
    root.option_add("*Font", "{Segoe UI} 10")


def apply_ttk_theme(style, sv_ttk=None):
    if sv_ttk is not None:
        sv_ttk.set_theme("light")
    else:
        style.theme_use("clam")

    style.configure("TLabel", background=COLORS["app_bg"], foreground=COLORS["text"], font=FONTS["ui"])
    style.configure("TFrame", background=COLORS["app_bg"])
    style.configure("TEntry", padding=6)
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["surface"],
        background=COLORS["surface"],
        foreground=COLORS["text"],
        arrowsize=14,
        padding=5,
    )
    style.configure(
        "Log.TCombobox",
        fieldbackground=COLORS["log_chip_bg"],
        background=COLORS["log_chip_bg"],
        foreground=COLORS["log_chip_text"],
        arrowcolor=COLORS["text_soft"],
        bordercolor=COLORS["log_chip_border"],
        darkcolor=COLORS["log_chip_bg"],
        lightcolor=COLORS["log_chip_bg"],
        insertcolor=COLORS["log_chip_text"],
        padding=4,
    )
    style.map(
        "Log.TCombobox",
        fieldbackground=[("readonly", COLORS["log_chip_bg"]), ("focus", COLORS["log_chip_bg"])],
        background=[("readonly", COLORS["log_chip_bg"]), ("active", COLORS["log_chip_bg"])],
        foreground=[("readonly", COLORS["log_chip_text"]), ("focus", COLORS["surface"])],
        arrowcolor=[("active", COLORS["surface"]), ("readonly", COLORS["text_soft"])],
    )
    style.configure("Accent.TButton", font=FONTS["ui_semibold"], padding=(12, 8))
    style.configure("Soft.TButton", font=FONTS["ui_semibold_small"], padding=(10, 7))
    style.configure("Tool.TButton", font=FONTS["ui_small"], padding=(8, 6))
    style.configure(
        "LogAction.TButton",
        font=FONTS["ui_small"],
        padding=(10, 5),
        background=COLORS["log_button_bg"],
        foreground=COLORS["log_chip_text"],
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "LogAction.TButton",
        background=[("active", COLORS["log_button_hover"]), ("pressed", COLORS["log_button_pressed"])],
        foreground=[("disabled", COLORS["text_soft"]), ("active", COLORS["surface"])],
    )
    style.configure(
        "LogDanger.TButton",
        font=FONTS["ui_small"],
        padding=(10, 5),
        background=COLORS["log_button_danger_bg"],
        foreground=COLORS["log_button_danger_text"],
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "LogDanger.TButton",
        background=[("active", COLORS["log_button_danger_hover"]), ("pressed", COLORS["log_button_pressed"])],
        foreground=[("active", COLORS["surface"])],
    )
    style.configure(
        "LogSwitch.TCheckbutton",
        background=COLORS["log_chip_bg"],
        foreground=COLORS["log_chip_text"],
        font=FONTS["ui_small"],
        padding=(6, 2),
    )
    style.map(
        "LogSwitch.TCheckbutton",
        background=[("active", COLORS["log_chip_bg"])],
        foreground=[("disabled", COLORS["text_soft"]), ("active", COLORS["surface"])],
    )
    style.configure("Section.TLabelframe", background=COLORS["app_bg"], borderwidth=1, relief="solid")
    style.configure("Section.TLabelframe.Label", background=COLORS["app_bg"], foreground=COLORS["heading"], font=FONTS["ui_semibold"])
    style.configure(
        "Treeview",
        font=FONTS["ui"],
        rowheight=30,
        background=COLORS["surface"],
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "Treeview.Heading",
        font=FONTS["ui_semibold"],
        background=COLORS["surface_muted"],
        foreground=COLORS["heading"],
        relief="flat",
        padding=6,
    )
    style.map("Treeview", background=[("selected", COLORS["accent_soft"])], foreground=[("selected", "#0f172a")])
    style.map("Treeview.Heading", background=[("active", "#e2e8f0")])


def style_dialog(window, title=None):
    window.configure(bg=COLORS["app_bg"])
    if title:
        window.title(title)


def apply_menu_theme(menu):
    menu.configure(
        bg=COLORS["menu_bg"],
        fg=COLORS["menu_fg"],
        activebackground=COLORS["menu_active_bg"],
        activeforeground=COLORS["menu_active_fg"],
        bd=1,
        relief="solid",
        borderwidth=1,
        activeborderwidth=0,
    )


def center_on_parent(window, parent, width, height):
    parent.update_idletasks()
    px = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    py = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    window.geometry(f"{width}x{height}+{px}+{py}")


def style_code_text(widget, *, read_only=False):
    widget.configure(
        bg=COLORS["log_bg"],
        fg=COLORS["log_text"],
        font=FONTS["mono_large"],
        insertbackground=COLORS["log_text"],
        bd=0,
        padx=12,
        pady=12,
        relief="flat",
    )
    if read_only:
        widget.configure(state="disabled")


class ThemedTooltip:
    def __init__(self, widget, text, delay_ms=250):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        if not self.text:
            return
        self._cancel_scheduled()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel_scheduled(self):
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self):
        self._after_id = None
        if self.tip is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        outer = tk.Frame(self.tip, bg=COLORS["tooltip_border"], bd=0)
        outer.pack()
        label = tk.Label(
            outer,
            text=self.text,
            justify=tk.LEFT,
            bg=COLORS["tooltip_bg"],
            fg=COLORS["text"],
            padx=10,
            pady=8,
            wraplength=380,
            font=FONTS["ui_small"],
        )
        label.pack(padx=1, pady=1)

    def _hide(self, _event=None):
        self._cancel_scheduled()
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None

```


======================================================================
📁 FILE: unmanned_trigger.py
======================================================================

```py
import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pre_processor import PreProcessor
from yaml_engine import QuartoYamlEngine


@dataclass
class ExportSettings:
    fmt: str = "typst"
    template: str = "Standard"
    footnote_mode: str = "endnotes"
    profile_name: str | None = None


@dataclass
class TriggerRequest:
    book_path: Path
    structure_json: Path
    md_source_path: Path
    export: ExportSettings
    run_render: bool = True
    sync_md_sources: bool = False
    quarto_bin: str = "quarto"
    run_id: str | None = None
    job_id: str | None = None
    log_file: Path | None = None
    timeout_sec: int | None = None
    strict: bool = False


def _emit(message: str, *, err: bool = False, log_handle=None, run_id=None, job_id=None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    meta_parts = []
    if run_id:
        meta_parts.append(f"run={run_id}")
    if job_id:
        meta_parts.append(f"job={job_id}")
    meta = f" [{' '.join(meta_parts)}]" if meta_parts else ""
    line = f"[{timestamp}]{meta} {message}"

    target = sys.stderr if err else sys.stdout
    print(line, file=target)

    if log_handle is not None:
        log_handle.write(line + "\n")
        log_handle.flush()


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _iter_tree_nodes(tree_data):
    for item in tree_data:
        if not isinstance(item, dict):
            continue
        yield item
        children = item.get("children", [])
        if isinstance(children, list):
            yield from _iter_tree_nodes(children)


def _collect_markdown_paths(tree_data):
    paths = []
    for item in _iter_tree_nodes(tree_data):
        path = item.get("path", "")
        if not isinstance(path, str):
            continue
        if not path or path.startswith("PART:"):
            continue
        if path == "index.md":
            continue
        if not path.lower().endswith(".md"):
            continue
        paths.append(path.replace("\\", "/"))
    return sorted(set(paths))


def _validate_structure(tree_data):
    if not isinstance(tree_data, list):
        raise ValueError("Die Strukturdatei muss eine JSON-Liste sein.")

    for item in _iter_tree_nodes(tree_data):
        if "path" not in item:
            raise ValueError("Jeder Knoten muss ein 'path'-Feld besitzen.")
        if "children" in item and not isinstance(item.get("children"), list):
            raise ValueError("'children' muss eine Liste sein.")


def _resolve_source_file(md_source_path: Path, rel_path: str):
    rel = Path(rel_path)
    candidates = [md_source_path / rel]

    rel_text = rel_path.replace("\\", "/")
    if rel_text.startswith("content/"):
        candidates.append(md_source_path / rel_text.removeprefix("content/"))

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _validate_source_paths(md_paths, md_source_path: Path):
    missing = []
    for rel_path in md_paths:
        source = _resolve_source_file(md_source_path, rel_path)
        if source is None:
            missing.append(rel_path)
    return missing


def _sync_sources(md_paths, md_source_path: Path, book_path: Path):
    copied = 0
    for rel_path in md_paths:
        source = _resolve_source_file(md_source_path, rel_path)
        if source is None:
            continue

        target = book_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return copied


def _resolve_render_target(export: ExportSettings):
    base_fmt = export.fmt
    selected_tpl = export.template

    target_fmt = base_fmt
    extra_opts = None

    if selected_tpl.startswith("EXT: "):
        ext_name = selected_tpl.replace("EXT: ", "").strip()
        target_fmt = f"{ext_name}-{base_fmt}"
        extra_opts = {
            target_fmt: {
                "toc": True,
                "toc-depth": 3,
                "number-sections": True,
                "section-numbering": "1.1.1",
            }
        }
    elif selected_tpl != "Standard":
        extra_opts = {base_fmt: {"template": f"templates/{selected_tpl}"}}

    return target_fmt, extra_opts


def _run_render(book_path: Path, target_fmt: str, quarto_bin: str, timeout_sec: int | None = None):
    command = [quarto_bin, "render", str(book_path), "--to", target_fmt]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "").splitlines()
        return 124, partial

    lines = (result.stdout or "").splitlines()
    return result.returncode, lines


def run_unmanned_trigger(request: TriggerRequest):
    log_handle = None
    if request.log_file is not None:
        request.log_file.parent.mkdir(parents=True, exist_ok=True)
        log_handle = request.log_file.open("a", encoding="utf-8")

    tree_data = _load_json(request.structure_json)
    _validate_structure(tree_data)

    try:
        _emit("🚀 Unmanned-Run gestartet", log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
        md_paths = _collect_markdown_paths(tree_data)
        missing = _validate_source_paths(md_paths, request.md_source_path)
        if missing:
            _emit("❌ Fehlende Markdown-Quellen:", err=True, log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
            for path in missing[:20]:
                _emit(f"  - {path}", err=True, log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
            if len(missing) > 20:
                _emit(f"  ... und {len(missing) - 20} weitere", err=True, log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
            return 2

        if request.sync_md_sources:
            copied = _sync_sources(md_paths, request.md_source_path, request.book_path)
            _emit(f"📥 Synchronisierte Quellen: {copied}", log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)

        yaml_engine = QuartoYamlEngine(request.book_path)
        target_fmt, extra_opts = _resolve_render_target(request.export)
        profile_name = request.export.profile_name

        processor = PreProcessor(request.book_path, footnote_mode=request.export.footnote_mode)
        processed_tree = processor.prepare_render_environment(tree_data)

        orphan_count = len(processor.harvester.orphan_warnings)
        if orphan_count:
            _emit(
                f"⚠️ Verwaiste Fußnotenmarker erkannt: {orphan_count}",
                err=request.strict,
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )
            if request.strict:
                _emit(
                    "❌ Strict-Mode aktiv: Abbruch wegen Warnungen.",
                    err=True,
                    log_handle=log_handle,
                    run_id=request.run_id,
                    job_id=request.job_id,
                )
                return 3

        yaml_engine.save_chapters(
            processed_tree,
            profile_name=profile_name,
            save_gui_state=False,
            extra_format_options=extra_opts,
        )

        if not request.run_render:
            _emit(
                "✅ Unmanned-Run vorbereitet (Render übersprungen).",
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )
            return 0

        _emit(
            f"🖨️  Starte Render: {target_fmt}",
            log_handle=log_handle,
            run_id=request.run_id,
            job_id=request.job_id,
        )
        render_code, render_lines = _run_render(
            request.book_path,
            target_fmt,
            request.quarto_bin,
            timeout_sec=request.timeout_sec,
        )
        for line in render_lines:
            if line.strip():
                _emit(line.rstrip(), log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)

        if render_code == 124:
            _emit(
                f"⏱️ Render-Timeout nach {request.timeout_sec}s",
                err=True,
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )
            return 124

        if render_code != 0:
            _emit(
                f"❌ Render fehlgeschlagen (Exit-Code {render_code})",
                err=True,
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )
            return render_code

        _emit("✅ Render erfolgreich", log_handle=log_handle, run_id=request.run_id, job_id=request.job_id)
        return 0
    finally:
        try:
            yaml_engine = QuartoYamlEngine(request.book_path)
            yaml_engine.save_chapters(tree_data, profile_name=request.export.profile_name, save_gui_state=False)
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            _emit(
                f"⚠️ Rückbau der _quarto.yml fehlgeschlagen: {exc}",
                err=True,
                log_handle=log_handle,
                run_id=request.run_id,
                job_id=request.job_id,
            )

        if log_handle is not None:
            log_handle.close()


def _parse_export_settings(args):
    settings = ExportSettings()

    if args.export_settings_json:
        settings_data = _load_json(Path(args.export_settings_json))
        if not isinstance(settings_data, dict):
            raise ValueError("export-settings-json muss ein JSON-Objekt enthalten.")
        settings = ExportSettings(
            fmt=str(settings_data.get("format", settings.fmt)),
            template=str(settings_data.get("template", settings.template)),
            footnote_mode=str(settings_data.get("footnote_mode", settings.footnote_mode)),
            profile_name=(str(settings_data["profile_name"]) if settings_data.get("profile_name") else None),
        )

    if args.format:
        settings.fmt = args.format
    if args.template:
        settings.template = args.template
    if args.footnote_mode:
        settings.footnote_mode = args.footnote_mode
    if args.profile_name:
        settings.profile_name = args.profile_name

    return settings


def _build_parser():
    parser = argparse.ArgumentParser(
        description="CLI-Trigger für unbeaufsichtigten Book-Studio-Export (unmanned mode)."
    )
    parser.add_argument("--book-path", required=True, help="Pfad zum Buchprojekt (enthält _quarto.yml).")
    parser.add_argument("--structure-json", required=True, help="JSON-Datei mit Buchstruktur (Book-Studio-Profil).")
    parser.add_argument("--md-source-path", required=True, help="Pfad zu den Markdown-Quelldateien.")

    parser.add_argument("--export-settings-json", help="Optional: JSON mit format/template/footnote_mode/profile_name.")
    parser.add_argument("--format", dest="format", help="Exportformat, z. B. typst/pdf/html/docx/epub.")
    parser.add_argument("--template", help="Template-Name oder 'EXT: <name>'.")
    parser.add_argument("--footnote-mode", help="Fußnotenmodus (z. B. endnotes).")
    parser.add_argument("--profile-name", help="Optionaler Profilname für output-dir Naming.")

    parser.add_argument("--sync-md-sources", action="store_true", help="Kopiert Quellen aus md-source-path ins Buchprojekt.")
    parser.add_argument("--no-render", action="store_true", help="Pipeline vorbereiten, aber Quarto-Render nicht starten.")
    parser.add_argument("--quarto-bin", default="quarto", help="Quarto-Binary/Command (Default: quarto).")
    parser.add_argument("--run-id", help="Optionale Run-ID zur externen Nachverfolgung.")
    parser.add_argument("--job-id", help="Optionale Job-ID zur externen Nachverfolgung.")
    parser.add_argument("--log-file", help="Optionaler Pfad für persistentes Logfile.")
    parser.add_argument("--timeout-sec", type=int, help="Optionales Render-Timeout in Sekunden.")
    parser.add_argument("--strict", action="store_true", help="Bricht bei Warnungen (z. B. verwaiste Fußnotenmarker) mit Code 3 ab.")
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    try:
        export = _parse_export_settings(args)
        request = TriggerRequest(
            book_path=Path(args.book_path).resolve(),
            structure_json=Path(args.structure_json).resolve(),
            md_source_path=Path(args.md_source_path).resolve(),
            export=export,
            run_render=not args.no_render,
            sync_md_sources=bool(args.sync_md_sources),
            quarto_bin=args.quarto_bin,
            run_id=args.run_id,
            job_id=args.job_id,
            log_file=Path(args.log_file).resolve() if args.log_file else None,
            timeout_sec=args.timeout_sec,
            strict=bool(args.strict),
        )

        if not request.book_path.exists():
            raise FileNotFoundError(f"book-path nicht gefunden: {request.book_path}")
        if not request.structure_json.exists():
            raise FileNotFoundError(f"structure-json nicht gefunden: {request.structure_json}")
        if not request.md_source_path.exists():
            raise FileNotFoundError(f"md-source-path nicht gefunden: {request.md_source_path}")
        if request.timeout_sec is not None and request.timeout_sec <= 0:
            raise ValueError("timeout-sec muss > 0 sein.")

        result = run_unmanned_trigger(request)
        raise SystemExit(result)
    except Exception as exc:
        print(f"❌ Unmanned-Trigger Fehler: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

```


======================================================================
📁 FILE: yaml_engine.py
======================================================================

```py
import yaml
import re
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class QuartoYamlEngine:
    def __init__(self, book_path):
        self.book_path = Path(book_path)
        self.yaml_path = self.book_path / "_quarto.yml"
        self.gui_state_path = self.book_path / "bookconfig" / ".gui_state.json"

    # =========================================================================
    # TITEL- & STATUS-EXTRAKTION (REGISTRY)
    # =========================================================================

    def extract_title_from_md(self, filepath):
        """Liest den Titel aus dem YAML-Frontmatter oder der ersten H1-Überschrift."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000) # Nur den Anfang lesen
            
            # 1. Suche in YAML Frontmatter
            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                t_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if t_match:
                    return t_match.group(1).strip()
            
            # 2. Suche nach erster # Überschrift
            h1_match = re.search(r'^#\s+(.*)$', content, re.MULTILINE)
            if h1_match:
                return h1_match.group(1).strip()
            
            return None
        except (OSError, ValueError, TypeError):
            return None

    def build_title_registry(self):
        """Erstellt eine Liste aller .md Dateien mit ihren Titeln und Icons (nur im content-Ordner)."""
        registry = {}
        content_dir = self.book_path / "content"
        
        # Sicherstellen, dass der content-Ordner existiert, bevor wir suchen
        if not content_dir.exists():
            return registry
            
        for p in content_dir.rglob("*.md"):
            # Wir ignorieren nur noch versteckte Systemordner innerhalb von content
            if not any(x.startswith(".") for x in p.parts):
                # Der relative Pfad MUSS weiterhin ab book_path gebildet werden, 
                # da die _quarto.yml die Pfade inkl. "content/..." erwartet!
                rel_path = p.relative_to(self.book_path).as_posix()
                
                title = self.extract_title_from_md(p)
                if title: 
                    content_role = self.extract_content_role_from_md(p)
                    icons = []
                    if "required" in p.parts:
                        icons.append("📌")
                    if content_role == "outline":
                        icons.append("🧭")
                    if icons:
                        title = f"{' '.join(icons)} {title}"
                    registry[rel_path] = title
                else: 
                    registry[rel_path] = f"[FEHLT] {p.stem}"
        return registry

    def extract_content_role_from_md(self, filepath):
        """Liest content_role aus dem YAML-Frontmatter (z. B. outline/content)."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000)

            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                role_match = re.search(r'^content_role:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if role_match:
                    return role_match.group(1).strip().lower()
            return None
        except (OSError, ValueError, TypeError):
            return None

    def build_status_registry(self):
        """Erstellt eine Registry aller Dateistatus für den Filter in der GUI (nur im content-Ordner)."""
        registry = {}
        content_dir = self.book_path / "content"
        
        if not content_dir.exists():
            return registry
            
        for p in content_dir.rglob("*.md"):
            if not any(x.startswith(".") for x in p.parts):
                rel_path = p.relative_to(self.book_path).as_posix()
                registry[rel_path] = self.extract_status_from_md(p)
        return registry

    def extract_status_from_md(self, filepath):
        """Liest den Status aus dem YAML-Frontmatter (status: "...") aus."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000)
            
            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                status_match = re.search(r'^status:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if status_match:
                    return status_match.group(1).strip()
            return "ohne Eintrag"
        except (OSError, ValueError, TypeError):
            return "ohne Eintrag"

    def ensure_required_frontmatter(self, filepath, fallback_title=None):
        """Ergänzt fehlende Pflichtfelder, ohne bestehendes Frontmatter-Formatting umzuschreiben."""

        def _yaml_quote(value):
            text = str(value)
            text = text.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{text}"'

        def _strip_outer_quotes(value):
            text = str(value).strip()
            if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
                return text[1:-1]
            return text

        filepath = Path(filepath)
        config_path = Path(__file__).parent / "studio_config.json"

        required_fields = {
            "title": "<filename>",
            "description": "<title>",
            "status": "bookstudio",
        }
        frontmatter_update_mode = "append_only"

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as c_f:
                    config_data = json.load(c_f)
                    required_fields = config_data.get(
                        "frontmatter_requirements", required_fields
                    )
                    frontmatter_update_mode = str(
                        config_data.get("frontmatter_update_mode", frontmatter_update_mode)
                    ).strip().lower()
            except (OSError, ValueError, TypeError) as e:
                logger.warning("Fehler beim Lesen der studio_config.json: %s", e)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            newline = "\r\n" if "\r\n" in content else "\n"

            # Gruppen: 1=BOM, 2=Frontmatter-Inhalt, 3=Body (unverändert)
            match = re.match(
                r'^(\uFEFF?)---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*(.*)$',
                content,
                re.DOTALL,
            )

            keys_to_process = list(required_fields.keys())
            if "title" in keys_to_process:
                keys_to_process.remove("title")
                keys_to_process.insert(0, "title")

            if frontmatter_update_mode == "reserialize":
                if match:
                    bom = match.group(1)
                    frontmatter_str = match.group(2)
                    body = match.group(3)
                    try:
                        parsed_yaml = yaml.safe_load(frontmatter_str) or {}
                    except yaml.YAMLError:
                        return False
                else:
                    bom = ""
                    body = content.strip("\r\n")
                    parsed_yaml = {}

                changed = False
                for key in keys_to_process:
                    if key in parsed_yaml:
                        continue

                    config_val = required_fields[key]
                    if config_val == "<filename>":
                        val = fallback_title if fallback_title else filepath.stem
                    elif config_val == "<title>":
                        val = parsed_yaml.get(
                            "title", fallback_title if fallback_title else filepath.stem
                        )
                    else:
                        val = config_val
                    parsed_yaml[key] = val
                    changed = True

                if not changed:
                    return False

                dumped = yaml.safe_dump(
                    parsed_yaml,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                ).rstrip("\r\n")
                new_content = f"{bom}---{newline}{dumped}{newline}---{newline}{body}"

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                return True

            if match:
                bom = match.group(1)
                frontmatter_str = match.group(2)
                body = match.group(3)

                existing_keys = set()
                for line in frontmatter_str.splitlines():
                    key_match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*:", line)
                    if key_match:
                        existing_keys.add(key_match.group(1))

                title_match = re.search(
                    r'^\s*title\s*:\s*(.*?)\s*$',
                    frontmatter_str,
                    flags=re.MULTILINE,
                )
                parsed_title = (
                    _strip_outer_quotes(title_match.group(1))
                    if title_match
                    else (fallback_title if fallback_title else filepath.stem)
                )

                additions = []
                for key in keys_to_process:
                    if key in existing_keys:
                        continue

                    config_val = required_fields[key]
                    if config_val == "<filename>":
                        val = fallback_title if fallback_title else filepath.stem
                    elif config_val == "<title>":
                        val = parsed_title
                    else:
                        val = config_val

                    additions.append(f"{key}: {_yaml_quote(val)}")
                    if key == "title":
                        parsed_title = str(val)

                if not additions:
                    return False

                updated_frontmatter = frontmatter_str.rstrip("\r\n")
                if updated_frontmatter:
                    updated_frontmatter += newline
                updated_frontmatter += newline.join(additions)

                new_content = (
                    f"{bom}---{newline}{updated_frontmatter}{newline}---{newline}{body}"
                )
            else:
                base_title = fallback_title if fallback_title else filepath.stem
                value_map = {}
                for key in keys_to_process:
                    config_val = required_fields[key]
                    if config_val == "<filename>":
                        value_map[key] = base_title
                    elif config_val == "<title>":
                        value_map[key] = value_map.get("title", base_title)
                    else:
                        value_map[key] = config_val

                fm_lines = [f"{key}: {_yaml_quote(value_map[key])}" for key in keys_to_process]
                body = content.lstrip("\r\n")
                new_content = f"---{newline}{newline.join(fm_lines)}{newline}---{newline}{body}"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True

        except (OSError, ValueError, TypeError) as e:
            logger.warning("Fehler beim Auto-Healing für %s: %s", filepath, e)
            return False
    # =========================================================================
    # QUARTO YAML PARSING & SAVING
    # =========================================================================

    def _load_quarto_yml(self):
        if not self.yaml_path.exists():
            return {"project": {"type": "book"}, "book": {"chapters": []}}
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def parse_chapters(self):
        """Konvertiert die Quarto-YAML Liste in das interne Tree-Format der GUI."""
        # 1. Versuche zuerst, den letzten GUI-Zustand (geöffnete Ordner etc.) zu laden
        gui_state = self._load_gui_state()
        if gui_state:
            return gui_state
            
        # 2. Falls kein GUI-State da ist, lade direkt aus der _quarto.yml
        config = self._load_quarto_yml()
        chapters = config.get("book", {}).get("chapters", [])
        
        def convert(items):
            res = []
            for item in items:
                if isinstance(item, str):
                    res.append({"path": item, "children": []})
                elif isinstance(item, dict):
                    # Quarto Parts/Chapters Logik
                    part_title = item.get("part") or item.get("text")
                    sub = item.get("chapters", [])
                    if part_title:
                        res.append({"path": f"PART:{part_title}", "children": convert(sub)})
                    else:
                        # Einfache Datei mit Meta-Daten
                        file_path = list(item.values())[0] if not item.get("file") else item.get("file")
                        res.append({"path": file_path, "children": []})
            return res
            
        return convert(chapters)

    def save_chapters(self, tree_data, profile_name=None, save_gui_state=True, extra_format_options=None):
        """Speichert die Baum-Struktur in _quarto.yml und injiziert Templates/Profile."""
        config = self._load_quarto_yml()
        
        # 1. Kapitel aus dem Tree konvertieren
        chapters = self._tree_to_quarto_list(tree_data)
        
        # --- FIX: index.md IMMER als erste Datei hinzufügen ---
        if "index.md" not in chapters:
            if (self.book_path / "index.md").exists():
                chapters.insert(0, "index.md")
            else:
                # Falls die Datei gar nicht existiert, erstellen wir eine minimale Version
                with open(self.book_path / "index.md", "w", encoding="utf-8") as f:
                    f.write("---\ntitle: Einleitung\n---\n\nWillkommen zu meinem Buch.")
                chapters.insert(0, "index.md")
        # -------------------------------------------------------

        # --- REQUIRED-FILE ORDERING ---
        # Extrahiert required-Dateien mit order-Frontmatter und setzt sie an Anfang/Ende.
        rest, front_required, end_required = self._apply_required_ordering(chapters)
        if front_required or end_required:
            # index.md aus rest entfernen, damit sie immer an Position 0 bleibt
            rest_without_index = [c for c in rest if c != "index.md"]
            chapters = ["index.md"] + front_required + rest_without_index + end_required
        # ------------------------------

        config["book"]["chapters"] = chapters
        
        # ... (Rest der Funktion bleibt gleich) ...
        
        # Ausgabe-Ordner basierend auf Profil anpassen
        if profile_name:
            safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', profile_name)
            config["project"]["output-dir"] = f"export/_book_{safe_name}"
        else:
            config["project"]["output-dir"] = "export/_book"

        # --- NEU: ZUSATZOPTIONEN (Templates etc.) INJIZIEREN ---
        if extra_format_options:
            if "format" not in config:
                config["format"] = {}
            for fmt, options in extra_format_options.items():
                if fmt not in config["format"]:
                    config["format"][fmt] = {}
                for key, val in options.items():
                    config["format"][fmt][key] = val
        # ---------------------------------------------------------

        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, sort_keys=False, allow_unicode=True, indent=2)
            
        if save_gui_state:
            self._save_gui_state(tree_data)

    # =========================================================================
    # REQUIRED-FILE ORDERING
    # =========================================================================

    def parse_required_order(self, rel_path):
        """
        Liest das 'order'-Feld aus dem Frontmatter einer required-Datei.

        Gültige Werte:
          "1", "2", "3" …       → Anfang des Buchs (nach index.md), aufsteigend sortiert
          "END-1", "END-2" …  → Ende des Buchs, aufsteigend sortiert

        Rückgabe: (sort_key: int, group: 'front'|'end'|None)
        """
        normalized_parts = [p.lower() for p in str(rel_path).replace("\\", "/").split("/") if p]
        if "required" not in normalized_parts:
            return None, None

        full_path = self.book_path / rel_path
        if not full_path.exists():
            return None, None

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read(12000)
            match = re.search(r'^\s*\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---', content, re.DOTALL | re.MULTILINE)
            if not match:
                return None, None
            fm = yaml.safe_load(match.group(1)) or {}
            order_val = str(fm.get("order", "")).strip().strip('"\'')
            if not order_val:
                return None, None

            end_match = re.match(r'^END\s*-\s*(\d+)$', order_val, re.IGNORECASE)
            if end_match:
                return int(end_match.group(1)), "end"
            if re.match(r'^\d+$', order_val):
                return int(order_val), "front"
        except (OSError, yaml.YAMLError, ValueError) as error:
            logger.warning("ORDER-Frontmatter konnte nicht gelesen werden (%s): %s", rel_path, error)

        return None, None

    def get_required_order(self, rel_path):
        """Öffentliche API für die ORDER-Auswertung bei required-Dateien."""
        return self.parse_required_order(rel_path)

    def _apply_required_ordering(self, chapters):
        """
        Extrahiert required-Dateien mit 'order'-Frontmatter aus der Kapitelliste
        und gibt (bereinigte Liste, front-Pfade, end-Pfade) zurück.

        Nicht-geordnete required-Dateien bleiben an ihrer GUI-Position.
        PART-Einträge werden rekursiv bereinigt.
        """
        front = []  # (sort_key, path)
        end = []    # (sort_key, path)

        def remove_ordered(items):
            cleaned = []
            for item in items:
                if isinstance(item, str):
                    sort_key, group = self.parse_required_order(item)
                    if group == "front":
                        front.append((sort_key, item))
                    elif group == "end":
                        end.append((sort_key, item))
                    else:
                        cleaned.append(item)
                elif isinstance(item, dict) and "part" in item:
                    sub = remove_ordered(item.get("chapters", []))
                    cleaned.append({**item, "chapters": sub})
                else:
                    cleaned.append(item)
            return cleaned

        cleaned = remove_ordered(chapters)
        front.sort(key=lambda x: x[0])                    # "1" < "2" < "3" → vorne
        end.sort(key=lambda x: x[0], reverse=True)        # "3" > "2" > "1" → END-1 landet ganz am Ende
        return cleaned, [p for _, p in front], [p for _, p in end]

    def _tree_to_quarto_list(self, tree_data):
        """Hilfsfunktion: Wandelt den GUI-Baum zurück in Quarto-Syntax."""
        res = []
        for item in tree_data:
            path = item["path"]
            if path.startswith("PART:"):
                res.append({
                    "part": path.replace("PART:", ""),
                    "chapters": self._tree_to_quarto_list(item["children"])
                })
            else:
                # --- DER WINDOWS-FIX ---
                # Wandelt alle Backslashes zwingend in Forward-Slashes um
                safe_path = path.replace("\\", "/")
                res.append(safe_path)
        return res

    # =========================================================================
    # GUI STATE (Sichert geöffnete Ordner & genaue GUI Struktur)
    # =========================================================================

    def _save_gui_state(self, tree_data):
        try:
            self.gui_state_path.parent.mkdir(exist_ok=True)
            with open(self.gui_state_path, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, indent=4, ensure_ascii=False)
        except (OSError, TypeError, ValueError) as error:
            logger.warning("GUI-State konnte nicht gespeichert werden (%s): %s", self.gui_state_path, error)

    def _load_gui_state(self):
        if self.gui_state_path.exists():
            try:
                with open(self.gui_state_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
                logger.warning("GUI-State konnte nicht geladen werden (%s): %s", self.gui_state_path, error)
                return None
        return None
    
    def _generate_yaml_string(self, tree_data, base_indent="  "):
        """Hilfsfunktion für den Preview-Inspektor."""
        lines = []
        for item in tree_data:
            path = item["path"]
            if path.startswith("PART:"):
                lines.append(f"{base_indent}- part: {path.replace('PART:', '')}")
                lines.append(f"{base_indent}  chapters:")
                if item.get("children"):
                    lines.append(self._generate_yaml_string(item["children"], base_indent + "    "))
            else:
                lines.append(f"{base_indent}- {path}")
        return "\n".join(lines)
    
    def generate_yaml_string(self, tree_data, base_indent="  "):
        return self._generate_yaml_string(tree_data, base_indent=base_indent)
```
