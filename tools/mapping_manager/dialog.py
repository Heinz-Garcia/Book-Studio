"""Tk-Dialog: Mapping Manager (Publish-Input → PDFs)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import tkinter as tk
from tkinter import messagebox, ttk

from tools.mapping_manager.actions import delete_pdf, open_path, reveal_in_explorer
from tools.mapping_manager.loader import load_renders, load_snapshots
from tools.mapping_manager.models import RenderView, SnapshotView
from tools.publish_map.store import remove_render
from ui_theme import COLORS, FONTS, style_dialog

_OPEN_ICON = "\uE8A7" if sys.platform.startswith("win") else "\u2197"
_DELETE_ICON = "\uE74D" if sys.platform.startswith("win") else "\u00D7"
_ACTION_ICON_FONT = (
    ("Segoe MDL2 Assets", 12)
    if sys.platform.startswith("win")
    else ("Segoe UI", 10, "bold")
)


class MappingManagerDialog:
    def __init__(self, studio: Any) -> None:
        self.studio = studio
        self._window: Optional[tk.Toplevel] = None
        self._snapshots: list[SnapshotView] = []
        self._renders: list[RenderView] = []
        self._snapshot_var: Optional[tk.StringVar] = None
        self._tree: Optional[ttk.Treeview] = None

    def show(self) -> None:
        parent = getattr(self.studio, "root", None)
        if parent is None:
            return
        if not getattr(self.studio, "current_book", None):
            messagebox.showwarning("Mapping Manager", "Kein Buchprojekt aktiv.", parent=parent)
            return
        self._open_window(parent)

    def _book_path(self) -> Path:
        return Path(self.studio.current_book)

    def _open_window(self, parent: tk.Misc) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            return

        win = tk.Toplevel(parent)
        self._window = win
        style_dialog(win, title="Mapping Manager")
        win.geometry("980x520")
        win.minsize(760, 400)

        header = ttk.Frame(win, padding=(12, 10, 12, 6))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Publish-Input → generierte PDFs",
            font=FONTS.get("title", ("Segoe UI Semibold", 11)),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Produktionslinien (Snapshots) mit zugehörigen Render-Läufen — Metadaten aus publish_map.json",
            foreground=COLORS.get("text_muted", "#64748b"),
        ).pack(anchor="w", pady=(2, 0))

        selector = ttk.Frame(win, padding=(12, 4, 12, 4))
        selector.pack(fill="x")
        ttk.Label(selector, text="Produktionslinie:").pack(side="left")
        self._snapshot_var = tk.StringVar()
        self._snapshot_combo = ttk.Combobox(
            selector,
            textvariable=self._snapshot_var,
            state="readonly",
            width=72,
        )
        self._snapshot_combo.pack(side="left", padx=(8, 0), fill="x", expand=True)
        self._snapshot_combo.bind("<<ComboboxSelected>>", lambda _e: self._reload_renders())

        body = ttk.Frame(win, padding=(12, 6, 12, 6))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        columns = ("pdf", "template", "format", "profile", "date", "status")
        tree = ttk.Treeview(body, columns=columns, show="headings", selectmode="browse", height=14)
        self._tree = tree
        tree.heading("pdf", text="PDF")
        tree.heading("template", text="Template")
        tree.heading("format", text="Format")
        tree.heading("profile", text="Profil")
        tree.heading("date", text="Datum")
        tree.heading("status", text="Status")
        tree.column("pdf", width=260, stretch=True)
        tree.column("template", width=160, stretch=False)
        tree.column("format", width=70, stretch=False)
        tree.column("profile", width=90, stretch=False)
        tree.column("date", width=120, stretch=False)
        tree.column("status", width=80, stretch=False)

        scroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        tree.bind("<Double-1>", lambda _e: self._open_selected())
        tree.bind("<Return>", lambda _e: self._open_selected())

        footer = ttk.Frame(win, padding=(12, 6, 12, 12))
        footer.pack(fill="x")
        ttk.Button(footer, text="Schließen", command=win.destroy).pack(side="right")
        ttk.Button(footer, text="Aktualisieren", command=self._reload_all).pack(side="right", padx=(0, 8))
        ttk.Button(footer, text="Löschen", command=self._delete_selected).pack(side="right", padx=(0, 8))
        ttk.Button(footer, text="Ordner zeigen", command=self._reveal_selected).pack(side="right", padx=(0, 8))
        ttk.Button(footer, text="PDF öffnen", command=self._open_selected).pack(side="right", padx=(0, 8))

        self._reload_all()
        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def _current_snapshot(self) -> Optional[SnapshotView]:
        label = self._snapshot_var.get() if self._snapshot_var else ""
        for snap in self._snapshots:
            if snap.label == label:
                return snap
        return self._snapshots[0] if self._snapshots else None

    def _reload_all(self) -> None:
        self._snapshots = load_snapshots(self._book_path())
        labels = [s.label for s in self._snapshots]
        self._snapshot_combo["values"] = labels
        if labels:
            current = self._snapshot_var.get() if self._snapshot_var else ""
            if current not in labels:
                self._snapshot_var.set(labels[-1])
        else:
            self._snapshot_var.set("")
        self._reload_renders()

    def _reload_renders(self) -> None:
        tree = self._tree
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        snap = self._current_snapshot()
        if snap is None:
            return
        self._renders = load_renders(self._book_path(), snap.id)
        for render in self._renders:
            status = "OK" if render.exists else "fehlt"
            tree.insert(
                "",
                "end",
                values=(
                    render.pdf_name,
                    render.template or "—",
                    render.format or "—",
                    render.profile_name or "—",
                    render.at_display,
                    status,
                ),
            )

    def _selected_render(self) -> Optional[RenderView]:
        tree = self._tree
        if tree is None:
            return None
        selected = tree.selection()
        if not selected:
            return None
        idx = tree.index(selected[0])
        if 0 <= idx < len(self._renders):
            return self._renders[idx]
        return None

    def _open_selected(self) -> None:
        render = self._selected_render()
        if render is None:
            messagebox.showinfo("Mapping Manager", "Bitte eine PDF-Zeile auswählen.", parent=self._window)
            return
        if not render.exists:
            messagebox.showwarning(
                "Mapping Manager",
                f"Datei nicht gefunden:\n{render.pdf_path}",
                parent=self._window,
            )
            return
        try:
            open_path(render.pdf_path)
        except OSError as exc:
            messagebox.showerror("Mapping Manager", f"Öffnen fehlgeschlagen:\n{exc}", parent=self._window)

    def _reveal_selected(self) -> None:
        render = self._selected_render()
        if render is None or not render.pdf_path:
            export_dir = self._book_path() / "export"
            if export_dir.is_dir():
                reveal_in_explorer(export_dir)
            return
        try:
            reveal_in_explorer(render.pdf_path)
        except OSError as exc:
            messagebox.showerror("Mapping Manager", f"Explorer fehlgeschlagen:\n{exc}", parent=self._window)

    def _delete_selected(self) -> None:
        render = self._selected_render()
        snap = self._current_snapshot()
        if render is None or snap is None:
            messagebox.showinfo("Mapping Manager", "Bitte eine PDF-Zeile auswählen.", parent=self._window)
            return
        if not messagebox.askyesno(
            "Mapping Manager",
            f"PDF wirklich löschen?\n\n{render.pdf_path}",
            parent=self._window,
        ):
            return
        try:
            if render.exists:
                delete_pdf(render.pdf_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Mapping Manager", str(exc), parent=self._window)
            return
        remove_render(self._book_path(), snap.id, render.id)
        self._reload_renders()


def open_mapping_manager_dialog(studio: Any, **kwargs) -> None:
    MappingManagerDialog(studio).show()
