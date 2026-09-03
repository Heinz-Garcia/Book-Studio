"""Zugriff auf die Layout-Bibliothek unter ``tools/doclayout/library/``.

Ein Layout ist eine YAML-Datei; der Dateiname ohne Endung ist sein Name. Der
Editor listet ueber :func:`available_layouts`, laedt ueber :func:`load_layout`
und speichert ueber :meth:`LayoutDefinition.save`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from tools.doclayout.schema import LayoutDefinition, LayoutError

#: Mitgelieferte Bibliothek. Ein Buchprojekt darf eigene Layouts danebenlegen.
LIBRARY_DIR = Path(__file__).resolve().parent / "library"

#: Ablage im Buchprojekt -- dorthin schreibt ``apply`` die erzeugten Vorlagen.
BOOK_SUBDIR = Path("bookconfig") / "doclayout"

_SUFFIXES = (".yaml", ".yml")


def available_layouts(directory: Optional[Path | str] = None) -> list[Path]:
    """Alle Layout-Dateien, alphabetisch."""
    root = Path(directory) if directory else LIBRARY_DIR
    if not root.is_dir():
        return []
    found = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in _SUFFIXES]
    return sorted(found, key=lambda p: p.stem.lower())


def layout_path(name: str, directory: Optional[Path | str] = None) -> Path:
    """Pfad zu einem Layout. Existenz wird nicht geprueft."""
    root = Path(directory) if directory else LIBRARY_DIR
    return root / f"{name}.yaml"


def load_layout(name: str, directory: Optional[Path | str] = None) -> LayoutDefinition:
    """Laedt ein Layout ueber seinen Namen.

    Bei einem Tippfehler nennt die Meldung die vorhandenen Namen -- der
    haeufigste Fehlerfall an der CLI.
    """
    root = Path(directory) if directory else LIBRARY_DIR
    for suffix in _SUFFIXES:
        candidate = root / f"{name}{suffix}"
        if candidate.is_file():
            return LayoutDefinition.load(candidate)
    known = ", ".join(p.stem for p in available_layouts(root)) or "keine"
    raise LayoutError(f"Layout '{name}' nicht gefunden in {root} (vorhanden: {known})")


def book_output_dir(book_path: Path | str) -> Path:
    """Wohin die erzeugten Vorlagen in einem Buchprojekt gehoeren."""
    return Path(book_path) / BOOK_SUBDIR


__all__ = [
    "BOOK_SUBDIR",
    "LIBRARY_DIR",
    "available_layouts",
    "book_output_dir",
    "layout_path",
    "load_layout",
]
