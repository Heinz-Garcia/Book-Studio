"""Reverse-Index: welche Buchdateien referenzieren welche Bilder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from markdown_asset_scanner import (
    collect_all_local_image_refs,
    resolve_local_image_file,
)
from tools.asset_manager.constants import IMAGE_EXTENSIONS

_SKIP_DIR_NAMES = frozenset(
    {
        ".backups",
        ".git",
        ".venv",
        "__pycache__",
        "_extensions",
        "bookconfig",
        "export",
        "processed",
        "node_modules",
    }
)


@dataclass(frozen=True)
class RefHit:
    """Eine Bildreferenz in einer Quelldatei."""

    relative_path: str
    line: int
    raw_target: str


def list_book_images(book_root: Path) -> list[Path]:
    """Dateien unter ``{book}/img/`` (flach), sortiert."""
    img_dir = Path(book_root) / "img"
    if not img_dir.is_dir():
        return []
    allowed = {ext.lower() for ext in IMAGE_EXTENSIONS}
    files = [
        p
        for p in img_dir.iterdir()
        if p.is_file() and p.suffix.lower() in allowed
    ]
    return sorted(files, key=lambda p: p.name.lower())


def _iter_source_files(book_root: Path) -> list[Path]:
    root = Path(book_root).resolve()
    results: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in _SKIP_DIR_NAMES for part in rel_parts[:-1]):
            continue
        suffix = path.suffix.lower()
        if suffix in {".md", ".typ", ".qmd"}:
            results.append(path)
    return sorted(results)


def build_image_ref_index(book_root: Path) -> dict[Path, list[RefHit]]:
    """Map: aufgelöste Bilddatei → Treffer (Datei:Zeile)."""
    root = Path(book_root).resolve()
    index: dict[Path, list[RefHit]] = {}

    for source in _iter_source_files(root):
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            rel = source.relative_to(root).as_posix()
        except ValueError:
            rel = str(source)

        for raw_target, line in collect_all_local_image_refs(text):
            resolved = resolve_local_image_file(raw_target, source, root)
            if resolved is None:
                continue
            key = resolved.resolve()
            index.setdefault(key, []).append(
                RefHit(relative_path=rel, line=int(line), raw_target=str(raw_target))
            )

    for path, hits in index.items():
        index[path] = sorted(hits, key=lambda h: (h.relative_path.lower(), h.line))
    return index


def can_delete_book_image(image_path: Path, ref_index: dict[Path, list[RefHit]]) -> bool:
    """True, wenn die Datei im Buch-``img/`` keine Referenzen hat (Policy 1C)."""
    key = Path(image_path).resolve()
    return not ref_index.get(key)
