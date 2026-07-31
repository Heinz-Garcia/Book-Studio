"""SSOT: Gliederungspunkte (``content_role: outline``).

Reine Markdown-Seiten ohne GrammarGraph-Nutzinhalt — nur Struktur
(z. B. „Teil I“, „Anhang“). Erkennung: ``yaml_engine`` / ``content_source``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

OUTLINE_CONTENT_ROLE = "outline"
_DEFAULT_DIR = "content"


def slugify_outline_stem(title: str, *, max_len: int = 48) -> str:
    """Dateiname-Stamm aus Titel (ASCII-freundlich, Windows-tauglich)."""
    text = (title or "").strip()
    for src, dst in (
        ("ä", "ae"),
        ("ö", "oe"),
        ("ü", "ue"),
        ("Ä", "Ae"),
        ("Ö", "Oe"),
        ("Ü", "Ue"),
        ("ß", "ss"),
    ):
        text = text.replace(src, dst)
    text = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("._")
    if not text:
        text = "Gliederungspunkt"
    return text[:max_len]


def suggest_outline_rel_path(title: str) -> str:
    """Vorschlag: ``content/<Slug>.md``."""
    return f"{_DEFAULT_DIR}/{slugify_outline_stem(title)}.md"


def build_outline_markdown(title: str) -> str:
    """Minimaler Markdown mit Frontmatter für einen Gliederungspunkt."""
    clean = (title or "").strip() or "Gliederungspunkt"
    # YAML double-quoted: escape internal quotes
    safe = clean.replace("\\", "\\\\").replace('"', '\\"')
    return (
        "---\n"
        f'title: "{safe}"\n'
        f'description: "{safe}"\n'
        "status: bookstudio\n"
        f"content_role: {OUTLINE_CONTENT_ROLE}\n"
        "---\n"
        "\n"
        f"# {clean}\n"
        "\n"
        "<!-- Gliederungspunkt: strukturelle Überschrift ohne Kapiteltext. -->\n"
    )


def unique_outline_rel_path(book_path: Path, preferred_rel: str) -> str:
    """Falls die Datei existiert: ``Name_2.md``, ``Name_3.md``, …"""
    rel = preferred_rel.replace("\\", "/").lstrip("/")
    if not rel.lower().endswith(".md"):
        rel = f"{rel}.md"
    candidate = Path(rel)
    if not (book_path / candidate).exists():
        return candidate.as_posix()
    stem = candidate.stem
    parent = candidate.parent.as_posix()
    for n in range(2, 1000):
        alt = Path(parent) / f"{stem}_{n}.md"
        if not (book_path / alt).exists():
            return alt.as_posix()
    raise FileExistsError(f"Kein freier Dateiname für {preferred_rel}")


def write_outline_page(
    book_path: Path,
    title: str,
    *,
    rel_path: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """Schreibt die Outline-``.md`` und gibt den relativen Pfad zurück."""
    book = Path(book_path)
    preferred = (rel_path or suggest_outline_rel_path(title)).replace("\\", "/").lstrip("/")
    if not preferred.lower().endswith(".md"):
        preferred = f"{preferred}.md"
    if overwrite:
        rel = preferred
    else:
        rel = unique_outline_rel_path(book, preferred)
    target = book / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_outline_markdown(title), encoding="utf-8")
    return Path(rel).as_posix()


__all__ = [
    "OUTLINE_CONTENT_ROLE",
    "build_outline_markdown",
    "slugify_outline_stem",
    "suggest_outline_rel_path",
    "unique_outline_rel_path",
    "write_outline_page",
]
