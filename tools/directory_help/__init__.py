"""Verzeichnis-Hilfe: README.md in Whitelist-Ordnern → Hilfe-Abschnitt.

Jedes strukturelle Verzeichnis kann eine ``README.md`` (oder ``_readme.md``)
tragen. Die Hilfe aggregiert diese Texte live beim Öffnen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

README_CANDIDATES = ("README.md", "_readme.md")

# Relativ zum Repo-Root. Nur diese Ordner erscheinen in der Hilfe.
BOOK_STUDIO_DIRECTORY_HELP: tuple[str, ...] = (
    "production",
    "production/books",
    "production/inbox",
    "tools/skeleton",
    "tools/production_paths",
    "doc",
    "plugins",
)


@dataclass(frozen=True)
class DirectoryHelpEntry:
    rel_path: str
    absolute_path: Path
    title: str
    body: str
    source_file: Path


def _repo_root(base: Path | None = None) -> Path:
    return Path(base).resolve() if base is not None else Path(__file__).resolve().parents[2]


def _read_readme(folder: Path) -> tuple[str, Path] | None:
    for name in README_CANDIDATES:
        path = folder / name
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8").strip()
            except OSError:
                return None
            if text:
                return text, path
    return None


def _seed_path(repo: Path, rel: str) -> Path:
    safe = rel.replace("\\", "/").replace("/", "__")
    return repo / "tools" / "directory_help" / "seeds" / f"{safe}.md"


def _body_from_seed_or_readme(repo: Path, rel: str, folder: Path) -> tuple[str, Path] | None:
    read = _read_readme(folder)
    if read is not None:
        return read
    seed = _seed_path(repo, rel)
    if seed.is_file():
        try:
            text = seed.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if text:
            return text, seed
    return None


def collect_directory_help(
    repo: Path | None = None,
    *,
    whitelist: Iterable[str] | None = None,
) -> list[DirectoryHelpEntry]:
    """Sammelt Hilfe-Einträge für existierende Whitelist-Ordner."""
    root = _repo_root(repo)
    paths = tuple(whitelist) if whitelist is not None else BOOK_STUDIO_DIRECTORY_HELP
    entries: list[DirectoryHelpEntry] = []
    for rel in paths:
        folder = root / Path(rel)
        if not folder.is_dir():
            # Seed trotzdem anzeigen, falls Ordner noch fehlt (z. B. inbox)
            seed = _seed_path(root, rel)
            if not seed.is_file():
                continue
            try:
                body = seed.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if not body:
                continue
            entries.append(
                DirectoryHelpEntry(
                    rel_path=rel.replace("\\", "/"),
                    absolute_path=folder,
                    title=rel.replace("\\", "/"),
                    body=body,
                    source_file=seed,
                )
            )
            continue
        loaded = _body_from_seed_or_readme(root, rel, folder)
        if loaded is None:
            continue
        body, source = loaded
        entries.append(
            DirectoryHelpEntry(
                rel_path=rel.replace("\\", "/"),
                absolute_path=folder,
                title=rel.replace("\\", "/"),
                body=body,
                source_file=source,
            )
        )
    return entries


def format_directory_help_markdown(
    repo: Path | None = None,
    *,
    whitelist: Iterable[str] | None = None,
    heading: str = "## Verzeichnisse",
) -> str:
    """Markdown-Abschnitt für Handbuch/Hilfe."""
    entries = collect_directory_help(repo, whitelist=whitelist)
    lines = [
        heading,
        "",
        "Texte stammen aus `README.md` (bzw. `_readme.md`) in den Ordnern selbst "
        "— oder aus den Seeds unter `tools/directory_help/seeds/`, wenn der Ordner "
        "noch leer ist.",
        "",
    ]
    if not entries:
        lines.append("*Keine Verzeichnis-READMEs gefunden.*")
        lines.append("")
        return "\n".join(lines)
    for entry in entries:
        lines.append(f"### `{entry.rel_path}/`")
        lines.append("")
        lines.append(entry.body)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_directory_help_html(
    repo: Path | None = None,
    *,
    whitelist: Iterable[str] | None = None,
) -> str:
    """HTML-Fragment (ohne Dokument-Wrapper) für Live-Injection in die Hilfe."""
    from tools.handbook_html import markdown_body_to_html

    md = format_directory_help_markdown(repo, whitelist=whitelist, heading="## Verzeichnisse")
    body_html, _sections = markdown_body_to_html(md)
    return (
        '<section id="directory-help" class="directory-help">\n'
        f"{body_html}\n"
        "</section>\n"
    )


def inject_directory_help_into_html(html: str, fragment: str) -> str:
    """Fügt das Fragment vor ``</body>`` ein (ersetzt vorhandenes ``#directory-help``)."""
    import re

    cleaned = re.sub(
        r'<section\s+id="directory-help"[^>]*>.*?</section>\s*',
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    marker = "</body>"
    lower = cleaned.lower()
    idx = lower.rfind(marker)
    if idx < 0:
        return cleaned + "\n" + fragment
    return cleaned[:idx] + fragment + cleaned[idx:]


def ensure_directory_readmes(
    repo: Path | None = None,
    *,
    whitelist: Iterable[str] | None = None,
) -> list[Path]:
    """Kopiert fehlende ``README.md`` aus Seeds in existierende Ordner."""
    root = _repo_root(repo)
    paths = tuple(whitelist) if whitelist is not None else BOOK_STUDIO_DIRECTORY_HELP
    written: list[Path] = []
    for rel in paths:
        folder = root / Path(rel)
        if not folder.is_dir():
            continue
        if any((folder / name).is_file() for name in README_CANDIDATES):
            continue
        seed = _seed_path(root, rel)
        if not seed.is_file():
            continue
        target = folder / "README.md"
        target.write_text(seed.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        written.append(target)
    return written
