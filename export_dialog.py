import tkinter as tk
from tkinter import ttk

from dialog_dirty_utils import DirtyStateController, confirm_discard_changes
from tools.layout_profiles.catalog import (
    LINE_STRETCH_OPTIONS,
    get_profile,
    linestretch_label,
    normalize_linestretch,
    profile_id_from_label,
    profile_labels,
)
from ui_theme import center_on_parent, style_dialog


class ExportDialog(tk.Toplevel):
    def __init__(self, parent, templates, initial=None, *, book_path=None):
        super().__init__(parent)
        self._base_title = "Export & Layout"
        self.title(self._base_title)
        self._dirty_controller = DirtyStateController(self, self._base_title)
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        w, h = 520, 480
        center_on_parent(self, parent, w, h)

        self.result = None
        self.book_path = book_path
        self.templates = templates or ["Standard"]
        self.initial = initial or {}

        initial_format = self.initial.get("format", "typst")
        initial_template = self.initial.get("template", self.templates[0])
        initial_profile_id = str(self.initial.get("layout_profile") or "taschenbuch-bod")
        initial_profile = get_profile(initial_profile_id)
        initial_linestretch = normalize_linestretch(
            self.initial.get("linestretch", initial_profile.linestretch)
        )

        if initial_template not in self.templates:
            initial_template = self.templates[0]

        self.format_var = tk.StringVar(value=initial_format)
        self.template_var = tk.StringVar(value=initial_template)
        self.layout_profile_var = tk.StringVar(value=initial_profile.label)
        self.linestretch_var = tk.StringVar(value=linestretch_label(initial_linestretch))
        self._profile_hint_var = tk.StringVar(value=initial_profile.description)

        self._initial_values = {
            "format": initial_format,
            "template": initial_template,
            "layout_profile": initial_profile_id,
            "linestretch": initial_linestretch,
        }

        self.format_var.trace_add("write", self._on_field_changed)
        self.template_var.trace_add("write", self._on_field_changed)
        self.layout_profile_var.trace_add("write", self._on_profile_changed)
        self.linestretch_var.trace_add("write", self._on_field_changed)

        self._build_ui()
        self._dirty_controller.capture_initial(self._initial_values)

    def _build_ui(self):
        style_dialog(self)
        wrapper = ttk.Frame(self, padding=(16, 14))
        wrapper.pack(fill=tk.BOTH, expand=True)

        ttk.Label(wrapper, text="Export & Layout", font=("Segoe UI Semibold", 11)).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        ttk.Label(wrapper, text="Format:").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.format_var,
            values=["typst", "docx", "html", "pdf"],
            state="readonly",
            width=28,
        ).grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(wrapper, text="Template:").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(
            wrapper,
            textvariable=self.template_var,
            values=self.templates,
            state="readonly",
            width=28,
        ).grid(row=2, column=1, sticky="w", pady=6)

        layout_frame = ttk.LabelFrame(wrapper, text="Layout-Profil (nur dieser Render-Lauf)", padding=(10, 8))
        layout_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        ttk.Label(layout_frame, text="Profil:").grid(row=0, column=0, sticky="w", pady=4)
        profile_combo = ttk.Combobox(
            layout_frame,
            textvariable=self.layout_profile_var,
            values=profile_labels(),
            state="readonly",
            width=30,
        )
        profile_combo.grid(row=0, column=1, sticky="w", pady=4, padx=(8, 0))
        profile_combo.bind("<<ComboboxSelected>>", self._on_profile_changed)

        ttk.Label(layout_frame, text="Zeilenabstand:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            layout_frame,
            textvariable=self.linestretch_var,
            values=[opt.label for opt in LINE_STRETCH_OPTIONS],
            state="readonly",
            width=30,
        ).grid(row=1, column=1, sticky="w", pady=4, padx=(8, 0))

        ttk.Label(
            layout_frame,
            textvariable=self._profile_hint_var,
            wraplength=420,
            foreground="#64748b",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Label(
            layout_frame,
            text="Wird nur in die Temp-Kopie für den Render geschrieben — _quarto.yml bleibt unverändert.",
            foreground="#64748b",
            font=("Segoe UI", 8),
            wraplength=420,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        button_row = ttk.Frame(wrapper)
        button_row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(18, 0))

        ttk.Button(button_row, text="Abbrechen", style="Tool.TButton", command=self._cancel).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(button_row, text="Export starten", style="Accent.TButton", command=self._confirm).pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _selected_profile_id(self) -> str:
        return profile_id_from_label(self.layout_profile_var.get())

    def _selected_linestretch(self) -> float:
        label = self.linestretch_var.get()
        for opt in LINE_STRETCH_OPTIONS:
            if opt.label == label:
                return opt.value
        return normalize_linestretch(1.2)

    def _on_profile_changed(self, *_args):
        profile = get_profile(self._selected_profile_id())
        self._profile_hint_var.set(profile.description)
        self.linestretch_var.set(linestretch_label(profile.linestretch))
        self._on_field_changed()

    def _confirm(self):
        self.result = {
            "format": self.format_var.get(),
            "template": self.template_var.get(),
            "layout_profile": self._selected_profile_id(),
            "linestretch": self._selected_linestretch(),
        }
        self.destroy()

    def _collect_values(self):
        return {
            "format": self.format_var.get(),
            "template": self.template_var.get(),
            "layout_profile": self._selected_profile_id(),
            "linestretch": self._selected_linestretch(),
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
    def ask(parent, templates, initial=None, *, book_path=None):
        dialog = ExportDialog(parent, templates, initial=initial, book_path=book_path)
        parent.wait_window(dialog)
        return dialog.result
