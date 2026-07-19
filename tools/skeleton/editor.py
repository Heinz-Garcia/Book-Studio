"""Skeleton-Bibliothek bearbeiten (autonomes Tk-Fenster)."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Optional

from tools.skeleton.config import read_skeleton_settings, set_default_profile, write_skeleton_settings
from tools.skeleton.manifest import (
    SkeletonFileEntry,
    SkeletonManifest,
    create_markdown_template,
    delete_profile,
    duplicate_profile,
    list_profiles,
    load_manifest,
    replace_manifest_entries,
    resolve_library_root,
    sync_markdown_order,
    update_manifest_meta,
    validate_profile_name,
)

_LOG = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _try_style_window(window: tk.Toplevel, parent: Optional[tk.Misc]) -> None:
    try:
        from ui_theme import center_on_parent, style_dialog

        style_dialog(window)
        if parent is not None:
            center_on_parent(window, parent, 980, 720)
    except ImportError:
        window.geometry("980x720")


def reveal_skeleton_path(path: Path) -> None:
    """Markiert eine Skeleton-Datei im Dateimanager (Windows Explorer o. ä.)."""
    path = Path(path).resolve()
    try:
        if sys.platform == "win32":
            if path.is_file():
                subprocess.Popen(["explorer", f"/select,{path}"])
            else:
                folder = path if path.is_dir() else path.parent
                subprocess.Popen(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            target = path if path.is_dir() else path.parent
            subprocess.Popen(["xdg-open", str(target)])
    except OSError as exc:
        _LOG.warning("Explorer konnte nicht geöffnet werden: %s", exc)
        raise


class SkeletonEditorWindow(tk.Toplevel):
    """Editor für Skeleton-Profile, Manifest-Einträge und Markdown-Vorlagen."""

    def __init__(
        self,
        parent: Optional[tk.Misc],
        *,
        library_root: Path,
        initial_profile: Optional[str] = None,
        studio: Any = None,
    ) -> None:
        super().__init__(parent)
        self.title("Skeleton-Bibliothek bearbeiten")
        self.library_root = Path(library_root).resolve()
        self._studio = studio
        self._manifest: Optional[SkeletonManifest] = None
        self._entries: list[SkeletonFileEntry] = []
        self._selected_index: Optional[int] = None
        self._editor_dirty = False
        self._meta_dirty = False

        if parent is not None:
            self.transient(parent)
        self.grab_set()
        _try_style_window(self, parent)

        self._profile_var = tk.StringVar()
        self._profile_label_var = tk.StringVar()
        self._profile_desc_var = tk.StringVar()
        self._profile_root_var = tk.StringVar(value="")
        self._rel_path_var = tk.StringVar(value="")
        self._abs_path_var = tk.StringVar(value="")
        self._title_var = tk.StringVar()
        self._order_var = tk.StringVar()
        self._optional_var = tk.BooleanVar(value=False)
        self._include_tree_var = tk.BooleanVar(value=True)
        for var in (self._title_var, self._order_var, self._optional_var, self._include_tree_var):
            var.trace_add("write", lambda *_a: self._mark_meta_dirty())

        self._build_ui()
        self._reload_profiles(initial_profile)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(outer)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(top, text="Profil:").pack(side=tk.LEFT)
        self._profile_combo = ttk.Combobox(top, textvariable=self._profile_var, state="readonly", width=28)
        self._profile_combo.pack(side=tk.LEFT, padx=(6, 12))
        self._profile_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_profile_changed())
        ttk.Button(top, text="Profil duplizieren…", command=self._duplicate_profile).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Als Standard", command=self._set_default_profile).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Profil löschen…", command=self._delete_profile).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Aktualisieren", command=lambda: self._reload_profiles(self._profile_var.get())).pack(
            side=tk.LEFT, padx=4
        )

        meta = ttk.LabelFrame(outer, text="Profil-Metadaten", padding=8)
        meta.pack(fill=tk.X, pady=(0, 8))
        row1 = ttk.Frame(meta)
        row1.pack(fill=tk.X)
        ttk.Label(row1, text="Label").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self._profile_label_var, width=50).pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        ttk.Button(row1, text="Speichern", command=self._save_profile_meta).pack(side=tk.RIGHT)
        row2 = ttk.Frame(meta)
        row2.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(row2, text="Beschreibung").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self._profile_desc_var, width=70).pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        info = ttk.Label(
            outer,
            text=(
                "Hier organisierst du den Skeleton-Pool (Vorlagen), unabhängig von jedem Buchprojekt. "
                "Populate kopiert später aus diesem Pool — Änderungen betreffen nur künftige Übernahmen."
            ),
            wraplength=900,
        )
        info.pack(anchor=tk.W, pady=(0, 4))

        profile_path_row = ttk.Frame(outer)
        profile_path_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(profile_path_row, text="Profilordner:").pack(side=tk.LEFT)
        ttk.Entry(profile_path_row, textvariable=self._profile_root_var, state="readonly").pack(
            side=tk.LEFT, padx=6, fill=tk.X, expand=True
        )
        ttk.Button(
            profile_path_row,
            text="📂 Im Explorer anzeigen",
            command=self._reveal_profile_folder,
        ).pack(side=tk.LEFT)

        paned = ttk.Panedwindow(outer, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, padding=(0, 0, 8, 0))
        paned.add(left, weight=1)
        ttk.Label(left, text="Vorlagen im Skeleton-Profil").pack(anchor=tk.W)
        ttk.Label(
            left,
            text="Populate legt Dateien nur im Projekt ab (links im Pool). "
            "Den Buchbaum (rechts) füllst du manuell.",
            wraplength=320,
        ).pack(anchor=tk.W, pady=(0, 2))
        self._file_list = tk.Listbox(left, exportselection=False, height=18)
        self._file_list.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        self._file_list.bind("<<ListboxSelect>>", lambda _e: self._on_file_selected())
        self._file_list.bind("<Double-Button-1>", lambda _e: self._open_in_markdown_editor())

        left_btns = ttk.Frame(left)
        left_btns.pack(fill=tk.X)
        ttk.Button(left_btns, text="Neue Vorlage…", command=self._add_file).pack(side=tk.LEFT)
        ttk.Button(left_btns, text="Vorlage löschen…", command=self._remove_entry).pack(side=tk.LEFT, padx=6)
        ttk.Button(
            left_btns,
            text="Im Markdown-Editor öffnen",
            command=self._open_in_markdown_editor,
        ).pack(side=tk.LEFT, padx=6)

        right = ttk.Frame(paned, padding=(8, 0, 0, 0))
        paned.add(right, weight=3)

        path_box = ttk.LabelFrame(right, text="Datei im Skeleton-Pool", padding=8)
        path_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(path_box, text="Relativ zum Profil:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(path_box, textvariable=self._rel_path_var, state="readonly").grid(
            row=0, column=1, sticky=tk.EW, padx=6, pady=2
        )
        ttk.Label(path_box, text="Vollständiger Pfad:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(path_box, textvariable=self._abs_path_var, state="readonly").grid(
            row=1, column=1, sticky=tk.EW, padx=6, pady=2
        )
        ttk.Button(
            path_box,
            text="📂 Im Explorer anzeigen",
            command=self._reveal_selected_file,
        ).grid(row=0, column=2, padx=(8, 0), sticky=tk.N)
        ttk.Button(
            path_box,
            text="📝 Im Markdown-Editor öffnen",
            command=self._open_in_markdown_editor,
        ).grid(row=1, column=2, padx=(8, 0), sticky=tk.N)
        path_box.columnconfigure(1, weight=1)

        meta = ttk.LabelFrame(right, text="Vorlagen-Metadaten", padding=8)
        meta.pack(fill=tk.X, pady=(0, 8))
        grid = ttk.Frame(meta)
        grid.pack(fill=tk.X)
        ttk.Label(grid, text="Titel").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid, textvariable=self._title_var, width=40).grid(row=0, column=1, sticky=tk.EW, padx=6)
        ttk.Label(grid, text="order").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid, textvariable=self._order_var, width=16).grid(row=1, column=1, sticky=tk.W, padx=6)
        ttk.Checkbutton(grid, text="optional (Populate nur mit Checkbox)", variable=self._optional_var).grid(
            row=2, column=1, sticky=tk.W
        )
        ttk.Label(
            grid,
            text="Populate trägt nichts in den Buchbaum ein (rechts = manuell).",
        ).grid(row=3, column=1, sticky=tk.W, pady=(2, 0))
        grid.columnconfigure(1, weight=1)
        ttk.Button(meta, text="Metadaten speichern", command=self._save_entry_meta).pack(anchor=tk.E, pady=(6, 0))

        ttk.Label(right, text="Markdown-Vorschau (nur lesen/schnell editieren)").pack(anchor=tk.W)
        self._text = tk.Text(right, wrap=tk.WORD, undo=True, height=20)
        scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self._text.yview)
        self._text.configure(yscrollcommand=scroll.set)
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(4, 0))
        scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(4, 0))
        self._text.bind("<<Modified>>", self._on_text_modified)

        bottom = ttk.Frame(outer)
        bottom.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(bottom, text="📝 Im Markdown-Editor öffnen", command=self._open_in_markdown_editor).pack(
            side=tk.LEFT
        )
        ttk.Button(bottom, text="Vorschau speichern", command=self._save_markdown).pack(side=tk.LEFT, padx=8)
        ttk.Button(bottom, text="Schließen", command=self._close).pack(side=tk.RIGHT)

    def _reload_profiles(self, select: Optional[str] = None) -> None:
        profiles = list_profiles(self.library_root)
        self._profile_combo["values"] = profiles
        if not profiles:
            messagebox.showwarning("Skeleton", "Keine Profile gefunden.", parent=self)
            return
        chosen = select if select in profiles else profiles[0]
        self._profile_var.set(chosen)
        self._load_profile(chosen)

    def _load_profile(self, profile_name: str) -> None:
        profile_dir = self.library_root / profile_name
        self._manifest = load_manifest(profile_dir)
        self._entries = list(self._manifest.files)
        self._profile_label_var.set(self._manifest.label)
        self._profile_desc_var.set(self._manifest.description)
        self._profile_root_var.set(str(self._manifest.root.resolve()))
        self._selected_index = None
        self._populate_file_list()
        self._clear_editor()

    def _on_profile_changed(self) -> None:
        if not self._confirm_discard():
            if self._manifest:
                self._profile_var.set(self._manifest.name)
            return
        self._load_profile(self._profile_var.get())

    def _populate_file_list(self) -> None:
        self._file_list.delete(0, tk.END)
        for entry in self._entries:
            # Liste: Titel + Pool-Pfad; [opt] = optional beim Populate
            flags = []
            if entry.optional:
                flags.append("opt")
            suffix = f"  [{', '.join(flags)}]" if flags else ""
            self._file_list.insert(tk.END, f"{entry.title}  —  {entry.path}{suffix}")

    def _clear_editor(self) -> None:
        self._title_var.set("")
        self._order_var.set("")
        self._optional_var.set(False)
        self._include_tree_var.set(True)
        self._rel_path_var.set("")
        self._abs_path_var.set("")
        self._text.delete("1.0", tk.END)
        self._editor_dirty = False
        self._meta_dirty = False
        self._text.edit_modified(False)

    def _selected_skeleton_file(self) -> Optional[Path]:
        entry = self._current_entry()
        if entry is None or self._manifest is None:
            return None
        return (self._manifest.root / entry.path).resolve()

    def _reveal_profile_folder(self) -> None:
        if self._manifest is None:
            messagebox.showinfo("Skeleton", "Kein Profil geladen.", parent=self)
            return
        try:
            reveal_skeleton_path(self._manifest.root)
        except OSError as exc:
            messagebox.showerror("Skeleton", f"Explorer konnte nicht geöffnet werden:\n{exc}", parent=self)

    def _reveal_selected_file(self) -> None:
        path = self._selected_skeleton_file()
        if path is None:
            messagebox.showinfo("Skeleton", "Bitte zuerst eine Vorlage auswählen.", parent=self)
            return
        if not path.exists():
            messagebox.showwarning(
                "Skeleton",
                f"Datei existiert noch nicht auf der Platte:\n{path}",
                parent=self,
            )
            try:
                reveal_skeleton_path(path.parent)
            except OSError as exc:
                messagebox.showerror("Skeleton", f"Explorer konnte nicht geöffnet werden:\n{exc}", parent=self)
            return
        try:
            reveal_skeleton_path(path)
        except OSError as exc:
            messagebox.showerror("Skeleton", f"Explorer konnte nicht geöffnet werden:\n{exc}", parent=self)

    def _open_in_markdown_editor(self) -> None:
        """Öffnet die gewählte Skeleton-Vorlage im Standard-MarkdownEditor."""
        path = self._selected_skeleton_file()
        if path is None:
            messagebox.showinfo("Skeleton", "Bitte zuerst eine Vorlage auswählen.", parent=self)
            return
        if not path.is_file():
            messagebox.showwarning(
                "Skeleton",
                f"Datei existiert noch nicht:\n{path}\n\nBitte zuerst „Vorschau speichern“ oder neu anlegen.",
                parent=self,
            )
            return
        if self._editor_dirty or self._meta_dirty:
            if not messagebox.askyesno(
                "Ungespeicherte Änderungen",
                "Im Skeleton-Fenster gibt es ungespeicherte Änderungen.\n\n"
                "Trotzdem den Markdown-Editor öffnen?\n"
                "(Ungespeicherte Vorschau-Änderungen werden verworfen.)",
                parent=self,
            ):
                return

        end_commands: list[Any] = []
        if self._studio is not None:
            getter = getattr(self._studio, "_get_editor_end_commands", None)
            if callable(getter):
                try:
                    end_commands = list(getter() or [])
                except (TypeError, AttributeError, RuntimeError):
                    end_commands = []

        try:
            from md_editor import MarkdownEditor
        except ImportError as exc:
            messagebox.showerror(
                "Skeleton",
                f"Markdown-Editor konnte nicht geladen werden:\n{exc}",
                parent=self,
            )
            return

        # Nested grab: Skeleton-Editor kurz freigeben, damit der MD-Editor bedienbar ist.
        try:
            self.grab_release()
        except tk.TclError:
            pass

        editor = MarkdownEditor(
            self,
            path,
            on_save_callback=self._on_markdown_editor_saved,
            end_commands=end_commands,
        )
        self.wait_window(editor)

        try:
            self.grab_set()
        except tk.TclError:
            pass
        self._reload_selected_from_disk()
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def _on_markdown_editor_saved(self, _saved_file_path=None) -> None:
        """Nach Speichern im MarkdownEditor die Vorschau neu laden."""
        self._reload_selected_from_disk()

    def _reload_selected_from_disk(self) -> None:
        path = self._selected_skeleton_file()
        if path is None or not path.is_file():
            return
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", content)
        self._editor_dirty = False
        self._meta_dirty = False
        self._text.edit_modified(False)

    def _on_file_selected(self) -> None:
        if not self._confirm_discard():
            return
        selection = self._file_list.curselection()
        if not selection:
            return
        self._selected_index = int(selection[0])
        entry = self._entries[self._selected_index]
        self._title_var.set(entry.title)
        self._order_var.set(entry.order or "")
        self._optional_var.set(entry.optional)
        self._include_tree_var.set(entry.include_in_tree)
        path = self._manifest.root / entry.path  # type: ignore[union-attr]
        self._rel_path_var.set(entry.path)
        self._abs_path_var.set(str(path.resolve()))
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Vorlage in anderer Kodierung (z. B. cp1252) – nicht crashen.
                content = path.read_text(encoding="utf-8", errors="replace")
        else:
            content = f"---\ntitle: \"{entry.title}\"\n---\n\n# {entry.title}\n"
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", content)
        self._editor_dirty = False
        self._meta_dirty = False
        self._text.edit_modified(False)

    def _on_text_modified(self, _event=None) -> None:
        if self._text.edit_modified():
            self._editor_dirty = True
            self._text.edit_modified(False)

    def _mark_meta_dirty(self) -> None:
        self._meta_dirty = True

    def _confirm_discard(self) -> bool:
        if not (self._editor_dirty or self._meta_dirty):
            return True
        return messagebox.askyesno(
            "Ungespeicherte Änderungen",
            "Änderungen an der aktuellen Datei verwerfen?",
            parent=self,
        )

    def _current_entry(self) -> Optional[SkeletonFileEntry]:
        if self._selected_index is None or self._selected_index >= len(self._entries):
            return None
        return self._entries[self._selected_index]

    def _save_markdown(self) -> None:
        entry = self._current_entry()
        if entry is None or self._manifest is None:
            messagebox.showinfo("Skeleton", "Bitte zuerst eine Datei auswählen.", parent=self)
            return
        target = self._manifest.root / entry.path
        target.parent.mkdir(parents=True, exist_ok=True)
        content = self._text.get("1.0", "end-1c") + "\n"
        target.write_text(content, encoding="utf-8")
        self._editor_dirty = False
        messagebox.showinfo("Skeleton", f"Gespeichert: {entry.path}", parent=self)

    def _save_entry_meta(self) -> None:
        entry = self._current_entry()
        if entry is None or self._manifest is None:
            messagebox.showinfo("Skeleton", "Bitte zuerst eine Datei auswählen.", parent=self)
            return
        order = self._order_var.get().strip() or None
        updated = SkeletonFileEntry(
            path=entry.path,
            title=self._title_var.get().strip() or Path(entry.path).stem,
            order=order,
            optional=bool(self._optional_var.get()),
            include_in_tree=entry.include_in_tree,
            description=entry.description,
        )
        self._entries[self._selected_index] = updated
        self._manifest = replace_manifest_entries(
            self._manifest.root,
            self._entries,
            name=self._manifest.name,
            label=self._manifest.label,
            description=self._manifest.description,
        )
        self._entries = list(self._manifest.files)

        # Order-SSOT (Batch 3): MD-Frontmatter `order` synchron zum
        # Manifest-Eintrag halten, damit keine zweite Order-Semantik driftet.
        md_path = self._manifest.root / updated.path
        if sync_markdown_order(md_path, updated.order):
            self._reload_markdown_after_sync(md_path)

        self._meta_dirty = False
        self._populate_file_list()
        self._file_list.selection_set(self._selected_index)
        messagebox.showinfo("Skeleton", "Vorlagen-Metadaten gespeichert.", parent=self)

    def _reload_markdown_after_sync(self, md_path: Path) -> None:
        """Lädt das Text-Widget nach `sync_markdown_order()` neu.

        Ohne diesen Refresh würde ein nachfolgendes "Markdown speichern" den
        (im Widget noch veralteten) `order`-Wert zurück auf die Platte
        schreiben und den gerade erst hergestellten Sync sofort wieder
        zerstören.
        """
        try:
            content = md_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", content)
        self._editor_dirty = False
        self._text.edit_modified(False)

    def _add_file(self) -> None:
        if self._manifest is None:
            return
        title = simpledialog.askstring("Neue Vorlage", "Titel der Vorlage:", parent=self)
        if not title:
            return
        suggested = f"content/required/{title.strip().replace(' ', '_')}.md"
        rel = simpledialog.askstring(
            "Pfad im Skeleton-Profil",
            "Relativer Pfad im Profilordner (nicht im Buch):\n"
            f"Profil: {self._manifest.root}",
            initialvalue=suggested,
            parent=self,
        )
        if not rel:
            return
        order_raw = simpledialog.askstring("order", "order (leer = keine feste Position):", parent=self)
        order = order_raw.strip() if order_raw else None
        try:
            target = create_markdown_template(
                self._manifest.root, rel, title=title.strip(), order=order
            )
            norm_path = str(target.relative_to(self._manifest.root)).replace("\\", "/")
            new_entry = SkeletonFileEntry(path=norm_path, title=title.strip(), order=order)
            self._entries.append(new_entry)
            self._manifest = replace_manifest_entries(
                self._manifest.root,
                self._entries,
                name=self._manifest.name,
                label=self._manifest.label,
                description=self._manifest.description,
            )
            self._entries = list(self._manifest.files)
            self._populate_file_list()
            self._file_list.selection_clear(0, tk.END)
            self._file_list.selection_set(len(self._entries) - 1)
            self._on_file_selected()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Skeleton", str(exc), parent=self)

    def _remove_entry(self) -> None:
        entry = self._current_entry()
        if entry is None or self._manifest is None:
            return
        file_path = self._manifest.root / entry.path
        delete_file = messagebox.askyesnocancel(
            "Vorlage löschen",
            f"Vorlage „{entry.title}“ aus dem Skeleton-Pool entfernen?\n\n"
            f"Pfad: {file_path.resolve()}\n\n"
            "Ja = aus Profil entfernen und Datei löschen\n"
            "Nein = nur aus Profil entfernen (Datei bleibt liegen)\n"
            "Abbrechen = nichts tun",
            parent=self,
        )
        if delete_file is None:
            return
        if delete_file and file_path.is_file():
            try:
                file_path.unlink()
            except OSError as exc:
                messagebox.showerror(
                    "Skeleton",
                    f"Datei konnte nicht gelöscht werden:\n{exc}",
                    parent=self,
                )
                return
        del self._entries[self._selected_index]
        self._manifest = replace_manifest_entries(
            self._manifest.root,
            self._entries,
            name=self._manifest.name,
            label=self._manifest.label,
            description=self._manifest.description,
        )
        self._entries = list(self._manifest.files)
        self._selected_index = None
        self._populate_file_list()
        self._clear_editor()

    def _duplicate_profile(self) -> None:
        if self._manifest is None:
            return
        dest = simpledialog.askstring(
            "Profil duplizieren",
            "Name für das neue Profil:",
            parent=self,
        )
        if not dest:
            return
        label = simpledialog.askstring("Label", "Anzeige-Label (optional):", parent=self)
        try:
            dest_name = validate_profile_name(dest)
            duplicate_profile(self.library_root, self._manifest.name, dest_name, label=label)
            self._reload_profiles(dest_name)
            messagebox.showinfo("Skeleton", f"Profil '{dest_name}' erstellt.", parent=self)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Skeleton", str(exc), parent=self)

    def _save_profile_meta(self) -> None:
        if self._manifest is None:
            return
        try:
            self._manifest = update_manifest_meta(
                self._manifest.root,
                label=self._profile_label_var.get().strip(),
                description=self._profile_desc_var.get().strip(),
            )
            messagebox.showinfo("Skeleton", "Profil-Metadaten gespeichert.", parent=self)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Skeleton", str(exc), parent=self)

    def _set_default_profile(self) -> None:
        if self._manifest is None:
            return
        try:
            set_default_profile(_repo_root(), self._manifest.name)
            messagebox.showinfo(
                "Skeleton",
                f"Standard-Profil gesetzt: {self._manifest.name}",
                parent=self,
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("Skeleton", str(exc), parent=self)

    def _delete_profile(self) -> None:
        if self._manifest is None:
            return
        if not messagebox.askyesno(
            "Profil löschen",
            f"Profil '{self._manifest.name}' unwiderruflich löschen?",
            parent=self,
        ):
            return
        name = self._manifest.name
        try:
            delete_profile(self.library_root, name)
            self._reload_profiles()
            messagebox.showinfo("Skeleton", f"Profil '{name}' gelöscht.", parent=self)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Skeleton", str(exc), parent=self)

    def _close(self) -> None:
        if self._confirm_discard():
            self.destroy()

    def show(self) -> None:
        self.wait_window()


def open_editor(
    parent: Optional[tk.Misc] = None,
    *,
    library_root: Path,
    initial_profile: Optional[str] = None,
    studio: Any = None,
) -> None:
    window = SkeletonEditorWindow(
        parent,
        library_root=library_root,
        initial_profile=initial_profile,
        studio=studio,
    )
    window.show()


def run(studio: Any = None, **kwargs: Any) -> int:
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from app_config import read_config

    cfg = read_config(repo_root / "app_config.json")
    library_root = resolve_library_root(
        repo_root,
        str(kwargs.get("library_root") or cfg.get("skeleton_library_path") or "tools/skeleton/library"),
    )
    if not library_root.is_dir():
        messagebox.showerror(
            "Skeleton-Editor",
            f"Bibliothek nicht gefunden:\n{library_root}",
            parent=getattr(studio, "root", None),
        )
        return 1

    parent = getattr(studio, "root", None) if studio is not None else None
    profile = kwargs.get("profile") or cfg.get("skeleton_default_profile")
    try:
        open_editor(parent, library_root=library_root, initial_profile=profile, studio=studio)
    except (OSError, ValueError) as exc:
        messagebox.showerror("Skeleton-Editor", str(exc), parent=parent)
        _LOG.exception("Skeleton editor failed")
        return 1
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Skeleton-Bibliothek bearbeiten.")
    parser.add_argument("--profile", default=None, help="Initial ausgewähltes Profil")
    args = parser.parse_args(argv)
    return run(studio=None, profile=args.profile)


if __name__ == "__main__":
    raise SystemExit(main())
