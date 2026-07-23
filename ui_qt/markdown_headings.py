"""Überschriften-Ebenen in Markdown-Quellen verschieben (Einrücken/Ausrücken)."""

from __future__ import annotations

import re
from pathlib import Path

from frontmatter_parser import parse
from quarto_block_parser import iter_body_lines_outside_code_fences

_HEADING_RE = re.compile(r"^(#+)(\s+.*)$")
_MIN_LEVEL = 1
_MAX_LEVEL = 6


def shift_body_headings(body: str, delta: int) -> str:
    """Verschiebt AT-Überschriften im Body um ``delta`` (Clamp 1–6).

    Zeilen in Code-Fences bleiben unverändert. ``delta==0`` → unverändert.
    """
    if not delta or not body:
        return body

    lines: list[str] = []
    for _num, line, in_fence in iter_body_lines_outside_code_fences(body):
        if in_fence:
            lines.append(line)
            continue
        match = _HEADING_RE.match(line)
        if match is None:
            lines.append(line)
            continue
        level = len(match.group(1))
        new_level = max(_MIN_LEVEL, min(_MAX_LEVEL, level + delta))
        lines.append("#" * new_level + match.group(2))

    new_body = "\n".join(lines)
    if body.endswith(("\n", "\r\n", "\r")) and not new_body.endswith("\n"):
        new_body += "\n"
    return new_body


def shift_markdown_headings(content: str, delta: int) -> str:
    """Frontmatter unverändert; Body-Überschriften um ``delta`` verschieben."""
    if not delta:
        return content
    parts = parse(content)
    new_body = shift_body_headings(parts.body, delta)
    if not parts.has_frontmatter:
        return f"{parts.bom}{new_body}"
    header = parts.header or ""
    if header and not header.endswith("\n"):
        header += "\n"
    return f"{parts.bom}---\n{header}---\n{new_body}"


def shift_markdown_file(path: Path, delta: int) -> bool:
    """Liest Datei, verschiebt Überschriften, schreibt zurück.

    Returns True wenn geschrieben wurde. False bei delta=0, fehlender Datei
    oder unverändertem Inhalt.
    """
    if not delta:
        return False
    target = Path(path)
    if not target.is_file():
        return False
    original = target.read_text(encoding="utf-8")
    updated = shift_markdown_headings(original, delta)
    if updated == original:
        return False
    target.write_text(updated, encoding="utf-8")
    return True


__all__ = [
    "shift_body_headings",
    "shift_markdown_file",
    "shift_markdown_headings",
]
