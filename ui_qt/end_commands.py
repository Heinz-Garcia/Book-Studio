"""End-Befehle für den Markdown-Editor (Seitenumbruch am Dateiende u. a.)."""

from __future__ import annotations

import re
from typing import Any, Optional


DEFAULT_PAGEBREAK_COMMAND: dict[str, Any] = {
    "id": "pdf_pagebreak_end",
    "label": "PDF-Seitenumbruch am Dateiende",
    "append_text": "```{=typst}\n#pagebreak()\n```\n",
    "detect_pattern": r"```\{=typst\}\s*#pagebreak(?:\([^\)]*\))?\s*```\s*\Z",
    "marks_state": "pdf_pagebreak_end",
}


def insert_end_command_text(
    content: str,
    command: dict[str, Any],
) -> tuple[Optional[str], str, str]:
    """Fügt einen End-Befehl ans Dateiende.

    Returns:
        (new_content | None, message, level)
        level: ``ok`` | ``warn`` | ``error``
        Bei Already-present / Fehler ist ``new_content`` None.
    """
    append_text = str(command.get("append_text") or "")
    label = str(command.get("label") or "Befehl")
    if not append_text.strip():
        return None, "Kein gültiger End-Befehl konfiguriert.", "error"

    detect_pattern = command.get("detect_pattern")
    if detect_pattern:
        try:
            if re.search(str(detect_pattern), content, re.DOTALL | re.MULTILINE):
                return None, f"„{label}“ ist am Dateiende bereits vorhanden.", "warn"
        except re.error:
            pass

    base = content.rstrip("\n")
    addition = append_text.strip("\n")
    if base:
        new_content = f"{base}\n\n{addition}\n"
    else:
        new_content = f"{addition}\n"
    return new_content, f"„{label}“ eingefügt (noch nicht gespeichert).", "ok"
