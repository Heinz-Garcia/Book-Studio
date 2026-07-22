"""Tk-Dialog: Plugin-/Tool-Konfiguration (GrammarGraph-Analog)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from services.plugin_config_registry import (
    FieldDef,
    ToolConfig,
    discover_configs,
    load_plugin_display_names,
    write_config,
)


class PluginConfigEditor(tk.Toplevel):
    """Liste links, Formular rechts — speichert in tools/*/config.toml."""

    def __init__(
        self,
        parent,
        *,
        project_root: Path,
        on_save: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.title("Plugin-Konfiguration")
        self.transient(parent)
        self.grab_set()
        self._project_root = Path(project_root)
        self._on_save = on_save
        self._configs: list[ToolConfig] = []
        self._widgets: dict[str, dict[str, dict[str, tk.Variable | ttk.Entry]]] = {}
        self._current_index: Optional[int] = None

        self.geometry("820x520")
        self.minsize(640, 400)
        self._build_ui()
        self._reload()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)

        paned = ttk.Panedwindow(outer, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, padding=(0, 0, 6, 0))
        right = ttk.Frame(paned, padding=(6, 0, 0, 0))
        paned.add(left, weight=1)
        paned.add(right, weight=3)

        ttk.Label(left, text="Tools mit config.toml").pack(anchor="w")
        self._list = tk.Listbox(left, exportselection=False, height=20)
        self._list.pack(fill="both", expand=True, pady=(4, 0))
        self._list.bind("<<ListboxSelect>>", self._on_select)

        self._form_host = ttk.Frame(right)
        self._form_host.pack(fill="both", expand=True)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Speichern", command=self._save_current).pack(side="right")
        ttk.Button(buttons, text="Schließen", command=self.destroy).pack(side="right", padx=(0, 8))

    def _reload(self) -> None:
        tools_dir = self._project_root / "tools"
        plugins_dir = self._project_root / "plugins"
        names = load_plugin_display_names(plugins_dir)
        self._configs = discover_configs(tools_dir, plugin_display_names=names)
        self._list.delete(0, "end")
        for cfg in self._configs:
            self._list.insert("end", cfg.display_name)
        for child in self._form_host.winfo_children():
            child.destroy()
        self._widgets.clear()
        self._current_index = None
        if self._configs:
            self._list.selection_set(0)
            self._on_select()
        else:
            ttk.Label(
                self._form_host,
                text="Keine tools/*/config.toml gefunden.",
            ).pack(anchor="w")

    def _on_select(self, _event=None) -> None:
        sel = self._list.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if self._current_index is not None and self._current_index != idx:
            # Werte aus Widgets zurück in die Datenstruktur spiegeln
            self._harvest_widgets(self._current_index)
        self._current_index = idx
        self._render_form(self._configs[idx])

    def _render_form(self, config: ToolConfig) -> None:
        for child in self._form_host.winfo_children():
            child.destroy()
        self._widgets[config.tool_id] = {}

        canvas = tk.Canvas(self._form_host, highlightthickness=0)
        scroll = ttk.Scrollbar(self._form_host, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        ttk.Label(
            inner,
            text=f"{config.display_name}\n{config.config_path}",
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        for section_name, section in config.sections.items():
            box = ttk.LabelFrame(inner, text=section_name or "(ohne Sektion)", padding=8)
            box.pack(fill="x", pady=4)
            self._widgets[config.tool_id][section_name] = {}
            for key, field_def in section.fields.items():
                row = ttk.Frame(box)
                row.pack(fill="x", pady=2)
                ttk.Label(row, text=key, width=22).pack(side="left")
                widget = self._make_field_widget(row, field_def)
                self._widgets[config.tool_id][section_name][key] = widget
                if field_def.comment:
                    ttk.Label(row, text=field_def.comment, foreground="#555").pack(
                        side="left", padx=(8, 0)
                    )

    def _make_field_widget(self, parent, field_def: FieldDef):
        if field_def.field_type == "bool":
            var = tk.BooleanVar(value=bool(field_def.value))
            ttk.Checkbutton(parent, variable=var).pack(side="left")
            return var
        if field_def.field_type in {"int", "float"}:
            var = tk.StringVar(value=str(field_def.value))
            ttk.Entry(parent, textvariable=var, width=28).pack(side="left")
            return var
        # string / array: als Text
        if field_def.field_type == "array":
            text = ", ".join(str(v) for v in (field_def.value or []))
        else:
            text = str(field_def.value if field_def.value is not None else "")
        if "\n" in text or len(text) > 60:
            frame = ttk.Frame(parent)
            frame.pack(side="left", fill="x", expand=True)
            widget = tk.Text(frame, height=4, width=48, wrap="word")
            widget.insert("1.0", text)
            widget.pack(fill="x", expand=True)
            return widget
        var = tk.StringVar(value=text)
        ttk.Entry(parent, textvariable=var, width=40).pack(side="left")
        return var

    def _harvest_widgets(self, index: int) -> None:
        config = self._configs[index]
        tool_widgets = self._widgets.get(config.tool_id) or {}
        for section_name, section in config.sections.items():
            section_widgets = tool_widgets.get(section_name) or {}
            for key, field_def in section.fields.items():
                widget = section_widgets.get(key)
                if widget is None:
                    continue
                field_def.value = self._read_widget_value(widget, field_def)

    def _read_widget_value(self, widget, field_def: FieldDef) -> Any:
        if isinstance(widget, tk.BooleanVar):
            return bool(widget.get())
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end-1c")
        raw = widget.get() if hasattr(widget, "get") else ""
        if field_def.field_type == "int":
            try:
                return int(str(raw).strip())
            except ValueError:
                return field_def.value
        if field_def.field_type == "float":
            try:
                return float(str(raw).strip())
            except ValueError:
                return field_def.value
        if field_def.field_type == "array":
            parts = [p.strip() for p in str(raw).split(",") if p.strip()]
            return parts
        return str(raw)

    def _save_current(self) -> None:
        if self._current_index is None:
            messagebox.showinfo("Plugin-Konfiguration", "Kein Tool ausgewählt.")
            return
        self._harvest_widgets(self._current_index)
        config = self._configs[self._current_index]
        try:
            write_config(config.config_path, config.sections)
        except OSError as exc:
            messagebox.showerror("Plugin-Konfiguration", f"Speichern fehlgeschlagen:\n{exc}")
            return
        if callable(self._on_save):
            self._on_save()
        messagebox.showinfo(
            "Plugin-Konfiguration",
            f"Gespeichert:\n{config.config_path}",
        )


__all__ = ["PluginConfigEditor"]
