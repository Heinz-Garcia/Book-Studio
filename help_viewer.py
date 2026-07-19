"""Integrierte HTML-Hilfe mit Inhaltsverzeichnis und Suchfeld."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from tools.handbook_html import HelpSection, build_handbook_html, filter_sections
from ui_theme import COLORS, FONTS, center_on_parent, style_dialog


class HelpViewer(tk.Toplevel):
    """Read-only Hilfe-Fenster: Suche + TOC + HTML-Inhalt."""

    def __init__(
        self,
        parent: tk.Misc,
        html_path: Path,
        *,
        md_path: Path | None = None,
        sections: list[HelpSection] | None = None,
    ) -> None:
        super().__init__(parent)
        self.html_path = Path(html_path).resolve()
        self.md_path = Path(md_path).resolve() if md_path else None
        self._sections: list[HelpSection] = list(sections or [])
        self._filtered: list[HelpSection] = []
        self._html_widget = None

        self.title("Hilfe — Quarto Book Studio")
        center_on_parent(self, parent, 960, 720)
        self.configure(bg=COLORS.get("app_bg", "#edf3f8"))
        style_dialog(self)

        if not self._sections:
            self._sections = self._load_sections()

        self._build_ui()
        self._apply_filter("")
        self._load_html()
        self.search_entry.focus_set()

    def _load_sections(self) -> list[HelpSection]:
        if self.md_path and self.md_path.is_file():
            _, sections = build_handbook_html(self.md_path.read_text(encoding="utf-8"))
            return sections
        return self._sections_from_html_file()

    def _sections_from_html_file(self) -> list[HelpSection]:
        """Fallback: IDs/Titel aus h1–h3 im HTML lesen (ohne Fließtext-Index)."""
        import re

        text = self.html_path.read_text(encoding="utf-8")
        found: list[HelpSection] = []
        for match in re.finditer(
            r"<h([1-3])\s+id=\"([^\"]+)\">(.+?)</h\1>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            level = int(match.group(1))
            sid = match.group(2)
            title = re.sub(r"<[^>]+>", "", match.group(3)).strip()
            found.append(HelpSection(id=sid, title=title, level=level, text=title))
        return found

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text="Suche:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=(6, 8), fill=tk.X, expand=True)
        self.search_var.trace_add("write", lambda *_: self._apply_filter(self.search_var.get()))

        ttk.Button(toolbar, text="Schließen", command=self.destroy).pack(side=tk.RIGHT)

        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(body, padding=4)
        body.add(left, weight=1)
        ttk.Label(left, text="Inhalt", font=FONTS.get("title", ("Segoe UI", 10, "bold"))).pack(
            anchor=tk.W
        )
        list_frame = ttk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.toc_list = tk.Listbox(
            list_frame,
            exportselection=False,
            activestyle="dotbox",
            font=FONTS.get("ui", ("Segoe UI", 10)),
            bg=COLORS.get("surface", "#ffffff"),
            fg=COLORS.get("text", "#1f2937"),
            selectbackground=COLORS.get("accent_soft", "#dbeafe"),
            selectforeground=COLORS.get("accent_text", "#1d4ed8"),
            borderwidth=1,
            relief=tk.SOLID,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.toc_list.yview)
        self.toc_list.configure(yscrollcommand=scroll.set)
        self.toc_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.toc_list.bind("<<ListboxSelect>>", self._on_toc_select)
        self.toc_list.bind("<Double-Button-1>", self._on_toc_select)

        right = ttk.Frame(body, padding=4)
        body.add(right, weight=3)
        self._html_host = right
        self._status = ttk.Label(self, text="", anchor=tk.W, padding=(10, 4))
        self._status.pack(fill=tk.X)

    def _load_html(self) -> None:
        for child in self._html_host.winfo_children():
            child.destroy()
        try:
            from tkinterweb import HtmlFrame
        except ImportError:
            ttk.Label(
                self._html_host,
                text=(
                    "Paket 'tkinterweb' fehlt.\n\n"
                    "Bitte installieren:\n  pip install tkinterweb\n\n"
                    f"HTML-Datei:\n{self.html_path}"
                ),
                justify=tk.LEFT,
            ).pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
            self._html_widget = None
            return

        frame = HtmlFrame(self._html_host, messages_enabled=False)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.load_file(str(self.html_path))
        self._html_widget = frame

    def _apply_filter(self, query: str) -> None:
        self._filtered = filter_sections(self._sections, query)
        self.toc_list.delete(0, tk.END)
        for section in self._filtered:
            indent = "  " * max(0, section.level - 1)
            self.toc_list.insert(tk.END, f"{indent}{section.title}")
        q = (query or "").strip()
        if q:
            self._status.configure(text=f"{len(self._filtered)} Treffer für „{q}“")
        else:
            self._status.configure(text=f"{len(self._filtered)} Abschnitte")

    def _on_toc_select(self, _event=None) -> None:
        selection = self.toc_list.curselection()
        if not selection:
            return
        index = int(selection[0])
        if index < 0 or index >= len(self._filtered):
            return
        section = self._filtered[index]
        self._jump_to_section(section.id)

    def _jump_to_section(self, section_id: str) -> None:
        widget = self._html_widget
        if widget is None:
            return
        # tkinterweb: Fragment laden bzw. Element anspringen
        try:
            widget.load_file(f"{self.html_path.as_uri()}#{section_id}")
            return
        except (OSError, TypeError, AttributeError, RuntimeError, ValueError):
            pass
        try:
            widget.load_file(str(self.html_path))
            html = getattr(widget, "html", None) or getattr(widget, "document", None)
            if html is not None and hasattr(html, "getElementById"):
                node = html.getElementById(section_id)
                if node is not None and hasattr(node, "scrollIntoView"):
                    node.scrollIntoView()
        except (OSError, TypeError, AttributeError, RuntimeError, ValueError):
            messagebox.showinfo(
                "Hilfe",
                f"Abschnitt „{section_id}“ konnte nicht angesprungen werden.",
                parent=self,
            )


__all__ = ["HelpViewer"]
