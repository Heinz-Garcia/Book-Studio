"""Dialoge für Skeleton-Populate (Vorschau, Konflikte, Bestätigung)."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Callable, Literal, Optional

ConflictMode = Literal["ask", "skip", "replace"]
RunConflictChoice = Literal["skip", "replace"]


@dataclass(frozen=True)
class PopulatePlanLine:
    rel_path: str
    exists: bool
    will_copy: bool
    include_in_tree: bool
    title: str


@dataclass(frozen=True)
class PopulateDialogResult:
    confirmed: bool
    conflict_choice: Optional[RunConflictChoice] = None
    remember_conflict_choice: bool = False


def _build_explanation(manifest_label: str, book_name: str, lines: list[PopulatePlanLine]) -> str:
    new_count = sum(1 for line in lines if line.will_copy and not line.exists)
    replace_count = sum(1 for line in lines if line.will_copy and line.exists)
    skip_count = sum(1 for line in lines if not line.will_copy and line.exists)
    tree_count = sum(1 for line in lines if line.will_copy and line.include_in_tree)

    parts = [
        f"Skeleton-Profil: {manifest_label}",
        f"Zielbuch: {book_name}",
        "",
        "Was passiert beim Bestätigen:",
        "1) Ausgewählte Vorlagen werden als KOPIE ins Buchprojekt geschrieben.",
        "2) Pflicht-Frontmatter wird bei neuen Dateien ergänzt (title, description, status).",
        "3) Neue Kapitel werden in den Buchbaum eingetragen (required-ORDER wird beachtet).",
        "4) _quarto.yml und .gui_state.json werden gespeichert (Struktur persistiert).",
        "5) Bereits vorhandene Dateien werden je nach Konflikt-Entscheidung übersprungen oder ersetzt.",
        "",
        f"Geplant: {new_count} neu, {replace_count} ersetzen, {skip_count} überspringen, "
        f"{tree_count} in den Buchbaum.",
    ]
    return "\n".join(parts)


class PopulateConfirmDialog(tk.Toplevel):
    """Modaler Bestätigungsdialog mit Konflikt-Optionen."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        manifest_label: str,
        book_name: str,
        lines: list[PopulatePlanLine],
        has_conflicts: bool,
        default_conflict: RunConflictChoice = "skip",
        on_remember: Optional[Callable[[RunConflictChoice], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.title("Skeleton ins Buch übernehmen")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(560, 420)

        self._result = PopulateDialogResult(confirmed=False)
        self._on_remember = on_remember

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        explanation = _build_explanation(manifest_label, book_name, lines)
        expl = tk.Text(body, height=12, wrap=tk.WORD, relief=tk.FLAT, bg=self.cget("bg"))
        expl.insert("1.0", explanation)
        expl.configure(state=tk.DISABLED)
        expl.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(body, text="Dateien:").pack(anchor=tk.W)
        list_frame = ttk.Frame(body)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        columns = ("path", "action")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        tree.heading("path", text="Pfad")
        tree.heading("action", text="Aktion")
        tree.column("path", width=360, stretch=True)
        tree.column("action", width=140, stretch=False)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for line in lines:
            if not line.exists:
                action = "kopieren (neu)"
            elif line.will_copy:
                action = "ersetzen"
            else:
                action = "überspringen"
            if line.will_copy and not line.include_in_tree:
                action += " · nicht im Baum"
            tree.insert("", tk.END, values=(line.rel_path, action))

        conflict_frame = ttk.LabelFrame(body, text="Bei bereits vorhandenen Dateien", padding=8)
        self._conflict_var = tk.StringVar(value=default_conflict)
        self._remember_var = tk.BooleanVar(value=False)

        if has_conflicts:
            conflict_frame.pack(fill=tk.X, pady=(0, 8))
            ttk.Radiobutton(
                conflict_frame,
                text="Vorhandene Dateien überspringen (empfohlen)",
                variable=self._conflict_var,
                value="skip",
            ).pack(anchor=tk.W)
            ttk.Radiobutton(
                conflict_frame,
                text="Vorhandene Dateien durch Skeleton-Kopie ersetzen",
                variable=self._conflict_var,
                value="replace",
            ).pack(anchor=tk.W)
            ttk.Checkbutton(
                conflict_frame,
                text="Entscheidung merken (für künftige Skeleton-Läufe)",
                variable=self._remember_var,
            ).pack(anchor=tk.W, pady=(6, 0))
        else:
            conflict_frame.pack_forget()

        btn_row = ttk.Frame(body)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="Abbrechen", command=self._cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_row, text="Übernehmen und speichern", command=self._confirm).pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.update_idletasks()
        self.geometry("720x560")

    def _cancel(self) -> None:
        self._result = PopulateDialogResult(confirmed=False)
        self.destroy()

    def _confirm(self) -> None:
        choice: Optional[RunConflictChoice] = self._conflict_var.get()  # type: ignore[assignment]
        remember = bool(self._remember_var.get())
        if remember and choice and self._on_remember:
            self._on_remember(choice)
        self._result = PopulateDialogResult(
            confirmed=True,
            conflict_choice=choice,
            remember_conflict_choice=remember,
        )
        self.destroy()

    def show(self) -> PopulateDialogResult:
        self.wait_window()
        return self._result


def ask_populate_confirmation(
    parent: tk.Misc,
    *,
    manifest_label: str,
    book_name: str,
    lines: list[PopulatePlanLine],
    has_conflicts: bool,
    default_conflict: RunConflictChoice = "skip",
    on_remember: Optional[Callable[[RunConflictChoice], None]] = None,
) -> PopulateDialogResult:
    dialog = PopulateConfirmDialog(
        parent,
        manifest_label=manifest_label,
        book_name=book_name,
        lines=lines,
        has_conflicts=has_conflicts,
        default_conflict=default_conflict,
        on_remember=on_remember,
    )
    return dialog.show()


def show_result_message(parent: Optional[tk.Misc], title: str, message: str, *, is_error: bool = False) -> None:
    if parent is None:
        print(f"{title}: {message}")
        return
    if is_error:
        messagebox.showerror(title, message, parent=parent)
    else:
        messagebox.showinfo(title, message, parent=parent)
