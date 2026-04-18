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
