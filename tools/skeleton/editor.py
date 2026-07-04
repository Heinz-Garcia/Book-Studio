"""Skeleton-Bibliothek bearbeiten (autonomes Tk-Fenster)."""

from __future__ import annotations

import argparse
import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Optional

from tools.skeleton.manifest import (
    SkeletonFileEntry,
    SkeletonManifest,
    create_markdown_template,
    duplicate_profile,
    list_profiles,
    load_manifest,
    replace_manifest_entries,
    resolve_library_root,
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


class SkeletonEditorWindow(tk.Toplevel):
    """Editor für Skeleton-Profile, Manifest-Einträge und Markdown-Vorlagen."""

    def __init__(
        self,
        parent: Optional[tk.Misc],
        *,
        library_root: Path,
        initial_profile: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.title("Skeleton-Bibliothek bearbeiten")
        self.library_root = Path(library_root).resolve()
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
        self._title_var = tk.StringVar()
        self._order_var = tk.StringVar()
        self._optional_var = tk.BooleanVar(value=False)
        self._include_tree_var = tk.BooleanVar(value=True)

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
        ttk.Button(top, text="Aktualisieren", command=lambda: self._reload_profiles(self._profile_var.get())).pack(
            side=tk.LEFT, padx=4
        )

        info = ttk.Label(
            outer,
            text=(
                "Bearbeite hier die Skeleton-VORLAGEN (nicht die Dateien im Buch). "
                "Änderungen gelten für künftige Populate-Läufe."
            ),
            wraplength=900,
        )
        info.pack(anchor=tk.W, pady=(0, 8))

        paned = ttk.Panedwindow(outer, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, padding=(0, 0, 8, 0))
        paned.add(left, weight=1)
        ttk.Label(left, text="Dateien im Profil").pack(anchor=tk.W)
        self._file_list = tk.Listbox(left, exportselection=False, height=18)
        self._file_list.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        self._file_list.bind("<<ListboxSelect>>", lambda _e: self._on_file_selected())

        left_btns = ttk.Frame(left)
        left_btns.pack(fill=tk.X)
        ttk.Button(left_btns, text="Neue Datei…", command=self._add_file).pack(side=tk.LEFT)
        ttk.Button(left_btns, text="Eintrag entfernen", command=self._remove_entry).pack(side=tk.LEFT, padx=6)

        right = ttk.Frame(paned, padding=(8, 0, 0, 0))
        paned.add(right, weight=3)

        meta = ttk.LabelFrame(right, text="Manifest-Eintrag", padding=8)
        meta.pack(fill=tk.X, pady=(0, 8))
        grid = ttk.Frame(meta)
        grid.pack(fill=tk.X)
        ttk.Label(grid, text="Titel").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid, textvariable=self._title_var, width=40).grid(row=0, column=1, sticky=tk.EW, padx=6)
        ttk.Label(grid, text="order").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid, textvariable=self._order_var, width=16).grid(row=1, column=1, sticky=tk.W, padx=6)
        ttk.Checkbutton(grid, text="optional", variable=self._optional_var).grid(row=2, column=1, sticky=tk.W)
        ttk.Checkbutton(grid, text="in Buchbaum aufnehmen", variable=self._include_tree_var).grid(
            row=3, column=1, sticky=tk.W
        )
        grid.columnconfigure(1, weight=1)
        ttk.Button(meta, text="Manifest-Eintrag speichern", command=self._save_entry_meta).pack(anchor=tk.E, pady=(6, 0))

        ttk.Label(right, text="Markdown-Inhalt").pack(anchor=tk.W)
        self._text = tk.Text(right, wrap=tk.WORD, undo=True, height=20)
        scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self._text.yview)
        self._text.configure(yscrollcommand=scroll.set)
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(4, 0))
        scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(4, 0))
        self._text.bind("<<Modified>>", self._on_text_modified)

        bottom = ttk.Frame(outer)
        bottom.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(bottom, text="Markdown speichern", command=self._save_markdown).pack(side=tk.LEFT)
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
            flags = []
            if entry.optional:
                flags.append("opt")
            if not entry.include_in_tree:
                flags.append("no-tree")
            suffix = f"  [{', '.join(flags)}]" if flags else ""
            self._file_list.insert(tk.END, f"{entry.path}{suffix}")

    def _clear_editor(self) -> None:
        self._title_var.set("")
        self._order_var.set("")
        self._optional_var.set(False)
        self._include_tree_var.set(True)
        self._text.delete("1.0", tk.END)
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
        if path.is_file():
            content = path.read_text(encoding="utf-8")
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
            include_in_tree=bool(self._include_tree_var.get()),
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
        self._meta_dirty = False
        self._populate_file_list()
        self._file_list.selection_set(self._selected_index)
        messagebox.showinfo("Skeleton", "Manifest-Eintrag gespeichert.", parent=self)

    def _add_file(self) -> None:
        if self._manifest is None:
            return
        rel = simpledialog.askstring(
            "Neue Skeleton-Datei",
            "Relativer Pfad (z. B. content/required/Vorwort.md):",
            parent=self,
        )
        if not rel:
            return
        rel = rel.replace("\\", "/").strip().lstrip("/")
        title = simpledialog.askstring("Titel", "Anzeige-Titel:", parent=self) or Path(rel).stem
        order_raw = simpledialog.askstring("order", "order (leer = keine feste Position):", parent=self)
        order = order_raw.strip() if order_raw else None
        try:
            target = create_markdown_template(self._manifest.root, rel, title=title, order=order)
            norm_path = str(target.relative_to(self._manifest.root)).replace("\\", "/")
            new_entry = SkeletonFileEntry(path=norm_path, title=title, order=order)
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
        if not messagebox.askyesno(
            "Eintrag entfernen",
            f"Nur Manifest-Eintrag entfernen?\n(Die Datei {entry.path} bleibt auf der Platte.)",
            parent=self,
        ):
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
) -> None:
    window = SkeletonEditorWindow(parent, library_root=library_root, initial_profile=initial_profile)
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
        open_editor(parent, library_root=library_root, initial_profile=profile)
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
