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

        self.studio.status = tk.Label(footer, text="Bereit.", bg=COLORS["panel_dark"], fg="#cbd5e1", font=("Consolas", 9))
        self.studio.status.pack(side=tk.RIGHT, padx=20)
        return footer

    def _add_middle_buttons(self, middle_frame):
        button_specs = [
            {"text": "Hinzufügen ➡️", "style": "Accent.TButton", "command": self.studio.add_files, "pack": {"pady": (36, 6)}},
            {"text": "⬅️ Entfernen", "style": "Soft.TButton", "command": self.studio.remove_files, "pack": {}},
            {"separator": True, "options": {"height": 20, "bg": COLORS["app_bg"]}},
            {"text": "⬆️ Hoch", "command": self.studio.move_up, "pack": {"pady": 2}},
            {"text": "⬇️ Runter", "command": self.studio.move_down, "pack": {"pady": 2}},
            {"text": "➡️ Einrücken", "command": self.studio.indent_item, "pack": {"pady": (10, 2)}},
            {"text": "⬅️ Ausrücken", "command": self.studio.outdent_item, "pack": {"pady": 2}},
            {"separator": True, "ttk": True},
            {"text": "↩️ Undo (Strg+Z)", "style": "Tool.TButton", "command": self.studio.undo, "pack": {"pady": 2}},
            {"text": "↪️ Redo (Strg+Y)", "style": "Tool.TButton", "command": self.studio.redo, "pack": {"pady": 2}},
        ]

        for spec in button_specs:
            if spec.get("separator"):
                if spec.get("ttk"):
                    ttk.Separator(middle_frame, orient="horizontal").pack(fill="x", pady=15, padx=10)
                else:
                    tk.Frame(middle_frame, **spec["options"]).pack()
                continue

            self._create_button(middle_frame, spec)

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
        outer.pack(fill=tk.X, side=tk.BOTTOM)
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
            textvariable=self.studio.log_filter_var,
            values=self.studio.log_filter_labels,
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
            textvariable=self.studio.log_max_lines_var,
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
            variable=self.studio.log_auto_clear_var,
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
        self.studio.log_output = ScrolledText(
            outer,
            state="disabled", wrap=tk.WORD,
        )
        style_code_text(self.studio.log_output)
        self.studio.log_output.configure(font=("Consolas", 9), padx=8, pady=6, state="disabled")
        self.studio.log_output.pack(fill=tk.BOTH, expand=True)
        self.studio.log_output.bind("<Button-3>", self._show_log_menu)

        # Farb-Tags definieren
        w = self.studio.log_output
        w.tag_configure("info",    foreground="#c9d1d9")
        w.tag_configure("success", foreground="#3fb950")
        w.tag_configure("error",   foreground="#f85149")
        w.tag_configure("warning", foreground="#d29922")
        w.tag_configure("header",  foreground="#58a6ff")
        w.tag_configure("dim",     foreground="#484f58")

        self.studio.log_menu = tk.Menu(self.studio.root, tearoff=0)
        apply_menu_theme(self.studio.log_menu)
        self.studio.log_menu.add_command(label="Kopieren", command=self._copy_log)
        self.studio.log_menu.add_command(label="Alles kopieren", command=lambda: self._copy_log(copy_all=True))
        self.studio.log_menu.add_separator()
        self.studio.log_menu.add_command(label="Leeren", command=self._clear_log)

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
        self.studio.on_log_preferences_changed()

    def _clear_log(self):
        self.studio.clear_log()

    def _copy_log(self, copy_all=False):
        self.studio.copy_log_to_clipboard(copy_all=copy_all)

    def _show_log_menu(self, event):
        try:
            self.studio.log_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.studio.log_menu.grab_release()
