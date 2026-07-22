"""Tk-Dialog: Mapping Manager (Publish-Input → PDFs).

Die Render-Tabelle ist ein handgebautes Frame/Canvas-Layout (kein
`ttk.Treeview`) — analog zu `tools/generated_books/dialog.py`, dem
Vorgänger-Plugin. Grund: ein `ttk.Treeview` kann keine echten Widgets
(Buttons, Entry) in einzelnen Zellen einbetten; die Spalten "Aktionen"
(Öffnen/Ordner/Umbenennen/Löschen) und "Notiz" (editierbares Textfeld)
brauchen das aber.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from tools.mapping_manager.actions import (
    delete_pdf,
    open_path,
    rename_pdf,
    reveal_in_explorer,
)
from tools.mapping_manager.loader import load_renders, load_snapshots
from tools.mapping_manager.models import RenderView, SnapshotView, layout_profile_label
from tools.publish_map.store import remove_render, update_render_fields
from ui_theme import COLORS, FONTS, style_dialog

# Windows: Segoe MDL2 — kein Emoji.
_OPEN_ICON = "" if sys.platform.startswith("win") else "↗"
_REVEAL_ICON = "" if sys.platform.startswith("win") else "▤"
_RENAME_ICON = "" if sys.platform.startswith("win") else "✎"
_DELETE_ICON = "" if sys.platform.startswith("win") else "×"
_ACTION_ICON_FONT = (
    ("Segoe MDL2 Assets", 12)
    if sys.platform.startswith("win")
    else ("Segoe UI", 10, "bold")
)

_ACTION_STYLES = {
    "primary": {
        "bg": COLORS["accent_soft"],
        "fg": COLORS["accent_text"],
        "activebackground": "#bfdbfe",
        "activeforeground": COLORS["accent_text"],
        "border": "#93c5fd",
    },
    "muted": {
        "bg": COLORS["surface_muted"],
        "fg": COLORS["heading"],
        "activebackground": COLORS["border"],
        "activeforeground": COLORS["text"],
        "border": COLORS["border"],
    },
}

_ROW_PADY = 2
_ROW_HEIGHT = 30
_PDF_NAME_MAX_LEN = 40


def _truncate_filename(name: str, max_len: int = _PDF_NAME_MAX_LEN) -> str:
    """Kürzt lange Dateinamen in der Mitte (Endung bleibt sichtbar, z. B.
    für die zeitstempel-eindeutigen Namen aus dem Publish-Renders-Archiv).
    Der volle Name bleibt über den Tooltip zugänglich. Ohne diese Kürzung
    würde eine sehr lange Zeile die PDF-Spalte über ihre Breite hinaus
    treiben."""
    if len(name) <= max_len:
        return name
    stem, dot, suffix = name.rpartition(".")
    if not dot:
        stem, suffix = name, ""
    suffix_display = f".{suffix}" if suffix else ""
    budget = max_len - len(suffix_display) - 1
    if budget <= 0:
        return name[: max_len - 1] + "…"
    head = (budget + 1) // 2
    tail = budget - head
    tail_part = stem[-tail:] if tail > 0 else ""
    return f"{stem[:head]}…{tail_part}{suffix_display}"


class MappingManagerDialog:
    def __init__(self, studio: Any) -> None:
        self.studio = studio
        self._window: Optional[tk.Toplevel] = None
        self._snapshots: list[SnapshotView] = []
        self._renders: list[RenderView] = []
        self._snapshot_var: Optional[tk.StringVar] = None
        self._canvas: Optional[tk.Canvas] = None
        self._rows_host: Optional[tk.Frame] = None
        self._row_frames: dict[str, tk.Frame] = {}
        self._note_vars: dict[str, tk.StringVar] = {}
        self._note_entries: dict[str, tk.Entry] = {}
        self._selected_render_id: Optional[str] = None

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

    def _configure_table_grid(self, widget: tk.Misc) -> None:
        widget.columnconfigure(0, weight=1, minsize=200)   # pdf
        widget.columnconfigure(1, minsize=130, weight=0)   # layout
        widget.columnconfigure(2, minsize=120, weight=0)   # template
        widget.columnconfigure(3, minsize=60, weight=0)    # format
        widget.columnconfigure(4, minsize=80, weight=0)    # profile
        widget.columnconfigure(5, minsize=110, weight=0)   # date
        widget.columnconfigure(6, minsize=60, weight=0)    # status
        widget.columnconfigure(7, weight=1, minsize=160)   # notes
        widget.columnconfigure(8, minsize=130, weight=0)   # actions

    def _open_window(self, parent: tk.Misc) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            return

        win = tk.Toplevel(parent)
        self._window = win
        style_dialog(win, title="Mapping Manager")
        win.geometry("1320x560")
        win.minsize(1100, 420)

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

        table_shell = ttk.Frame(win, padding=(12, 6, 12, 6))
        table_shell.pack(fill="both", expand=True)

        # Header und Scroll-Bereich teilen sich DIESELBE Grid-Spalte 0 in
        # body, mit der Scrollbar konsequent in Spalte 1 — nur so haben
        # Header- und Datenspalten garantiert exakt dieselbe Breite (sonst
        # ist die Kopfzeile um die Breite der Scrollbar breiter als die
        # Datenzeilen darunter, und "Datum"/"Status" laufen sichtbar
        # auseinander).
        body = ttk.Frame(table_shell)
        body.pack(fill="both", expand=True)
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)

        table_header = tk.Frame(body, bg=COLORS["surface_muted"], height=28)
        table_header.grid(row=0, column=0, sticky="ew")
        table_header.grid_propagate(False)
        self._configure_table_grid(table_header)
        for col, text in enumerate(
            ("PDF", "Layout-Profil", "Template", "Format", "Profil", "Datum", "Status", "Notiz", "Aktionen")
        ):
            tk.Label(
                table_header,
                text=text,
                bg=COLORS["surface_muted"],
                fg=COLORS["heading"],
                font=FONTS["ui_semibold_small"],
                anchor="w" if col not in (8,) else "center",
            ).grid(row=0, column=col, sticky="ew", padx=(8 if col == 0 else 4, 4), pady=4)

        ttk.Separator(body, orient="horizontal").grid(row=0, column=0, columnspan=2, sticky="sew")

        self._canvas = tk.Canvas(body, highlightthickness=0, borderwidth=0, bg=COLORS["surface"])
        scroll = ttk.Scrollbar(body, orient="vertical", command=self._canvas.yview)
        self._rows_host = tk.Frame(self._canvas, bg=COLORS["surface"])
        self._configure_table_grid(self._rows_host)
        self._rows_host.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        canvas_window = self._canvas.create_window((0, 0), window=self._rows_host, anchor="nw")
        self._canvas.configure(yscrollcommand=scroll.set)
        self._canvas.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, rowspan=2, sticky="ns")
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfigure(canvas_window, width=e.width),
        )
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

        footer = ttk.Frame(win, padding=(12, 6, 12, 12))
        footer.pack(fill="x")
        ttk.Button(footer, text="Schließen", command=win.destroy).pack(side="right")
        ttk.Button(footer, text="Aktualisieren", command=self._reload_all).pack(side="right", padx=(0, 8))
        ttk.Button(footer, text="Löschen", command=self._delete_selected).pack(side="right", padx=(0, 8))
        ttk.Button(footer, text="Umbenennen", command=self._rename_selected).pack(side="right", padx=(0, 8))
        ttk.Button(footer, text="Ordner zeigen", command=self._reveal_selected).pack(side="right", padx=(0, 8))
        ttk.Button(footer, text="PDF öffnen", command=self._open_selected).pack(side="right", padx=(0, 8))

        self._reload_all()
        win.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        win = self._window
        if win is None:
            return
        try:
            win.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        win.destroy()

    def _on_mousewheel(self, event) -> None:
        canvas = self._canvas
        if canvas is None or not str(canvas.winfo_exists()) == "1":
            return
        delta = int(-1 * (event.delta / 120))
        canvas.yview_scroll(delta, "units")

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

    # --- Tabellen-Rendering (Frame pro Zeile, s. generated_books/dialog.py) --

    def _make_action_button(self, parent: tk.Frame, *, icon: str, command, variant: str) -> tk.Button:
        style = _ACTION_STYLES[variant]
        return tk.Button(
            parent,
            text=icon,
            command=command,
            bg=style["bg"],
            fg=style["fg"],
            activebackground=style["activebackground"],
            activeforeground=style["activeforeground"],
            bd=0,
            relief="flat",
            overrelief="flat",
            font=_ACTION_ICON_FONT,
            padx=3,
            pady=0,
            width=2,
            height=1,
            highlightthickness=1,
            highlightbackground=style["border"],
            highlightcolor=style["border"],
            cursor="hand2",
        )

    def _row_bg(self, row_idx: int, selected: bool) -> str:
        if selected:
            return COLORS["accent_soft"]
        return COLORS["surface"] if row_idx % 2 == 0 else COLORS["surface_alt"]

    def _select_render(self, render_id: str) -> None:
        self._selected_render_id = render_id
        self._repaint_row_backgrounds()

    def _repaint_row_backgrounds(self) -> None:
        for idx, render in enumerate(self._renders):
            row = self._row_frames.get(render.id)
            if row is None:
                continue
            bg = self._row_bg(idx, render.id == self._selected_render_id)
            row.configure(bg=bg)
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=bg)

    def _reload_renders(self) -> None:
        rows_host = self._rows_host
        if rows_host is None:
            return
        for child in rows_host.winfo_children():
            child.destroy()
        self._row_frames.clear()
        self._note_vars.clear()
        self._note_entries.clear()

        snap = self._current_snapshot()
        self._renders = load_renders(self._book_path(), snap.id) if snap is not None else []

        if not self._renders:
            tk.Label(
                rows_host,
                text="Noch keine Renders für diese Produktionslinie.",
                bg=COLORS["surface"],
                fg=COLORS["text_muted"],
                font=FONTS["ui_small"],
                anchor="w",
            ).grid(row=0, column=0, columnspan=9, sticky="w", padx=8, pady=12)
            self._selected_render_id = None
            return

        valid_ids = {r.id for r in self._renders}
        if self._selected_render_id not in valid_ids:
            self._selected_render_id = None

        for row_idx, render in enumerate(self._renders):
            selected = render.id == self._selected_render_id
            bg = self._row_bg(row_idx, selected)
            status = "OK" if render.exists else "fehlt"

            # Feste Höhe + grid_propagate(False): die Zeile darf NICHT
            # mitwachsen, egal wie lang ein Dateiname oder Notiz-Text ist —
            # sonst würde die vertikale Ausrichtung zwischen Zeilen von der
            # Textlänge abhängen. Lange Dateinamen werden stattdessen
            # gekürzt (siehe _truncate_filename) statt zu umbrechen.
            row = tk.Frame(rows_host, bg=bg, height=_ROW_HEIGHT)
            row.grid(row=row_idx * 2, column=0, columnspan=9, sticky="ew")
            row.grid_propagate(False)
            self._configure_table_grid(row)
            self._row_frames[render.id] = row

            values = (
                _truncate_filename(render.pdf_name),
                layout_profile_label(render.layout_profile),
                render.template or "—",
                render.format or "—",
                render.profile_name or "—",
                render.at_display,
                status,
            )
            for col, text in enumerate(values):
                lbl = tk.Label(
                    row,
                    text=text,
                    bg=bg,
                    fg=COLORS["text"],
                    font=FONTS["ui"],
                    anchor="w",
                )
                lbl.grid(row=0, column=col, sticky="ew", padx=(8 if col == 0 else 4, 4), pady=_ROW_PADY)
                lbl.bind("<Button-1>", lambda _e, rid=render.id: self._select_render(rid))
                if col == 0:
                    lbl.bind("<Double-1>", lambda _e, rid=render.id: self._open_by_id(rid))
                    if text != render.pdf_name:
                        self._attach_tooltip(lbl, render.pdf_name)

            note_var = tk.StringVar(value=render.notes)
            self._note_vars[render.id] = note_var
            # Klassisches tk.Entry statt ttk.Entry: nur so laesst sich der
            # Hintergrund kurz aufblitzen lassen, um "gespeichert" sichtbar
            # zu bestaetigen (ttk-Widgets sind Theme-gestylt, bg nicht
            # direkt setzbar).
            note_entry = tk.Entry(
                row,
                textvariable=note_var,
                bg=COLORS["surface"],
                fg=COLORS["text"],
                font=FONTS["ui"],
                relief="solid",
                bd=1,
                highlightthickness=0,
            )
            note_entry.grid(row=0, column=7, sticky="ew", padx=(4, 4), pady=_ROW_PADY)
            self._note_entries[render.id] = note_entry
            note_entry.bind("<FocusIn>", lambda _e, rid=render.id: self._select_render(rid))
            note_entry.bind("<FocusOut>", lambda _e, rid=render.id: self._save_note(rid))
            note_entry.bind("<Return>", lambda _e, rid=render.id: self._save_note(rid))

            actions = tk.Frame(row, bg=bg)
            actions.grid(row=0, column=8, sticky="w", padx=(4, 8), pady=_ROW_PADY)

            open_btn = self._make_action_button(
                actions, icon=_OPEN_ICON, command=lambda rid=render.id: self._open_by_id(rid), variant="primary"
            )
            open_btn.pack(side="left", padx=(0, 2))
            self._attach_tooltip(open_btn, "PDF öffnen")

            reveal_btn = self._make_action_button(
                actions, icon=_REVEAL_ICON, command=lambda rid=render.id: self._reveal_by_id(rid), variant="muted"
            )
            reveal_btn.pack(side="left", padx=(0, 2))
            self._attach_tooltip(reveal_btn, "Ordner zeigen")

            rename_btn = self._make_action_button(
                actions, icon=_RENAME_ICON, command=lambda rid=render.id: self._rename_by_id(rid), variant="muted"
            )
            rename_btn.pack(side="left", padx=(0, 2))
            self._attach_tooltip(rename_btn, "Umbenennen")

            delete_btn = self._make_action_button(
                actions, icon=_DELETE_ICON, command=lambda rid=render.id: self._delete_by_id(rid), variant="muted"
            )
            delete_btn.pack(side="left")
            self._attach_tooltip(delete_btn, "Löschen")

            sep = ttk.Separator(rows_host, orient="horizontal")
            sep.grid(row=row_idx * 2 + 1, column=0, columnspan=9, sticky="ew")

    def _attach_tooltip(self, widget: tk.Widget, text: str) -> None:
        tip: dict[str, Optional[tk.Toplevel]] = {"win": None}

        def show(_event=None):
            if tip["win"] is not None:
                return
            tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.configure(bg=COLORS["tooltip_border"])
            lbl = tk.Label(
                tw,
                text=text,
                bg=COLORS["tooltip_bg"],
                fg=COLORS["text"],
                font=FONTS["ui_small"],
                padx=6,
                pady=3,
            )
            lbl.pack(padx=1, pady=1)
            x = widget.winfo_rootx() + 10
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tw.wm_geometry(f"+{x}+{y}")
            tip["win"] = tw

        def hide(_event=None):
            if tip["win"] is not None:
                tip["win"].destroy()
                tip["win"] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    # --- Datenzugriff -----------------------------------------------------

    def _render_by_id(self, render_id: str) -> Optional[RenderView]:
        for render in self._renders:
            if render.id == render_id:
                return render
        return None

    def _selected_render(self) -> Optional[RenderView]:
        if self._selected_render_id is None:
            return None
        return self._render_by_id(self._selected_render_id)

    # --- Aktionen -----------------------------------------------------------

    def _save_note(self, render_id: str) -> None:
        render = self._render_by_id(render_id)
        var = self._note_vars.get(render_id)
        snap = self._current_snapshot()
        if render is None or var is None or snap is None:
            return
        new_note = var.get()
        if new_note == render.notes:
            return
        update_render_fields(self._book_path(), snap.id, render.id, {"notes": new_note})
        # In-memory-Liste aktualisieren statt komplett neu zu laden — ein
        # voller _reload_renders() wuerde alle Zeilen-Widgets neu aufbauen
        # und damit z. B. eine noch ungespeicherte Notiz in einer ANDEREN
        # Zeile verwerfen.
        self._renders = [
            replace(r, notes=new_note) if r.id == render_id else r for r in self._renders
        ]
        self._flash_note_saved(render_id)

    def _flash_note_saved(self, render_id: str) -> None:
        """Kurzes grünes Aufblitzen als sichtbare Bestätigung, dass die
        Notiz gespeichert wurde — ohne dieses Feedback ist für den Nutzer
        nicht erkennbar, ob/wann Enter oder Fokuswechsel tatsächlich
        gespeichert hat."""
        entry = self._note_entries.get(render_id)
        if entry is None or not entry.winfo_exists():
            return
        entry.configure(bg="#dcfce7")
        entry.after(500, lambda: entry.configure(bg=COLORS["surface"]) if entry.winfo_exists() else None)

    def _open_by_id(self, render_id: str) -> None:
        self._select_render(render_id)
        self._open_selected()

    def _reveal_by_id(self, render_id: str) -> None:
        self._select_render(render_id)
        self._reveal_selected()

    def _rename_by_id(self, render_id: str) -> None:
        self._select_render(render_id)
        self._rename_selected()

    def _delete_by_id(self, render_id: str) -> None:
        self._select_render(render_id)
        self._delete_selected()

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

    def _rename_selected(self) -> None:
        render = self._selected_render()
        snap = self._current_snapshot()
        if render is None or snap is None:
            messagebox.showinfo("Mapping Manager", "Bitte eine PDF-Zeile auswählen.", parent=self._window)
            return
        if not render.exists:
            messagebox.showwarning(
                "Mapping Manager",
                f"Datei nicht gefunden:\n{render.pdf_path}",
                parent=self._window,
            )
            return
        new_name = simpledialog.askstring(
            "Umbenennen",
            "Neuer Dateiname:",
            initialvalue=render.pdf_name,
            parent=self._window,
        )
        if not new_name:
            return
        try:
            new_path = rename_pdf(render.pdf_path, new_name)
        except (OSError, ValueError, FileNotFoundError) as exc:
            messagebox.showerror("Mapping Manager", str(exc), parent=self._window)
            return
        update_render_fields(self._book_path(), snap.id, render.id, {"artifact_path": str(new_path)})
        self._selected_render_id = render.id
        self._reload_renders()

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
        self._selected_render_id = None
        self._reload_renders()


def open_mapping_manager_dialog(studio: Any, **kwargs) -> None:
    MappingManagerDialog(studio).show()
