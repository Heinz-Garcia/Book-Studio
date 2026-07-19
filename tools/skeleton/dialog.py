"""Dialoge für Skeleton-Populate (Vorschau, Konflikte, Bestätigung)."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Callable, Literal, Optional

from tools.skeleton.diff import FileDiffInfo

ConflictMode = Literal["ask", "skip", "replace"]
RunConflictChoice = Literal["skip", "replace"]
PopulateMode = Literal["all", "missing_only"]


@dataclass(frozen=True)
class PopulatePlanLine:
    rel_path: str
    exists: bool
    will_copy: bool
    include_in_tree: bool
    title: str
    diff_summary: str = ""
    optional: bool = False


@dataclass(frozen=True)
class PopulateDialogResult:
    confirmed: bool
    conflict_choice: Optional[RunConflictChoice] = None
    remember_conflict_choice: bool = False
    selected_profile: Optional[str] = None
    missing_only: bool = False
    remember_populate_mode: bool = False
    include_optional: bool = False


def ask_profile_selection(
    parent: tk.Misc,
    profiles: list[str],
    *,
    default_profile: Optional[str] = None,
    labels: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Profil-Auswahl vor dem Populate-Dialog."""
    if not profiles:
        return None
    if len(profiles) == 1:
        return profiles[0]

    labels = labels or {}
    dialog = tk.Toplevel(parent)
    dialog.title("Skeleton-Profil wählen")
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)

    chosen: dict[str, Optional[str]] = {"value": None}
    var = tk.StringVar(value=default_profile if default_profile in profiles else profiles[0])

    body = ttk.Frame(dialog, padding=12)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(body, text="Welches Skeleton-Profil soll ins Buch kopiert werden?").pack(anchor=tk.W, pady=(0, 8))

    combo = ttk.Combobox(body, textvariable=var, state="readonly", width=48)
    display = [f"{name} — {labels.get(name, name)}" for name in profiles]
    combo["values"] = display
    if default_profile in profiles:
        combo.current(profiles.index(default_profile))
    combo.pack(fill=tk.X, pady=(0, 12))

    def confirm() -> None:
        idx = combo.current()
        if idx < 0:
            idx = 0
        chosen["value"] = profiles[idx]
        dialog.destroy()

    def cancel() -> None:
        chosen["value"] = None
        dialog.destroy()

    row = ttk.Frame(body)
    row.pack(fill=tk.X)
    ttk.Button(row, text="Abbrechen", command=cancel).pack(side=tk.RIGHT, padx=(6, 0))
    ttk.Button(row, text="Weiter", command=confirm).pack(side=tk.RIGHT)
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.wait_window()
    return chosen["value"]


def _build_explanation(manifest_label: str, book_name: str, lines: list[PopulatePlanLine]) -> str:
    new_count = sum(1 for line in lines if line.will_copy and not line.exists)
    replace_count = sum(1 for line in lines if line.will_copy and line.exists)
    skip_count = sum(1 for line in lines if not line.will_copy)
    optional_skip_count = sum(1 for line in lines if not line.will_copy and line.optional)
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
        "6) Optionale Slots (z. B. Widmung, Vorlagen-Referenz) werden nur bei aktivierter "
        "Checkbox mitkopiert.",
        "",
        f"Geplant: {new_count} neu, {replace_count} ersetzen, {skip_count} überspringen "
        f"(davon {optional_skip_count} optional), {tree_count} in den Buchbaum.",
    ]
    return "\n".join(parts)


class DiffViewerDialog(tk.Toplevel):
    """Zeigt Unified-Diff für eine Skeleton-Datei."""

    def __init__(self, parent: tk.Misc, *, title: str, diff_text: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.geometry("820x520")
        body = ttk.Frame(self, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        text = tk.Text(body, wrap=tk.NONE, font=("Consolas", 10))
        xscroll = ttk.Scrollbar(body, orient=tk.HORIZONTAL, command=text.xview)
        yscroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=text.yview)
        text.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        text.insert("1.0", diff_text)
        text.configure(state=tk.DISABLED)
        ttk.Button(body, text="Schließen", command=self.destroy).grid(row=2, column=0, columnspan=2, pady=(8, 0))
        self.protocol("WM_DELETE_WINDOW", self.destroy)


def _action_label(line: PopulatePlanLine) -> str:
    if not line.will_copy and line.optional:
        action = "überspringen (optional)"
    elif not line.exists:
        action = "kopieren (neu)"
    elif line.will_copy:
        action = "ersetzen"
    else:
        action = "überspringen"
    if line.will_copy and not line.include_in_tree:
        action += " · nicht im Baum"
    return action


def _apply_plan_rules(
    base_lines: list[PopulatePlanLine],
    *,
    conflict_choice: RunConflictChoice,
    missing_only: bool,
    include_optional: bool = False,
) -> list[PopulatePlanLine]:
    """Berechnet `will_copy` je Zeile aus Konflikt-Modus, Missing-Only und
    dem `optional`-Flag (Batch 2: `optional: true`-Slots werden standard-
    mäßig NICHT mitkopiert, es sei denn `include_optional=True`)."""
    updated: list[PopulatePlanLine] = []
    for line in base_lines:
        if line.optional and not include_optional:
            will_copy = False
        elif line.exists:
            will_copy = False if missing_only else conflict_choice == "replace"
        else:
            will_copy = True
        updated.append(
            PopulatePlanLine(
                rel_path=line.rel_path,
                exists=line.exists,
                will_copy=will_copy,
                include_in_tree=line.include_in_tree,
                title=line.title,
                diff_summary=line.diff_summary,
                optional=line.optional,
            )
        )
    return updated


class PopulateConfirmDialog(tk.Toplevel):
    """Modaler Bestätigungsdialog mit Konflikt-Optionen."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        manifest_label: str,
        profile_name: str,
        book_name: str,
        lines: list[PopulatePlanLine],
        has_conflicts: bool,
        default_conflict: RunConflictChoice = "skip",
        populate_mode: PopulateMode = "all",
        diff_map: Optional[dict[str, FileDiffInfo]] = None,
        on_remember: Optional[Callable[[RunConflictChoice], None]] = None,
        on_remember_mode: Optional[Callable[[PopulateMode], None]] = None,
        include_optional: bool = False,
    ) -> None:
        super().__init__(parent)
        self.title("Skeleton ins Buch übernehmen")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(560, 420)

        self._result = PopulateDialogResult(confirmed=False)
        self._on_remember = on_remember
        self._on_remember_mode = on_remember_mode
        self._profile_name = profile_name
        self._manifest_label = manifest_label
        self._book_name = book_name
        self._base_lines = lines
        self._diff_map = diff_map or {}

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        self._conflict_var = tk.StringVar(value=default_conflict)
        self._remember_var = tk.BooleanVar(value=False)
        self._remember_mode_var = tk.BooleanVar(value=False)
        self._missing_only_var = tk.BooleanVar(value=populate_mode == "missing_only")
        self._include_optional_var = tk.BooleanVar(value=include_optional)

        explanation = _build_explanation(
            manifest_label,
            book_name,
            _apply_plan_rules(
                lines,
                conflict_choice=default_conflict,
                missing_only=populate_mode == "missing_only",
                include_optional=include_optional,
            ),
        )
        expl = tk.Text(body, height=10, wrap=tk.WORD, relief=tk.FLAT, bg=self.cget("bg"))
        expl.insert("1.0", explanation)
        expl.configure(state=tk.DISABLED)
        expl.pack(fill=tk.X, pady=(0, 8))
        self._expl_widget = expl
        self._full_explanation_prefix = explanation.split("Geplant:")[0].rstrip()

        list_header = ttk.Frame(body)
        list_header.pack(fill=tk.X)
        ttk.Label(list_header, text="Dateien:").pack(side=tk.LEFT)
        ttk.Button(list_header, text="Diff für Auswahl…", command=self._show_diff).pack(side=tk.RIGHT)

        list_frame = ttk.Frame(body)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        columns = ("path", "diff", "action")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        self._tree.heading("path", text="Pfad")
        self._tree.heading("diff", text="Diff")
        self._tree.heading("action", text="Aktion")
        self._tree.column("path", width=300, stretch=True)
        self._tree.column("diff", width=100, stretch=False)
        self._tree.column("action", width=160, stretch=False)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<Double-1>", lambda _e: self._show_diff())

        mode_frame = ttk.LabelFrame(body, text="Modus", padding=8)
        mode_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(
            mode_frame,
            text="Nur fehlende Dateien übernehmen (vorhandene nie ersetzen)",
            variable=self._missing_only_var,
            command=self._refresh_plan_view,
        ).pack(anchor=tk.W)
        ttk.Checkbutton(
            mode_frame,
            text="Modus merken (skeleton_populate_mode in app_config.json)",
            variable=self._remember_mode_var,
        ).pack(anchor=tk.W, pady=(4, 0))
        ttk.Checkbutton(
            mode_frame,
            text="Optionale Slots mitnehmen (z. B. Widmung, Vorlagen-Referenz)",
            variable=self._include_optional_var,
            command=self._refresh_plan_view,
        ).pack(anchor=tk.W, pady=(4, 0))

        conflict_frame = ttk.LabelFrame(body, text="Bei bereits vorhandenen Dateien", padding=8)
        self._conflict_frame = conflict_frame

        if has_conflicts:
            conflict_frame.pack(fill=tk.X, pady=(0, 8))
            ttk.Radiobutton(
                conflict_frame,
                text="Vorhandene Dateien überspringen (empfohlen)",
                variable=self._conflict_var,
                value="skip",
                command=self._refresh_plan_view,
            ).pack(anchor=tk.W)
            ttk.Radiobutton(
                conflict_frame,
                text="Vorhandene Dateien durch Skeleton-Kopie ersetzen",
                variable=self._conflict_var,
                value="replace",
                command=self._refresh_plan_view,
            ).pack(anchor=tk.W)
            ttk.Checkbutton(
                conflict_frame,
                text="Entscheidung merken (für künftige Skeleton-Läufe)",
                variable=self._remember_var,
            ).pack(anchor=tk.W, pady=(6, 0))
        else:
            conflict_frame.pack_forget()

        self._refresh_plan_view()

        btn_row = ttk.Frame(body)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="Abbrechen", command=self._cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_row, text="Übernehmen und speichern", command=self._confirm).pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.update_idletasks()
        self.geometry("800x620")

    def _current_missing_only(self) -> bool:
        return bool(self._missing_only_var.get())

    def _current_conflict_choice(self) -> RunConflictChoice:
        return self._conflict_var.get()  # type: ignore[return-value]

    def _current_include_optional(self) -> bool:
        return bool(self._include_optional_var.get())

    def _current_plan(self) -> list[PopulatePlanLine]:
        return _apply_plan_rules(
            self._base_lines,
            conflict_choice=self._current_conflict_choice(),
            missing_only=self._current_missing_only(),
            include_optional=self._current_include_optional(),
        )

    def _refresh_plan_view(self) -> None:
        plan = self._current_plan()
        for item in self._tree.get_children():
            self._tree.delete(item)
        for line in plan:
            diff_summary = line.diff_summary or self._diff_map.get(line.rel_path, None)
            if hasattr(diff_summary, "summary"):
                diff_text = diff_summary.summary
            else:
                diff_text = str(diff_summary or ("neu" if not line.exists else "—"))
            self._tree.insert("", tk.END, values=(line.rel_path, diff_text, _action_label(line)))

        missing_only = self._current_missing_only()
        for child in self._conflict_frame.winfo_children():
            try:
                child.configure(state="disabled" if missing_only else "normal")
            except tk.TclError:
                pass

        plan = self._current_plan()
        new_count = sum(1 for line in plan if line.will_copy and not line.exists)
        replace_count = sum(1 for line in plan if line.will_copy and line.exists)
        skip_count = sum(1 for line in plan if not line.will_copy)
        optional_skip_count = sum(1 for line in plan if not line.will_copy and line.optional)
        tree_count = sum(1 for line in plan if line.will_copy and line.include_in_tree)
        mode_hint = "\n[Modus: Nur fehlende Dateien]\n" if missing_only else ""
        self._expl_widget.configure(state=tk.NORMAL)
        self._expl_widget.delete("1.0", tk.END)
        self._expl_widget.insert(
            "1.0",
            self._full_explanation_prefix
            + mode_hint
            + f"\nGeplant: {new_count} neu, {replace_count} ersetzen, {skip_count} überspringen "
            f"(davon {optional_skip_count} optional), {tree_count} in den Buchbaum.\n\n"
            "Tipp: Doppelklick oder „Diff für Auswahl…“ zeigt Textunterschiede.",
        )
        self._expl_widget.configure(state=tk.DISABLED)

    def _show_diff(self) -> None:
        selection = self._tree.selection()
        if not selection:
            messagebox.showinfo("Diff", "Bitte zuerst eine Datei auswählen.", parent=self)
            return
        rel_path = self._tree.item(selection[0], "values")[0]
        info = self._diff_map.get(rel_path)
        if info is None:
            messagebox.showinfo("Diff", "Keine Diff-Daten für diese Datei.", parent=self)
            return
        DiffViewerDialog(self, title=f"Diff: {rel_path}", diff_text=info.unified_diff)

    def _cancel(self) -> None:
        self._result = PopulateDialogResult(confirmed=False)
        self.destroy()

    def _confirm(self) -> None:
        choice: Optional[RunConflictChoice] = self._current_conflict_choice()
        remember = bool(self._remember_var.get())
        missing_only = self._current_missing_only()
        remember_mode = bool(self._remember_mode_var.get())
        include_optional = self._current_include_optional()
        if remember and choice and self._on_remember:
            self._on_remember(choice)
        if remember_mode and self._on_remember_mode:
            self._on_remember_mode("missing_only" if missing_only else "all")
        self._result = PopulateDialogResult(
            confirmed=True,
            conflict_choice=choice,
            remember_conflict_choice=remember,
            selected_profile=self._profile_name,
            missing_only=missing_only,
            remember_populate_mode=remember_mode,
            include_optional=include_optional,
        )
        self.destroy()

    def show(self) -> PopulateDialogResult:
        self.wait_window()
        return self._result


def ask_populate_confirmation(
    parent: tk.Misc,
    *,
    manifest_label: str,
    profile_name: str,
    book_name: str,
    lines: list[PopulatePlanLine],
    has_conflicts: bool,
    default_conflict: RunConflictChoice = "skip",
    populate_mode: PopulateMode = "all",
    diff_map: Optional[dict[str, FileDiffInfo]] = None,
    on_remember: Optional[Callable[[RunConflictChoice], None]] = None,
    on_remember_mode: Optional[Callable[[PopulateMode], None]] = None,
    include_optional: bool = False,
) -> PopulateDialogResult:
    dialog = PopulateConfirmDialog(
        parent,
        manifest_label=manifest_label,
        profile_name=profile_name,
        book_name=book_name,
        lines=lines,
        has_conflicts=has_conflicts,
        default_conflict=default_conflict,
        populate_mode=populate_mode,
        diff_map=diff_map,
        on_remember=on_remember,
        on_remember_mode=on_remember_mode,
        include_optional=include_optional,
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
