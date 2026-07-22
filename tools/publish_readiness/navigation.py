"""Navigation von Publish-Readiness-Befunden zur Problemzeile."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from tkinter import messagebox


def resolve_issue_line(studio: Any, issue: dict[str, Any]) -> Optional[int]:
    """Ermittelt die Zeilennummer für einen Befund."""
    line = issue.get("line_number")
    if isinstance(line, int) and line > 0:
        return line
    path = (issue.get("path") or "").strip()
    if not path or path == "—":
        return None
    registry = getattr(studio, "doctor_issue_line_registry", None) or {}
    fallback = registry.get(path)
    if isinstance(fallback, int) and fallback > 0:
        return fallback
    return None


def jump_to_issue(
    studio: Any,
    issue: dict[str, Any],
    *,
    parent: Any = None,
) -> bool:
    """Öffnet die betroffene Datei im Editor und springt zur Zeile."""
    path = (issue.get("path") or "").strip()
    if not path or path == "—":
        messagebox.showinfo(
            "Publish Readiness",
            "Dieser Befund ist keiner Datei zugeordnet (z. B. Pool-Hinweis).\n"
            "Details stehen im Buch-Doktor-Log.",
            parent=parent,
        )
        return False

    if not getattr(studio, "current_book", None):
        return False

    target_file = Path(studio.current_book) / path
    if not target_file.is_file():
        messagebox.showwarning(
            "Publish Readiness",
            f"Datei nicht gefunden:\n{path}",
            parent=parent,
        )
        return False

    opener = getattr(studio, "open_log_target", None)
    if not callable(opener):
        return False

    line = resolve_issue_line(studio, issue)
    opener(path, line)
    return True
