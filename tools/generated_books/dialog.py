"""Tk-Dialog: generierte PDF-Ausgaben (sortierbare Tabelle + Löschen)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal, Optional

import tkinter as tk
from tkinter import messagebox, ttk

from tools.generated_books.discovery import (
    GeneratedPdf,
    collect_book_paths_from_studio,
    delete_generated_pdf,
    find_generated_pdfs,
    load_settings,
    sort_generated_pdfs,
)
from ui_theme import COLORS, FONTS, style_dialog

SortColumn = Literal["name", "date"]

_COL_NAME_MINSIZE = 420
_COL_DATE_MINSIZE = 132
_COL_OPEN_MINSIZE = 34
_COL_DELETE_MINSIZE = 34
_ROW_PADY = 2

# Windows: Segoe MDL2 — kein Emoji.
_OPEN_ICON = "\uE8A7" if sys.platform.startswith("win") else "\u2197"
_DELETE_ICON = "\uE74D" if sys.platform.startswith("win") else "\u00D7"
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


def _open_path(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _reveal_in_explorer(path: Path) -> None:
    target = path if path.is_dir() else path.parent
    if sys.platform.startswith("win"):
        if path.is_file():
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        else:
            os.startfile(str(target))  # noqa: S606
    else:
        _open_path(target)


class GeneratedBooksDialog(tk.Toplevel):
    def __init__(self, parent, studio: Any):
        super().__init__(parent)
        style_dialog(self, "Generierte Bücher")
        self.transient(parent)
        self.grab_set()
        self._studio = studio
        self._entries: list[GeneratedPdf] = []
        self._sort_column: SortColumn = "date"
        self._sort_reverse = True
        self._header_labels: dict[str, tk.Label] = {}
        self._row_frames: dict[str, tk.Frame] = {}
        self._selected_paths: set[str] = set()
        self._selection_anchor: Optional[str] = None
        self.geometry("860x480")
        self.minsize(680, 380)
        self._build_ui()
        self._reload()

    def _configure_table_grid(self, widget: tk.Misc) -> None:
        widget.columnconfigure(0, weight=1, minsize=_COL_NAME_MINSIZE)
        widget.columnconfigure(1, minsize=_COL_DATE_MINSIZE, weight=0)
        widget.columnconfigure(2, minsize=_COL_OPEN_MINSIZE, weight=0)
        widget.columnconfigure(3, minsize=_COL_DELETE_MINSIZE, weight=0)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Fertige PDF-Ausgaben unter export/_book",
            font=FONTS["ui_semibold"],
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Strg+Klick Mehrfachauswahl · Umschalt+Klick Bereich · "
                "Doppelklick auf Name öffnet die PDF"
            ),
            foreground=COLORS["text_muted"],
            font=FONTS["ui_small"],
        ).pack(anchor="w", pady=(0, 8))

        table_shell = ttk.LabelFrame(outer, text="PDF-Ausgaben", style="Section.TLabelframe")
        table_shell.pack(fill="both", expand=True)

        inner = ttk.Frame(table_shell, padding=(0, 4))
        inner.pack(fill="both", expand=True)

        header = tk.Frame(inner, bg=COLORS["surface_muted"], height=28)
        header.pack(fill="x")
        header.pack_propagate(False)
        self._configure_table_grid(header)

        self._header_labels["name"] = self._make_header_cell(
            header, 0, "Name", "name"
        )
        self._header_labels["date"] = self._make_header_cell(
            header, 1, "Datum", "date"
        )
        tk.Label(
            header,
            text="Aktionen",
            bg=COLORS["surface_muted"],
            fg=COLORS["heading"],
            font=FONTS["ui_semibold_small"],
            anchor="center",
        ).grid(row=0, column=2, columnspan=2, sticky="nsew", padx=(0, 6), pady=4)

        ttk.Separator(inner, orient="horizontal").pack(fill="x")

        body = ttk.Frame(inner)
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            body,
            highlightthickness=0,
            borderwidth=0,
            bg=COLORS["surface"],
        )
        scroll = ttk.Scrollbar(body, orient="vertical", command=self._canvas.yview)
        self._rows_host = tk.Frame(self._canvas, bg=COLORS["surface"])
        self._configure_table_grid(self._rows_host)
        self._rows_host.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._rows_host, anchor="nw"
        )
        self._canvas.configure(yscrollcommand=scroll.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfigure(self._canvas_window, width=e.width),
        )
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Öffnen", command=self._open_selected).pack(side="left")
        ttk.Button(buttons, text="Ordner zeigen", command=self._reveal_selected).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(buttons, text="Auswahl löschen", command=self._delete_selected).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(buttons, text="Aktualisieren", command=self._reload).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(buttons, text="Schließen", command=self.destroy).pack(side="right")

        self._status = ttk.Label(outer, text="", foreground=COLORS["text_muted"])
        self._status.pack(anchor="w", pady=(8, 0))

        self._update_header_sort_indicators()

    def _make_header_cell(
        self, parent: tk.Frame, column: int, text: str, sort_key: SortColumn
    ) -> tk.Label:
        lbl = tk.Label(
            parent,
            text=text,
            bg=COLORS["surface_muted"],
            fg=COLORS["heading"],
            font=FONTS["ui_semibold_small"],
            anchor="w",
            cursor="hand2",
        )
        lbl.grid(row=0, column=column, sticky="ew", padx=(8, 6), pady=4)
        lbl.bind("<Button-1>", lambda _e: self._toggle_sort(sort_key))
        return lbl

    def _make_action_button(
        self,
        parent: tk.Frame,
        *,
        icon: str,
        command,
        variant: Literal["primary", "muted"],
    ) -> tk.Button:
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
            padx=4,
            pady=0,
            width=2,
            height=1,
            highlightthickness=1,
            highlightbackground=style["border"],
            highlightcolor=style["border"],
            cursor="hand2",
        )

    def destroy(self):
        try:
            self._canvas.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        super().destroy()

    def _on_mousewheel(self, event) -> None:
        if not str(self._canvas.winfo_exists()) == "1":
            return
        delta = int(-1 * (event.delta / 120))
        self._canvas.yview_scroll(delta, "units")

    def _toggle_sort(self, column: SortColumn) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = column == "date"
        self._update_header_sort_indicators()
        self._render_rows()

    def _update_header_sort_indicators(self) -> None:
        arrow = " ▲" if self._sort_reverse else " ▼"
        for key, base in (("name", "Name"), ("date", "Datum")):
            suffix = arrow if self._sort_column == key else ""
            self._header_labels[key].config(text=f"{base}{suffix}")

    def _sorted_entries(self) -> list[GeneratedPdf]:
        return sort_generated_pdfs(
            self._entries,
            self._sort_column,
            reverse=self._sort_reverse,
        )

    def _path_key(self, path: Path) -> str:
        return str(path)

    def _is_selected(self, path: Path) -> bool:
        return self._path_key(path) in self._selected_paths

    def _row_bg(self, row_idx: int, selected: bool) -> str:
        if selected:
            return COLORS["accent_soft"]
        return COLORS["surface"] if row_idx % 2 == 0 else COLORS["surface_alt"]

    def _prune_selection(self) -> None:
        valid = {self._path_key(e.path) for e in self._entries}
        self._selected_paths &= valid
        if self._selection_anchor is not None and self._selection_anchor not in valid:
            self._selection_anchor = None

    def _reload(self) -> None:
        settings = load_settings()
        books = collect_book_paths_from_studio(
            self._studio, recent_only=settings["recent_only"]
        )
        self._entries = find_generated_pdfs(books, max_entries=settings["max_entries"])
        self._prune_selection()
        self._render_rows()
        self._update_status()

    def _handle_row_click(self, path: Path, event: tk.Event) -> None:
        key = self._path_key(path)
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)
        visible_keys = [self._path_key(e.path) for e in self._sorted_entries()]

        if shift and self._selection_anchor and self._selection_anchor in visible_keys:
            start = visible_keys.index(self._selection_anchor)
            end = visible_keys.index(key) if key in visible_keys else start
            lo, hi = sorted((start, end))
            block = set(visible_keys[lo : hi + 1])
            if ctrl:
                self._selected_paths |= block
            else:
                self._selected_paths = block
        elif ctrl:
            if key in self._selected_paths:
                self._selected_paths.discard(key)
            else:
                self._selected_paths.add(key)
            self._selection_anchor = key
        else:
            self._selected_paths = {key}
            self._selection_anchor = key

        self._render_rows()

    def _render_rows(self) -> None:
        for child in self._rows_host.winfo_children():
            child.destroy()
        self._row_frames.clear()

        entries = self._sorted_entries()
        if not entries:
            tk.Label(
                self._rows_host,
                text="Noch keine PDF unter export/_book – zuerst rendern.",
                bg=COLORS["surface"],
                fg=COLORS["text_muted"],
                font=FONTS["ui_small"],
                anchor="w",
            ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=12)
            return

        for row_idx, entry in enumerate(entries):
            path_key = self._path_key(entry.path)
            selected = self._is_selected(entry.path)
            bg = self._row_bg(row_idx, selected)

            row = tk.Frame(self._rows_host, bg=bg)
            row.grid(row=row_idx * 2, column=0, columnspan=4, sticky="ew")
            self._configure_table_grid(row)
            self._row_frames[path_key] = row

            name_cell = tk.Frame(row, bg=bg)
            name_cell.grid(row=0, column=0, sticky="nsew", padx=(8, 6), pady=_ROW_PADY)
            name_lbl = tk.Label(
                name_cell,
                text=entry.path.name,
                bg=bg,
                fg=COLORS["text"],
                font=FONTS["ui"],
                anchor="w",
            )
            name_lbl.pack(fill="x")
            proj_lbl = tk.Label(
                name_cell,
                text=entry.book_name,
                bg=bg,
                fg=COLORS["text_muted"],
                font=FONTS["ui_small"],
                anchor="w",
            )
            proj_lbl.pack(fill="x")
            for widget in (name_cell, name_lbl, proj_lbl):
                widget.bind("<Double-1>", lambda _e, p=entry.path: self._open_path(p))
                widget.bind(
                    "<Button-1>",
                    lambda e, p=entry.path: self._handle_row_click(p, e),
                )

            date_lbl = tk.Label(
                row,
                text=entry.date_str,
                bg=bg,
                fg=COLORS["text"],
                font=FONTS["ui"],
                anchor="w",
            )
            date_lbl.grid(row=0, column=1, sticky="nw", padx=(0, 6), pady=_ROW_PADY)
            date_lbl.bind(
                "<Button-1>",
                lambda e, p=entry.path: self._handle_row_click(p, e),
            )

            open_btn = self._make_action_button(
                row,
                icon=_OPEN_ICON,
                command=lambda p=entry.path: self._open_path(p),
                variant="primary",
            )
            open_btn.grid(row=0, column=2, padx=(0, 2), pady=_ROW_PADY, sticky="n")
            self._attach_tooltip(open_btn, "PDF öffnen")

            del_btn = self._make_action_button(
                row,
                icon=_DELETE_ICON,
                command=lambda e=entry: self._delete_entry(e),
                variant="muted",
            )
            del_btn.grid(row=0, column=3, padx=(0, 6), pady=_ROW_PADY, sticky="n")
            self._attach_tooltip(del_btn, "PDF löschen")

            sep = ttk.Separator(self._rows_host, orient="horizontal")
            sep.grid(row=row_idx * 2 + 1, column=0, columnspan=4, sticky="ew")

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

    def _selected_entries(self) -> list[GeneratedPdf]:
        selected = self._selected_paths
        return [e for e in self._sorted_entries() if self._path_key(e.path) in selected]

    def _open_path(self, path: Path) -> None:
        try:
            _open_path(path)
        except OSError as exc:
            messagebox.showerror("Generierte Bücher", f"Öffnen fehlgeschlagen:\n{exc}")

    def _open_selected(self) -> None:
        entries = self._selected_entries()
        if not entries:
            messagebox.showinfo("Generierte Bücher", "Bitte mindestens eine Zeile auswählen.")
            return
        errors: list[str] = []
        for entry in entries:
            try:
                _open_path(entry.path)
            except OSError as exc:
                errors.append(f"{entry.path.name}: {exc}")
        if errors:
            messagebox.showerror(
                "Generierte Bücher",
                "Einige PDFs konnten nicht geöffnet werden:\n\n" + "\n".join(errors),
            )

    def _reveal_selected(self) -> None:
        entries = self._selected_entries()
        if not entries:
            current = getattr(self._studio, "current_book", None)
            if current is not None:
                export_dir = Path(current) / "export"
                if export_dir.is_dir():
                    _reveal_in_explorer(export_dir)
                    return
            messagebox.showinfo("Generierte Bücher", "Bitte mindestens eine Zeile auswählen.")
            return
        try:
            _reveal_in_explorer(entries[0].path)
        except OSError as exc:
            messagebox.showerror("Generierte Bücher", f"Explorer fehlgeschlagen:\n{exc}")

    def _delete_entry(self, entry: GeneratedPdf) -> None:
        self._delete_entries([entry])

    def _delete_selected(self) -> None:
        entries = self._selected_entries()
        if not entries:
            messagebox.showinfo("Generierte Bücher", "Bitte mindestens eine Zeile auswählen.")
            return
        self._delete_entries(entries)

    def _delete_entries(self, entries: list[GeneratedPdf]) -> None:
        if len(entries) == 1:
            entry = entries[0]
            msg = (
                f"PDF wirklich löschen?\n\n{entry.path}\n\n"
                "Die Datei wird von der Festplatte entfernt."
            )
        else:
            preview = "\n".join(f"· {e.path.name}" for e in entries[:8])
            if len(entries) > 8:
                preview += f"\n· … und {len(entries) - 8} weitere"
            msg = (
                f"{len(entries)} PDF(s) wirklich löschen?\n\n{preview}\n\n"
                "Die Dateien werden von der Festplatte entfernt."
            )
        if not messagebox.askyesno("Generierte Bücher – Löschen", msg):
            return

        deleted_keys: set[str] = set()
        errors: list[str] = []
        for entry in entries:
            try:
                delete_generated_pdf(entry.path)
            except (OSError, ValueError, FileNotFoundError) as exc:
                errors.append(f"{entry.path.name}: {exc}")
                continue
            deleted_keys.add(self._path_key(entry.path))

        if deleted_keys:
            self._entries = [
                e for e in self._entries if self._path_key(e.path) not in deleted_keys
            ]
            self._selected_paths -= deleted_keys
            self._prune_selection()
            self._render_rows()
            self._update_status()

            log = getattr(self._studio, "log", None)
            if callable(log):
                log(f"{len(deleted_keys)} PDF(s) gelöscht", "warning")

        if errors:
            messagebox.showerror(
                "Generierte Bücher",
                "Einige Dateien konnten nicht gelöscht werden:\n\n" + "\n".join(errors),
            )

    def _update_status(self) -> None:
        total = len(self._entries)
        selected = len(self._selected_paths)
        if total:
            text = f"{total} PDF(s) gefunden"
            if selected:
                text += f" · {selected} ausgewählt"
            self._status.config(text=text)
        else:
            self._status.config(
                text="Noch keine PDF unter export/_book – zuerst rendern."
            )


def run_dialog(studio: Any) -> int:
    parent = getattr(studio, "root", None)
    if parent is None:
        return 2
    GeneratedBooksDialog(parent, studio)
    return 0


__all__ = ["GeneratedBooksDialog", "run_dialog"]
