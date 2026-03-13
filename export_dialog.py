import tkinter as tk
from tkinter import ttk
from ui_theme import center_on_parent, style_dialog


class ExportDialog(tk.Toplevel):
    def __init__(self, parent, templates, initial=None):
        super().__init__(parent)
        self.title("Export-Optionen")
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

        self._build_ui()

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
            values=["endnotes", "pandoc"],
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

    def _cancel(self):
        self.result = None
        self.destroy()

    @staticmethod
    def ask(parent, templates, initial=None):
        dialog = ExportDialog(parent, templates, initial=initial)
        parent.wait_window(dialog)
        return dialog.result
