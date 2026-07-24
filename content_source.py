"""SSOT: Inhalts-Herkunft / GG-Nutzinhalt-Erkennung.

Regel (Book Studio):
- Skeleton-/Rahmen-Seiten (``required: true`` bzw. Legacy ``content/required/``)
  und ``index.md`` sowie Gliederungspunkte (``content_role: outline``)
  gehören Book Studio.
- Alle anderen Markdown-Dateien sind GrammarGraph-Nutzinhalt-Kandidaten
  (typisch eine aggregierte Inhaltsdatei).

Optional weiterhin Frontmatter ``content_source: grammargraph`` als
explizites Opt-in (nicht mehr nötig für den Normalfall).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

import frontmatter_parser
from page_required import is_page_required

CONTENT_SOURCE_KEY = "content_source"
CONTENT_SOURCE_GRAMMARGRAPH = "grammargraph"


def normalize_content_source(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def content_source_from_mapping(data: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not isinstance(data, dict) or CONTENT_SOURCE_KEY not in data:
        return None
    return normalize_content_source(data.get(CONTENT_SOURCE_KEY))


def is_grammargraph_content(
    *,
    frontmatter: Optional[Mapping[str, Any]] = None,
    content: Optional[str] = None,
) -> bool:
    """True bei explizitem ``content_source: grammargraph``."""
    fm = frontmatter
    if fm is None and content is not None:
        parts = frontmatter_parser.parse(content)
        if parts.has_frontmatter:
            parsed = parts.parsed()
            if isinstance(parsed, dict):
                fm = parsed
    return content_source_from_mapping(fm if isinstance(fm, dict) else None) == (
        CONTENT_SOURCE_GRAMMARGRAPH
    )


def _content_role(content: Optional[str]) -> Optional[str]:
    if not content:
        return None
    role = frontmatter_parser.extract_field(content, "content_role")
    return role.strip().lower() if role else None


def is_gg_nutzinhalt_candidate(
    *,
    rel_path: str,
    content: Optional[str] = None,
) -> bool:
    """Automatische GG-Erkennung: nicht Rahmen/index/outline.

    Explizites ``content_source: grammargraph`` erzwingt True (auch wenn
    die Datei sonst als Rahmen gälte — Ausnahme für Spezialfälle).
    """
    rel = str(rel_path).replace("\\", "/").lstrip("./")
    if is_grammargraph_content(content=content):
        return True
    if rel.lower() == "index.md" or rel.lower().endswith("/index.md"):
        # Nur Root-index ausschließen; content/.../index.md eher ungewöhnlich
        if "/" not in rel:
            return False
    if is_page_required(rel_path=rel, content=content):
        return False
    if _content_role(content) == "outline":
        return False
    return True


def is_grammargraph_file(path: Path, *, book_root: Optional[Path] = None) -> bool:
    path = Path(path)
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if book_root is not None:
        try:
            rel = path.resolve().relative_to(Path(book_root).resolve()).as_posix()
        except ValueError:
            rel = path.name
        return is_gg_nutzinhalt_candidate(rel_path=rel, content=text)
    return is_gg_nutzinhalt_candidate(rel_path=path.name, content=text)


def apply_content_source_to_content(
    content: str,
    source: Optional[str],
) -> str:
    """Setzt oder entfernt Frontmatter ``content_source`` (Legacy/Opt-in)."""
    import yaml

    parts = frontmatter_parser.parse(content)
    newline = "\r\n" if "\r\n" in content else "\n"
    normalized = normalize_content_source(source)

    if not parts.has_frontmatter:
        if not normalized:
            return content
        header = yaml.safe_dump(
            {CONTENT_SOURCE_KEY: normalized},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).rstrip("\r\n")
        return (
            parts.bom
            + "---"
            + newline
            + header
            + newline
            + "---"
            + newline
            + (parts.body if parts.body is not None else content)
        )

    data = parts.parsed()
    if not isinstance(data, dict):
        data = {}

    current = normalize_content_source(data.get(CONTENT_SOURCE_KEY))
    if normalized:
        if current == normalized:
            return content
        data[CONTENT_SOURCE_KEY] = normalized
    else:
        if CONTENT_SOURCE_KEY not in data:
            return content
        data.pop(CONTENT_SOURCE_KEY, None)

    header_text = yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).rstrip("\r\n")
    return (
        parts.bom
        + "---"
        + newline
        + header_text
        + newline
        + "---"
        + newline
        + parts.body
    )


def toggle_grammargraph_in_content(content: str) -> tuple[str, bool]:
    """Legacy: schaltet ``content_source: grammargraph``."""
    new_state = not is_grammargraph_content(content=content)
    source = CONTENT_SOURCE_GRAMMARGRAPH if new_state else None
    return apply_content_source_to_content(content, source), new_state


__all__ = [
    "CONTENT_SOURCE_GRAMMARGRAPH",
    "CONTENT_SOURCE_KEY",
    "apply_content_source_to_content",
    "content_source_from_mapping",
    "is_gg_nutzinhalt_candidate",
    "is_grammargraph_content",
    "is_grammargraph_file",
    "normalize_content_source",
    "toggle_grammargraph_in_content",
]
