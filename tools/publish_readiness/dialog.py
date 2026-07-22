"""Tk-Dialog: Publish Readiness (Owner, Schwere, Fix-Spur)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import tkinter as tk
from tkinter import messagebox, ttk

from tools.publish_readiness.analysis import enrich_analysis
from tools.publish_readiness.navigation import jump_to_issue
from tools.provenance.io import read_provenance
from ui_theme import COLORS, FONTS, style_dialog

def _owner_summary(issues: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in issues:
        label = item.get("owner_label", item.get("owner", "?"))
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return "Keine Befunde."
    return " · ".join(f"{name}: {count}" for name, count in sorted(counts.items()))


def _issue_count_label(issues: list[dict[str, Any]], *, healthy: bool) -> str:
    if not issues:
        return (
            "0 Befunde — Buch wirkt bereit (Pool-Hinweise siehe Buch-Doktor-Log)."
            if healthy
            else "0 Befunde in der Matrix — kritische Meldungen evtl. nur im Log."
        )
    blockers = sum(1 for i in issues if i.get("severity") == "blocker")
    warnings = sum(1 for i in issues if i.get("severity") == "warning")
    infos = len(issues) - blockers - warnings
    parts = [f"{len(issues)} Befund{'e' if len(issues) != 1 else ''}"]
    if blockers:
        parts.append(f"{blockers} Blocker")
    if warnings:
        parts.append(f"{warnings} Warnungen")
    if infos:
        parts.append(f"{infos} Hinweise")
    return " · ".join(parts)


class PublishReadinessDialog:
    def __init__(self, studio: Any, *, analysis: Optional[dict] = None) -> None:
        self.studio = studio
        self._analysis = analysis
        self._issues: list[dict[str, Any]] = []
        self._window: Optional[tk.Toplevel] = None
        self._tree: Optional[ttk.Treeview] = None

    def show(self) -> None:
        parent = getattr(self.studio, "root", None)
        if parent is None:
            return
        if not getattr(self.studio, "current_book", None):
            messagebox.showwarning("Publish Readiness", "Kein Buchprojekt aktiv.", parent=parent)
            return

        analysis = self._analysis
        if analysis is None and hasattr(self.studio, "_run_doctor_check"):
            _, analysis = self.studio._run_doctor_check(
                "Publish Readiness",
                emit_success_log=False,
            )
        if not analysis:
            messagebox.showwarning(
                "Publish Readiness",
                "Buch-Doktor-Analyse nicht verfügbar.",
                parent=parent,
            )
            return

        self._issues = enrich_analysis(analysis, studio=self.studio)
        self._open_window(parent, analysis)

    def _open_window(self, parent: tk.Misc, analysis: dict) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            return

        win = tk.Toplevel(parent)
        self._window = win
        style_dialog(win, title="Publish Readiness")
        win.geometry("980x520")
        win.minsize(720, 360)

        header = ttk.Frame(win, padding=(12, 10, 12, 6))
        header.pack(fill="x")

        healthy = bool(analysis.get("is_healthy"))
        status = "Bereit" if healthy else "Nicht bereit"
        status_fg = COLORS.get("success", "#16a34a") if healthy else COLORS.get("danger", "#dc2626")
        ttk.Label(
            header,
            text=f"Status: {status}",
            font=FONTS.get("heading", ("Segoe UI", 11, "bold")),
            foreground=status_fg,
        ).pack(anchor="w")
        ttk.Label(header, text=_owner_summary(self._issues), wraplength=900).pack(anchor="w", pady=(4, 0))
        count_text = _issue_count_label(self._issues, healthy=healthy)
        ttk.Label(header, text=count_text, foreground=COLORS.get("text_muted", "#64748b")).pack(
            anchor="w", pady=(2, 0)
        )

        provenance = read_provenance(Path(self.studio.current_book))
        if provenance:
            exported = provenance.get("exported_at", "—")
            llm = provenance.get("llm") or {}
            model = llm.get("model") or "—"
            ttk.Label(
                header,
                text=f"Provenance: Export {exported} · Modell {model}",
                foreground=COLORS.get("dim", "#6b7280"),
            ).pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(win, padding=(12, 6, 12, 6))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        columns = ("severity", "owner", "path", "line", "fix_lane", "message")
        tree = ttk.Treeview(
            body,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=max(8, min(len(self._issues), 18)),
        )
        self._tree = tree
        tree.heading("severity", text="Schwere")
        tree.heading("owner", text="Owner")
        tree.heading("path", text="Datei")
        tree.heading("line", text="Zeile")
        tree.heading("fix_lane", text="Fix-Spur")
        tree.heading("message", text="Befund")
        tree.column("severity", width=72, stretch=False)
        tree.column("owner", width=100, stretch=False)
        tree.column("path", width=160, stretch=False)
        tree.column("line", width=44, stretch=False, anchor=tk.CENTER)
        tree.column("fix_lane", width=120, stretch=False)
        tree.column("message", width=380, stretch=True)

        scroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        if not self._issues:
            empty = ttk.Label(
                body,
                text=(
                    "Keine Befunde in der Tabelle."
                    if healthy
                    else "Keine zuordenbaren Befunde — bitte Tools → Buch-Doktor ausführen und Log prüfen."
                ),
                foreground=COLORS.get("text_muted", "#64748b"),
                wraplength=860,
                justify="left",
            )
            empty.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        for item in self._issues:
            line = item.get("line_number")
            line_text = str(line) if isinstance(line, int) and line > 0 else ""
            tree.insert(
                "",
                "end",
                values=(
                    item.get("severity", ""),
                    item.get("owner_label", ""),
                    item.get("path", ""),
                    line_text,
                    item.get("fix_lane_label", ""),
                    item.get("message", ""),
                ),
            )

        tree.bind("<Double-1>", lambda _e: self._jump_selected(win))
        tree.bind("<Return>", lambda _e: self._jump_selected(win))
        if self._issues:
            ttk.Label(
                body,
                text="Doppelklick oder Enter: Editor an Problemzeile · Button „Zur Fundstelle“",
                foreground=COLORS.get("text_muted", "#64748b"),
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        footer = ttk.Frame(win, padding=(12, 6, 12, 12))
        footer.pack(fill="x")
        ttk.Button(footer, text="Schließen", command=win.destroy).pack(side="right")
        ttk.Button(
            footer,
            text="Erneut prüfen",
            command=lambda: self._rerun(parent, win),
        ).pack(side="right", padx=(0, 8))
        ttk.Button(
            footer,
            text="Zur Fundstelle ➜",
            command=lambda: self._jump_selected(win),
        ).pack(side="right", padx=(0, 8))

        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def _selected_issue(self) -> Optional[dict[str, Any]]:
        tree = self._tree
        if tree is None:
            return None
        selected = tree.selection()
        if not selected:
            return None
        idx = tree.index(selected[0])
        if 0 <= idx < len(self._issues):
            return self._issues[idx]
        return None

    def _jump_selected(self, parent: tk.Misc) -> None:
        issue = self._selected_issue()
        if issue is None:
            messagebox.showinfo(
                "Publish Readiness",
                "Bitte zuerst einen Befund in der Tabelle auswählen.",
                parent=parent,
            )
            return
        jump_to_issue(self.studio, issue, parent=parent)

    def _rerun(self, parent: tk.Misc, win: tk.Toplevel) -> None:
        if not hasattr(self.studio, "_run_doctor_check"):
            return
        _, analysis = self.studio._run_doctor_check("Publish Readiness", emit_success_log=False)
        if not analysis:
            return
        self._analysis = analysis
        win.destroy()
        self._window = None
        self.show()


def open_publish_readiness_dialog(studio: Any, **kwargs) -> None:
    PublishReadinessDialog(studio, analysis=kwargs.get("analysis")).show()
