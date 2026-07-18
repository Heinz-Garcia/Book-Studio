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
    repair_orphan_fenced_div_closes(content) → (content, removed_line_numbers)

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


def iter_body_lines_outside_code_fences(body: str):
    """Liefert (line_number, line, in_code_fence) für jede Body-Zeile.

    `line_number` ist 1-basiert relativ zum `body`-Anfang (Aufrufer
    addiert ggf. `base_line_number` selbst, analog zu
    `find_fenced_div_issues`). `in_code_fence=True` für Zeilen
    innerhalb ```-/~~~-Code-Blöcken (inkl. der Fence-Zeilen selbst).

    Merkt sich den öffnenden Fence-Typ (Zeichen ` bzw. ~ und Lauflänge)
    und schließt nur bei einer Fence-Zeile desselben Zeichens mit
    mindestens gleicher Länge (CommonMark-Semantik) — verhindert, dass
    ein `~~~`-Fence in einem verschachtelten Beispiel einen äußeren
    ```-Block vorzeitig schließt (R1, Rescan 2026-07-18).
    """
    in_code_block = False
    fence_char = None
    fence_len = 0
    for offset, raw_line in enumerate(body.splitlines()):
        line = raw_line.rstrip("\r")
        line_number = offset + 1
        match = _CODE_FENCE_PATTERN.match(line)
        if match:
            marker = match.group(1)
            char = marker[0]
            length = len(marker)
            if not in_code_block:
                in_code_block = True
                fence_char = char
                fence_len = length
            elif char == fence_char and length >= fence_len:
                in_code_block = False
                fence_char = None
                fence_len = 0
            # sonst: fence-ähnliche Zeile eines anderen Typs/kürzerer
            # Länge INNERHALB eines offenen Blocks -> bleibt "in_fence",
            # togglet den Zustand NICHT.
            yield line_number, line, True
            continue
        yield line_number, line, in_code_block


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


def _detect_newline(content: str) -> str:
    if "\r\n" in content:
        return "\r\n"
    if "\r" in content:
        return "\r"
    return "\n"


def repair_orphan_fenced_div_closes(content: str) -> tuple[str, list[int]]:
    """Entfernt verwaiste schließende ``:::``-Zeilen (orphan-close) im Body.

    Analog zu ``frontmatter_parser.repair_hidden_yaml_dividers``: konservative
    Auto-Reparatur vor dem Render-Preflight. Frontmatter bleibt unangetastet;
    Code-Fences werden respektiert. Nicht geheilt werden ``unclosed-open``,
    ``mismatched-close`` und ``inline`` (zu riskant / mehrdeutig).

    Returns:
        ``(new_content, removed_line_numbers)`` — die Zeilennummern sind
        1-basiert bezogen auf die Originaldatei (identisch zum Buch-Doktor),
        damit Auto-Healing-Logs ``L3611`` etc. anzeigen können. Leere Liste
        bedeutet: keine Änderung.

    Lazy-Import von ``frontmatter_parser``, um den Circular-Import zu vermeiden
    (``frontmatter_parser`` importiert bereits dieses Modul).
    """
    from frontmatter_parser import parse as fm_parse

    parts = fm_parse(content)
    body = parts.body
    newline = _detect_newline(content)

    # Body-Offset wie in book_doctor.analyze_health — damit Log-Zeilen
    # denselben L-Nummern entsprechen wie die Vorabcheck-Befunde.
    if parts.has_frontmatter:
        opener_count = 1 + parts.duplicate_opening_count
        if parts.had_closing_delimiter:
            opener_count += 1
        body_base = (
            (1 if parts.bom else 0)
            + opener_count
            + len((parts.header or "").splitlines())
            + 1
        )
    else:
        body_base = 1

    stack: list[int] = []  # colon_count of open divs
    new_body_lines: list[str] = []
    removed_lines: list[int] = []

    for body_line_number, line, in_fence in iter_body_lines_outside_code_fences(body):
        if in_fence:
            new_body_lines.append(line)
            continue

        marker_match = _MARKER_PATTERN.match(line)
        if marker_match:
            colon_count = len(marker_match.group(1))
            tail = marker_match.group(2).strip()
            if tail:
                stack.append(colon_count)
                new_body_lines.append(line)
            elif stack:
                top_colon_count = stack[-1]
                if colon_count >= top_colon_count:
                    stack.pop()
                # mismatched-close: Zeile behalten (nicht auto-heilen)
                new_body_lines.append(line)
            else:
                # orphan-close: Zeile entfernen und Datei-Zeile merken
                removed_lines.append(body_base + body_line_number - 1)
            continue

        new_body_lines.append(line)

    if not removed_lines:
        return content, []

    new_body = newline.join(new_body_lines)
    if body.endswith(("\n", "\r\n", "\r")) and not new_body.endswith(("\n", "\r")):
        new_body += newline

    if not parts.has_frontmatter:
        new_content = parts.bom + new_body
        if not new_content.endswith(("\n", "\r")) and content.endswith(("\n", "\r\n", "\r")):
            new_content += newline
        return new_content, removed_lines

    header_text = (parts.header or "").rstrip("\r\n") + newline
    closing = f"---{newline}"
    body_text = new_body
    if not body_text.startswith(("\n", "\r")) and body_text:
        body_text = newline + body_text

    new_content = parts.bom + "---" + newline + header_text + closing + body_text
    if not new_content.endswith(("\n", "\r")):
        new_content += newline
    return new_content, removed_lines


__all__ = [
    "FencedDivIssue",
    "LEGACY_ISSUE_MESSAGES",
    "find_fenced_div_issues",
    "find_unclosed_answer_divs",
    "iter_body_lines_outside_code_fences",
    "repair_orphan_fenced_div_closes",
    "to_legacy_tuples",
]
