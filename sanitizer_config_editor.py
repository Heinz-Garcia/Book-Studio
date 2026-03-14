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

        self.config_data = self._load_config_with_defaults()
        self.schema = self._build_runtime_schema(self.config_data)
        self._build_ui()
        self._capture_initial_dirty_snapshot()
        self._start_dirty_watch()

    def _load_config_with_defaults(self):
        data = {}
        if self.config_path.exists() and tomllib is not None:
            try:
                with open(self.config_path, "rb") as f:
                    loaded = tomllib.load(f)
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, ValueError):
                data = {}

        merged = {}
        for section_name, section_schema in SANITIZER_SCHEMA.items():
            current_section = data.get(section_name, {})
            merged_section = {}
            for key, spec in section_schema.items():
                if key == "__meta__":
                    continue
                merged_section[key] = current_section.get(key, spec.get("default"))
            for key, value in current_section.items():
                if key not in merged_section:
                    merged_section[key] = value
            merged[section_name] = merged_section
        for section_name, section_data in data.items():
            if section_name not in merged and isinstance(section_data, dict):
                merged[section_name] = dict(section_data)
        return merged

    def _build_runtime_schema(self, config_data):
        runtime_schema = {}
        section_names = list(SANITIZER_SCHEMA.keys())
        for section_name in config_data.keys():
            if section_name not in section_names:
                section_names.append(section_name)

        for section_name in section_names:
            base_section = SANITIZER_SCHEMA.get(section_name, {})
            config_section = config_data.get(section_name, {})
            section_schema = dict(base_section)
            if "__meta__" not in section_schema:
                section_schema["__meta__"] = {
                    "label": section_name.replace("_", " ").title(),
                    "doc": "Benutzerdefinierte TOML-Sektion ohne hinterlegte Dokumentation.",
                }

            for key, value in config_section.items():
                if key not in section_schema:
                    inferred_type = self._infer_type(value)
                    section_schema[key] = {
                        "type": inferred_type,
                        "label": key,
                        "doc": "Benutzerdefinierter TOML-Eintrag ohne hinterlegte Dokumentation.",
                        "default": value,
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
            self._add_tag_row(key, value, spec.get("doc", "Benutzerdefinierter Tag-Eintrag."))

        ttk.Button(body, text="+ Eintrag hinzufügen", style="Tool.TButton", command=lambda: self._add_tag_row("", "", "Benutzerdefinierter Tag-Eintrag.")).pack(anchor="w", pady=(8, 0))

    def _add_tag_row(self, key, value, doc_text):
        row = tk.Frame(self.tags_rows_frame, bg=COLORS["app_bg"])
        row.pack(fill=tk.X, pady=2)

        key_var = tk.StringVar(value=key)
        value_var = tk.StringVar(value=value)

        key_entry = ttk.Entry(row, textvariable=key_var, width=20)
        key_entry.pack(side=tk.LEFT, padx=(0, 8))
        value_entry = ttk.Entry(row, textvariable=value_var)
        value_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        remove_btn = ttk.Button(row, text="Entfernen", style="Tool.TButton", command=lambda: self._remove_tag_row(row))
        remove_btn.pack(side=tk.LEFT, padx=(8, 0))

        ThemedTooltip(key_entry, doc_text)
        ThemedTooltip(value_entry, doc_text)
        ThemedTooltip(remove_btn, "Entfernt diesen Tag-Eintrag aus der Konfiguration.")

        self.tag_rows.append({
            "frame": row,
            "key_var": key_var,
            "value_var": value_var,
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
        lines = ["# Sanitizer-Konfiguration für Quarto/Pandoc -> Typst Pipeline", ""]
        section_names = list(self.schema.keys())
        for section_name in config.keys():
            if section_name not in section_names:
                section_names.append(section_name)

        for idx, section_name in enumerate(section_names):
            section_data = config.get(section_name, {})
            section_schema = self.schema.get(section_name, {})
            meta = section_schema.get("__meta__", {})

            if meta.get("doc"):
                for line in meta["doc"].splitlines():
                    lines.append(f"# {line}")
            lines.append(f"[{section_name}]")

            ordered_keys = [key for key in section_schema.keys() if key != "__meta__"]
            for key in section_data.keys():
                if key not in ordered_keys:
                    ordered_keys.append(key)

            for key in ordered_keys:
                if key not in section_data:
                    continue
                spec = section_schema.get(key, {})
                doc = spec.get("doc")
                if doc:
                    for line in doc.splitlines():
                        lines.append(f"# {line}")
                lines.append(f"{key} = {self._to_toml_value(section_data[key])}")

            if idx < len(section_names) - 1:
                lines.append("")

        lines.append("")
        return "\n".join(lines)

    def _to_toml_value(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
