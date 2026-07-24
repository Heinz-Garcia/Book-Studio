"""Datei-Statusmarker und Icon-Legende (Tk-Parität für Qt).

Prefix-Icons (📌 required, 🧬 GrammarGraph, 🧭 outline) kommen aus ``yaml_engine.build_title_registry``.
Suffix-Icons (↵ Seitenumbruch, 🖼 fehlende Bilder, ☠ Doktor) werden hier ergänzt.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Optional

from markdown_asset_scanner import find_missing_image_refs
from services.constants import MarkerState

# Vollständige Legende — Anzeige im mittleren Aktionsbereich
ICON_LEGEND_TITLE = "Icon-Legende"
ICON_LEGEND_LINES: tuple[str, ...] = (
    "📌 required (Frontmatter required: true)",
    "🧬 GrammarGraph-Nutzinhalt (automatisch: nicht Required/Skeleton)",
    "🧭 Nur Gliederungspunkt",
    "↵ Seitenumbruch am Dateiende",
    "🖼 Fehlende Bildreferenz",
    "☠ Buch-Doktor-Befund",
    "📌/🧬/🧭 vor Titel · ↵/🖼/☠ dahinter",
)

_DEFAULT_PAGEBREAK = re.compile(
    r"```\{=typst\}\s*#pagebreak(?:\([^\)]*\))?\s*```\s*\Z",
    re.DOTALL,
)


def _pagebreak_patterns(editor_end_commands: Optional[Iterable[dict[str, Any]]]) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    for command in editor_end_commands or ():
        if not isinstance(command, dict):
            continue
        if command.get("marks_state") != MarkerState.PDF_PAGEBREAK_END.value:
            continue
        pattern = command.get("detect_pattern")
        if not pattern:
            continue
        try:
            patterns.append(re.compile(str(pattern), re.DOTALL | re.MULTILINE))
        except re.error:
            continue
    if not patterns:
        patterns.append(_DEFAULT_PAGEBREAK)
    return patterns


def build_file_state_registry(
    book_path: Path,
    paths: Iterable[str],
    *,
    editor_end_commands: Optional[Iterable[dict[str, Any]]] = None,
) -> dict[str, dict[str, Any]]:
    """Scannt Markdown-Dateien auf Seitenumbruch und fehlende Bilder."""
    book = Path(book_path)
    pagebreak_patterns = _pagebreak_patterns(editor_end_commands)
    registry: dict[str, dict[str, Any]] = {}

    for path in paths:
        state: dict[str, Any] = {
            "pdf_pagebreak_end": False,
            "missing_images": False,
            "missing_images_count": 0,
            "missing_image_targets": (),
            "missing_image_refs": (),
        }
        if not str(path).lower().endswith(".md"):
            registry[path] = state
            continue

        abs_path = book / path
        if not abs_path.is_file():
            registry[path] = state
            continue

        try:
            text = abs_path.read_text(encoding="utf-8")
        except OSError:
            registry[path] = state
            continue

        state["pdf_pagebreak_end"] = any(pattern.search(text) for pattern in pagebreak_patterns)
        missing_image_refs = find_missing_image_refs(text, abs_path, book)
        missing_images = [target for _, target in missing_image_refs]
        state["missing_images"] = bool(missing_image_refs)
        state["missing_images_count"] = len(missing_image_refs)
        state["missing_image_targets"] = tuple(sorted(set(missing_images)))
        state["missing_image_refs"] = tuple(missing_image_refs)
        registry[path] = state

    return registry


def decorate_title(
    title: str,
    path: str,
    *,
    file_state: Optional[dict[str, Any]] = None,
    doctor_issue_paths: Optional[Iterable[str]] = None,
) -> str:
    """Hängt Suffix-Marker an den Anzeigetitel (ohne doppelte Anhänge)."""
    if not path:
        return title

    base = _strip_status_suffixes(str(title))
    state = file_state or {}
    doctor_set = set(doctor_issue_paths or ())

    suffixes: list[str] = []
    if state.get("pdf_pagebreak_end"):
        suffixes.append("↵")
    if state.get("missing_images"):
        suffixes.append("🖼")
    if path in doctor_set:
        suffixes.append("☠")

    if not suffixes:
        return base
    return f"{base} {' '.join(suffixes)}"


_SUFFIX_TAIL = re.compile(r"(?:\s+[↵🖼☠]+)+\s*$")


def _strip_status_suffixes(title: str) -> str:
    return _SUFFIX_TAIL.sub("", title).rstrip()
