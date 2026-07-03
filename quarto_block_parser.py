"""Quarto-Block-Parser – SSOT (Single Source of Truth) für ::: {…} Divs.

Vor dem Refactoring gab es **drei** verschiedene Fenced-Div-Parser:
- `book_doctor.find_fenced_div_issues` (mit Klartext-Issues)
- `export_manager._detect_fenced_div_issues` (mit Issue-Kind-Codes)
- `Sanitizer._find_unclosed_answer_divs` (nur `{.answer}`-Divs)

Sie teilten denselben Algorithmus, aber divergierten in den Issue-Strings
und im Detail-Umfang. Das führte zu inkonsistenten Meldungen.

Dieses Modul bündelt die Erkennung in einer stabilen API.

API:
    FencedDivIssue                   – Dataclass mit line_number und kind
    find_fenced_div_issues(body, …)  → list[FencedDivIssue]
    find_unclosed_answer_divs(body)  → list[dict]

Issue-Kinds (kanonisch):
    "unclosed-open"     – Öffner ohne Schluss
    "orphan-close"      – Schluss ohne Öffner
    "mismatched-close"  – Schluss-Marker passt nicht zum Top-Öffner
    "inline"            – ':::' außerhalb eines Markers (z. B. im Fließtext)

Referenz: .doc/refactoring-master.md, Batch B3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# --- Regex-Konstanten -------------------------------------------------------

# 3 oder mehr Doppelpunkte am Zeilenanfang (mit Whitespace davor erlaubt).
# Die zweite Gruppe erfasst den Rest (Attribute, schließendes Marker, etc.).
_MARKER_PATTERN = re.compile(r"^\s*(:{3,})(\s*.*)$")
# Code-Fence: ``` oder ~~~ mit beliebig vielen Folgezeichen
_CODE_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")
# Div-Öffner mit Pandoc-Attributen: `::: {key=value}`
_DIV_OPEN_PATTERN = re.compile(r"^\s*:::+\s*\{[^}]+\}\s*$")
# Div-Schließer: `:::`, `::::`, etc. ohne weitere Zeichen
_DIV_CLOSE_PATTERN = re.compile(r"^\s*:::+\s*$")
# Spezifischer `{.answer}`-Öffner
_ANSWER_DIV_OPEN_PATTERN = re.compile(r"^\s*:::+\s*\{[^}]*\B\.answer\b[^}]*\}\s*$")


# --- Datenklasse ------------------------------------------------------------


@dataclass
class FencedDivIssue:
    """Ein einzelner Fenced-Div-Befund."""

    line_number: int
    kind: str  # "unclosed-open" | "orphan-close" | "mismatched-close" | "inline"

    def __repr__(self) -> str:
        return f"FencedDivIssue(line={self.line_number}, kind={self.kind!r})"


# --- Haupt-API --------------------------------------------------------------


def find_fenced_div_issues(
    body: str,
    base_line_number: int = 1,
) -> list[FencedDivIssue]:
    """Findet alle Fenced-Div-Probleme im `body`.

    Erkennt:
    - ungeschlossene Öffner (z. B. `::: {.note}` ohne `:::`-Ende)
    - verwaiste Schließer (z. B. `:::` ohne vorherigen Öffner)
    - falsch verschachtelte Schließer (z. B. `:::` schließt `::::`)
    - Inline-`:::`-Vorkommen im Fließtext (außerhalb von Markern)
    - ignoriert `:::`-Vorkommen in Code-Blöcken (zwischen ```-Fences)

    `base_line_number` ist der Offset für die Zeilennummern (z. B. 1 + Anzahl
    der Header-Zeilen), damit die Befunde auf die Originaldatei zeigen.
    """
    issues: list[FencedDivIssue] = []
    stack: list[tuple[int, int]] = []  # (colon_count, line_number)
    in_code_block = False

    for offset, raw_line in enumerate(body.splitlines()):
        line = raw_line.rstrip("\r")
        line_number = base_line_number + offset

        if _CODE_FENCE_PATTERN.match(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        marker_match = _MARKER_PATTERN.match(line)
        if marker_match:
            colon_count = len(marker_match.group(1))
            tail = marker_match.group(2).strip()

            if tail:
                # Öffner (mit Attributen oder Inhalt danach)
                stack.append((colon_count, line_number))
            else:
                # Schließer
                if stack:
                    top_colon_count, _top_line = stack[-1]
                    if colon_count >= top_colon_count:
                        stack.pop()
                    else:
                        issues.append(
                            FencedDivIssue(line_number, "mismatched-close")
                        )
                else:
                    issues.append(
                        FencedDivIssue(line_number, "orphan-close")
                    )
            continue

        if ":::" in line:
            issues.append(FencedDivIssue(line_number, "inline"))

    for _colon_count, open_line in stack:
        issues.append(FencedDivIssue(open_line, "unclosed-open"))

    return issues


def find_unclosed_answer_divs(body: str) -> list[dict]:
    """Findet ungeschlossene `{.answer}`-Divs im `body`.

    Liefert eine Liste von Dicts mit `is_answer` (True) und `line_number`.
    Andere Div-Typen werden ignoriert.

    Wird vom Sanitizer für `--only-unclosed-answer-div-check` benutzt.
    """
    stack: list[dict] = []
    for line_number, raw_line in enumerate(body.splitlines(), start=1):
        line = raw_line.rstrip("\r")

        if _DIV_CLOSE_PATTERN.match(line):
            if stack:
                stack.pop()
            continue

        if _DIV_OPEN_PATTERN.match(line):
            stack.append(
                {
                    "is_answer": bool(_ANSWER_DIV_OPEN_PATTERN.match(line)),
                    "line_number": line_number,
                }
            )

    return [entry for entry in stack if entry["is_answer"]]


# --- Mapping-Helper für Legacy-Issue-Strings --------------------------------


# Mapping von kanonischen Issue-Kinds zu den Legacy-Klartextmeldungen
# (kompatibel zu `book_doctor.find_fenced_div_issues`).
LEGACY_ISSUE_MESSAGES: dict[str, str] = {
    "unclosed-open": "❌ FENCED-DIV FEHLER: Öffnender :::-Marker ohne passenden Abschluss.",
    "orphan-close": "❌ FENCED-DIV FEHLER: Schließender :::-Marker ohne passende Öffnung.",
    "mismatched-close": "❌ FENCED-DIV FEHLER: Schließender :::-Marker passt nicht zur Öffnung.",
    "inline": "❌ FENCED-DIV WARNZEICHEN: ':::' im Fließtext gefunden (möglicherweise defekter Div-Block).",
}


def to_legacy_tuples(issues: list[FencedDivIssue]) -> list[tuple[int, str]]:
    """Konvertiert eine Liste von `FencedDivIssue` in das Legacy-Format
    `(line_number, message_str)` aus `book_doctor.find_fenced_div_issues`."""
    return [
        (issue.line_number, LEGACY_ISSUE_MESSAGES.get(issue.kind, issue.kind))
        for issue in issues
    ]


__all__ = [
    "FencedDivIssue",
    "LEGACY_ISSUE_MESSAGES",
    "find_fenced_div_issues",
    "find_unclosed_answer_divs",
    "to_legacy_tuples",
]
