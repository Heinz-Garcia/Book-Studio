"""Reine Text-Transformationslogik für die Formatier-Buttons im Markdown-Editor.

Kein Qt-Import - `ui_qt/dialogs/text_dialogs.py` verdrahtet das gegen den
echten `QTextCursor`. Die Syntax orientiert sich an Pandoc-Markdown, wie es
diese App tatsächlich rendert (Quarto/Pandoc -> Typst); siehe insbesondere
`wrap_selection` für Inline-Marker (**fett**, *kursiv*, ...) und
`apply_line_prefix` für Block-Präfixe (Liste, Zitat).
"""

from __future__ import annotations

import re
from typing import Callable, NamedTuple


class WrapResult(NamedTuple):
    """Ersatztext für eine (evtl. leere) Auswahl + relative Selektion danach,
    damit der Aufrufer sofort weiterschreiben kann (Platzhalter oder
    ursprünglich ausgewählter Text bleibt markiert)."""

    replacement: str
    select_from: int
    select_to: int


def wrap_selection(selected: str, before: str, after: str, placeholder: str = "Text") -> WrapResult:
    """Umschließt `selected` mit `before`/`after`. Ohne Auswahl wird ein
    Platzhalter eingefügt und selektiert."""
    if selected:
        return WrapResult(f"{before}{selected}{after}", len(before), len(before) + len(selected))
    return WrapResult(f"{before}{placeholder}{after}", len(before), len(before) + len(placeholder))


_HEADING_RE = re.compile(r"^#{1,6}[ \t]*")


def set_heading_level(line: str, level: int) -> str:
    """Setzt/ersetzt die führenden '#' einer Zeile auf `level` (1-6)."""
    content = _HEADING_RE.sub("", line, count=1)
    return f"{'#' * level} {content}"


_LINE_PREFIX_PATTERNS = (
    re.compile(r"^[-*+][ \t]+"),  # Aufzählungsliste
    re.compile(r"^\d+\.[ \t]+"),  # Nummerierte Liste
    re.compile(r"^>[ \t]*"),  # Zitat
)


def _strip_known_line_prefix(line: str) -> str:
    for pattern in _LINE_PREFIX_PATTERNS:
        stripped = pattern.sub("", line, count=1)
        if stripped != line:
            return stripped
    return line


def apply_line_prefix(lines: list[str], marker_for_index: Callable[[int], str]) -> list[str]:
    """Setzt pro nicht-leerer Zeile ein Präfix (z. B. "- ", "> ", "3. ").

    Entfernt zuerst ein evtl. vorhandenes anderes Zeilen-Präfix (Liste/Zitat),
    damit sich der Zeilentyp per Klick sauber wechseln lässt statt sich zu
    stapeln. `marker_for_index` bekommt den 1-basierten Index, gezählt nur
    über nicht-leere Zeilen (für fortlaufende Nummerierung bei Mehrfachauswahl)."""
    result = []
    n = 0
    for line in lines:
        if not line.strip():
            result.append(line)
            continue
        n += 1
        result.append(marker_for_index(n) + _strip_known_line_prefix(line))
    return result


def table_skeleton(columns: int = 2, rows: int = 2) -> str:
    """Pandoc-Pipe-Table-Grundgerüst (führt zu einer echten Tabelle beim Rendern)."""
    header = "| " + " | ".join(f"Spalte {i + 1}" for i in range(columns)) + " |"
    divider = "| " + " | ".join("---" for _ in range(columns)) + " |"
    body_lines = ["| " + " | ".join("Zelle" for _ in range(columns)) + " |" for _ in range(rows)]
    return "\n".join([header, divider, *body_lines])


def next_footnote_index(text: str) -> int:
    """Nächste freie Fußnoten-Nummer, basierend auf vorhandenen `[^n]`-Referenzen."""
    used = {int(m) for m in re.findall(r"\[\^(\d+)\]", text)}
    n = 1
    while n in used:
        n += 1
    return n
