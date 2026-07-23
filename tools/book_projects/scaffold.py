"""Leeres Quarto-Buch anlegen (minimal, ohne Skeleton)."""

from __future__ import annotations

import re
from pathlib import Path

_INVALID_FOLDER = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_book_folder_name(name: str) -> str:
    """Ordnername ohne Windows-verbotene Zeichen; Leerzeichen → Unterstrich."""
    raw = (name or "").strip()
    if not raw or "/" in raw or "\\" in raw or raw in {".", ".."}:
        raise ValueError("Ungültiger Buchname.")
    cleaned = _INVALID_FOLDER.sub("", raw)
    cleaned = cleaned.replace(" ", "_")
    cleaned = cleaned.strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("Ungültiger Buchname.")
    return cleaned


def is_quarto_book(path: Path) -> bool:
    return (Path(path) / "_quarto.yml").is_file()


def create_empty_book(
    parent: Path,
    folder_name: str,
    *,
    title: str | None = None,
    template_yml: Path | None = None,
) -> Path:
    """Erzeugt ein minimales Buch unter `parent/<folder_name>/`.

    Layout: `_quarto.yml`, `index.md`, `bookconfig/`, `content/`.
    Wirft ValueError bei ungültigem Namen oder wenn der Ordner schon existiert.
    """
    parent = Path(parent)
    if not parent.is_dir():
        raise ValueError(f"Zielordner existiert nicht: {parent}")

    safe = sanitize_book_folder_name(folder_name)
    book_dir = parent / safe
    if book_dir.exists():
        raise ValueError(f"Ordner existiert bereits: {book_dir}")

    book_title = (title or safe).strip() or safe
    yml_src = template_yml or (
        Path(__file__).resolve().parents[2] / "templates" / "quarto_reset_minimal.yml"
    )
    yml_text = yml_src.read_text(encoding="utf-8")
    yml_text = yml_text.replace("{{BOOK_TITLE}}", book_title)

    book_dir.mkdir(parents=False)
    (book_dir / "_quarto.yml").write_text(yml_text, encoding="utf-8", newline="\n")
    (book_dir / "index.md").write_text(
        f'---\ntitle: "{book_title}"\nunnumbered: true\n---\n\n'
        f"# {book_title}\n\n"
        "Platzhalter-Kapitel. Skeleton optional über *Skeleton ins Buch übernehmen…*.\n",
        encoding="utf-8",
        newline="\n",
    )
    (book_dir / "bookconfig").mkdir()
    (book_dir / "content").mkdir()
    return book_dir.resolve()
