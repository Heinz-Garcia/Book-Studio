"""Tk-Dialog: Publish Readiness (Owner, Schwere, Fix-Spur)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import tkinter as tk
from tkinter import messagebox, ttk

from tools.publish_readiness.analysis import build_readiness_report, enrich_analysis
from tools.provenance.io import read_provenance
from ui_theme import COLORS, FONTS, style_dialog

_SEVERITY_COLORS = {
    "blocker": COLORS.get("danger", "#dc2626"),
    "warning": COLORS.get("warning", "#d97706"),
    "info": COLORS.get("dim", "#6b7280"),
}


def _owner_summary(issues: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in issues:
        label = item.get("owner_label", item.get("owner", "?"))
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return "Keine Befunde."
    return " · ".join(f"{name}: {count}" for name, count in sorted(counts.items()))


class PublishReadinessDialog:
    def __init__(self, studio: Any, *, analysis: Optional[dict] = None) -> None:
        self.studio = studio
        self._analysis = analysis
        self._issues: list[dict[str, Any]] = []
        self._window: Optional[tk.Toplevel] = None

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

        self._issues = enrich_analysis(analysis)
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

        columns = ("severity", "owner", "path", "fix_lane", "message")
        tree = ttk.Treeview(body, columns=columns, show="headings", selectmode="browse")
        tree.heading("severity", text="Schwere")
        tree.heading("owner", text="Owner")
        tree.heading("path", text="Datei")
        tree.heading("fix_lane", text="Fix-Spur")
        tree.heading("message", text="Befund")
        tree.column("severity", width=80, stretch=False)
        tree.column("owner", width=110, stretch=False)
        tree.column("path", width=180, stretch=False)
        tree.column("fix_lane", width=130, stretch=False)
        tree.column("message", width=420, stretch=True)

        scroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for item in self._issues:
            iid = tree.insert(
                "",
                "end",
                values=(
                    item.get("severity", ""),
                    item.get("owner_label", ""),
                    item.get("path", ""),
                    item.get("fix_lane_label", ""),
                    item.get("message", ""),
                ),
            )
            color = _SEVERITY_COLORS.get(item.get("severity", ""), "")
            if color:
                tree.tag_configure(item.get("severity", ""), foreground=color)
                tree.item(iid, tags=(item.get("severity", ""),))

        footer = ttk.Frame(win, padding=(12, 6, 12, 12))
        footer.pack(fill="x")
        ttk.Button(footer, text="Schließen", command=win.destroy).pack(side="right")
        ttk.Button(
            footer,
            text="Erneut prüfen",
            command=lambda: self._rerun(parent, win),
        ).pack(side="right", padx=(0, 8))

        win.protocol("WM_DELETE_WINDOW", win.destroy)

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
